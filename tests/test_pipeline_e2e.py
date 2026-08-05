"""End-to-end pipeline integration tests across all generation strategies with mock calls."""

from __future__ import annotations

import pytest

from pipeline import engine
from pipeline.backends import get_backend
from pipeline.config import GenStrategy, Settings
from pipeline.steps import get_pipeline


@pytest.mark.parametrize(
    "strategy",
    [
        GenStrategy.BLIND_T,
        GenStrategy.U_WRITES,
        GenStrategy.U_PLANS_T_WRITES,
        GenStrategy.U_PLANS_U_WRITES,
    ],
)
def test_pipeline_e2e_all_strategies(strategy: GenStrategy, tmp_path):
    run_id = f"test_e2e_{strategy.value}"
    args = [
        "--domain",
        "mock",
        "--mock",
        "--limit",
        "2",
        "--runs",
        "1",
        "--run-id",
        run_id,
        "--gen-strategy",
        strategy.value,
        "--exec-mode",
        "inprocess",
        "--no-progress",
    ]

    settings = Settings(_cli_parse_args=args, _env_file=None)
    config = settings.to_config(run_id)
    backend = get_backend(config.domain.value)

    run_dir, agg = engine.run(config, backend, {}, get_pipeline())

    assert run_dir.exists()
    assert agg is not None
    assert agg["n_runs"] == 1
