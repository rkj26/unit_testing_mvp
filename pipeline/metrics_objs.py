"""Metric objects — decoupled consumers of a run's artifacts.

A `Metric` takes a run's rows plus the derived task-level maps and returns a fragment of the
per-run metrics dict; the engine merges every fragment into one dict, which `aggregate_runs` then
combines across runs. Adding a measurement means appending a `Metric` to `METRICS`, with no change
to the engine or the steps.

Public surface: `Metric`, the metric classes, and `METRICS`.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable

from . import metrics as metrics_mod
from .config import Config
from .outcome import Blame


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
        suite_blame: Mapping[str, Blame | None] | None = None,
    ) -> dict[str, Any]:
        """Return this metric's contribution to the run's metrics dict (keys merged by the engine)."""
        ...


class DeploymentGame:
    """The canonical per-run bundle: usefulness, per-protocol safety / evasion / FPR / AUC,
    paired deltas vs TM, PBT suite health, and the metric config they were produced under.
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
        suite_blame: Mapping[str, Blame | None] | None = None,
    ) -> dict[str, Any]:
        return metrics_mod.compute_run_metrics(
            rows,
            selected_policy,
            config=config.metrics.model_copy(update={"seed": seed}),
            suite_validity=suite_validity,
            suite_soundness=suite_soundness,
            suite_blame=suite_blame,
        )


METRICS: list[Metric] = [DeploymentGame()]
