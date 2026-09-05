"""Typed application contract and controlled world mutation path."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .contracts import (
    AddRelationInput,
    CreateObjectInput,
    ExecutionContext,
    InspectObjectInput,
    ListRelationsInput,
    RelationStatus,
    RemoveRelationInput,
    SearchObjectsInput,
    SetAttributeInput,
    StrictModel,
    ToolExecution,
    new_id,
)
from .database import (
    EventRow,
    ObjectRow,
    RelationRow,
    SourceRow,
    TransactionRow,
    WorldRow,
)


class CapabilityError(RuntimeError):
    """Safe, model-visible capability failure."""


class NotFoundError(CapabilityError):
    pass


class ConflictError(CapabilityError):
    pass


InputT = TypeVar("InputT", bound=StrictModel)


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    description: str
    input_model: type[StrictModel]
    mutates: bool

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }


def _object_dict(row: ObjectRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "world_id": row.world_id,
        "scope": row.scope,
        "type": row.object_type,
        "schema_id": row.schema_id,
        "definition_id": row.definition_id,
        "definition_version": row.definition_version,
        "attributes": row.attributes,
        "revision": row.revision,
        "source_id": row.source_id,
    }


def _relation_dict(row: RelationRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "world_id": row.world_id,
        "scope": row.scope,
        "subject_id": row.subject_id,
        "predicate": row.predicate,
        "target_id": row.target_id,
        "metadata": row.metadata_json,
        "status": row.status,
        "revision": row.revision,
        "source_id": row.source_id,
    }


class CapabilityService:
    """The only world interface handed to the runtime model orchestration."""

    def __init__(self, session_factory: sessionmaker):
        self._sessions = session_factory
        self._specs = {
            spec.name: spec
            for spec in [
                CapabilitySpec(
                    "create_object",
                    "Create one generic object instance in the bound world and return its stable ID.",
                    CreateObjectInput,
                    True,
                ),
                CapabilitySpec(
                    "inspect_object",
                    "Read the authoritative current structured state of a known object ID.",
                    InspectObjectInput,
                    False,
                ),
                CapabilitySpec(
                    "search_objects",
                    "Find candidate object IDs by deterministic text matching; inspect a result before relying on it.",
                    SearchObjectsInput,
                    False,
                ),
                CapabilitySpec(
                    "set_attribute",
                    "Set one attribute on an existing object through a validated, revisioned command.",
                    SetAttributeInput,
                    True,
                ),
                CapabilitySpec(
                    "add_relation",
                    "Create a typed directed relation between two existing objects in the bound world.",
                    AddRelationInput,
                    True,
                ),
                CapabilitySpec(
                    "list_relations",
                    "List authoritative relations matching optional subject, predicate, and target filters.",
                    ListRelationsInput,
                    False,
                ),
                CapabilitySpec(
                    "remove_relation",
                    "Explicitly mark a relation removed while preserving its committed history.",
                    RemoveRelationInput,
                    True,
                ),
            ]
        }

    @property
    def specs(self) -> tuple[CapabilitySpec, ...]:
        return tuple(self._specs.values())

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [spec.openai_schema() for spec in self.specs]

    def ensure_world(self, world_id: str = "world:default") -> None:
        with self._sessions.begin() as session:
            if session.get(WorldRow, world_id) is None:
                session.add(WorldRow(id=world_id, revision=0))

    def world_revision(self, context: ExecutionContext) -> int:
        with self._sessions() as session:
            world = session.get(WorldRow, context.world_id)
            if world is None:
                raise NotFoundError("The bound world does not exist")
            return world.revision

    def execute(
        self, name: str, arguments: dict[str, Any], context: ExecutionContext
    ) -> ToolExecution:
        spec = self._specs.get(name)
        if spec is None:
            raise CapabilityError(f"Unknown capability: {name}")
        try:
            parsed = spec.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise CapabilityError(f"Invalid {name} arguments: {exc}") from exc
        if spec.mutates:
            updates: dict[str, Any] = {}
            if getattr(parsed, "command_id", None) is None:
                updates["command_id"] = new_id("command")
            if getattr(parsed, "expected_world_revision", None) is None:
                # Bind a precondition at command acceptance time even when the model
                # omits one. A concurrent change between this read and commit is rejected.
                updates["expected_world_revision"] = self.world_revision(context)
            if updates:
                parsed = parsed.model_copy(update=updates)

        handlers: dict[
            str, Callable[[StrictModel, ExecutionContext], ToolExecution]
        ] = {
            "create_object": self._create_object,
            "inspect_object": self._inspect_object,
            "search_objects": self._search_objects,
            "set_attribute": self._set_attribute,
            "add_relation": self._add_relation,
            "list_relations": self._list_relations,
            "remove_relation": self._remove_relation,
        }
        return handlers[name](parsed, context)

    def _visible_object(
        self, session: Session, object_id: str, context: ExecutionContext
    ) -> ObjectRow:
        row = session.scalar(
            select(ObjectRow).where(
                ObjectRow.id == object_id,
                ObjectRow.world_id == context.world_id,
                ObjectRow.scope == context.scope,
            )
        )
        if row is None:
            # Deliberately does not reveal whether the ID exists in another scope.
            raise NotFoundError(f"Object not found in the active world: {object_id}")
        return row

    def _source(
        self, session: Session, context: ExecutionContext, description: str | None
    ) -> str | None:
        if not description:
            return None
        source_id = new_id("source")
        session.add(
            SourceRow(
                id=source_id,
                world_id=context.world_id,
                description=description,
                metadata_json={"actor_id": context.actor_id},
            )
        )
        return source_id

    def _command(
        self,
        operation: str,
        args: Any,
        context: ExecutionContext,
        mutation: Callable[
            [Session, int, str | None], tuple[dict[str, Any], list[str], list[str]]
        ],
    ) -> ToolExecution:
        payload = args.model_dump(mode="json")
        command_id = payload["command_id"]
        with self._sessions.begin() as session:
            replay = session.scalar(
                select(TransactionRow).where(
                    TransactionRow.world_id == context.world_id,
                    TransactionRow.command_id == command_id,
                )
            )
            if replay is not None:
                if replay.operation != operation:
                    raise ConflictError(
                        "Command ID was already used for a different operation"
                    )
                replay_semantics = {
                    key: value
                    for key, value in replay.arguments.items()
                    if key != "expected_world_revision"
                }
                payload_semantics = {
                    key: value
                    for key, value in payload.items()
                    if key != "expected_world_revision"
                }
                if replay_semantics != payload_semantics:
                    raise ConflictError(
                        "Command ID was already used with different arguments"
                    )
                return ToolExecution(
                    result=replay.result,
                    reads=replay.reads,
                    writes=replay.writes,
                    revision_before=replay.revision_before,
                    revision_after=replay.revision_after,
                    transaction_id=replay.id,
                    event_ids=[event.id for event in replay.events],
                    replayed=True,
                )

            world = session.get(WorldRow, context.world_id)
            if world is None:
                raise NotFoundError("The bound world does not exist")
            before = world.revision
            expected = payload.get("expected_world_revision")
            if expected is not None and expected != before:
                raise ConflictError(
                    f"Stale world revision: expected {expected}, current {before}"
                )

            after = before + 1
            source_id = self._source(session, context, payload.get("source"))
            result, reads, writes = mutation(session, after, source_id)
            world.revision = after
            transaction_id = new_id("transaction")
            event_id = new_id("event")
            transaction = TransactionRow(
                id=transaction_id,
                world_id=context.world_id,
                scope=context.scope,
                command_id=command_id,
                operation=operation,
                revision_before=before,
                revision_after=after,
                arguments=payload,
                result=result,
                reads=reads,
                writes=writes,
                source_id=source_id,
            )
            transaction.events.append(
                EventRow(
                    id=event_id,
                    world_id=context.world_id,
                    scope=context.scope,
                    event_type=operation,
                    revision=after,
                    payload=result,
                    affected_ids=writes,
                )
            )
            session.add(transaction)
            return ToolExecution(
                result=result,
                reads=reads,
                writes=writes,
                revision_before=before,
                revision_after=after,
                transaction_id=transaction_id,
                event_ids=[event_id],
            )

    def _create_object(
        self, untyped: StrictModel, context: ExecutionContext
    ) -> ToolExecution:
        args = CreateObjectInput.model_validate(untyped)

        def mutate(session: Session, revision: int, source_id: str | None):
            object_id = args.object_id or new_id("object")
            if session.get(ObjectRow, object_id) is not None:
                raise ConflictError(f"Object ID already exists: {object_id}")
            row = ObjectRow(
                id=object_id,
                world_id=context.world_id,
                scope=context.scope,
                object_type=args.object_type,
                schema_id=args.schema_id,
                attributes=args.attributes,
                revision=revision,
                source_id=source_id,
            )
            session.add(row)
            result = _object_dict(row)
            return result, [], [object_id]

        return self._command("create_object", args, context, mutate)

    def _inspect_object(
        self, untyped: StrictModel, context: ExecutionContext
    ) -> ToolExecution:
        args = InspectObjectInput.model_validate(untyped)
        with self._sessions() as session:
            world = session.get(WorldRow, context.world_id)
            if world is None:
                raise NotFoundError("The bound world does not exist")
            row = self._visible_object(session, args.object_id, context)
            return ToolExecution(
                result={"object": _object_dict(row), "world_revision": world.revision},
                reads=[row.id],
                revision_before=world.revision,
                revision_after=world.revision,
            )

    def _search_objects(
        self, untyped: StrictModel, context: ExecutionContext
    ) -> ToolExecution:
        args = SearchObjectsInput.model_validate(untyped)
        query = args.query.casefold()
        with self._sessions() as session:
            world = session.get(WorldRow, context.world_id)
            if world is None:
                raise NotFoundError("The bound world does not exist")
            statement = select(ObjectRow).where(
                ObjectRow.world_id == context.world_id,
                ObjectRow.scope == context.scope,
            )
            if args.object_type:
                statement = statement.where(ObjectRow.object_type == args.object_type)
            rows = session.scalars(statement.order_by(ObjectRow.id)).all()
            matches: list[dict[str, Any]] = []
            for row in rows:
                haystack = f"{row.id} {row.object_type} {json.dumps(row.attributes, sort_keys=True)}".casefold()
                if query in haystack:
                    matches.append(
                        {
                            "id": row.id,
                            "type": row.object_type,
                            "revision": row.revision,
                            "attributes": row.attributes,
                        }
                    )
                if len(matches) >= args.limit:
                    break
            ids = [match["id"] for match in matches]
            return ToolExecution(
                result={"matches": matches, "world_revision": world.revision},
                reads=ids,
                revision_before=world.revision,
                revision_after=world.revision,
            )

    def _set_attribute(
        self, untyped: StrictModel, context: ExecutionContext
    ) -> ToolExecution:
        args = SetAttributeInput.model_validate(untyped)

        def mutate(session: Session, revision: int, _source_id: str | None):
            row = self._visible_object(session, args.object_id, context)
            if (
                args.expected_object_revision is not None
                and row.revision != args.expected_object_revision
            ):
                raise ConflictError(
                    f"Stale object revision: expected {args.expected_object_revision}, current {row.revision}"
                )
            attributes = dict(row.attributes)
            previous = attributes.get(args.attribute)
            attributes[args.attribute] = args.value
            row.attributes = attributes
            row.revision = revision
            result = {
                "object_id": row.id,
                "attribute": args.attribute,
                "previous": previous,
                "value": args.value,
                "revision": revision,
            }
            return result, [row.id], [row.id]

        return self._command("set_attribute", args, context, mutate)

    def _add_relation(
        self, untyped: StrictModel, context: ExecutionContext
    ) -> ToolExecution:
        args = AddRelationInput.model_validate(untyped)

        def mutate(session: Session, revision: int, source_id: str | None):
            subject = self._visible_object(session, args.subject_id, context)
            target = self._visible_object(session, args.target_id, context)
            relation_id = args.relation_id or new_id("relation")
            if session.get(RelationRow, relation_id) is not None:
                raise ConflictError(f"Relation ID already exists: {relation_id}")
            row = RelationRow(
                id=relation_id,
                world_id=context.world_id,
                scope=context.scope,
                subject_id=subject.id,
                predicate=args.predicate,
                target_id=target.id,
                metadata_json=args.metadata,
                status=RelationStatus.ACTIVE.value,
                revision=revision,
                source_id=source_id,
            )
            session.add(row)
            return _relation_dict(row), [subject.id, target.id], [relation_id]

        return self._command("add_relation", args, context, mutate)

    def _list_relations(
        self, untyped: StrictModel, context: ExecutionContext
    ) -> ToolExecution:
        args = ListRelationsInput.model_validate(untyped)
        with self._sessions() as session:
            world = session.get(WorldRow, context.world_id)
            if world is None:
                raise NotFoundError("The bound world does not exist")
            statement = select(RelationRow).where(
                RelationRow.world_id == context.world_id,
                RelationRow.scope == context.scope,
            )
            if not args.include_removed:
                statement = statement.where(
                    RelationRow.status == RelationStatus.ACTIVE.value
                )
            if args.subject_id:
                statement = statement.where(RelationRow.subject_id == args.subject_id)
            if args.predicate:
                statement = statement.where(RelationRow.predicate == args.predicate)
            if args.target_id:
                statement = statement.where(RelationRow.target_id == args.target_id)
            rows = session.scalars(statement.order_by(RelationRow.id)).all()
            return ToolExecution(
                result={
                    "relations": [_relation_dict(row) for row in rows],
                    "world_revision": world.revision,
                },
                reads=[row.id for row in rows],
                revision_before=world.revision,
                revision_after=world.revision,
            )

    def _remove_relation(
        self, untyped: StrictModel, context: ExecutionContext
    ) -> ToolExecution:
        args = RemoveRelationInput.model_validate(untyped)

        def mutate(session: Session, revision: int, _source_id: str | None):
            row = session.scalar(
                select(RelationRow).where(
                    RelationRow.id == args.relation_id,
                    RelationRow.world_id == context.world_id,
                    RelationRow.scope == context.scope,
                )
            )
            if row is None:
                raise NotFoundError(
                    f"Relation not found in the active world: {args.relation_id}"
                )
            if row.status == RelationStatus.REMOVED.value:
                raise ConflictError(f"Relation is already removed: {args.relation_id}")
            if (
                args.expected_relation_revision is not None
                and row.revision != args.expected_relation_revision
            ):
                raise ConflictError(
                    f"Stale relation revision: expected {args.expected_relation_revision}, current {row.revision}"
                )
            previous_revision = row.revision
            row.status = RelationStatus.REMOVED.value
            row.revision = revision
            metadata = dict(row.metadata_json)
            if args.reason:
                metadata["removal_reason"] = args.reason
            row.metadata_json = metadata
            result = {
                "relation_id": row.id,
                "status": row.status,
                "previous_revision": previous_revision,
                "revision": revision,
            }
            return result, [row.id], [row.id]

        return self._command("remove_relation", args, context, mutate)
