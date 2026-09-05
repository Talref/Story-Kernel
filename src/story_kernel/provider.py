"""Provider boundary and NanoGPT implementation."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

import httpx
from dotenv import load_dotenv

from .contracts import (
    ModelInfo,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
    ToolCall,
)


class ProviderError(RuntimeError):
    """A credential-safe provider failure suitable for traces and UI output."""


class ModelProvider(Protocol):
    name: str

    def list_models(self) -> list[ModelInfo]: ...

    def complete(self, request: ProviderRequest) -> ProviderResponse: ...


class NanoGPTAdapter:
    """Small OpenAI-compatible NanoGPT adapter with no persistence knowledge."""

    name = "nanogpt"

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

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._client.request(
                method, path, headers=self._headers(), **kwargs
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"NanoGPT request failed with HTTP {exc.response.status_code}"
            ) from None
        except (httpx.HTTPError, ValueError):
            raise ProviderError("NanoGPT request failed") from None
        if not isinstance(payload, dict):
            raise ProviderError("NanoGPT returned an invalid response")
        return payload

    def list_models(self) -> list[ModelInfo]:
        payload = self._request(
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
        payload = self._request(
            "POST",
            "/v1/chat/completions",
            json={
                "model": request.model,
                "messages": [
                    self._message_payload(message) for message in request.messages
                ],
                "tools": request.tools,
                "tool_choice": "auto",
                "stream": False,
            },
        )
        try:
            raw_message = payload["choices"][0]["message"]
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
            message = ProviderMessage(
                role="assistant",
                content=raw_message.get("content"),
                tool_calls=tool_calls,
            )
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            raise ProviderError("NanoGPT returned an invalid chat completion") from None
        return ProviderResponse(
            message=message,
            model=str(payload.get("model") or request.model),
            usage=payload.get("usage") or {},
            raw_id=payload.get("id"),
        )
