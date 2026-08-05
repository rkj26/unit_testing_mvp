"""Run configuration: a small set of choices, everything else derived.

`Settings` is the single declaration of the command line, the environment fallbacks, and the
validation rules; `Settings.to_config()` turns it into the nested `Config` the pipeline uses.
Token caps, the timeout ladder, retry budgets and concurrency are derived from the chosen models,
so they cannot drift out of agreement, and the ladder refuses to build itself out of order.

Public surface: Domain, GenStrategy, Stage, ExecMode, ModelSpec, Config, Settings.
"""

from __future__ import annotations

import sys
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .metrics import PROTOCOLS, MetricConfig


class Domain(str, Enum):
    """Benchmark backend to run against."""

    APPS = "apps"
    BCB = "bcb"
    MOCK = "mock"


class GenStrategy(str, Enum):
    """Who authors the PBT properties, as who-plans x who-writes.

    Only the u_* strategies use the untrusted model. The trigger search space is always
    trusted-authored. U_PLANS_T_WRITES is the collusion-safe split: the untrusted plan never
    becomes executable code untouched.
    """

    BLIND_T = "blind_t"
    U_WRITES = "u_writes"
    U_PLANS_T_WRITES = "u_plans_t_writes"
    U_PLANS_U_WRITES = "u_plans_u_writes"

    @property
    def uses_untrusted(self) -> bool:
        return self is not GenStrategy.BLIND_T


class Stage(str, Enum):
    """Which half of the pipeline to run: everything, ground-truth scoring only, or models only."""

    ALL = "all"
    SCORE = "score"
    MONITOR = "monitor"


class ExecMode(str, Enum):
    """Isolation boundary for steps and runs."""

    INPROCESS = "inprocess"
    SUBPROCESS = "subprocess"
    DOCKER = "docker"


class Reasoning(str, Enum):
    """Reasoning effort, which sets both the token cap and the measured per-call budget."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAX = "max"


MEASURED_CALL_SECONDS_BY_EFFORT = {
    Reasoning.LOW: 120, Reasoning.MEDIUM: 300, Reasoning.HIGH: 420, Reasoning.MAX: 420,
}
MAX_TOKENS_BY_EFFORT = {
    Reasoning.LOW: 4_000, Reasoning.MEDIUM: 32_000, Reasoning.HIGH: 32_000, Reasoning.MAX: 32_000,
}

MEASURED_SAFE_CONCURRENCY = 12
MODEL_POOL_CONNECTIONS = 16
SINGLE_RUN_TEMPERATURE = 0.0
MULTI_RUN_TEMPERATURE = 0.7
RETRY_BUDGET_PER_CALL = 2
MIN_RETRY_BUDGET_SECONDS = 240
OUTER_CALL_MARGIN_SECONDS = 60
CALLS_PER_UNIT = 3
UNITS_PER_RUN = 4
MIN_RUN_BUDGET_SECONDS = 3600

ENGINE_CALL_RETRIES = 2
INSPECT_HTTP_RETRIES = 1
RUN_RETRIES = 2
PBT_HARNESS_TIMEOUT_SECONDS = 60
PBT_EXEC_WORKERS = 8
MAX_SEARCH_SPACE = 60
TESTS_PER_PROBLEM = 5

ALWAYS_ATTACK_ALIASES = ("always", "none")
NO_MODEL = ""
ALL_TASKS = 0
DERIVE_FROM_REASONING = 0

Seconds = Annotated[int, Field(ge=0)]


class ModelSpec(BaseModel):
    """A model and the three things worth deciding about it.

    `timeout` bounds one provider request and is the only timeout a caller should think about;
    every wider bound derives from it. Zero means derive it from `reasoning`.
    """

    model_config = ConfigDict(frozen=True)

    name: str = NO_MODEL
    reasoning: Reasoning = Reasoning.LOW
    timeout: Seconds = DERIVE_FROM_REASONING

    @property
    def resolved_timeout(self) -> int:
        return self.timeout or MEASURED_CALL_SECONDS_BY_EFFORT[self.reasoning]

    @property
    def max_tokens(self) -> int:
        return MAX_TOKENS_BY_EFFORT[self.reasoning]


class TimeoutLadder(BaseModel):
    """Nested request bounds, strictly increasing outwards.

        per-call attempt < http retry budget < outer call < unit < run

    A per-call bound catches a dead socket, since chat completions are non-streaming REST and send
    no bytes while the model generates. A unit bound keeps one pathological task from taking the
    whole run down with it.
    """

    model_config = ConfigDict(frozen=True)

    trusted_call: Seconds
    untrusted_call: Seconds
    http_retry_budget: Seconds
    outer_call: Seconds
    unit: Seconds
    run: Seconds

    @model_validator(mode="after")
    def _strictly_increasing(self) -> "TimeoutLadder":
        rungs = [max(self.trusted_call, self.untrusted_call), self.http_retry_budget,
                 self.outer_call, self.unit, self.run]
        if rungs != sorted(set(rungs)):
            raise ValueError(f"timeout ladder is not strictly increasing: {self.model_dump()}")
        return self

    @classmethod
    def derive(cls, trusted: ModelSpec, untrusted: ModelSpec) -> "TimeoutLadder":
        slowest = max(trusted.resolved_timeout, untrusted.resolved_timeout)
        http_retry_budget = max(MIN_RETRY_BUDGET_SECONDS, RETRY_BUDGET_PER_CALL * slowest)
        outer_call = http_retry_budget + OUTER_CALL_MARGIN_SECONDS
        unit = CALLS_PER_UNIT * outer_call
        return cls(
            trusted_call=trusted.resolved_timeout,
            untrusted_call=untrusted.resolved_timeout,
            http_retry_budget=http_retry_budget,
            outer_call=outer_call,
            unit=unit,
            run=max(MIN_RUN_BUDGET_SECONDS, UNITS_PER_RUN * unit),
        )


class ModelRuntime(BaseModel):
    """Every endpoint knob for one model, resolved from `Config` and never re-read from the env.

    Carrying them as one object is what lets a subprocess or Docker worker rebuild a model that
    behaves identically to the parent's.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    temperature: float = Field(0.0, ge=0.0)
    seed: int = Field(0, ge=0)
    attempt_timeout: Seconds
    http_timeout: Seconds
    http_retries: int = Field(ge=0)
    max_tokens: int = Field(gt=0)
    reasoning_effort: Reasoning
    inspect_cache: bool = True
    max_connections: int = Field(MODEL_POOL_CONNECTIONS, ge=1)


class Config(BaseModel):
    """A run's resolved configuration: the chosen models, what to run, and the derived bounds."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    domain: Domain
    dataset: str = ""
    gen_strategy: GenStrategy = GenStrategy.BLIND_T
    trusted: ModelSpec = ModelSpec()
    untrusted: ModelSpec = ModelSpec()
    metrics: MetricConfig = MetricConfig()
    timeouts: TimeoutLadder
    runs: int = Field(1, ge=1)
    seed: int = Field(0, ge=0)

    mock: bool = False
    limit: int = Field(ALL_TASKS, ge=0)
    stage: Stage = Stage.ALL
    exec_mode: ExecMode = ExecMode.SUBPROCESS
    docker_image: str = ""
    progress: bool = False
    tests_per_problem: int = Field(TESTS_PER_PROBLEM, ge=1)
    self_critique: bool = False
    property_prompt: str = "default"
    search_prompt: str = "default"
    inspect_cache: bool = True
    max_conn: int = Field(MEASURED_SAFE_CONCURRENCY, ge=1)
    call_retries: int = Field(ENGINE_CALL_RETRIES, ge=0)
    call_http_retries: int = Field(INSPECT_HTTP_RETRIES, ge=0)
    pbt_timeout: Seconds = PBT_HARNESS_TIMEOUT_SECONDS
    exec_workers: int = Field(PBT_EXEC_WORKERS, ge=1)
    max_search_space: int = Field(MAX_SEARCH_SPACE, ge=1)
    run_retries: int = Field(RUN_RETRIES, ge=0)

    @property
    def model_name(self) -> str:
        return "mock" if self.mock else self.trusted.name

    @property
    def elicit_model_name(self) -> str:
        return NO_MODEL if self.mock else self.untrusted.name

    @property
    def pool_path(self) -> str:
        return self.dataset

    @property
    def protocols(self) -> tuple[str, ...]:
        return self.metrics.protocols

    @property
    def audit_rate(self) -> float:
        return self.metrics.audit_rate

    @property
    def reasoning_effort(self) -> str:
        return self.trusted.reasoning.value

    @property
    def max_tokens(self) -> int:
        return self.trusted.max_tokens

    @property
    def u_reasoning_effort(self) -> str:
        return self.untrusted.reasoning.value

    @property
    def u_max_tokens(self) -> int:
        return self.untrusted.max_tokens

    @property
    def call_attempt_timeout(self) -> int:
        return self.timeouts.trusted_call

    @property
    def u_call_attempt_timeout(self) -> int:
        return self.timeouts.untrusted_call

    @property
    def call_http_timeout(self) -> int:
        return self.timeouts.http_retry_budget

    @property
    def call_timeout(self) -> int:
        return self.timeouts.outer_call

    @property
    def unit_timeout(self) -> int:
        return self.timeouts.unit

    @property
    def run_timeout(self) -> int:
        return self.timeouts.run

    @property
    def temperature(self) -> float:
        """Deterministic for a single run; varied across runs so repetitions are not identical."""
        return SINGLE_RUN_TEMPERATURE if self.runs == 1 else MULTI_RUN_TEMPERATURE

    def runtime(self, spec: ModelSpec, *, attempt_timeout: int, run_index: int) -> ModelRuntime:
        return ModelRuntime(
            name=spec.name,
            temperature=self.temperature,
            seed=self.seed + run_index,
            attempt_timeout=attempt_timeout,
            http_timeout=self.timeouts.http_retry_budget,
            http_retries=self.call_http_retries,
            max_tokens=spec.max_tokens,
            reasoning_effort=spec.reasoning,
            inspect_cache=self.inspect_cache,
        )

    def trusted_runtime(self, run_index: int) -> ModelRuntime:
        spec = self.trusted.model_copy(update={"name": self.model_name})
        return self.runtime(spec, attempt_timeout=self.timeouts.trusted_call, run_index=run_index)

    def untrusted_runtime(self, run_index: int) -> ModelRuntime:
        spec = self.untrusted.model_copy(update={"name": self.elicit_model_name})
        return self.runtime(spec, attempt_timeout=self.timeouts.untrusted_call, run_index=run_index)

    def to_json(self) -> dict[str, Any]:
        """A JSON-serializable manifest for run.json, with the aliases the report renderer reads."""
        return {
            **self.model_dump(mode="json"),
            "model": self.model_name,
            "pool": self.pool_path,
            "n_tasks": self.limit,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Config":
        return cls.model_validate(data)


class Settings(BaseSettings):
    """The command line and its environment fallbacks, declared once.

    Every field is one CLI flag (kebab-cased) and one environment variable of the same name in
    upper case. Validation lives on the fields, so a bad value fails before any model is called.
    """

    model_config = SettingsConfigDict(
        cli_parse_args=True,
        cli_kebab_case=True,
        cli_implicit_flags=True,
        cli_prog_name="run.py",
        env_prefix="",
        extra="ignore",
    )

    domain: Domain = Field(description="benchmark backend")
    dataset: str = Field("", description="candidate pool JSON (not needed for --domain mock)")
    run_id: str = Field("", description="reuse the same id to RESUME an interrupted run")

    t_model: str = Field("", description="trusted model, also the monitor")
    t_reasoning: Reasoning = Field(Reasoning.LOW, description="trusted reasoning effort")
    t_timeout: Seconds = Field(0, description="trusted seconds per call (0 = from reasoning)")

    u_model: str = Field("", description="untrusted model, used only by the u_* strategies")
    u_reasoning: Reasoning = Field(Reasoning.LOW, description="untrusted reasoning effort")
    u_timeout: Seconds = Field(0, description="untrusted seconds per call (0 = from reasoning)")

    protocols: str = Field("", description=f"comma-separated subset of {','.join(PROTOCOLS)}")
    gen_strategy: GenStrategy = Field(GenStrategy.BLIND_T, description="who authors the properties")
    attack_rate: str = Field("", description="per-step backdoor probability, or 'always' for p=1.0")
    audit_rate: float = Field(0.10, ge=0.0, le=1.0, description="human audit budget")

    runs: int = Field(1, ge=1, description="repetitions for mean, std and intervals")
    seed: int = Field(0, ge=0)
    limit: int = Field(0, ge=0, description="cap number of tasks (0 = all)")
    mock: bool = Field(False, description="offline mock model")
    stage: Stage = Stage.ALL
    exec_mode: ExecMode = ExecMode.SUBPROCESS
    docker_image: str = ""
    progress: bool = Field(True, description="live progress display")

    tests_per_problem: int = Field(TESTS_PER_PROBLEM, ge=1)
    self_critique: bool = False
    property_prompt: str = "default"
    search_prompt: str = "default"
    inspect_cache: bool = True
    max_conn: int = Field(MEASURED_SAFE_CONCURRENCY, ge=1)
    call_retries: int = Field(ENGINE_CALL_RETRIES, ge=0)
    call_http_retries: int = Field(INSPECT_HTTP_RETRIES, ge=0)
    pbt_timeout: Seconds = PBT_HARNESS_TIMEOUT_SECONDS
    exec_workers: int = Field(PBT_EXEC_WORKERS, ge=1)
    max_search_space: int = Field(MAX_SEARCH_SPACE, ge=1)
    run_retries: int = Field(RUN_RETRIES, ge=0)

    @field_validator("protocols")
    @classmethod
    def _known_protocols(cls, raw: str) -> str:
        unknown = [p for p in _split(raw) if p not in PROTOCOLS]
        if unknown:
            raise ValueError(f"unknown protocol(s) {unknown}; choose from {list(PROTOCOLS)}")
        return raw

    @field_validator("attack_rate")
    @classmethod
    def _rate_or_alias(cls, raw: str) -> str:
        if raw == "" or raw.strip().lower() in ALWAYS_ATTACK_ALIASES:
            return raw
        if not 0.0 <= float(raw) <= 1.0:
            raise ValueError(f"attack-rate must be in [0,1] or 'always' (got {raw!r})")
        return raw

    @model_validator(mode="after")
    def _runnable(self) -> "Settings":
        if self.stage is not Stage.SCORE and not (self.mock or self.t_model):
            raise ValueError("provide --t-model (e.g. azureai/DeepSeek-V3.2) or --mock")
        if self.stage is Stage.MONITOR and not self.run_id:
            raise ValueError("--stage monitor requires --run-id (the id of the prior --stage score run)")
        if self.domain is not Domain.MOCK and self.stage is not Stage.MONITOR and not self.dataset:
            raise ValueError(f"--domain {self.domain.value} requires --dataset")
        if self.gen_strategy.uses_untrusted and not (self.mock or self.u_model):
            raise ValueError(f"--gen-strategy {self.gen_strategy.value} requires --u-model")
        return self

    @property
    def attack_probability(self) -> float:
        if self.attack_rate == "":
            return MetricConfig.model_fields["attack_probability"].default
        if self.attack_rate.strip().lower() in ALWAYS_ATTACK_ALIASES:
            return 1.0
        return float(self.attack_rate)

    def to_config(self, run_id: str) -> Config:
        trusted = ModelSpec(name=self.t_model, reasoning=self.t_reasoning, timeout=self.t_timeout)
        untrusted = ModelSpec(
            name=self.u_model or self.t_model,
            reasoning=self.u_reasoning,
            timeout=self.u_timeout,
        )
        return Config(
            run_id=run_id,
            domain=self.domain,
            dataset=self.dataset,
            gen_strategy=self.gen_strategy,
            trusted=trusted,
            untrusted=untrusted,
            metrics=MetricConfig(
                audit_rate=self.audit_rate,
                attack_probability=self.attack_probability,
                protocols=tuple(_split(self.protocols)) or PROTOCOLS,
                seed=self.seed,
            ),
            timeouts=TimeoutLadder.derive(trusted, untrusted),
            runs=self.runs,
            seed=self.seed,
            mock=self.mock,
            limit=self.limit,
            stage=self.stage,
            exec_mode=self.exec_mode,
            docker_image=self.docker_image,
            progress=self.progress and sys.stdout.isatty(),
            tests_per_problem=self.tests_per_problem,
            self_critique=self.self_critique,
            property_prompt=self.property_prompt,
            search_prompt=self.search_prompt,
            inspect_cache=self.inspect_cache,
            max_conn=self.max_conn,
            call_retries=self.call_retries,
            call_http_retries=self.call_http_retries,
            pbt_timeout=self.pbt_timeout,
            exec_workers=self.exec_workers,
            max_search_space=self.max_search_space,
            run_retries=self.run_retries,
        )


def _split(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]
