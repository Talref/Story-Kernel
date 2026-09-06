"""Provider boundary and NanoGPT implementation."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

import httpx
from dotenv import load_dotenv

from .contracts import (
    ModelInfo,
    ProviderDiagnostics,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
    ToolCall,
)


class ProviderError(RuntimeError):
    """A credential-safe provider failure suitable for traces and UI output."""

    def __init__(
        self, message: str, diagnostics: ProviderDiagnostics | None = None
    ) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics or ProviderDiagnostics()


class ModelProvider(Protocol):
    name: str

    def list_models(self) -> list[ModelInfo]: ...

    def complete(self, request: ProviderRequest) -> ProviderResponse: ...


class NanoGPTAdapter:
    """Small OpenAI-compatible NanoGPT adapter with no persistence knowledge."""

    name = "nanogpt"
    _ROUTING_KEYS = (
        "provider",
        "routing",
        "upstream",
        "provider_info",
        "service_tier",
        "system_fingerprint",
    )

    def __init__(
        self,
        api_key: str | None,
        *,
        base_url: str = "https://nano-gpt.com/api",
        client: httpx.Client | None = None,
        timeout: float = 90.0,
    ):
        self._api_key = api_key
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout)

    def __repr__(self) -> str:
        return "NanoGPTAdapter(api_key=[REDACTED])"

    @classmethod
    def from_env(cls, env_file: str = ".env", **kwargs: Any) -> NanoGPTAdapter:
        load_dotenv(env_file)
        return cls(os.getenv("NANOGPT_API_KEY"), **kwargs)

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise ProviderError("NANOGPT_API_KEY is not configured")
        return {"Authorization": f"Bearer {self._api_key}"}

    @staticmethod
    def _response_payload(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text

    @classmethod
    def _diagnostics(
        cls,
        operation: str,
        *,
        http_status: int | None = None,
        raw_request: Any = None,
        raw_response: Any = None,
        parse_warnings: list[str] | None = None,
    ) -> ProviderDiagnostics:
        response = raw_response if isinstance(raw_response, dict) else {}
        usage = response.get("usage")
        return ProviderDiagnostics(
            operation=operation,
            http_status=http_status,
            response_id=(
                str(response["id"]) if response.get("id") is not None else None
            ),
            response_model=(
                str(response["model"]) if response.get("model") is not None else None
            ),
            usage=usage if isinstance(usage, dict) else {},
            parse_warnings=parse_warnings or [],
            routing_metadata={
                key: response[key] for key in cls._ROUTING_KEYS if key in response
            },
            raw_request=raw_request,
            raw_response=raw_response,
        )

    def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> tuple[dict[str, Any], int]:
        operation = f"{method} {path}"
        raw_request = kwargs.get("json")
        try:
            headers = self._headers()
            response = self._client.request(method, path, headers=headers, **kwargs)
        except ProviderError as exc:
            exc.diagnostics.operation = operation
            exc.diagnostics.raw_request = raw_request
            raise
        except httpx.HTTPStatusError as exc:
            # Kept for clients/transports that raise before the explicit check below.
            diagnostics = self._diagnostics(
                operation,
                http_status=exc.response.status_code,
                raw_request=raw_request,
                raw_response=self._response_payload(exc.response),
            )
            raise ProviderError(
                f"NanoGPT request failed with HTTP {exc.response.status_code}",
                diagnostics,
            ) from None
        except httpx.HTTPError:
            raise ProviderError(
                "NanoGPT request failed",
                ProviderDiagnostics(operation=operation, raw_request=raw_request),
            ) from None
        if response.is_error:
            diagnostics = self._diagnostics(
                operation,
                http_status=response.status_code,
                raw_request=raw_request,
                raw_response=self._response_payload(response),
            )
            raise ProviderError(
                f"NanoGPT request failed with HTTP {response.status_code}", diagnostics
            )
        try:
            payload = response.json()
        except ValueError:
            raise ProviderError(
                "NanoGPT returned an invalid response",
                self._diagnostics(
                    operation,
                    http_status=response.status_code,
                    raw_request=raw_request,
                    raw_response=response.text,
                    parse_warnings=["Response body was not valid JSON"],
                ),
            ) from None
        if not isinstance(payload, dict):
            raise ProviderError(
                "NanoGPT returned an invalid response",
                self._diagnostics(
                    operation,
                    http_status=response.status_code,
                    raw_request=raw_request,
                    raw_response=payload,
                    parse_warnings=["Response JSON was not an object"],
                ),
            )
        return payload, response.status_code

    def list_models(self) -> list[ModelInfo]:
        payload, _status = self._request(
            "GET", "/subscription/v1/models", params={"detailed": "true"}
        )
        data = payload.get("data")
        if not isinstance(data, list):
            raise ProviderError("NanoGPT model response did not contain a model list")
        models: list[ModelInfo] = []
        for item in data:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            models.append(
                ModelInfo(
                    id=item["id"],
                    name=item.get("name"),
                    owned_by=item.get("owned_by"),
                    capabilities=item.get("capabilities") or {},
                )
            )
        return sorted(models, key=lambda model: (model.name or model.id).casefold())

    @staticmethod
    def _message_payload(message: ProviderMessage) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments),
                    },
                }
                for call in message.tool_calls
            ]
        return payload

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        request_payload = {
            "model": request.model,
            "messages": [
                self._message_payload(message) for message in request.messages
            ],
            "tools": request.tools,
            "tool_choice": "auto",
            "stream": False,
        }
        payload, status = self._request(
            "POST", "/v1/chat/completions", json=request_payload
        )
        diagnostics = self._diagnostics(
            "POST /v1/chat/completions",
            http_status=status,
            raw_request=request_payload,
            raw_response=payload,
        )
        try:
            choice = payload["choices"][0]
            raw_message = choice["message"]
            if not isinstance(raw_message, dict):
                raise TypeError
            diagnostics.finish_reason = (
                str(choice["finish_reason"])
                if choice.get("finish_reason") is not None
                else None
            )
            action_fields = {
                "tool_calls",
                "tool_call",
                "function_call",
                "action",
                "actions",
            }.intersection(raw_message)
            diagnostics.raw_tool_call_fields_present = bool(action_fields)
            unnormalized_fields = sorted(action_fields - {"tool_calls"})
            if unnormalized_fields:
                diagnostics.parse_warnings.append(
                    "Unnormalized provider action fields present: "
                    + ", ".join(unnormalized_fields)
                )
            tool_calls = []
            for raw_call in raw_message.get("tool_calls") or []:
                arguments = raw_call["function"].get("arguments") or "{}"
                parsed_arguments = (
                    json.loads(arguments) if isinstance(arguments, str) else arguments
                )
                if not isinstance(parsed_arguments, dict):
                    raise TypeError
                tool_calls.append(
                    ToolCall(
                        id=raw_call["id"],
                        name=raw_call["function"]["name"],
                        arguments=parsed_arguments,
                    )
                )
            diagnostics.normalized_tool_call_names = [call.name for call in tool_calls]
            message = ProviderMessage(
                role="assistant",
                content=raw_message.get("content"),
                tool_calls=tool_calls,
            )
        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            diagnostics.parse_warnings.append(
                f"Adapter failed to normalize chat completion: {type(exc).__name__}"
            )
            raise ProviderError(
                "NanoGPT returned an invalid chat completion", diagnostics
            ) from None
        return ProviderResponse(
            message=message,
            model=str(payload.get("model") or request.model),
            usage=payload.get("usage") or {},
            raw_id=payload.get("id"),
            diagnostics=diagnostics,
        )
