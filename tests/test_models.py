import json
import httpx
import pytest
from devpilot.models import OpenAIModel, ModelError


def body(message, finish="stop"):
    return {"choices": [{"message": message, "finish_reason": finish}], "usage": {"prompt_tokens": 17, "completion_tokens": 4}}


async def test_real_adapter_sends_and_parses_openai_tool_messages(config):
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=body({"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "files__read_file", "arguments": '{"path":"app.py"}'}}]}, "tool_calls"))
    model = OpenAIModel(config, httpx.MockTransport(handler))
    try:
        result = await model.complete([{"role": "user", "content": "inspect"}], [])
        assert result.calls[0].name == "files__read_file"
        assert json.loads(result.calls[0].arguments)["path"] == "app.py"
        assert seen[0]["tool_choice"] == "auto"
        assert result.usage["prompt_tokens"] == 17
    finally:
        await model.close()


async def test_model_does_not_surface_reasoning_fields(config):
    model = OpenAIModel(config, httpx.MockTransport(lambda r: httpx.Response(200, json=body({"content": "<think>private reasoning</think>Answer", "reasoning_content": "private"}))))
    try:
        assert (await model.complete([], [])).content == "Answer"
    finally:
        await model.close()


@pytest.mark.parametrize("response", [{}, {"choices": []}, body({"content": "partial"}, "length")])
async def test_malformed_or_truncated_model_response_fails(config, response):
    model = OpenAIModel(config, httpx.MockTransport(lambda r: httpx.Response(200, json=response)))
    try:
        with pytest.raises(ModelError):
            await model.complete([], [])
    finally:
        await model.close()


async def test_transient_inference_retry(config):
    calls = []
    def handler(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json=body({"content": "ok"}))
    model = OpenAIModel(config, httpx.MockTransport(handler))
    try:
        assert (await model.complete([], [])).content == "ok"
        assert len(calls) == 2
    finally:
        await model.close()


async def test_auth_failure_does_not_leak_response_body(config):
    model = OpenAIModel(config, httpx.MockTransport(lambda r: httpx.Response(401, text="private server details")))
    try:
        with pytest.raises(ModelError, match="401") as error:
            await model.complete([], [])
        assert "private server details" not in str(error.value)
    finally:
        await model.close()
