"""Exercise the real Inspect/OpenAI/httpx request boundary without network access."""

import asyncio
import json

import httpx

from pipeline.model import Completion, ModelRuntime, Reasoning, resolve
from pipeline.protocols.trigger_search import call_record
from pipeline.protocols.unit_testing import _call, tests_schema as suite_schema


def test_azure_provider_sends_numeric_socket_timeouts(monkeypatch):
    monkeypatch.setenv("AZUREAI_API_KEY", "offline-test-key")
    monkeypatch.setenv("AZUREAI_BASE_URL", "https://azure-timeout-test.invalid/openai/v1")
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={
            "id": "offline-timeout-check", "object": "chat.completion", "created": 0,
            "model": "gpt-5.6-terra",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": "{}"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18,
                      "prompt_tokens_details": {"cached_tokens": 3},
                      "completion_tokens_details": {"reasoning_tokens": 4}},
        })

    transport = httpx.MockTransport(respond)

    async def intercepted(_transport, request):
        return await transport.handle_async_request(request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", intercepted)
    runtime = ModelRuntime(
        name="openai-api/azureai/gpt-5.6-terra", seed=300,
        attempt_timeout=120, http_timeout=240, http_retries=1,
        max_tokens=8192, reasoning_effort=Reasoning.LOW, inspect_cache=False,
    )
    client = resolve(runtime)

    async def request_and_close():
        try:
            return await client.completion("Return a suite", "property_gen", suite_schema(1))
        finally:
            await client._resolve_inspect().api.aclose()

    answer = asyncio.run(request_and_close())
    assert answer.text == "{}"
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://azure-timeout-test.invalid/openai/v1/chat/completions"
    timeouts = request.extensions["timeout"]
    assert set(timeouts) == {"connect", "read", "write", "pool"}
    assert all(isinstance(value, (int, float)) for value in timeouts.values()), timeouts
    assert all(0 < value <= runtime.attempt_timeout for value in timeouts.values())
    body = json.loads(request.content)
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["reasoning_effort"] == "low"
    assert answer.usage["input_tokens"] == 8
    assert answer.usage["input_tokens_cache_read"] == 3
    assert answer.usage["output_tokens"] == 7
    assert answer.usage["reasoning_tokens"] == 4
    assert answer.usage["total_tokens"] == 18
    assert answer.response_model == "gpt-5.6-terra"
    # Inspect's adapter does not forward the response ID in ModelOutput.
    assert answer.response_id is None
    for record in (_call("Return a suite", answer),
                   call_record(0, 300, "Return inputs", answer, None)):
        assert record["usage"] == answer.usage
        assert record["response_model"] == answer.response_model
        assert record["response_id"] is None
    for record in (_call("mock", Completion("{}", "stop")),
                   call_record(0, 300, "mock", Completion("[]", "stop"), None)):
        assert record["usage"] is None
        assert record["response_model"] is None
