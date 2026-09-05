"""Temporary, modular JSON import/export format for Experiment 0.1a."""

from __future__ import annotations

import json
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
    WorldRow,
)


SENSITIVE_KEYS = {"api_key", "apikey", "authorization", "token", "secret", "password"}


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
            key: "[REDACTED]" if key.casefold() in SENSITIVE_KEYS else redact(item, known_secrets)
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


class ExperimentSerializer:
    def __init__(self, session_factory: sessionmaker, known_secrets: tuple[str, ...] = ()):
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
            sources = _rows(session, SourceRow, ("id", "world_id", "kind", "description", "metadata_json"))
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
                ("id", "transaction_id", "world_id", "scope", "event_type", "revision", "payload", "affected_ids"),
            )
            prompts = _rows(session, PromptRow, ("version", "content"))
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
                column.name for column in ExecutionRow.__table__.columns if column.name != "created_at"
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
            application={"prompt_versions": prompts, "contract_version": "0.1a"},
            model_configuration={
                "providers": sorted({row["provider"] for row in conversations}),
                "selected_models": sorted({row["model"] for row in conversations}),
            },
            conversations={"sessions": conversations, "messages": messages},
            execution_trace=executions,
        )
        return ExportBundle.model_validate(redact(bundle.model_dump(mode="json"), self._known_secrets))

    def export_json(self) -> str:
        return self.export_bundle().model_dump_json(indent=2)

    def import_json(self, document: str) -> ExportBundle:
        bundle = ExportBundle.model_validate_json(document)
        if bundle.format != "story-kernel-experiment" or bundle.version != "0.1a":
            raise ValueError("Unsupported experiment bundle format or version")
        safe = ExportBundle.model_validate(redact(bundle.model_dump(mode="json"), self._known_secrets))
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
            for item in conversations.get("sessions", []):
                session.add(ConversationRow(**item))
            session.flush()
            for item in conversations.get("messages", []):
                session.add(MessageRow(**item))
            for item in safe.execution_trace:
                session.add(ExecutionRow(**item))
        return safe
