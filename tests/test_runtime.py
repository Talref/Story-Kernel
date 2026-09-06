from __future__ import annotations

import json
from dataclasses import dataclass, field

from story_kernel.contracts import (
    ModelInfo,
    ProviderDiagnostics,
    ProviderMessage,
    ProviderResponse,
    ToolCall,
)
from story_kernel.exporting import ExperimentSerializer, redact
from story_kernel.provider import ProviderError
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
    assert [call["call_index"] for call in execution["provider_calls"]] == [1, 2]
    assert execution["provider_calls"][0]["normalized_tool_call_names"] == [
        "create_object"
    ]


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


def test_provider_failure_is_traced_but_not_persisted_as_assistant_message(kernel_db):
    _, sessions, capabilities = kernel_db
    state = StateStore(sessions)
    state.initialize()
    conversation = state.create_conversation("fake/medium", provider="fake")

    @dataclass
    class FailingProvider:
        name: str = "fake"

        def list_models(self):
            return []

        def complete(self, _request):
            raise ProviderError(
                "upstream unavailable",
                ProviderDiagnostics(
                    operation="POST /v1/chat/completions",
                    http_status=502,
                    raw_request={"authorization": "Bearer very-secret"},
                    raw_response={"error": "upstream unavailable"},
                ),
            )

    result = KernelRuntime(
        capabilities, state, FailingProvider(), sanitizer=redact
    ).run_turn(conversation["id"], "Try this")

    assert result["runtime_error"] == {
        "type": "ProviderError",
        "message": "upstream unavailable",
    }
    assert state.messages(conversation["id"]) == [
        {"role": "user", "content": "Try this"}
    ]
    execution = state.executions(conversation["id"])[0]
    call = execution["provider_calls"][0]
    assert call["http_status"] == 502
    assert call["error"]["type"] == "ProviderError"
    assert call["normalized_tool_call_count"] == 0
    assert call["raw_payloads_present"] is True
    assert "very-secret" not in str(state.provider_payloads(conversation["id"]))
    assert state.clear_provider_payloads() == 2
    assert state.provider_payloads(conversation["id"]) == []
    preserved = state.executions(conversation["id"])[0]
    assert preserved["provider_calls"][0]["http_status"] == 502
    assert preserved["provider_calls"][0]["raw_payloads_present"] is False
    assert state.messages(conversation["id"])[0]["content"] == "Try this"


def test_raw_provider_capture_can_be_disabled(kernel_db):
    _, sessions, capabilities = kernel_db
    state = StateStore(sessions)
    state.initialize()
    conversation = state.create_conversation("fake/medium", provider="fake")
    provider = FakeProvider(
        [
            ProviderResponse(
                model="fake/medium",
                message=ProviderMessage(role="assistant", content="Done."),
                diagnostics=ProviderDiagnostics(
                    http_status=200,
                    finish_reason="stop",
                    raw_request={"message": "raw"},
                    raw_response={"answer": "Done."},
                ),
            )
        ]
    )

    KernelRuntime(
        capabilities,
        state,
        provider,
        capture_raw_provider_payloads=False,
    ).run_turn(conversation["id"], "Go")

    execution = state.executions(conversation["id"])[0]
    assert execution["provider_calls"][0]["raw_payloads_present"] is False
    assert state.provider_payloads(conversation["id"]) == []
    assert state.messages(conversation["id"])[-1] == {
        "role": "assistant",
        "content": "Done.",
    }


def test_provider_diagnostics_export_keeps_raw_artifacts_separate_and_redacted(
    kernel_db,
):
    _, sessions, capabilities = kernel_db
    state = StateStore(sessions)
    state.initialize()
    conversation = state.create_conversation("fake/medium", provider="fake")
    secret = "provider-secret"
    provider = FakeProvider(
        [
            ProviderResponse(
                model="fake/upstream-model",
                raw_id="response:1",
                usage={"total_tokens": 7},
                message=ProviderMessage(role="assistant", content="Ready."),
                diagnostics=ProviderDiagnostics(
                    operation="POST /v1/chat/completions",
                    http_status=200,
                    response_id="response:1",
                    response_model="fake/upstream-model",
                    finish_reason="stop",
                    routing_metadata={"upstream": "fake-route"},
                    raw_request={"authorization": f"Bearer {secret}"},
                    raw_response={"cookie": secret, "content": "Ready."},
                ),
            )
        ]
    )
    sanitize = lambda value: redact(value, (secret,))
    KernelRuntime(capabilities, state, provider, sanitizer=sanitize).run_turn(
        conversation["id"], "Begin"
    )
    serializer = ExperimentSerializer(sessions, known_secrets=(secret,))

    exported = serializer.export_json()
    document = json.loads(exported)

    assert secret not in exported
    assert "provider_calls" not in document["execution_trace"][0]
    assert document["provider_diagnostics"]["calls"][0]["finish_reason"] == "stop"
    assert len(document["provider_diagnostics"]["raw_payloads"]) == 2
    serializer.import_json(exported)
    assert len(state.provider_payloads(conversation["id"])) == 2
    assert state.executions(conversation["id"])[0]["provider_calls"][0][
        "response_id"
    ] == "response:1"
