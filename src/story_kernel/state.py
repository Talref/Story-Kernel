"""Application state that is deliberately separate from the model-facing world API."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

from .contracts import ExecutionContext, new_id
from .database import (
    ConversationRow,
    EventRow,
    ExecutionRow,
    MessageRow,
    ObjectRow,
    PromptRow,
    ProviderCallRow,
    ProviderPayloadArtifactRow,
    RelationRow,
    SourceRow,
    TransactionRow,
    UiPreferenceRow,
    WorldRow,
)

DEFAULT_PROMPT = """You operate a persistent generic world through the provided tools.
Use tools to inspect relevant state before asserting stored facts. Persist facts the user asks
you to remember with generic objects, attributes, and relations. Never claim a mutation
succeeded unless its tool result confirms a commit. Conversation history is not world truth."""

ACTIVE_CONVERSATION_KEY = "active_conversation_id"
SELECTED_MODEL_KEY = "selected_model"


class StateStore:
    def __init__(self, session_factory: sessionmaker):
        self._sessions = session_factory

    def initialize(self, world_id: str = "world:default") -> None:
        with self._sessions.begin() as session:
            if session.get(WorldRow, world_id) is None:
                session.add(WorldRow(id=world_id, revision=0))
            if session.scalar(select(func.count()).select_from(PromptRow)) == 0:
                session.add(PromptRow(content=DEFAULT_PROMPT))

    def current_prompt(self) -> tuple[int, str]:
        with self._sessions() as session:
            prompt = session.scalar(
                select(PromptRow).order_by(PromptRow.version.desc()).limit(1)
            )
            if prompt is None:
                raise RuntimeError("Application prompt has not been initialized")
            return prompt.version, prompt.content

    def save_prompt(self, content: str) -> tuple[int, str]:
        normalized = content.strip()
        if not normalized:
            raise ValueError("Application prompt cannot be empty")
        with self._sessions.begin() as session:
            current = session.scalar(
                select(PromptRow).order_by(PromptRow.version.desc()).limit(1)
            )
            if current is not None and current.content == normalized:
                return current.version, current.content
            row = PromptRow(content=normalized)
            session.add(row)
            session.flush()
            return row.version, row.content

    @staticmethod
    def _set_preference(session: Any, key: str, value: Any) -> None:
        row = session.get(UiPreferenceRow, key)
        if row is None:
            session.add(UiPreferenceRow(key=key, value=value))
        else:
            row.value = value

    def set_selected_model(self, model: str | None) -> None:
        with self._sessions.begin() as session:
            self._set_preference(session, SELECTED_MODEL_KEY, model)

    def selected_model(self) -> str | None:
        with self._sessions() as session:
            row = session.get(UiPreferenceRow, SELECTED_MODEL_KEY)
            return row.value if row and isinstance(row.value, str) else None

    def set_active_conversation(self, conversation_id: str | None) -> None:
        with self._sessions.begin() as session:
            if conversation_id is not None:
                conversation = session.get(ConversationRow, conversation_id)
                if conversation is None:
                    raise KeyError(f"Conversation not found: {conversation_id}")
            self._set_preference(session, ACTIVE_CONVERSATION_KEY, conversation_id)

    def active_conversation_id(self) -> str | None:
        with self._sessions() as session:
            row = session.get(UiPreferenceRow, ACTIVE_CONVERSATION_KEY)
            if row is None or not isinstance(row.value, str):
                return None
            if session.get(ConversationRow, row.value) is None:
                return None
            return row.value

    def create_conversation(
        self,
        model: str,
        provider: str = "nanogpt",
        context: ExecutionContext | None = None,
    ) -> dict[str, Any]:
        if not model.strip():
            raise ValueError("Select a model before starting a conversation")
        bound = context or ExecutionContext()
        conversation_id = new_id("conversation")
        with self._sessions.begin() as session:
            row = ConversationRow(
                id=conversation_id,
                world_id=bound.world_id,
                scope=bound.scope,
                provider=provider,
                model=model,
            )
            session.add(row)
            self._set_preference(session, ACTIVE_CONVERSATION_KEY, conversation_id)
            self._set_preference(session, SELECTED_MODEL_KEY, model)
        return self.get_conversation(conversation_id)

    def list_conversations(self) -> list[dict[str, Any]]:
        with self._sessions() as session:
            rows = session.scalars(
                select(ConversationRow).order_by(
                    ConversationRow.created_at.desc(), ConversationRow.id.desc()
                )
            ).all()
            return [
                {
                    "id": row.id,
                    "world_id": row.world_id,
                    "scope": row.scope,
                    "provider": row.provider,
                    "model": row.model,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        with self._sessions() as session:
            row = session.get(ConversationRow, conversation_id)
            if row is None:
                raise KeyError(f"Conversation not found: {conversation_id}")
            return {
                "id": row.id,
                "world_id": row.world_id,
                "scope": row.scope,
                "provider": row.provider,
                "model": row.model,
            }

    def append_message(
        self, conversation_id: str, role: str, content: str
    ) -> dict[str, Any]:
        with self._sessions.begin() as session:
            maximum = session.scalar(
                select(func.max(MessageRow.sequence)).where(
                    MessageRow.conversation_id == conversation_id
                )
            )
            row = MessageRow(
                id=new_id("message"),
                conversation_id=conversation_id,
                role=role,
                content=content,
                sequence=(maximum or 0) + 1,
            )
            session.add(row)
            return {
                "id": row.id,
                "role": role,
                "content": content,
                "sequence": row.sequence,
            }

    def messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with self._sessions() as session:
            rows = session.scalars(
                select(MessageRow)
                .where(MessageRow.conversation_id == conversation_id)
                .order_by(MessageRow.sequence)
            ).all()
            return [{"role": row.role, "content": row.content} for row in rows]

    def record_execution(self, record: dict[str, Any]) -> str:
        data = dict(record)
        execution_id = data.pop("id", None) or new_id("execution")
        provider_calls = data.pop("provider_calls", [])
        with self._sessions.begin() as session:
            session.add(ExecutionRow(id=execution_id, **data))
            session.flush()
            for call in provider_calls:
                call_data = dict(call)
                raw_payloads = call_data.pop("raw_payloads", {})
                provider_call_id = call_data.pop("id", None) or new_id("provider-call")
                session.add(
                    ProviderCallRow(
                        id=provider_call_id,
                        execution_id=execution_id,
                        **call_data,
                    )
                )
                session.flush()
                for kind, payload in raw_payloads.items():
                    session.add(
                        ProviderPayloadArtifactRow(
                            id=new_id("provider-payload"),
                            provider_call_id=provider_call_id,
                            execution_id=execution_id,
                            kind=kind,
                            payload=payload,
                        )
                    )
        return execution_id

    def reset_world(self, world_id: str = "world:default") -> None:
        """Reset A only. Prompt, conversations, messages, and execution evidence survive."""
        with self._sessions.begin() as session:
            session.execute(delete(EventRow).where(EventRow.world_id == world_id))
            session.execute(
                delete(TransactionRow).where(TransactionRow.world_id == world_id)
            )
            session.execute(delete(RelationRow).where(RelationRow.world_id == world_id))
            session.execute(delete(ObjectRow).where(ObjectRow.world_id == world_id))
            session.execute(delete(SourceRow).where(SourceRow.world_id == world_id))
            world = session.get(WorldRow, world_id)
            if world is None:
                session.add(WorldRow(id=world_id, revision=0))
            else:
                world.revision = 0

    def world_snapshot(self, context: ExecutionContext | None = None) -> dict[str, Any]:
        bound = context or ExecutionContext()
        with self._sessions() as session:
            world = session.get(WorldRow, bound.world_id)
            if world is None:
                raise KeyError(f"World not found: {bound.world_id}")
            objects = session.scalars(
                select(ObjectRow)
                .where(
                    ObjectRow.world_id == bound.world_id, ObjectRow.scope == bound.scope
                )
                .order_by(ObjectRow.id)
            ).all()
            relations = session.scalars(
                select(RelationRow)
                .where(
                    RelationRow.world_id == bound.world_id,
                    RelationRow.scope == bound.scope,
                )
                .order_by(RelationRow.id)
            ).all()
            events = session.scalars(
                select(EventRow)
                .where(
                    EventRow.world_id == bound.world_id, EventRow.scope == bound.scope
                )
                .order_by(EventRow.revision, EventRow.id)
            ).all()
            return {
                "world_id": world.id,
                "scope": bound.scope,
                "revision": world.revision,
                "objects": [
                    {
                        "id": row.id,
                        "type": row.object_type,
                        "schema_id": row.schema_id,
                        "definition_id": row.definition_id,
                        "definition_version": row.definition_version,
                        "attributes": row.attributes,
                        "revision": row.revision,
                        "source_id": row.source_id,
                    }
                    for row in objects
                ],
                "relations": [
                    {
                        "id": row.id,
                        "subject_id": row.subject_id,
                        "predicate": row.predicate,
                        "target_id": row.target_id,
                        "metadata": row.metadata_json,
                        "status": row.status,
                        "revision": row.revision,
                        "source_id": row.source_id,
                    }
                    for row in relations
                ],
                "events": [
                    {
                        "id": row.id,
                        "transaction_id": row.transaction_id,
                        "type": row.event_type,
                        "revision": row.revision,
                        "payload": row.payload,
                        "affected_ids": row.affected_ids,
                    }
                    for row in events
                ],
            }

    def human_world(self, context: ExecutionContext | None = None) -> str:
        snapshot = self.world_snapshot(context)
        lines = [f"World `{snapshot['world_id']}` · revision {snapshot['revision']}"]
        lines.append(f"\nObjects ({len(snapshot['objects'])})")
        for item in snapshot["objects"]:
            attributes = json.dumps(
                item["attributes"], ensure_ascii=False, sort_keys=True
            )
            lines.append(
                f"- `{item['id']}` [{item['type']}] r{item['revision']}: {attributes}"
            )
        lines.append(f"\nRelations ({len(snapshot['relations'])})")
        for relation in snapshot["relations"]:
            lines.append(
                f"- `{relation['subject_id']}` —{relation['predicate']}→ `{relation['target_id']}` "
                f"({relation['status']}, r{relation['revision']})"
            )
        if not snapshot["objects"]:
            lines.append("- Empty world")
        return "\n".join(lines)

    def executions(self, conversation_id: str | None = None) -> list[dict[str, Any]]:
        with self._sessions() as session:
            statement = select(ExecutionRow)
            if conversation_id:
                statement = statement.where(
                    ExecutionRow.conversation_id == conversation_id
                )
            rows = session.scalars(
                statement.order_by(ExecutionRow.created_at, ExecutionRow.id)
            ).all()
            execution_ids = [row.id for row in rows]
            provider_calls = (
                session.scalars(
                    select(ProviderCallRow)
                    .where(ProviderCallRow.execution_id.in_(execution_ids))
                    .order_by(ProviderCallRow.execution_id, ProviderCallRow.call_index)
                ).all()
                if execution_ids
                else []
            )
            artifact_call_ids = set(
                session.scalars(
                    select(ProviderPayloadArtifactRow.provider_call_id).where(
                        ProviderPayloadArtifactRow.execution_id.in_(execution_ids)
                    )
                ).all()
                if execution_ids
                else []
            )
            calls_by_execution: dict[str, list[dict[str, Any]]] = {}
            for call in provider_calls:
                summary = {
                    column.name: getattr(call, column.name)
                    for column in ProviderCallRow.__table__.columns
                    if column.name not in {"created_at", "execution_id"}
                }
                summary["raw_payloads_present"] = call.id in artifact_call_ids
                calls_by_execution.setdefault(call.execution_id, []).append(summary)

            results = []
            for row in rows:
                result = {
                    column.name: getattr(row, column.name)
                    for column in ExecutionRow.__table__.columns
                    if column.name != "created_at"
                }
                result["provider_calls"] = calls_by_execution.get(row.id, [])
                results.append(result)
            return results

    def provider_payloads(
        self, conversation_id: str | None = None
    ) -> list[dict[str, Any]]:
        with self._sessions() as session:
            statement = select(ProviderPayloadArtifactRow)
            if conversation_id:
                execution_ids = select(ExecutionRow.id).where(
                    ExecutionRow.conversation_id == conversation_id
                )
                statement = statement.where(
                    ProviderPayloadArtifactRow.execution_id.in_(execution_ids)
                )
            rows = session.scalars(
                statement.order_by(
                    ProviderPayloadArtifactRow.created_at,
                    ProviderPayloadArtifactRow.id,
                )
            ).all()
            return [
                {
                    "id": row.id,
                    "execution_id": row.execution_id,
                    "provider_call_id": row.provider_call_id,
                    "kind": row.kind,
                    "payload": row.payload,
                }
                for row in rows
            ]

    def clear_provider_payloads(self) -> int:
        with self._sessions.begin() as session:
            result = session.execute(delete(ProviderPayloadArtifactRow))
            return result.rowcount or 0
