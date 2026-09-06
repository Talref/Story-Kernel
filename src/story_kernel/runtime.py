"""Live model/tool orchestration for the C -> B -> A experiment loop."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any, Protocol

from .capabilities import CapabilityError, CapabilityService
from .contracts import (
    ExecutionContext,
    ProviderDiagnostics,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
)
from .provider import ModelProvider, ProviderError


class RuntimeState(Protocol):
    """Narrow ledger/config surface: deliberately contains no world mutation method."""

    def get_conversation(self, conversation_id: str) -> dict[str, Any]: ...

    def messages(self, conversation_id: str) -> list[dict[str, Any]]: ...

    def current_prompt(self) -> tuple[int, str]: ...

    def append_message(
        self, conversation_id: str, role: str, content: str
    ) -> dict[str, Any]: ...

    def record_execution(self, record: dict[str, Any]) -> str: ...


class KernelRuntime:
    def __init__(
        self,
        capabilities: CapabilityService,
        state: RuntimeState,
        provider: ModelProvider,
        *,
        max_tool_rounds: int = 8,
        sanitizer: Callable[[Any], Any] | None = None,
        capture_raw_provider_payloads: bool = True,
    ):
        self._capabilities = capabilities
        self._state = state
        self._provider = provider
        self._max_tool_rounds = max_tool_rounds
        self._sanitize = sanitizer or (lambda value: value)
        self._capture_raw_provider_payloads = capture_raw_provider_payloads

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def run_turn(self, conversation_id: str, user_message: str) -> dict[str, Any]:
        if not user_message.strip():
            raise ValueError("User message cannot be empty")
        safe_user_message = self._sanitize(user_message)
        conversation = self._state.get_conversation(conversation_id)
        if conversation["provider"] != self._provider.name:
            raise ValueError("Conversation is pinned to a different provider")
        context = ExecutionContext(
            world_id=conversation["world_id"], scope=conversation["scope"]
        )
        revision_before = self._capabilities.world_revision(context)
        prompt_version, prompt = self._state.current_prompt()
        prompt = self._sanitize(prompt)
        history = self._state.messages(conversation_id)
        messages = [ProviderMessage(role="system", content=prompt)]
        messages.extend(
            ProviderMessage.model_validate(self._sanitize(message))
            for message in history
        )
        messages.append(ProviderMessage(role="user", content=safe_user_message))
        initial_input = [message.model_dump(mode="json") for message in messages]
        schemas = self._capabilities.tool_schemas()
        activity: list[dict[str, Any]] = []
        reads: list[str] = []
        writes: list[str] = []
        transaction_ids: list[str] = []
        event_ids: list[str] = []
        errors: list[dict[str, Any]] = []
        provider_calls: list[dict[str, Any]] = []
        usage: dict[str, Any] = {}
        retries = 0
        assistant_response = ""
        started = time.perf_counter()
        completed = False

        try:
            for round_number in range(self._max_tool_rounds + 1):
                call_started = time.perf_counter()
                try:
                    response = self._provider.complete(
                        ProviderRequest(
                            model=conversation["model"],
                            messages=messages,
                            tools=schemas,
                        )
                    )
                except ProviderError as exc:
                    provider_calls.append(
                        self._provider_call_record(
                            conversation["model"],
                            round_number + 1,
                            exc.diagnostics,
                            round((time.perf_counter() - call_started) * 1000),
                            error={
                                "type": type(exc).__name__,
                                "message": self._sanitize(str(exc)),
                            },
                        )
                    )
                    raise
                provider_calls.append(
                    self._provider_call_record(
                        conversation["model"],
                        round_number + 1,
                        response.diagnostics,
                        round((time.perf_counter() - call_started) * 1000),
                        response=response,
                    )
                )
                usage = self._merge_usage(usage, response.usage)
                assistant = ProviderMessage.model_validate(
                    self._sanitize(response.message.model_dump(mode="json"))
                )
                messages.append(assistant)
                if not assistant.tool_calls:
                    assistant_response = assistant.content or ""
                    completed = True
                    break
                if round_number == self._max_tool_rounds:
                    raise RuntimeError("Model exceeded the tool-call round limit")

                for call in assistant.tool_calls:
                    safe_arguments = self._sanitize(call.arguments)
                    trace: dict[str, Any] = {
                        "round": round_number + 1,
                        "call_id": call.id,
                        "name": call.name,
                        "arguments": safe_arguments,
                    }
                    try:
                        outcome = self._capabilities.execute(
                            call.name, safe_arguments, context
                        )
                        safe_result = self._sanitize(outcome.result)
                        trace.update(
                            {
                                "result": safe_result,
                                "reads": outcome.reads,
                                "writes": outcome.writes,
                                "revision_before": outcome.revision_before,
                                "revision_after": outcome.revision_after,
                                "transaction_id": outcome.transaction_id,
                                "event_ids": outcome.event_ids,
                                "replayed": outcome.replayed,
                            }
                        )
                        reads.extend(outcome.reads)
                        writes.extend(outcome.writes)
                        if outcome.transaction_id:
                            transaction_ids.append(outcome.transaction_id)
                        event_ids.extend(outcome.event_ids)
                        tool_result = {"ok": True, **safe_result}
                    except CapabilityError as exc:
                        retries += 1
                        safe_error = {
                            "type": type(exc).__name__,
                            "message": self._sanitize(str(exc)),
                        }
                        errors.append(safe_error)
                        trace["error"] = safe_error
                        tool_result = {"ok": False, "error": safe_error}
                    activity.append(trace)
                    messages.append(
                        ProviderMessage(
                            role="tool",
                            content=json.dumps(tool_result, ensure_ascii=False),
                            tool_call_id=call.id,
                        )
                    )
            else:  # pragma: no cover - loop always exits via break or exception
                raise RuntimeError("Model did not produce a final response")
        except (ProviderError, RuntimeError) as exc:
            safe_message = self._sanitize(str(exc))
            errors.append({"type": type(exc).__name__, "message": safe_message})

        latency_ms = round((time.perf_counter() - started) * 1000)
        revision_after = self._capabilities.world_revision(context)
        self._state.append_message(conversation_id, "user", safe_user_message)
        if completed:
            self._state.append_message(conversation_id, "assistant", assistant_response)
        execution_id = self._state.record_execution(
            {
                "conversation_id": conversation_id,
                "world_id": context.world_id,
                "scope": context.scope,
                "contract_version": context.contract_version,
                "prompt_version": prompt_version,
                "prompt_content": prompt,
                "provider": conversation["provider"],
                "model": conversation["model"],
                "user_message": safe_user_message,
                "model_input": initial_input,
                "tool_schemas": schemas,
                "tool_activity": activity,
                "reads": list(dict.fromkeys(reads)),
                "writes": list(dict.fromkeys(writes)),
                "revision_before": revision_before,
                "revision_after": revision_after,
                "transaction_ids": transaction_ids,
                "event_ids": event_ids,
                "assistant_response": assistant_response,
                "errors": errors,
                "retries": retries,
                "latency_ms": latency_ms,
                "token_usage": usage,
                "provider_calls": provider_calls,
            }
        )
        return {
            "execution_id": execution_id,
            "conversation_id": conversation_id,
            "assistant_response": assistant_response,
            "revision_before": revision_before,
            "revision_after": revision_after,
            "errors": errors,
            "runtime_error": errors[-1] if not completed and errors else None,
        }

    def _provider_call_record(
        self,
        selected_model: str,
        call_index: int,
        diagnostics: ProviderDiagnostics,
        latency_ms: int,
        *,
        response: ProviderResponse | None = None,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_names = list(diagnostics.normalized_tool_call_names)
        if response is not None and not normalized_names:
            normalized_names = [call.name for call in response.message.tool_calls]
        raw_payloads: dict[str, Any] = {}
        if self._capture_raw_provider_payloads:
            if diagnostics.raw_request is not None:
                raw_payloads["request"] = self._sanitize(diagnostics.raw_request)
            if diagnostics.raw_response is not None:
                raw_payloads["response"] = self._sanitize(diagnostics.raw_response)
        return {
            "provider": self._provider.name,
            "selected_model": selected_model,
            "call_index": call_index,
            "operation": diagnostics.operation,
            "http_status": diagnostics.http_status,
            "response_id": diagnostics.response_id
            or (response.raw_id if response else None),
            "response_model": diagnostics.response_model
            or (response.model if response else None),
            "finish_reason": diagnostics.finish_reason,
            "raw_tool_call_fields_present": (diagnostics.raw_tool_call_fields_present),
            "normalized_tool_call_names": normalized_names,
            "normalized_tool_call_count": len(normalized_names),
            "latency_ms": latency_ms,
            "usage": self._sanitize(response.usage if response else {}),
            "parse_warnings": self._sanitize(diagnostics.parse_warnings),
            "error": error,
            "routing_metadata": self._sanitize(diagnostics.routing_metadata),
            "raw_payloads": raw_payloads,
        }

    @staticmethod
    def _merge_usage(total: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        merged = dict(total)
        for key, value in update.items():
            if isinstance(value, (int, float)) and isinstance(
                merged.get(key, 0), (int, float)
            ):
                merged[key] = merged.get(key, 0) + value
            else:
                merged[key] = value
        return merged
