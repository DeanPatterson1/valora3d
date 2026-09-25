import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from engine.director.llm import LLMError
from engine.director.providers.anthropic_provider import DEFAULT_MODEL, AnthropicProvider


class _Stream:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.msg


def _msg(text, stop="end_turn"):
    blocks = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(content=blocks, stop_reason=stop, model="claude-opus-5-5", _request_id="req_1",
                           usage=SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=7,
                                                 cache_creation_input_tokens=0),
                           to_dict=lambda: {"content": [{"type": "thinking", "thinking": ""},
                                                        {"type": "text", "text": text}]})


class _Client:
    def __init__(self, msg=None, exc=None):
        self.kw, self.msg, self.exc = None, msg, exc
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))
        self.messages = SimpleNamespace(stream=self._stream)

    def _stream(self, **kw):
        self.kw = kw
        if self.exc:
            raise self.exc
        return _Stream(self.msg)


def test_request_shape_caching_schema_thinking_and_fallbacks(monkeypatch):
    monkeypatch.delenv("VALORA_DIRECTOR_MODEL", raising=False)
    c = _Client(_msg('{"shots": []}'))
    p = AnthropicProvider(client=c)
    r = p.generate(system="RULEBOOK", messages=[{"role": "user", "content": "u"}], schema={"type": "object"},
                   max_tokens=32000)
    kw = c.kw
    assert kw["model"] == DEFAULT_MODEL == "claude-opus-5-5"
    assert kw["system"] == [{"type": "text", "text": "RULEBOOK", "cache_control": {"type": "ephemeral"}}]
    assert kw["thinking"] == {"type": "adaptive"}
    assert kw["output_config"]["format"] == {"type": "json_schema", "schema": {"type": "object"}}
    assert kw["output_config"]["effort"] == "high"  # Opus 5.5 defaults to medium: set it explicitly
    assert "temperature" not in kw and "budget_tokens" not in json.dumps(kw) and "extra_body" not in kw
    assert kw["betas"] == ["server-side-fallback-2026-07-01"] and kw["fallbacks"] == "default"
    assert r.text == '{"shots": []}' and r.usage["cache_read_input_tokens"] == 7
    assert r.assistant_content[-1] == {"type": "text", "text": '{"shots": []}'} and r.request_id == "req_1"


def test_without_fallbacks_uses_the_plain_endpoint():
    c = _Client(_msg("{}"))
    c.beta = None  # would raise if touched
    AnthropicProvider(client=c, fallbacks=False).generate(system="S", messages=[], schema={}, max_tokens=10)
    assert "betas" not in c.kw and "fallbacks" not in c.kw


def test_model_override_by_env(monkeypatch):
    monkeypatch.setenv("VALORA_DIRECTOR_MODEL", "claude-fable-5-1")
    assert AnthropicProvider(client=_Client(_msg("{}"))).model == "claude-fable-5-1"


def test_refusal_is_returned_not_parsed():
    r = AnthropicProvider(client=_Client(_msg("", stop="refusal"))).generate(
        system="S", messages=[], schema={}, max_tokens=10)
    assert r.stop_reason == "refusal" and r.text == ""


def test_sdk_errors_map_to_llm_error():
    anthropic = pytest.importorskip("anthropic")
    httpx2 = pytest.importorskip("httpx2")
    req = httpx2.Request("POST", "https://api.invalid/v1/messages")
    exc = anthropic.APIConnectionError(request=req)
    with pytest.raises(LLMError) as e:
        AnthropicProvider(client=_Client(exc=exc)).generate(system="S", messages=[], schema={}, max_tokens=10)
    assert e.value.retryable
    for status, cls, retry in ((429, anthropic.RateLimitError, True), (400, anthropic.BadRequestError, False),
                               (529, anthropic.APIStatusError, True)):
        err = cls("x", response=httpx2.Response(status, request=req), body=None)
        with pytest.raises(LLMError) as e:
            AnthropicProvider(client=_Client(exc=err)).generate(system="S", messages=[], schema={}, max_tokens=10)
        assert e.value.retryable is retry, status


def test_engine_stays_importable_without_the_sdk():
    code = ("import sys; import engine.director.providers.anthropic_provider, engine.director.llm; "
            "print('anthropic' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
