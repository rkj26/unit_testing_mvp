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

KINDS = ("property_gen", "trigger_search", "tm", "informed", "plan", "write_from_plan")

TEMPERATURE_REJECTING_PREFIXES = ("gpt-5", "o1", "o3", "o4")
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

    def _rejects_temperature(self) -> bool:
        """OpenAI reasoning models 400 on any temperature but the default, so omit it for them."""
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
        if kind not in KINDS:
            raise ValueError(f"unknown model-call kind: {kind}")
        if self._mock:
            return _MOCK[kind]
        from inspect_ai.model import ChatMessageUser

        out = await self._resolve_inspect().generate(
            [ChatMessageUser(content=prompt)], cache=self.runtime.inspect_cache
        )
        return out.completion or (out.message.text if out.message else "")


def resolve(runtime: ModelRuntime) -> TrustedModel:
    """Build a model from its runtime knobs, validating provider credentials up front."""
    if not runtime.name:
        raise ValueError("a model is required (e.g. --t-model openai-api/azureai/DeepSeek-V3.2 or --mock)")
    if "azureai" in runtime.name.split("/"):
        _require_azure_credentials(runtime.name)
    return TrustedModel(runtime)


def _require_azure_credentials(name: str) -> None:
    missing = [var for var, group in (("AZUREAI_API_KEY", AZURE_KEY_VARS),
                                      ("AZUREAI_BASE_URL", AZURE_URL_VARS))
               if not any(os.getenv(alias) for alias in group)]
    if missing:
        raise EnvironmentError(
            f"Azure model {name!r} needs {' + '.join(missing)} in .env (see .env.example). "
            "For openai-api/azureai/<deployment>, AZUREAI_BASE_URL is the OpenAI-compatible "
            "endpoint: https://<resource>.services.ai.azure.com/openai/v1"
        )
