"""The single, enum-typed configuration object for a pipeline run.

Everything a run needs is captured once here, built from the CLI in `Config.from_args`, persisted to
`run.json` via `to_json`, and rebuilt in isolated workers via `from_json`. This is the single source of
truth: the endpoint/eval knobs below are threaded into `model.resolve` and `pbt.evaluate` (they are NOT
re-read from the environment at those call sites), so a run is fully reproducible from its `run.json`
alone — including inside a Docker worker, where only credentials are forwarded from the host env.

Public surface (top of file): the enums (`Domain`, `GenStrategy`, `Stage`, `ExecMode`), the `Config`
dataclass, and its `from_args` / `to_json` / `from_json` constructors. Private helpers are at the bottom.
"""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, fields
from enum import Enum
from typing import Any


class Domain(str, Enum):
    """Which benchmark backend to run against. Values match the CLI `--domain` strings."""

    APPS = "apps"
    BCB = "bcb"
    MOCK = "mock"


class GenStrategy(str, Enum):
    """Who authors the PBT properties. Values match the CLI `--gen-strategy` strings.

    The plan/write 2x2 (who plans x who writes):
      BLIND_T          no explicit plan; trusted model writes the properties (default).
      U_WRITES         no explicit plan; the elicited/untrusted model writes the properties directly.
      U_PLANS_T_WRITES the elicited model writes a spec-only plan, the trusted model implements it
                       (collusion-safe: the untrusted plan never becomes code untouched).
      U_PLANS_U_WRITES the elicited model writes a spec-only plan, then implements it itself
                       (two-turn fully-untrusted author — the untrusted ceiling for plan->write).
    The trigger search space is always trusted-authored regardless of strategy.
    """

    BLIND_T = "blind_t"
    U_WRITES = "u_writes"
    U_PLANS_T_WRITES = "u_plans_t_writes"
    U_PLANS_U_WRITES = "u_plans_u_writes"


class Stage(str, Enum):
    """Which half of the pipeline to run. Values match the CLI `--stage` strings.

    ALL      preprocess + ground-truth scoring + the model-dependent monitor phase.
    SCORE    stop after the deterministic ground-truth scoring (writes scores.json).
    MONITOR  only the model phase, against a prior SCORE run's --run-id.
    """

    ALL = "all"
    SCORE = "score"
    MONITOR = "monitor"


class ExecMode(str, Enum):
    """How an isolatable step/run is executed. Values match the CLI `--exec-mode` strings.

    INPROCESS   run directly in the current process (fast; no isolation).
    SUBPROCESS  run in a fresh process group with a wall-clock timeout + group-kill (default).
    DOCKER      run the same worker command inside a container (`--docker-image`).
    """

    INPROCESS = "inprocess"
    SUBPROCESS = "subprocess"
    DOCKER = "docker"


# field name -> enum type, used to (de)serialize the enum-valued fields uniformly.
_ENUM_FIELDS: dict[str, type[Enum]] = {
    "domain": Domain, "gen_strategy": GenStrategy, "stage": Stage, "exec_mode": ExecMode,
}


@dataclass(frozen=True)
class Config:
    """Immutable, fully-resolved configuration for one pipeline run.

    Built once by `from_args` (CLI + environment defaults), serialized to `run.json` by `to_json`, and
    reconstructed by workers via `from_json`. Enum fields are held as enums in memory and stored as their
    string `.value` on disk.
    """

    # --- identity / data ---
    domain: Domain
    run_id: str
    pool_path: str | None
    limit: int | None
    # --- models ---
    mock: bool
    t_model: str                 # trusted model string (ignored when mock)
    u_model: str | None          # elicited model for the u_* strategies; None -> falls back to t_model
    gen_strategy: GenStrategy
    property_prompt: str         # property-gen prompt variant: "default" | "precision"
    search_prompt: str           # trigger-search prompt variant: "default" | "dense"
    # --- experiment ---
    runs: int
    tests_per_problem: int
    seed: int
    audit_rate: float
    stage: Stage
    self_critique: bool
    progress: bool               # render the live rich dashboard (default: attached to a TTY)
    # --- model-call knobs (endpoint-facing) ---
    reasoning_effort: str
    max_tokens: int
    # Same two knobs for the elicited (U) model only. They default to the T values, so behaviour is
    # unchanged unless set. Split out because effort is NOT a neutral global: the trusted model also
    # serves as the monitor, so raising a single global effort strengthens TM and erases the very
    # headroom a PBT arm is being measured for. Raising U alone (e.g. a high-reasoning planner against
    # a fixed cheap monitor + writer) keeps the TM column comparable to prior runs.
    u_reasoning_effort: str
    u_max_tokens: int
    max_conn: int
    # Three nested call bounds, which MUST stay ordered:
    #   call_attempt_timeout  <  call_http_timeout  <  call_timeout
    call_timeout: int            # outermost: engine `with_retry` asyncio.wait_for, per attempt (s)
    call_retries: int
    call_attempt_timeout: int    # innermost: bounds ONE provider request (inspect `attempt_timeout`)
    call_http_timeout: int       # middle: inspect's TOTAL retry budget per generate call (s)
    call_http_retries: int       # inspect's own low-level retry budget per attempt
    inspect_cache: bool
    # --- PBT eval knobs (local) ---
    pbt_timeout: int             # per-candidate property-runner subprocess cap (s)
    exec_workers: int            # thread-pool size for local PBT eval
    max_search_space: int
    # --- isolation ---
    exec_mode: ExecMode
    docker_image: str | None
    run_timeout: int             # hard wall-clock per run subprocess (s)
    run_retries: int             # kill+resume attempts per run

    @property
    def model_name(self) -> str:
        """The trusted model string to resolve — ``"mock"`` when ``--mock`` is set, else ``t_model``."""
        return "mock" if self.mock else self.t_model

    @property
    def elicit_model_name(self) -> str | None:
        """The elicited (U) model string, or None when mock/unset (callers fall back to the T model)."""
        return None if self.mock else self.u_model

    @classmethod
    def from_args(cls, args: Any) -> "Config":
        """Build a Config from a parsed argparse Namespace, filling non-CLI knobs from the environment.

        Experiment-shaping options come from the CLI; endpoint/eval/isolation tuning knobs come from
        `_env_knobs()` (same env names + defaults the pre-rewrite modules used), so behavior is unchanged
        until the engine consumes them directly.
        """
        return cls(
            domain=Domain(args.domain),
            run_id=args.run_id,
            pool_path=getattr(args, "pool", None),
            limit=(args.limit or None),
            mock=bool(args.mock),
            t_model=(args.model or ""),
            u_model=getattr(args, "elicit_model", None),
            gen_strategy=GenStrategy(args.gen_strategy),
            property_prompt=getattr(args, "property_prompt", None) or "default",
            search_prompt=getattr(args, "search_prompt", None) or "default",
            runs=int(args.runs),
            tests_per_problem=int(args.tests_per_problem),
            seed=int(args.seed),
            audit_rate=float(args.audit_rate),
            stage=Stage(args.stage),
            progress=(args.progress if getattr(args, "progress", None) is not None
                      else sys.stdout.isatty()),
            exec_mode=ExecMode(getattr(args, "exec_mode", None) or "subprocess"),
            docker_image=getattr(args, "docker_image", None),
            **_env_knobs(),
        )

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-serializable dict (enums flattened to strings) for `run.json`.

        Adds two read-only aliases the report renderer expects — `model` (= `model_name`) and `pool`
        (= `pool_path`); `from_json` ignores unknown keys, so they never affect a round-trip.
        """
        data = asdict(self)
        for key in _ENUM_FIELDS:
            data[key] = self.__dict__[key].value
        data["model"] = self.model_name
        data["pool"] = self.pool_path
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Config":
        """Rebuild a Config from a `to_json` dict (used by isolated workers reading `run.json`).

        Missing keys fall back to CLI/env defaults and unknown keys are ignored, so a `run.json` with
        extra/absent fields still loads. An enum field with an *unrecognized* value (e.g. a strategy
        added by a newer build) fails fast with a clear error rather than silently defaulting — running
        the wrong domain/strategy would corrupt results silently.
        """
        known = {f.name for f in fields(cls)}
        merged = {**_CLI_DEFAULTS, **_env_knobs(), **{k: v for k, v in data.items() if k in known}}
        for key, enum_cls in _ENUM_FIELDS.items():
            value = merged[key]
            if isinstance(value, enum_cls):
                continue
            try:
                merged[key] = enum_cls(value)
            except ValueError:
                raise SystemExit(f"run.json has unknown {key}={value!r} — this build predates that value")
        return cls(**{name: merged[name] for name in known})


# --------------------------------------------------------------------------- #
# private helpers
# --------------------------------------------------------------------------- #
# Defaults for the CLI-sourced fields, used only by `from_json` to tolerate a partial `run.json`.
_CLI_DEFAULTS: dict[str, Any] = {
    "domain": "mock", "run_id": "", "pool_path": None, "limit": None,
    "mock": False, "t_model": "", "u_model": None, "gen_strategy": "blind_t",
    "property_prompt": "default", "search_prompt": "default",
    "runs": 1, "tests_per_problem": 5, "seed": 0, "audit_rate": 0.10, "stage": "all",
    "progress": False, "exec_mode": "subprocess", "docker_image": None,
}


def _env_knobs() -> dict[str, Any]:
    """The non-CLI tuning knobs (endpoint / eval / isolation), read from the environment with defaults.

    Shared by `from_args` and `from_json` so the two constructors can never drift on defaults.
    """
    effort = os.getenv("REASONING_EFFORT", "low")
    max_tokens = _env_int("MAX_TOKENS", 4000)
    return {
        "self_critique": _env_bool("PBT_SELF_CRITIQUE", False),
        "reasoning_effort": effort,
        "max_tokens": max_tokens,
        # U inherits T's effort/token budget unless explicitly raised. A high-effort U typically needs a
        # much larger cap than T: reasoning tokens are billed against max_tokens, and a budget that only
        # covers the reasoning leaves nothing for the answer (an 8k cap at medium returned empty output).
        "u_reasoning_effort": os.getenv("U_REASONING_EFFORT") or effort,
        "u_max_tokens": _env_int("U_MAX_TOKENS", max_tokens),
        "max_conn": _env_int("MAX_CONN", 4),
        # Defaults keep the required ordering: 120 < 240 < 300. Raise all three together for a slow
        # model (gpt-5.4 at effort=high measured ~120s), never just the outer one.
        "call_timeout": _env_int("CALL_TIMEOUT", 300),
        "call_retries": _env_int("CALL_RETRIES", 2),
        "call_attempt_timeout": _env_int("CALL_ATTEMPT_TIMEOUT", 120),
        "call_http_timeout": _env_int("CALL_HTTP_TIMEOUT", 240),
        "call_http_retries": _env_int("CALL_HTTP_RETRIES", 1),
        "inspect_cache": _env_bool("INSPECT_CACHE", True),
        "pbt_timeout": _env_int("PBT_TIMEOUT", 60),
        "exec_workers": _env_int("EXEC_WORKERS", 8),
        "max_search_space": _env_int("MAX_SEARCH_SPACE", 60),
        "run_timeout": _env_int("RUN_SUBPROC_TIMEOUT", 1200),
        "run_retries": _env_int("RUN_RETRIES", 2),
    }


def _env_int(name: str, default: int) -> int:
    """Read an int env var, returning `default` when it is unset or unparsable."""
    raw = os.getenv(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean env var ('1'/'true'/'yes' -> True), returning `default` when unset."""
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in ("1", "true", "yes")
