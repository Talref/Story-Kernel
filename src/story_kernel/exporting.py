"""Temporary, modular JSON import/export format for Experiment 0.1a."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from .database import (
    ConversationRow,
    DefinitionRow,
    EventRow,
    ExecutionRow,
    MessageRow,
    ObjectRow,
    PromptRow,
    RelationRow,
    SourceRow,
    TransactionRow,
    UiPreferenceRow,
    WorldRow,
)

SENSITIVE_KEYS = {"api_key", "apikey", "authorization", "token", "secret", "password"}


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return normalized in SENSITIVE_KEYS or normalized.endswith("_api_key")


class ExportBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: str = "story-kernel-experiment"
    version: str = "0.1a"
    world: dict[str, Any]
    application: dict[str, Any]
    model_configuration: dict[str, Any]
    conversations: dict[str, Any]
    execution_trace: list[dict[str, Any]] = Field(default_factory=list)


def redact(value: Any, known_secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_sensitive_key(key) else redact(item, known_secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, known_secrets) for item in value]
    if isinstance(value, str):
        result = value
        for secret in known_secrets:
            if secret:
                result = result.replace(secret, "[REDACTED]")
        return result
    return value


def _rows(session: Any, model: Any, fields: tuple[str, ...]) -> list[dict[str, Any]]:
    rows = session.scalars(select(model)).all()
    return [{field: deepcopy(getattr(row, field)) for field in fields} for row in rows]


def _indexed(items: Any, label: str, key: str = "id") -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        raise TypeError(f"{label} must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get(key), (str, int)):
            raise TypeError(f"{label} contains an invalid record")
        identity = str(item[key])
        if identity in indexed:
            raise ValueError(f"{label} contains duplicate {key}: {identity}")
        indexed[identity] = item
    return indexed


def _validate_references(bundle: ExportBundle) -> None:
    world = bundle.world
    application = bundle.application
    conversations = bundle.conversations
    worlds = _indexed(world.get("worlds"), "worlds")
    if not worlds:
        raise ValueError("Import must contain at least one world")
    definitions = _indexed(world.get("definitions", []), "definitions")
    sources = _indexed(world.get("sources", []), "sources")
    objects = _indexed(world.get("objects", []), "objects")
    relations = _indexed(world.get("relations", []), "relations")
    transactions = _indexed(world.get("transactions", []), "transactions")
    events = _indexed(world.get("events", []), "events")
    prompts = _indexed(application.get("prompt_versions"), "prompt_versions", "version")
    preferences = _indexed(
        application.get("ui_preferences", []), "ui_preferences", "key"
    )
    sessions = _indexed(conversations.get("sessions", []), "conversations")
    messages = _indexed(conversations.get("messages", []), "messages")
    executions = _indexed(bundle.execution_trace, "execution_trace")
    if not prompts:
        raise ValueError("Import must contain at least one application prompt")
    active_preference = preferences.get("active_conversation_id")

    for source in sources.values():
        if source.get("world_id") not in worlds:
            raise ValueError("Source refers to an unknown world")
    for item in objects.values():
        if item.get("world_id") not in worlds:
            raise ValueError("Object refers to an unknown world")
        if item.get("definition_id") and item["definition_id"] not in definitions:
            raise ValueError("Object refers to an unknown definition")
        if item.get("source_id") and item["source_id"] not in sources:
            raise ValueError("Object refers to an unknown source")
    for relation in relations.values():
        subject = objects.get(str(relation.get("subject_id")))
        target = objects.get(str(relation.get("target_id")))
        if subject is None or target is None:
            raise ValueError("Relation refers to an unknown object")
        expected_scope = (relation.get("world_id"), relation.get("scope"))
        if (subject.get("world_id"), subject.get("scope")) != expected_scope or (
            target.get("world_id"),
            target.get("scope"),
        ) != expected_scope:
            raise ValueError("Relation endpoints must share its world and scope")
        if relation.get("source_id") and relation["source_id"] not in sources:
            raise ValueError("Relation refers to an unknown source")
    for transaction in transactions.values():
        if transaction.get("world_id") not in worlds:
            raise ValueError("Transaction refers to an unknown world")
        if transaction.get("source_id") and transaction["source_id"] not in sources:
            raise ValueError("Transaction refers to an unknown source")
    for event in events.values():
        transaction = transactions.get(str(event.get("transaction_id")))
        if transaction is None:
            raise ValueError("Event refers to an unknown transaction")
        if (event.get("world_id"), event.get("scope")) != (
            transaction.get("world_id"),
            transaction.get("scope"),
        ):
            raise ValueError("Event must share its transaction's world and scope")
    for conversation in sessions.values():
        if conversation.get("world_id") not in worlds:
            raise ValueError("Conversation refers to an unknown world")
        if not conversation.get("provider") or not conversation.get("model"):
            raise ValueError("Conversation must pin a provider and model")
    if active_preference and active_preference.get("value") not in sessions:
        raise ValueError(
            "Active conversation preference refers to an unknown conversation"
        )
    for message in messages.values():
        if message.get("conversation_id") not in sessions:
            raise ValueError("Message refers to an unknown conversation")
    for execution in executions.values():
        conversation = sessions.get(str(execution.get("conversation_id")))
        if conversation is None:
            raise ValueError("Execution refers to an unknown conversation")
        if execution.get("world_id") != conversation.get("world_id"):
            raise ValueError("Execution must share its conversation's world")


class ExperimentSerializer:
    def __init__(
        self, session_factory: sessionmaker, known_secrets: tuple[str, ...] = ()
    ):
        self._sessions = session_factory
        self._known_secrets = tuple(secret for secret in known_secrets if secret)

    def export_bundle(self) -> ExportBundle:
        with self._sessions() as session:
            worlds = _rows(session, WorldRow, ("id", "revision"))
            definitions = _rows(
                session,
                DefinitionRow,
                ("id", "object_type", "schema_id", "version", "data", "provenance"),
            )
            sources = _rows(
                session,
                SourceRow,
                ("id", "world_id", "kind", "description", "metadata_json"),
            )
            objects = _rows(
                session,
                ObjectRow,
                (
                    "id",
                    "world_id",
                    "scope",
                    "object_type",
                    "schema_id",
                    "definition_id",
                    "definition_version",
                    "attributes",
                    "revision",
                    "source_id",
                ),
            )
            relations = _rows(
                session,
                RelationRow,
                (
                    "id",
                    "world_id",
                    "scope",
                    "subject_id",
                    "predicate",
                    "target_id",
                    "metadata_json",
                    "status",
                    "revision",
                    "source_id",
                ),
            )
            transactions = _rows(
                session,
                TransactionRow,
                (
                    "id",
                    "world_id",
                    "scope",
                    "command_id",
                    "operation",
                    "status",
                    "revision_before",
                    "revision_after",
                    "arguments",
                    "result",
                    "reads",
                    "writes",
                    "source_id",
                ),
            )
            events = _rows(
                session,
                EventRow,
                (
                    "id",
                    "transaction_id",
                    "world_id",
                    "scope",
                    "event_type",
                    "revision",
                    "payload",
                    "affected_ids",
                ),
            )
            prompts = _rows(session, PromptRow, ("version", "content"))
            preferences = _rows(session, UiPreferenceRow, ("key", "value"))
            conversations = _rows(
                session,
                ConversationRow,
                ("id", "world_id", "scope", "provider", "model"),
            )
            messages = _rows(
                session,
                MessageRow,
                ("id", "conversation_id", "role", "content", "sequence"),
            )
            execution_fields = tuple(
                column.name
                for column in ExecutionRow.__table__.columns
                if column.name != "created_at"
            )
            executions = _rows(session, ExecutionRow, execution_fields)

        bundle = ExportBundle(
            world={
                "worlds": worlds,
                "definitions": definitions,
                "sources": sources,
                "objects": objects,
                "relations": relations,
                "transactions": transactions,
                "events": events,
            },
            application={
                "prompt_versions": prompts,
                "ui_preferences": preferences,
                "contract_version": "0.1a",
            },
            model_configuration={
                "providers": sorted({row["provider"] for row in conversations}),
                "selected_models": sorted({row["model"] for row in conversations}),
            },
            conversations={"sessions": conversations, "messages": messages},
            execution_trace=executions,
        )
        return ExportBundle.model_validate(
            redact(bundle.model_dump(mode="json"), self._known_secrets)
        )

    def export_json(self) -> str:
        return self.export_bundle().model_dump_json(indent=2)

    def import_json(self, document: str) -> ExportBundle:
        bundle = ExportBundle.model_validate_json(document)
        if bundle.format != "story-kernel-experiment" or bundle.version != "0.1a":
            raise ValueError("Unsupported experiment bundle format or version")
        safe = ExportBundle.model_validate(
            redact(bundle.model_dump(mode="json"), self._known_secrets)
        )
        _validate_references(safe)
        world = safe.world
        application = safe.application
        conversations = safe.conversations

        with self._sessions.begin() as session:
            for model in (
                EventRow,
                ExecutionRow,
                MessageRow,
                TransactionRow,
                RelationRow,
                ObjectRow,
                SourceRow,
                ConversationRow,
                UiPreferenceRow,
                PromptRow,
                DefinitionRow,
                WorldRow,
            ):
                session.execute(delete(model))

            for item in world.get("worlds", []):
                session.add(WorldRow(**item))
            session.flush()
            for item in world.get("definitions", []):
                session.add(DefinitionRow(**item))
            session.flush()
            for item in world.get("sources", []):
                session.add(SourceRow(**item))
            session.flush()
            for item in world.get("objects", []):
                session.add(ObjectRow(**item))
            session.flush()
            for item in world.get("relations", []):
                session.add(RelationRow(**item))
            session.flush()
            for item in world.get("transactions", []):
                session.add(TransactionRow(**item))
            session.flush()
            for item in world.get("events", []):
                session.add(EventRow(**item))
            session.flush()
            for item in application.get("prompt_versions", []):
                session.add(PromptRow(**item))
            session.flush()
            for item in application.get("ui_preferences", []):
                session.add(UiPreferenceRow(**item))
            session.flush()
            for item in conversations.get("sessions", []):
                session.add(ConversationRow(**item))
            session.flush()
            for item in conversations.get("messages", []):
                session.add(MessageRow(**item))
            for item in safe.execution_trace:
                session.add(ExecutionRow(**item))
        return safe
