"""End-to-end pipeline integration tests across all generation strategies with mock calls."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import engine
from pipeline.artifacts import ArtifactKind, ArtifactStore
from pipeline.backends import get_backend
from pipeline.config import GenStrategy
from pipeline.steps import get_pipeline

RUN_INDEX = 0


@pytest.mark.parametrize(
    "strategy",
    [
        GenStrategy.BLIND_T,
        GenStrategy.U_WRITES,
        GenStrategy.U_PLANS_T_WRITES,
        GenStrategy.U_PLANS_U_WRITES,
    ],
)
def test_pipeline_e2e_all_strategies(strategy: GenStrategy, settings_from_cli):
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

    settings = settings_from_cli(args)
    config = settings.to_config(run_id)
    backend = get_backend(config.domain.value)

    checkpoints_the_engine_would_resume_from = ArtifactStore(Path("runs") / run_id)
    assert not checkpoints_the_engine_would_resume_from.has(ArtifactKind.PROBLEMS)
    assert not checkpoints_the_engine_would_resume_from.has(ArtifactKind.SCORES)
    assert not checkpoints_the_engine_would_resume_from.has(
        ArtifactKind.RUN_METRICS, run=RUN_INDEX
    )

    run_dir, agg = engine.run(config, backend, {}, get_pipeline())

    assert run_dir.exists()
    assert agg is not None
    assert agg["n_runs"] == 1

    store = ArtifactStore(run_dir)
    problems = store.load(ArtifactKind.PROBLEMS)
    assert len(problems) == 2

    for problem in problems:
        suite = store.load(ArtifactKind.SUITE, run=RUN_INDEX, task_id=problem.task_id)
        assert suite is not None, f"generate wrote no suite for {problem.task_id}"
        assert suite["gen_strategy"] == strategy.value
        assert set(suite["results"]) == {c.candidate_id for c in problem.candidates}

    rows = store.load(ArtifactKind.ROWS, run=RUN_INDEX)
    expected_candidates = {
        (p.task_id, c.candidate_id) for p in problems for c in p.candidates
    }
    assert {(r["task_id"], r["candidate_id"]) for r in rows} == expected_candidates
    for row in rows:
        assert row["evidence"]["tm"]["score"] is not None
        assert row["evidence"]["pbt_informed_tm"]["score"] is not None
