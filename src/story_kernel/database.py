"""SQLAlchemy setup and physical persistence models for Experiment 0.1a."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class WorldRow(Base):
    __tablename__ = "worlds"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class DefinitionRow(Base):
    __tablename__ = "object_definitions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    object_type: Mapped[str] = mapped_column(String, nullable=False)
    schema_id: Mapped[str | None] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SourceRow(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False, default="runtime_command")
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ObjectRow(Base):
    __tablename__ = "objects"
    __table_args__ = (UniqueConstraint("world_id", "scope", "id", name="uq_object_scope_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String, nullable=False, default="world")
    object_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    schema_id: Mapped[str | None] = mapped_column(String)
    definition_id: Mapped[str | None] = mapped_column(ForeignKey("object_definitions.id"))
    definition_version: Mapped[int | None] = mapped_column(Integer)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class RelationRow(Base):
    __tablename__ = "relations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String, nullable=False, default="world")
    subject_id: Mapped[str] = mapped_column(ForeignKey("objects.id"), index=True)
    predicate: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("objects.id"), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class TransactionRow(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("world_id", "command_id", name="uq_world_command"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    command_id: Mapped[str] = mapped_column(String, nullable=False)
    operation: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="committed")
    revision_before: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_after: Mapped[int] = mapped_column(Integer, nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reads: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    writes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    events: Mapped[list[EventRow]] = relationship(back_populates="transaction", cascade="all, delete-orphan")


class EventRow(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    affected_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    transaction: Mapped[TransactionRow] = relationship(back_populates="events")


class PromptRow(Base):
    __tablename__ = "prompt_versions"

    version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConversationRow(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ExecutionRow(Base):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    world_id: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    contract_version: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_content: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    model_input: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    tool_schemas: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    tool_activity: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    reads: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    writes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    revision_before: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_after: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    event_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    assistant_response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    token_usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


def create_database(path: str | Path) -> tuple[Engine, sessionmaker]:
    database_path = str(path)
    if database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    url = "sqlite+pysqlite:///:memory:" if database_path == ":memory:" else f"sqlite+pysqlite:///{database_path}"
    kwargs: dict[str, Any] = {"future": True}
    if database_path == ":memory:":
        from sqlalchemy.pool import StaticPool

        kwargs.update(connect_args={"check_same_thread": False}, poolclass=StaticPool)
    else:
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)

