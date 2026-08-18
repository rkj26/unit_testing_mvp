"""Model wiring: one `ModelRuntime` in, one awaitable `complete()` out.

Every model-dependent step (property-gen, trigger-search, TM, informed-TM, plan, write-from-plan)
goes through here; the untrusted candidates are frozen in the pool, so nothing else calls a model
at run time.

Model strings are inspect_ai's:
  - ``openai-api/azureai/<deployment>``  Azure AI Foundry via its OpenAI-compatible endpoint;
        service prefix ``azureai`` reads AZUREAI_BASE_URL + AZUREAI_API_KEY
  - ``openai/...`` / ``anthropic/...``   any provider inspect_ai supports
  - ``mockllm/...`` or ``mock``          offline canned responses (tests / smoke runs)
"""

from __future__ import annotations

import os
import re
from typing import Any

from .config import ModelRuntime

MAX_RETRY_AFTER_SECONDS = 120
ERROR_MESSAGE_CAP = 500

RETRY_HINT_PATTERNS = (
    re.compile(r"retry in\s+([0-9]+(?:\.[0-9]+)?)\s*s", re.IGNORECASE),
    re.compile(r"retry_?delay\D{0,4}([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE),
)

KINDS = (
    "property_gen",
    "trigger_search",
    "tm",
    "informed",
    "plan",
    "write_from_plan",
    "code_monitor",
)

TEMPERATURE_REJECTING_PREFIXES = ("gpt-5", "o1", "o3", "o4", "deepseek-v3.2", "v3.2")
AZURE_KEY_VARS = ("AZUREAI_API_KEY", "AZURE_API_KEY")
AZURE_URL_VARS = ("AZUREAI_BASE_URL", "AZUREAI_ENDPOINT_URL", "AZURE_ENDPOINT_URL")


_MOCK_PROPS = (
    "```python\n"
    "def prop_commutative(run, x):\n"
    '    """PROPERTY: the function is commutative: f(a, b) == f(b, a)."""\n'
    '    assert run(x) == run({"a": x["b"], "b": x["a"]})\n'
    "```\n"
)
_MOCK: dict[str, str] = {
    "property_gen": _MOCK_PROPS,
    "write_from_plan": _MOCK_PROPS,
    "plan": "1. PROPERTY: f is commutative, f(a,b)==f(b,a). CHECK VIA: run(x) vs run(swapped x). "
    "TARGET INPUTS: small pairs like {a:0,b:0}, {a:1,b:2}.",
    "trigger_search": '[{"a": 999, "b": 1}, {"a": 1, "b": 2}, {"a": 0, "b": 0}]',
    "tm": "Looks routine.\nSUSPICION_SCORE: 3",
    "informed": "No property failure noted.\nSUSPICION_SCORE: 3",
    "code_monitor": "[[ ## reasoning ## ]]\nNothing stands out.\n\n"
    "[[ ## suspicion_score ## ]]\n3\n\n[[ ## completed ## ]]",
}


def unwrap_error(error: BaseException) -> BaseException:
    """The provider exception a retry wrapper is hiding.

    `tenacity.RetryError` stringifies as a `Future` repr, naming neither the status code nor the
    message — a run of 11 dropped submissions once could not be diagnosed from its own artifact
    because of it. Follow `last_attempt` / `__cause__` down to what actually failed.
    """
    seen: set[int] = set()
    current = error
    while id(current) not in seen:
        seen.add(id(current))
        last_attempt = getattr(current, "last_attempt", None)
        if last_attempt is not None:
            try:
                inner = last_attempt.exception()
            except Exception:
                return current
            if inner is not None:
                current = inner
                continue
        if current.__cause__ is not None:
            current = current.__cause__
            continue
        break
    return current


def error_message(error: BaseException) -> str:
    message = getattr(error, "message", "")
    if not message:
        message = str(error)
    return message


def describe_error(error: BaseException) -> str:
    """One legible line naming the real failure: type, HTTP status, provider message."""
    inner = unwrap_error(error)
    parts = [type(inner).__name__]
    for attr in ("code", "status"):
        value = getattr(inner, attr, None)
        if value is not None:
            parts.append(f"{attr}={value}")
    return f"{' '.join(parts)}: {error_message(inner)[:ERROR_MESSAGE_CAP]}"


def retry_after_seconds(error: BaseException) -> float | None:
    """The provider's stated wait before a retry can succeed, or None when it stated none.

    Retrying a rate limit before the server's stated reset is guaranteed to fail AND to spend
    another request against the quota, so the hint is strictly better than blind exponential
    backoff. Headers come first via inspect's parser; Google states its RetryInfo in the message
    body instead, which that parser does not read, so the text is checked too. Capped so a bogus
    hint cannot park a run indefinitely.
    """
    from inspect_ai._util.http import parse_retry_after_from_exception

    inner = unwrap_error(error)
    hint = parse_retry_after_from_exception(inner)
    if hint is None:
        message = error_message(inner)
        for pattern in RETRY_HINT_PATTERNS:
            match = pattern.search(message)
            if match:
                hint = float(match.group(1))
                break
    if hint is None:
        return None
    return min(hint, MAX_RETRY_AFTER_SECONDS)


class TrustedModel:
    """Thin async wrapper over one inspect model: ``await model.complete(prompt, kind) -> str``."""

    def __init__(self, runtime: ModelRuntime):
        self.runtime = runtime
        self._mock = runtime.name.startswith("mock")
        self._model = None

    @property
    def name(self) -> str:
        return self.runtime.name

    @property
    def reasoning_effort(self) -> str:
        return self.runtime.reasoning_effort.value

    @property
    def max_tokens(self) -> int:
        return self.runtime.max_tokens

    @property
    def honors_temperature(self) -> bool:
        """Whether this model accepts our explicit temperature, or runs at the provider default.

        Reasoning models reject a non-default temperature, so a manifest that records the value we
        asked for would be asserting a setting that was never sent.
        """
        return not self._rejects_temperature()

    def _rejects_temperature(self) -> bool:
        """Reasoning models (gpt-5, o1, o3, o4, DeepSeek-V3.2) reject non-default temperature."""
        base = self.runtime.name.lower().split("/")[-1]
        return base.startswith(TEMPERATURE_REJECTING_PREFIXES)

    def _gen_config(self):
        from inspect_ai.model import GenerateConfig

        cfg: dict[str, Any] = {
            "attempt_timeout": self.runtime.attempt_timeout,
            "timeout": self.runtime.http_timeout,
            "max_retries": self.runtime.http_retries,
            "max_connections": self.runtime.max_connections,
            "max_tokens": self.runtime.max_tokens,
            "seed": self.runtime.seed,
            "reasoning_effort": self.runtime.reasoning_effort.value,
        }
        if not self._rejects_temperature():
            cfg["temperature"] = self.runtime.temperature
        return GenerateConfig(**cfg)

    def _resolve_inspect(self):
        if self._model is None:
            from inspect_ai.model import get_model

            self._model = get_model(self.runtime.name, config=self._gen_config())
        return self._model

    def ensure_ready(self) -> str:
        """Construct the provider client WITHOUT sending a request; returns the resolved name.

        Lets a pre-flight check prove the model string and credentials are wired up without
        spending a request against a metered quota.
        """
        if self._mock:
            return self.name
        return self._resolve_inspect().name

    async def complete(self, prompt: str, kind: str, system: str = "") -> str:
        """Complete `prompt`, optionally under a system message (empty string = none)."""
        if kind not in KINDS:
            raise ValueError(f"unknown model-call kind: {kind}")
        if self._mock:
            return _MOCK[kind]
        from inspect_ai.model import ChatMessageSystem, ChatMessageUser

        messages = [ChatMessageUser(content=prompt)]
        if system:
            messages.insert(0, ChatMessageSystem(content=system))
        out = await self._resolve_inspect().generate(
            messages, cache=self.runtime.inspect_cache
        )
        return out.completion or (out.message.text if out.message else "")


def resolve(runtime: ModelRuntime) -> TrustedModel:
    """Build a model from its runtime knobs, validating provider credentials up front."""
    if not runtime.name:
        raise ValueError(
            "a model is required (e.g. --t-model openai-api/azureai/DeepSeek-V3.2 or --mock)"
        )
    
    # Auto-export standard Azure / OpenAI variables that inspect-ai / SDKs expect internally
    # This allows a unified Azure AI Foundry endpoint (AZUREAI_BASE_URL) to map to everything
    key = next((os.getenv(alias) for alias in AZURE_KEY_VARS if os.getenv(alias)), None)
    url = next((os.getenv(alias) for alias in AZURE_URL_VARS if os.getenv(alias)), None)
    
    if key:
        os.environ.setdefault("AZURE_API_KEY", key)
        os.environ.setdefault("AZURE_OPENAI_API_KEY", key)
        os.environ.setdefault("OPENAI_API_KEY", key)
    if url:
        os.environ.setdefault("AZUREAI_ENDPOINT_URL", url)
        os.environ.setdefault("AZURE_OPENAI_ENDPOINT", url)
        os.environ.setdefault("OPENAI_BASE_URL", url)

    if "azureai" in runtime.name.split("/"):
        _require_azure_credentials(runtime.name)
    return TrustedModel(runtime)


def _require_azure_credentials(name: str) -> None:
    missing = [
        var
        for var, group in (
            ("AZUREAI_API_KEY", AZURE_KEY_VARS),
            ("AZUREAI_BASE_URL", AZURE_URL_VARS),
        )
        if not any(os.getenv(alias) for alias in group)
    ]
    if missing:
        raise OSError(
            f"Azure model {name!r} needs {' + '.join(missing)} in .env (see .env.example). "
            "For openai-api/azureai/<deployment>, AZUREAI_BASE_URL is the OpenAI-compatible "
            "endpoint: https://<resource>.services.ai.azure.com/openai/v1"
        )
