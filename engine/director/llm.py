"""Provider-neutral LLM interface (spec §4.9). A provider turns (system, messages, schema) into one
LLMResult. `assistant_content` is the provider's own reply payload, replayed unchanged in the next
turn of a repair conversation (Claude: content blocks, including thinking blocks)."""
import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LLMResult:
    text: str
    stop_reason: str               # end_turn | max_tokens | refusal | ...
    model: str
    usage: dict = field(default_factory=dict)
    assistant_content: object = None
    request_id: str = None


class LLMError(RuntimeError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


class FakeProvider:
    """Offline provider for tests and fixtures. A reply is a script dict (sent as JSON), a raw string,
    {"stop_reason": ..., "text": ...}, or {"error": ..., "retryable": bool}."""
    name = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    @classmethod
    def from_fixture(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8"))["replies"])

    def generate(self, *, system, messages, schema, max_tokens):
        self.calls.append({"system": system, "messages": copy.deepcopy(messages), "schema": schema})
        if not self.replies:
            raise LLMError("fake provider has no reply left")
        r = self.replies.pop(0)
        if isinstance(r, dict) and "error" in r:
            raise LLMError(r["error"], retryable=r.get("retryable", False))
        if isinstance(r, dict) and "stop_reason" in r:
            text, stop = r.get("text", ""), r["stop_reason"]
        else:
            text, stop = (r if isinstance(r, str) else json.dumps(r)), "end_turn"
        return LLMResult(text=text, stop_reason=stop, model="fake",
                         usage={"input_tokens": 0, "output_tokens": 0}, assistant_content=text)


class RecordingProvider:
    """Wraps a live provider and appends each reply to a fixture file FakeProvider can replay. Never
    records the system text (only its hash) or any credential."""

    def __init__(self, inner, path):
        self.inner, self.path = inner, Path(path)
        self.name = f"recording:{inner.name}"

    def generate(self, **kw):
        res = self.inner.generate(**kw)
        data = (json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists()
                else {"replies": [], "recorded": []})
        data["replies"].append({"text": res.text, "stop_reason": res.stop_reason})
        data["recorded"].append({"model": res.model, "usage": res.usage, "requestId": res.request_id,
                                 "rulebookSha": hashlib.sha256(kw["system"].encode()).hexdigest()[:12]})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return res
