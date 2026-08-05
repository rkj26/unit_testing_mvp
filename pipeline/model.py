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
    """Thin async wrapper: ``await model.complete(prompt, kind) -> str``.

    All endpoint knobs (timeouts, retry budget, token cap, reasoning effort, cache) are passed in from
    the run's `Config` via `resolve` — never re-read from the environment here — so the model behaves
    identically wherever it is reconstructed (parent, subprocess, or Docker worker reading `run.json`).
    """

    def __init__(self, name: str, *, temperature: float, seed: int | None,
                 http_timeout: int = 240, http_retries: int = 1, max_tokens: int = 4000,
                 reasoning_effort: str = "low", inspect_cache: bool = True,
                 attempt_timeout: int = 120):
        self.name = name
        self.temperature = temperature
        self.seed = seed
        self._mock = name.startswith("mock")
        self._model = None  # lazily resolved inspect model
        self.http_timeout = http_timeout
        self.http_retries = http_retries
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.attempt_timeout = attempt_timeout
        # inspect's on-disk completion cache: identical (prompt, seed, temperature) served from disk
        # on a resume/retry instead of re-hitting the flaky endpoint.
        self._cache = inspect_cache

    def _omits_temperature(self) -> bool:
        """OpenAI reasoning models (gpt-5.x, o1/o3/o4) reject any temperature but the default (1);
        sending temperature=0 to them is a 400. For those we omit it and let the API default stand.
        DeepSeek and the like keep their configured temperature (needed for per-run variance)."""
        base = self.name.lower().split("/")[-1]
        return base.startswith(("gpt-5", "o1", "o3", "o4"))

    def _gen_config(self):
        from inspect_ai.model import GenerateConfig

        cfg: dict[str, Any] = {
            # THREE NESTED BOUNDS, and they must stay ordered
            #   attempt_timeout  <  timeout  <  the engine's `with_retry` asyncio.wait_for
            #
            # `attempt_timeout` bounds ONE provider request (inspect wraps each attempt in
            # `anyio.move_on_after`). Leaving it unset means `nullcontext()` — an attempt is then
            # completely UNBOUNDED, so a silently-dead socket hangs forever. Chat completions are
            # non-streaming REST, so a long generation sends no bytes for its whole duration and an
            # idle connection reaped mid-flight looks identical to a slow one; this is the only bound
            # that catches it. (Measured: gpt-5.4 at reasoning_effort=high ~120s on a real prompt.)
            "attempt_timeout": self.attempt_timeout,
            # NOT an httpx read timeout (an earlier comment here claimed it was, which is how the
            # bound above came to be missing): this is inspect's TOTAL retry budget for the whole
            # generate call, spanning all of its internal attempts.
            "timeout": self.http_timeout,
            # Keep inspect's own retries low: the engine's `with_retry` retries at a higher level with a
            # hard wall-clock timeout, so we don't want two large nested retry budgets.
            "max_retries": self.http_retries,
            "max_connections": 16,
            # Bounding output makes concurrency safe on this endpoint (unbounded generations hang);
            # plenty for ~60 search-space inputs or a few property functions.
            "max_tokens": self.max_tokens,
        }
        if not self._omits_temperature():
            cfg["temperature"] = self.temperature
        if self.seed is not None:
            cfg["seed"] = self.seed
        # DeepSeek-V3.2 is ~10s at "low" vs ~117s at "medium"; the default effort was stalling us.
        if self.reasoning_effort and self.reasoning_effort.lower() != "none":
            cfg["reasoning_effort"] = self.reasoning_effort
        return GenerateConfig(**cfg)

    def _resolve_inspect(self):
        """Lazily build + memoize the inspect model (one shared httpx pool for this model's lifetime)."""
        if self._model is None:
            from inspect_ai.model import get_model

            self._model = get_model(self.name, config=self._gen_config())
        return self._model

    async def complete(self, prompt: str, kind: str) -> str:
        """The one model-call path: generate a completion for `prompt` (mock returns a canned response).

        Hang safety lives one level up in the engine's `with_retry` (a hard `asyncio.wait_for` per
        attempt); this just issues the request over the memoized inspect model + its shared pool.
        """
        if kind not in KINDS:
            raise ValueError(f"unknown model-call kind: {kind}")
        if self._mock:
            return _MOCK[kind]
        from inspect_ai.model import ChatMessageUser

        out = await self._resolve_inspect().generate([ChatMessageUser(content=prompt)], cache=self._cache)
        return out.completion or (out.message.text if out.message else "")


def resolve(name: str, *, temperature: float = 0.0, seed: int | None = None,
            http_timeout: int = 240, http_retries: int = 1, max_tokens: int = 4000,
            reasoning_effort: str = "low", inspect_cache: bool = True,
            attempt_timeout: int = 120) -> TrustedModel:
    """Build the trusted model from explicit Config-sourced knobs, validating provider env up front."""
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
    return TrustedModel(name, temperature=temperature, seed=seed, http_timeout=http_timeout,
                        http_retries=http_retries, max_tokens=max_tokens,
                        reasoning_effort=reasoning_effort, inspect_cache=inspect_cache,
                        attempt_timeout=attempt_timeout)
