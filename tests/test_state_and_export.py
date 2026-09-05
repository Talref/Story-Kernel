from __future__ import annotations

import json

from story_kernel.exporting import ExperimentSerializer
from story_kernel.state import StateStore


def test_new_conversation_preserves_world_state(kernel_db, context):
    _, sessions, capabilities = kernel_db
    state = StateStore(sessions)
    state.initialize()
    created = capabilities.execute(
        "create_object",
        {"object_type": "fixture.Fact", "attributes": {"value": "persistent"}},
        context,
    )
    first = state.create_conversation("model-a")
    state.append_message(first["id"], "user", "remember this")

    second = state.create_conversation("model-a")
    assert second["id"] != first["id"]
    assert state.messages(second["id"]) == []
    inspected = capabilities.execute("inspect_object", {"object_id": created.result["id"]}, context)
    assert inspected.result["object"]["attributes"]["value"] == "persistent"


def test_world_reset_is_independent_of_conversation_and_prompt(kernel_db, context):
    _, sessions, capabilities = kernel_db
    state = StateStore(sessions)
    state.initialize()
    prompt_version, _ = state.save_prompt("A revised application prompt")
    conversation = state.create_conversation("model-a")
    state.append_message(conversation["id"], "user", "evidence")
    capabilities.execute("create_object", {"object_type": "fixture.Fact"}, context)

    state.reset_world()

    assert state.world_snapshot()["objects"] == []
    assert state.world_snapshot()["revision"] == 0
    assert state.messages(conversation["id"])[0]["content"] == "evidence"
    assert state.current_prompt() == (prompt_version, "A revised application prompt")


def test_export_import_round_trip_and_secret_redaction(kernel_db, context):
    _, sessions, capabilities = kernel_db
    state = StateStore(sessions)
    state.initialize()
    secret = "nano-secret-value"
    state.save_prompt(f"Do not leak {secret}")
    conversation = state.create_conversation("medium-model")
    state.append_message(conversation["id"], "user", f"accidental {secret}")
    capabilities.execute(
        "create_object",
        {
            "object_type": "fixture.Entity",
            "attributes": {"name": "Archive"},
            "source": f"header Authorization {secret}",
        },
        context,
    )
    serializer = ExperimentSerializer(sessions, known_secrets=(secret,))

    exported = serializer.export_json()
    assert secret not in exported
    assert "[REDACTED]" in exported
    expected = json.loads(exported)

    state.reset_world()
    serializer.import_json(exported)
    actual = json.loads(serializer.export_json())
    assert actual == expected


def test_sensitive_configuration_keys_are_redacted():
    from story_kernel.exporting import redact

    result = redact({"api_key": "value", "nested": {"authorization": "Bearer value"}})
    assert result == {"api_key": "[REDACTED]", "nested": {"authorization": "[REDACTED]"}}

