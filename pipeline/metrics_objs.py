"""Metric objects — decoupled consumers of a run's artifacts.

A `Metric` takes a run's rows + the derived task-level maps and returns a fragment of the per-run
metrics dict; the engine merges every metric's fragment into one dict (then `metrics.aggregate_runs`
combines those across runs). Adding a measurement = append a `Metric` to `METRICS`, with no change to
the engine or steps — this is the "artifacts flow into different metric objects → results" split.

The default `METRICS` is a single `DeploymentGame` bundle that delegates to the proven
`metrics.compute_run_metrics`, so the output shape is byte-identical to the pre-rewrite pipeline. It can
be decomposed into finer metric objects later without touching anything else.

Public surface (top): `Metric`, the metric classes, and `METRICS`.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable

from . import metrics as metrics_mod
from .config import Config


@runtime_checkable
class Metric(Protocol):
    """A named measurement over a run's artifacts, returning a fragment of the per-run metrics dict."""

    name: str

    def compute(
        self,
        rows: list[Mapping[str, Any]],
        selected_policy: Mapping[str, str],
        suite_validity: Mapping[str, bool],
        suite_soundness: Mapping[str, bool] | None,
        *,
        config: Config,
        seed: int,
        suite_harness_failed: Mapping[str, bool] | None = None,
    ) -> dict[str, Any]:
        """Return this metric's contribution to the run's metrics dict (keys merged by the engine)."""
        ...


class DeploymentGame:
    """The canonical per-run metrics bundle: usefulness, per-protocol safety@audit / evasion / FPR,
    paired deltas vs TM, PBT health, and the deployment-game config.

    Delegates to `metrics.compute_run_metrics` so the produced dict exactly matches the pre-rewrite
    output that `report` and `aggregate_runs` consume.
    """

    name = "deployment_game"

    def compute(
        self,
        rows: list[Mapping[str, Any]],
        selected_policy: Mapping[str, str],
        suite_validity: Mapping[str, bool],
        suite_soundness: Mapping[str, bool] | None,
        *,
        config: Config,
        seed: int,
        suite_harness_failed: Mapping[str, bool] | None = None,
    ) -> dict[str, Any]:
        """Compute the full per-run metrics dict via the deployment safety game at `config.audit_rate`."""
        return metrics_mod.compute_run_metrics(
            rows, selected_policy, seed=seed, suite_validity=suite_validity,
            suite_soundness=suite_soundness, audit_rate=config.audit_rate,
            suite_harness_failed=suite_harness_failed,
            attack_probability=config.attack_probability,
            attack_rates=config.attack_rates)


# The default metric set. Append more `Metric` objects here to enrich per-run metrics.json.
METRICS: list[Metric] = [DeploymentGame()]
