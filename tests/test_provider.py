from __future__ import annotations

import json

import httpx

from story_kernel.contracts import ProviderMessage, ProviderRequest
from story_kernel.provider import NanoGPTAdapter, ProviderError


def test_nanogpt_lists_subscription_models_without_exposing_key():
    seen = {}

    def handler(request: httpx.Request):
        seen["path"] = request.url.path
        seen["authorization"] = request.headers["Authorization"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "provider/medium",
                        "name": "Medium",
                        "owned_by": "provider",
                        "capabilities": {"tool_calling": True},
                    }
                ]
            },
        )

    client = httpx.Client(base_url="https://example.invalid/api", transport=httpx.MockTransport(handler))
    adapter = NanoGPTAdapter("top-secret", client=client)
    models = adapter.list_models()

    assert seen == {"path": "/api/subscription/v1/models", "authorization": "Bearer top-secret"}
    assert models[0].id == "provider/medium"
    assert "top-secret" not in repr(adapter)


def test_nanogpt_parses_openai_tool_calls():
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        assert body["model"] == "provider/medium"
        assert body["tools"][0]["function"]["name"] == "inspect_object"
        return httpx.Response(
            200,
            json={
                "id": "completion:1",
                "model": "provider/medium",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call:1",
                                    "function": {
                                        "name": "inspect_object",
                                        "arguments": '{"object_id":"object:1"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"total_tokens": 12},
            },
        )

    adapter = NanoGPTAdapter(
        "top-secret",
        client=httpx.Client(base_url="https://example.invalid/api", transport=httpx.MockTransport(handler)),
    )
    response = adapter.complete(
        ProviderRequest(
            model="provider/medium",
            messages=[ProviderMessage(role="user", content="look")],
            tools=[{"type": "function", "function": {"name": "inspect_object"}}],
        )
    )
    assert response.message.tool_calls[0].arguments == {"object_id": "object:1"}
    assert response.usage == {"total_tokens": 12}


def test_nanogpt_errors_are_credential_safe():
    transport = httpx.MockTransport(lambda _request: httpx.Response(401, text="top-secret"))
    adapter = NanoGPTAdapter(
        "top-secret",
        client=httpx.Client(base_url="https://example.invalid/api", transport=transport),
    )
    try:
        adapter.list_models()
    except ProviderError as exc:
        assert str(exc) == "NanoGPT request failed with HTTP 401"
        assert "top-secret" not in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ProviderError")
