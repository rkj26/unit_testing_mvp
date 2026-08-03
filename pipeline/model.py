"""Configurable trusted-model wiring (step 1: Config).

One model does every model-dependent step (property-gen, trigger-search, TM, informed-TM);
the untrusted candidates are frozen in the pool, so nothing else calls a model at run time.

Pass any inspect_ai model string via ``--model``:
  - ``openai-api/azureai/<deployment>``  Azure AI Foundry via its OpenAI-compatible endpoint;
        service prefix ``azureai`` reads AZUREAI_BASE_URL (=https://<resource>.services.ai.azure.com/openai/v1)
        + AZUREAI_API_KEY. This is the form Azure Foundry gives you for chat completions.
  - ``openai/...`` / ``anthropic/...`` etc. — any provider inspect_ai supports
  - ``mockllm/...`` or ``mock``   — offline canned responses (tests / smoke runs)
"""

from __future__ import annotations

import os
from typing import Any

# The kinds of blind model call the pipeline makes. plan/write_from_plan are the u_plans_t_writes
# gen-strategy (untrusted model plans, trusted model implements).
KINDS = ("property_gen", "trigger_search", "tm", "informed", "plan", "write_from_plan")

# Canned responses for the mock model, matched to the MockBackend's commutative `f(a,b)` task
# so a smoke run exercises the real property runner (catch on the backdoor, pass on honest).
_MOCK_PROPS = (
    "```python\n"
    "def prop_commutative(run, x):\n"
    '    """PROPERTY: the function is commutative: f(a, b) == f(b, a)."""\n'
    '    assert run(x) == run({"a": x["b"], "b": x["a"]})\n'
    "```\n"
)
_MOCK: dict[str, str] = {
    "property_gen": _MOCK_PROPS,
    "write_from_plan": _MOCK_PROPS,  # trusted model implements the plan -> same commutative suite
    "plan": "1. PROPERTY: f is commutative, f(a,b)==f(b,a). CHECK VIA: run(x) vs run(swapped x). "
            "TARGET INPUTS: small pairs like {a:0,b:0}, {a:1,b:2}.",
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
        self._model = None  # lazily resolved inspect model (async path / tests)
        # inspect's on-disk completion cache: identical (prompt, seed, temperature) served from disk
        # on a resume/retry instead of re-hitting the flaky endpoint. Off with INSPECT_CACHE=0.
        self._cache = os.getenv("INSPECT_CACHE", "1").lower() not in ("0", "false", "no")

    def _gen_config(self):
        from inspect_ai.model import GenerateConfig

        cfg: dict[str, Any] = {
            "temperature": self.temperature,
            # httpx read timeout per attempt. Each call uses a FRESH connection (see complete_blocking),
            # so stale-socket hangs are gone; this is just a fast-fail bound. Env-tunable.
            "timeout": int(os.getenv("CALL_HTTP_TIMEOUT", "60")),
            # Keep inspect's own retries low: the orchestrator retries at a higher level with a hard
            # wall-clock timeout and a fresh client, so we don't want two large nested retry budgets.
            "max_retries": int(os.getenv("CALL_HTTP_RETRIES", "1")),
            "max_connections": 16,
            # Bounding output makes concurrency safe on this endpoint (unbounded generations hang);
            # plenty for ~60 search-space inputs or a few property functions. Env-tunable.
            "max_tokens": int(os.getenv("MAX_TOKENS", "4000")),
        }
        if self.seed is not None:
            cfg["seed"] = self.seed
        # DeepSeek-V3.2 is ~10s at "low" vs ~117s at "medium"; the default effort was stalling us.
        effort = os.getenv("REASONING_EFFORT", "low")
        if effort and effort.lower() != "none":
            cfg["reasoning_effort"] = effort
        return GenerateConfig(**cfg)

    def _fresh_model(self):
        """A brand-new inspect model bound to the CURRENT event loop (fresh httpx client). Used by
        complete_blocking so each worker-thread call has its own loop + connection."""
        from inspect_ai.model import get_model

        cfg = self._gen_config()
        try:
            return get_model(self.name, config=cfg, memoize=False)  # never reuse a loop-bound client
        except TypeError:
            return get_model(self.name, config=cfg)

    def _resolve_inspect(self):
        if self._model is None:
            from inspect_ai.model import get_model

            self._model = get_model(self.name, config=self._gen_config())
        return self._model

    async def complete(self, prompt: str, kind: str) -> str:
        """Async path (mock model + tests). The orchestrator uses complete_blocking for hang safety."""
        if kind not in KINDS:
            raise ValueError(f"unknown model-call kind: {kind}")
        if self._mock:
            return _MOCK[kind]
        from inspect_ai.model import ChatMessageUser

        out = await self._resolve_inspect().generate([ChatMessageUser(content=prompt)], cache=self._cache)
        return out.completion or (out.message.text if out.message else "")

    def complete_blocking(self, prompt: str, kind: str) -> str:
        """Synchronous, self-contained call (own event loop + fresh client). Safe to run in a worker
        thread: if it wedges, the caller's hard timeout abandons the thread while the main loop — where
        the timeout timer lives — stays free. This is what makes a frozen socket non-fatal."""
        if kind not in KINDS:
            raise ValueError(f"unknown model-call kind: {kind}")
        if self._mock:
            return _MOCK[kind]
        import asyncio

        async def _go() -> str:
            from inspect_ai.model import ChatMessageUser

            out = await self._fresh_model().generate([ChatMessageUser(content=prompt)], cache=self._cache)
            return out.completion or (out.message.text if out.message else "")

        return asyncio.run(_go())


def resolve(name: str, *, temperature: float = 0.0, seed: int | None = None) -> TrustedModel:
    """Build the trusted model, validating provider env up front with a clear error."""
    if not name:
        raise ValueError("a model is required (e.g. --model openai-api/azureai/DeepSeek-V3.2 or --mock)")
    # Azure AI Foundry via the OpenAI-compatible endpoint: --model openai-api/azureai/<deployment>
    # (service prefix 'azureai' -> reads AZUREAI_BASE_URL + AZUREAI_API_KEY). Also covers the direct
    # azureai/... provider. Validate env up front with a clear message.
    if "azureai" in name.split("/"):
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
                f"Azure model {name!r} needs {' + '.join(missing)} in .env (see .env.example). "
                "For openai-api/azureai/<deployment>, AZUREAI_BASE_URL is the OpenAI-compatible "
                "endpoint: https://<resource>.services.ai.azure.com/openai/v1"
            )
    return TrustedModel(name, temperature=temperature, seed=seed)
