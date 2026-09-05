from __future__ import annotations

import pytest

from story_kernel.capabilities import ConflictError, NotFoundError


def create(capabilities, context, name: str):
    return capabilities.execute(
        "create_object",
        {"object_type": "fixture.Entity", "attributes": {"name": name}},
        context,
    )


def test_object_create_inspect_search_and_update(kernel_db, context):
    _, _, capabilities = kernel_db
    created = create(capabilities, context, "North Archive")
    object_id = created.result["id"]
    assert created.revision_before == 0
    assert created.revision_after == 1

    inspected = capabilities.execute(
        "inspect_object", {"object_id": object_id}, context
    )
    assert inspected.result["object"]["attributes"] == {"name": "North Archive"}
    assert inspected.reads == [object_id]

    matches = capabilities.execute("search_objects", {"query": "archive"}, context)
    assert [match["id"] for match in matches.result["matches"]] == [object_id]

    changed = capabilities.execute(
        "set_attribute",
        {
            "object_id": object_id,
            "attribute": "open",
            "value": True,
            "expected_world_revision": 1,
            "expected_object_revision": 1,
        },
        context,
    )
    assert changed.revision_after == 2
    inspected = capabilities.execute(
        "inspect_object", {"object_id": object_id}, context
    )
    assert inspected.result["object"]["attributes"]["open"] is True
    assert inspected.result["object"]["revision"] == 2


def test_relation_lifecycle_preserves_removed_record(kernel_db, context):
    _, _, capabilities = kernel_db
    alice = create(capabilities, context, "Alice").result["id"]
    archive = create(capabilities, context, "Archive").result["id"]
    added = capabilities.execute(
        "add_relation",
        {"subject_id": alice, "predicate": "visits", "target_id": archive},
        context,
    )
    relation_id = added.result["id"]

    active = capabilities.execute("list_relations", {"subject_id": alice}, context)
    assert [relation["id"] for relation in active.result["relations"]] == [relation_id]

    removed = capabilities.execute(
        "remove_relation",
        {
            "relation_id": relation_id,
            "expected_relation_revision": added.result["revision"],
        },
        context,
    )
    assert removed.result["status"] == "removed"
    assert capabilities.execute("list_relations", {}, context).result["relations"] == []
    historical = capabilities.execute(
        "list_relations", {"include_removed": True}, context
    )
    assert historical.result["relations"][0]["status"] == "removed"


def test_mutation_is_idempotent_and_rejects_stale_revision(kernel_db, context):
    _, _, capabilities = kernel_db
    arguments = {
        "object_type": "fixture.Entity",
        "attributes": {"name": "Once"},
        "command_id": "command:once",
    }
    first = capabilities.execute("create_object", arguments, context)
    replay = capabilities.execute("create_object", arguments, context)
    assert replay.replayed is True
    assert replay.result == first.result
    assert capabilities.world_revision(context) == 1

    with pytest.raises(ConflictError, match="different arguments"):
        capabilities.execute(
            "create_object",
            {**arguments, "attributes": {"name": "Changed"}},
            context,
        )

    with pytest.raises(ConflictError, match="Stale world revision"):
        capabilities.execute(
            "create_object",
            {"object_type": "fixture.Entity", "expected_world_revision": 0},
            context,
        )


def test_scope_is_bound_by_runtime_context(kernel_db, context):
    _, _, capabilities = kernel_db
    object_id = create(capabilities, context, "Scoped").result["id"]
    other_scope = context.model_copy(update={"scope": "private"})
    with pytest.raises(NotFoundError):
        capabilities.execute("inspect_object", {"object_id": object_id}, other_scope)


def test_relation_requires_endpoints_in_bound_scope(kernel_db, context):
    _, _, capabilities = kernel_db
    alice = create(capabilities, context, "Alice").result["id"]
    with pytest.raises(NotFoundError):
        capabilities.execute(
            "add_relation",
            {"subject_id": alice, "predicate": "knows", "target_id": "object:missing"},
            context,
        )
