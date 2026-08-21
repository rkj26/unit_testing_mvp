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
from typing import Any

from .config import ModelRuntime
from .outcome import Blame, Measured, Unknown
from .schema import Completion

KINDS = ("property_gen", "trigger_search", "tm", "informed", "plan", "write_from_plan")

MOCK_STOP_REASON = "stop"
EMPTY_RESPONSE_STOP_REASON = "empty_response"
NO_REASONING = ""
REASONING_PART_TYPE = "reasoning"

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
}


def _reasoning(out: Any) -> Measured[str]:
    """The provider's thinking, or `Unknown` when the response shape could not be read.

    `ModelOutput.completion` returns the answer text alone; on a reasoning model the thinking
    arrives as `ContentReasoning` blocks in the message content and is dropped there. A plain
    string content is the ordinary shape of a reply carrying no thinking, so it is `NO_REASONING`
    — an answer. A content that is neither a string nor a list of parts is not an answer, and used
    to leave the same empty string, which reads as a model that does not reason.
    """
    content = getattr(getattr(out, "message", None), "content", None)
    if isinstance(content, str):
        return NO_REASONING
    if not isinstance(content, list):
        return Unknown(
            Blame.INFRA,
            f"message content is {type(content).__name__}, not a string or a list of parts",
        )
    return _joined_reasoning(content)


def _joined_reasoning(content: list[Any]) -> Measured[str]:
    """Every reasoning part of a parts list, joined. `Unknown` if one carries no reasoning text."""
    parts = [part for part in content if getattr(part, "type", "") == REASONING_PART_TYPE]
    unreadable = [part for part in parts if not isinstance(getattr(part, "reasoning", None), str)]
    if unreadable:
        return Unknown(
            Blame.INFRA,
            f"{len(unreadable)} of {len(parts)} reasoning parts carry no reasoning text "
            f"(first is {type(unreadable[0]).__name__})",
        )
    return "\n".join(part.reasoning for part in parts)


class TrustedModel:
    """Thin async wrapper over one inspect model: ``await model.complete(prompt, kind) -> str``,
    or ``await model.completion(prompt, kind) -> Completion`` when the stop reason matters."""

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

    async def complete(self, prompt: str, kind: str) -> str:
        return (await self.completion(prompt, kind)).text

    async def completion(self, prompt: str, kind: str, schema: Any = None) -> Completion:
        """The same single call as `complete`, keeping the provider's stop reason attached.

        `schema` is an `inspect_ai.model.ResponseSchema`. When given, the provider is required to
        return JSON matching it, so a malformed answer becomes an API-level failure rather than a
        parse this side has to cope with.
        """
        if kind not in KINDS:
            raise ValueError(f"unknown model-call kind: {kind}")
        if self._mock:
            return Completion(_MOCK[kind], MOCK_STOP_REASON, reasoning=NO_REASONING)
        from inspect_ai.model import ChatMessageUser, GenerateConfig

        config = GenerateConfig(response_schema=schema) if schema is not None else None
        out = await self._resolve_inspect().generate(
            [ChatMessageUser(content=prompt)], cache=self.runtime.inspect_cache, config=config
        )
        if out.empty:
            return Completion("", EMPTY_RESPONSE_STOP_REASON, reasoning=_reasoning(out))
        return Completion(
            out.completion or out.message.text, out.stop_reason, reasoning=_reasoning(out)
        )


def resolve(runtime: ModelRuntime) -> TrustedModel:
    """Build a model from its runtime knobs, validating provider credentials up front.

    One Azure AI Foundry endpoint serves every deployment we use, but inspect_ai and the SDKs
    beneath it read a different variable name each, so the single `AZUREAI_*` pair configured in
    `.env` is fanned out to the names they expect. `setdefault`, so anything already exported wins.
    """
    if not runtime.name:
        raise ValueError(
            "a model is required (e.g. --t-model openai-api/azureai/DeepSeek-V3.2 or --mock)"
        )

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
