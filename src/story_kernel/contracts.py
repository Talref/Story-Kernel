"""Storage-independent contracts exposed by the application layer."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def new_id(prefix: str) -> str:
    return f"{prefix}:{uuid4().hex}"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RelationStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"


class ExecutionContext(StrictModel):
    world_id: str = "world:default"
    scope: str = "world"
    contract_version: str = "0.1a"
    observer_id: str | None = None
    actor_id: str | None = None


class CommandFields(StrictModel):
    command_id: str | None = Field(
        default=None,
        description="Optional idempotency key. Reusing it replays the original result.",
    )
    expected_world_revision: int | None = Field(
        default=None,
        ge=0,
        description="Optional optimistic-concurrency precondition.",
    )
    source: str | None = Field(
        default=None,
        description="Human-readable provenance for this mutation.",
    )


class CreateObjectInput(CommandFields):
    object_type: str = Field(min_length=1, description="World-defined type name.")
    attributes: dict[str, Any] = Field(default_factory=dict)
    object_id: str | None = Field(
        default=None, description="Optional stable object ID."
    )
    schema_id: str | None = None


class InspectObjectInput(StrictModel):
    object_id: str


class SearchObjectsInput(StrictModel):
    query: str = Field(min_length=1)
    object_type: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class SetAttributeInput(CommandFields):
    object_id: str
    attribute: str = Field(min_length=1)
    value: Any
    expected_object_revision: int | None = Field(default=None, ge=1)


class AddRelationInput(CommandFields):
    subject_id: str
    predicate: str = Field(min_length=1)
    target_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    relation_id: str | None = None


class ListRelationsInput(StrictModel):
    subject_id: str | None = None
    predicate: str | None = None
    target_id: str | None = None
    include_removed: bool = False


class RemoveRelationInput(CommandFields):
    relation_id: str
    expected_relation_revision: int | None = Field(default=None, ge=1)
    reason: str | None = None


class ToolExecution(StrictModel):
    result: dict[str, Any]
    reads: list[str] = Field(default_factory=list)
    writes: list[str] = Field(default_factory=list)
    revision_before: int
    revision_after: int
    transaction_id: str | None = None
    event_ids: list[str] = Field(default_factory=list)
    replayed: bool = False


class ToolCall(StrictModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ProviderMessage(StrictModel):
    role: str
    content: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ProviderRequest(StrictModel):
    model: str
    messages: list[ProviderMessage]
    tools: list[dict[str, Any]]


class ProviderDiagnostics(StrictModel):
    operation: str = "chat.completions"
    http_status: int | None = None
    response_id: str | None = None
    response_model: str | None = None
    finish_reason: str | None = None
    raw_tool_call_fields_present: bool = False
    normalized_tool_call_names: list[str] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
    parse_warnings: list[str] = Field(default_factory=list)
    routing_metadata: dict[str, Any] = Field(default_factory=dict)
    raw_request: Any = None
    raw_response: Any = None


class ProviderResponse(StrictModel):
    message: ProviderMessage
    model: str
    usage: dict[str, Any] = Field(default_factory=dict)
    raw_id: str | None = None
    diagnostics: ProviderDiagnostics = Field(default_factory=ProviderDiagnostics)


class ModelInfo(StrictModel):
    id: str
    name: str | None = None
    owned_by: str | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
