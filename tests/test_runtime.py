from __future__ import annotations

from dataclasses import dataclass, field

from story_kernel.contracts import (
    ModelInfo,
    ProviderMessage,
    ProviderResponse,
    ToolCall,
)
from story_kernel.exporting import redact
from story_kernel.runtime import KernelRuntime, RuntimeState
from story_kernel.state import StateStore


@dataclass
class FakeProvider:
    responses: list[ProviderResponse]
    name: str = "fake"
    requests: list = field(default_factory=list)

    def list_models(self):
        return [ModelInfo(id="fake/medium")]

    def complete(self, request):
        self.requests.append(request)
        return self.responses.pop(0)


def test_runtime_mutates_world_only_through_typed_tool(kernel_db):
    _, sessions, capabilities = kernel_db
    state = StateStore(sessions)
    state.initialize()
    conversation = state.create_conversation("fake/medium", provider="fake")
    provider = FakeProvider(
        responses=[
            ProviderResponse(
                model="fake/medium",
                message=ProviderMessage(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id="call:1",
                            name="create_object",
                            arguments={
                                "object_type": "fixture.Fact",
                                "attributes": {"statement": "The bell is bronze"},
                            },
                        )
                    ],
                ),
                usage={"prompt_tokens": 10},
            ),
            ProviderResponse(
                model="fake/medium",
                message=ProviderMessage(
                    role="assistant", content="I stored that fact."
                ),
                usage={"completion_tokens": 5},
            ),
        ]
    )
    runtime = KernelRuntime(capabilities, state, provider)

    result = runtime.run_turn(conversation["id"], "Remember that the bell is bronze")

    assert result["revision_before"] == 0
    assert result["revision_after"] == 1
    assert result["assistant_response"] == "I stored that fact."
    snapshot = state.world_snapshot()
    assert snapshot["objects"][0]["attributes"]["statement"] == "The bell is bronze"
    assert provider.requests[1].messages[-1].role == "tool"
    assert '"ok": true' in provider.requests[1].messages[-1].content
    execution = state.executions(conversation["id"])[0]
    assert execution["model"] == "fake/medium"
    assert execution["writes"] == [snapshot["objects"][0]["id"]]
    assert execution["transaction_ids"]
    assert execution["event_ids"]
    assert execution["token_usage"] == {"prompt_tokens": 10, "completion_tokens": 5}


def test_runtime_returns_tool_validation_error_for_model_retry(kernel_db):
    _, sessions, capabilities = kernel_db
    state = StateStore(sessions)
    state.initialize()
    conversation = state.create_conversation("fake/medium", provider="fake")
    provider = FakeProvider(
        responses=[
            ProviderResponse(
                model="fake/medium",
                message=ProviderMessage(
                    role="assistant",
                    tool_calls=[
                        ToolCall(id="bad", name="inspect_object", arguments={})
                    ],
                ),
            ),
            ProviderResponse(
                model="fake/medium",
                message=ProviderMessage(
                    role="assistant", content="I could not find an object ID."
                ),
            ),
        ]
    )
    result = KernelRuntime(capabilities, state, provider).run_turn(
        conversation["id"], "Inspect it"
    )

    assert result["errors"][0]["type"] == "CapabilityError"
    execution = state.executions(conversation["id"])[0]
    assert execution["retries"] == 1
    assert execution["revision_before"] == execution["revision_after"] == 0


def test_runtime_has_no_direct_storage_or_world_admin_surface(kernel_db):
    _, sessions, capabilities = kernel_db
    state = StateStore(sessions)
    state.initialize()
    runtime = KernelRuntime(capabilities, state, FakeProvider([]))

    assert not hasattr(runtime, "session")
    assert not hasattr(runtime, "engine")
    assert "reset_world" not in RuntimeState.__dict__
    assert "world_snapshot" not in RuntimeState.__dict__


def test_runtime_redacts_configured_secret_before_model_trace_and_world(kernel_db):
    _, sessions, capabilities = kernel_db
    state = StateStore(sessions)
    state.initialize()
    conversation = state.create_conversation("fake/medium", provider="fake")
    secret = "configured-nanogpt-key"
    provider = FakeProvider(
        responses=[
            ProviderResponse(
                model="fake/medium",
                message=ProviderMessage(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id="call:secret",
                            name="create_object",
                            arguments={
                                "object_type": "fixture.Fact",
                                "attributes": {"value": secret},
                            },
                        )
                    ],
                ),
            ),
            ProviderResponse(
                model="fake/medium",
                message=ProviderMessage(role="assistant", content=f"Stored {secret}"),
            ),
        ]
    )
    runtime = KernelRuntime(
        capabilities,
        state,
        provider,
        sanitizer=lambda value: redact(value, (secret,)),
    )

    runtime.run_turn(conversation["id"], f"Remember {secret}")

    assert secret not in str(state.messages(conversation["id"]))
    assert secret not in str(state.executions(conversation["id"]))
    assert secret not in str(state.world_snapshot())
    assert secret not in str(provider.requests)
