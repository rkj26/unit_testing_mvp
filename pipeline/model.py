"""Configurable trusted-model wiring (step 1: Config).

One model does every model-dependent step (property-gen, trigger-search, TM, informed-TM);
the untrusted candidates are frozen in the pool, so nothing else calls a model at run time.

Pass any inspect_ai model string via ``--model``:
  - ``azureai/<deployment>``      Azure AI Foundry (needs AZUREAI_BASE_URL + AZUREAI_API_KEY)
  - ``openai/...`` / ``anthropic/...`` etc. — any provider inspect_ai supports
  - ``mockllm/...`` or ``mock``   — offline canned responses (tests / smoke runs)
"""

from __future__ import annotations

import os
from typing import Any

# The four kinds of blind model call the pipeline makes.
KINDS = ("property_gen", "trigger_search", "tm", "informed")

# Canned responses for the mock model, matched to the MockBackend's commutative `f(a,b)` task
# so a smoke run exercises the real property runner (catch on the backdoor, pass on honest).
_MOCK: dict[str, str] = {
    "property_gen": (
        "```python\n"
        "def prop_commutative(run, x):\n"
        '    """PROPERTY: the function is commutative: f(a, b) == f(b, a)."""\n'
        '    assert run(x) == run({"a": x["b"], "b": x["a"]})\n'
        "```\n"
    ),
    "trigger_search": '[{"a": 999, "b": 1}, {"a": 1, "b": 2}, {"a": 0, "b": 0}]',
    "tm": "Looks routine.\nSUSPICION_SCORE: 3",
    "informed": "No property failure noted.\nSUSPICION_SCORE: 3",
}


class TrustedModel:
    """Thin async wrapper: ``await model.complete(prompt, kind) -> str``."""

    def __init__(self, name: str, *, temperature: float, seed: int | None):
        self.name = name
        self.temperature = temperature
        self.seed = seed
        self._mock = name.startswith("mock")
        self._model = None  # lazily resolved inspect model

    def _resolve_inspect(self):
        if self._model is not None:
            return self._model
        from inspect_ai.model import GenerateConfig, get_model

        cfg: dict[str, Any] = {
            "temperature": self.temperature,
            "timeout": 180,
            "max_retries": 2,
        }
        if self.seed is not None:
            cfg["seed"] = self.seed
        # NOTE: no `max_tokens` cap and no gemini-specific `reasoning_tokens` — capping output
        # is what truncated suites before, and reasoning_tokens is not an Azure/OpenAI param.
        self._model = get_model(self.name, config=GenerateConfig(**cfg))
        return self._model

    async def complete(self, prompt: str, kind: str) -> str:
        if kind not in KINDS:
            raise ValueError(f"unknown model-call kind: {kind}")
        if self._mock:
            return _MOCK[kind]
        from inspect_ai.model import ChatMessageUser

        out = await self._resolve_inspect().generate(
            [ChatMessageUser(content=prompt)], cache=False
        )
        return out.completion or (out.message.text if out.message else "")


def resolve(name: str, *, temperature: float = 0.0, seed: int | None = None) -> TrustedModel:
    """Build the trusted model, validating provider env up front with a clear error."""
    if not name:
        raise ValueError("a model is required (e.g. --model azureai/DeepSeek-V3.2 or --mock)")
    if name.startswith("azureai/"):
        has_key = os.getenv("AZUREAI_API_KEY") or os.getenv("AZURE_API_KEY")
        has_url = (
            os.getenv("AZUREAI_BASE_URL")
            or os.getenv("AZUREAI_ENDPOINT_URL")
            or os.getenv("AZURE_ENDPOINT_URL")
        )
        missing = []
        if not has_key:
            missing.append("AZUREAI_API_KEY")
        if not has_url:
            missing.append("AZUREAI_BASE_URL")
        if missing:
            raise EnvironmentError(
                f"Azure AI Foundry model {name!r} needs {' + '.join(missing)} in .env "
                "(see .env.example). AZUREAI_BASE_URL looks like "
                "https://<resource>.services.ai.azure.com/models"
            )
    return TrustedModel(name, temperature=temperature, seed=seed)
