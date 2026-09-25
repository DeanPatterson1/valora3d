"""Claude provider (spec §4.9: provider-neutral interface, Claude by default, server-side only).
The SDK is imported lazily so engine/ stays importable inside Blender's bundled Python.
Credentials: the SDK's own chain (ANTHROPIC_API_KEY, or an `ant auth login` profile). Never log them.

Request shape checked against the claude-api skill (cached 2026-06-24) and anthropic 1.8.0's
signatures (2026-09-24): Opus 5.5 always thinks (adaptive; no budget_tokens, no temperature) and its
default effort is medium, so effort is set explicitly; structured output via output_config.format;
refusal fallbacks via the "default" scalar under beta server-side-fallback-2026-07-01. A fallback
model runs without Opus 5.5's thinking blocks (they are model-bound); the API drops them itself."""
import os

from engine.director.llm import LLMError, LLMResult

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
PASS_THROUGH_EXTRA_BODY = False  # anthropic 1.8.0 names fallbacks/output_config; True only for an SDK that lacks them


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model=None, effort="high", client=None, fallbacks=True, max_retries=2, timeout_s=600):
        self.model = model or os.environ.get("VALORA_DIRECTOR_MODEL", DEFAULT_MODEL)
        self.effort, self.fallbacks = effort, fallbacks
        self._client, self._max_retries, self._timeout = client, max_retries, timeout_s

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(max_retries=self._max_retries, timeout=self._timeout)
        return self._client

    def generate(self, *, system, messages, schema, max_tokens):
        client = self._get_client()
        kw = {"model": self.model, "max_tokens": max_tokens,
              "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
              "messages": messages, "thinking": {"type": "adaptive"}}
        extra = {"output_config": {"effort": self.effort, "format": {"type": "json_schema", "schema": schema}}}
        api = client.messages
        if self.fallbacks:
            api = client.beta.messages
            kw["betas"] = [FALLBACK_BETA]
            extra["fallbacks"] = "default"
        if PASS_THROUGH_EXTRA_BODY:
            kw["extra_body"] = extra
        else:
            kw.update(extra)
        try:
            with api.stream(**kw) as stream:
                msg = stream.get_final_message()
        except Exception as e:  # noqa: BLE001 - mapped to the provider-neutral error below
            raise _map_error(e) from e
        # Refusals come back as data (stop_reason "refusal"), never parsed here; the pipeline decides.
        text = next((b.text for b in msg.content if getattr(b, "type", "") == "text"), "")
        usage = {k: int(getattr(msg.usage, k, 0) or 0) for k in USAGE_KEYS}
        return LLMResult(text=text, stop_reason=msg.stop_reason, model=msg.model, usage=usage,
                         assistant_content=msg.to_dict()["content"], request_id=getattr(msg, "_request_id", None))


def _map_error(e):
    try:
        import anthropic
    except ImportError:
        return LLMError(f"{type(e).__name__}: {e}")
    if isinstance(e, anthropic.RateLimitError):
        return LLMError(f"rate limited: {e}", retryable=True)
    if isinstance(e, anthropic.APIConnectionError):
        return LLMError(f"connection failed (check network / antivirus web shield): {e}", retryable=True)
    if isinstance(e, anthropic.APIStatusError):
        return LLMError(f"HTTP {e.status_code}: {e}", retryable=e.status_code >= 500)
    return LLMError(f"{type(e).__name__}: {e}")
