"""Optimize the blind-PBT property prompt with GEPA, and log everything needed to trust the result.

    .venv/bin/python -m gepa_opt.run_gepa --mock --run-id smoke
    .venv/bin/python -m gepa_opt.run_gepa \
        --dataset apps_pool_hard10.json \
        --writer-model openai-api/azureai/gemini-3.6-flash --writer-reasoning low \
        --reflection-model openai/gpt-5 --max-metric-calls 150 --run-id gepa-hard10

The WRITER (the model whose prompt is optimized) goes through the repo's inspect wrapper, so it can
be any provider the pipeline already uses. The REFLECTION model (which proposes new prompts) goes
through GEPA's own LM via litellm and needs its own credentials — keep it strong, and treat it as
blue-team elicitation to be validated on held-out tasks, not as part of a deployed protocol.

Artifacts written under runs/gepa-<run-id>/:
  rollouts.jsonl        every per-task rollout: caught, sound, verdict, score, blame
  candidates.jsonl      every GEPA candidate prompt and its aggregate val score
  best_instructions.txt the selected property instructions
  holdout_metrics.json  catch/soundness on the held-out pool (infra abstentions excluded)
  summary.json          headline numbers and paths
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

import gepa
from dotenv import load_dotenv

from pipeline.config import (
    MAX_TOKENS_BY_EFFORT,
    MEASURED_CALL_SECONDS_BY_EFFORT,
    MODEL_POOL_CONNECTIONS,
    Reasoning,
)
from pipeline.config import ModelRuntime
from pipeline.model import TrustedModel, resolve

from . import data
from .adapter import COMPONENT, PropertyGenAdapter
from .throttle import (
    DEFAULT_REFLECTION_RPM,
    DEFAULT_WRITER_RPM,
    LiteLLMReflection,
    RateLimitedWriter,
)

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
SEED_FILE = "property_gen_seed.txt"
MOCK_MODEL = "mock"
WRITER_HTTP_RETRIES = 8


def build_writer(name: str, reasoning: Reasoning) -> TrustedModel:
    runtime = ModelRuntime(
        name=name,
        temperature=0.0,
        seed=0,
        attempt_timeout=MEASURED_CALL_SECONDS_BY_EFFORT[reasoning],
        http_timeout=MEASURED_CALL_SECONDS_BY_EFFORT[reasoning] * 2,
        http_retries=WRITER_HTTP_RETRIES,
        max_tokens=MAX_TOKENS_BY_EFFORT[reasoning],
        reasoning_effort=reasoning,
        inspect_cache=True,
        max_connections=MODEL_POOL_CONNECTIONS,
    )
    return resolve(runtime)


def _mock_reflection(prompt: str) -> str:
    """Offline stand-in for the reflection LM so --mock exercises the loop without a provider."""
    return (SEED_FILE and (PROMPTS / SEED_FILE).read_text(encoding="utf-8")).strip()


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in records if not r["infra_unknown"]]
    n = len(scored)
    catch_rate = statistics.mean(r["caught"] for r in scored) if n else 0.0
    sound_rate = statistics.mean(r["sound"] for r in scored) if n else 0.0
    mean_score = statistics.mean(r["score"] for r in scored) if n else 0.0
    return {
        "n_scored": n,
        "n_infra_excluded": len(records) - n,
        "catch_rate": catch_rate,
        "sound_rate": sound_rate,
        "mean_score": mean_score,
    }


def _save_candidates(result: Any, path: Path) -> None:
    scores = list(getattr(result, "val_aggregate_scores", []) or [])
    with path.open("w", encoding="utf-8") as out:
        for i, candidate in enumerate(result.candidates):
            row = {
                "index": i,
                "val_score": scores[i] if i < len(scores) else None,
                "is_best": i == result.best_idx,
                "instructions": candidate.get(COMPONENT, ""),
            }
            out.write(json.dumps(row) + "\n")


def main() -> None:
    load_dotenv()
    args = _parse_args()

    run_dir = Path("runs") / f"gepa-{args.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    raw_writer = build_writer(
        MOCK_MODEL if args.mock else args.writer_model, Reasoning(args.writer_reasoning)
    )
    writer = raw_writer if args.mock else RateLimitedWriter(raw_writer, args.rpm)
    reflection = (
        _mock_reflection
        if args.mock
        else LiteLLMReflection(args.reflection_model, args.reflection_rpm)
    )

    problems = data.load_problems(args.dataset, limit=args.limit)
    spaces = data.freeze_search_spaces(
        problems, writer, str(run_dir / "search_spaces.json")
    )
    holdout_problems, holdout_spaces = None, None
    if args.holdout_dataset:
        holdout_problems = data.load_problems(args.holdout_dataset)
        holdout_spaces = data.freeze_search_spaces(
            holdout_problems, writer, str(run_dir / "search_spaces_holdout.json")
        )
    split = data.make_split(problems, spaces, holdout_problems, holdout_spaces)
    print(
        f"  split: {len(split.train)} train / {len(split.val)} val / {len(split.holdout)} holdout"
    )

    seed_candidate = {COMPONENT: (PROMPTS / SEED_FILE).read_text(encoding="utf-8").strip()}
    adapter = PropertyGenAdapter(
        writer, args.tests_per_problem, str(run_dir / "rollouts.jsonl"), phase="opt"
    )

    result = gepa.optimize(
        seed_candidate=seed_candidate,
        trainset=split.train,
        valset=split.val,
        adapter=adapter,
        reflection_lm=reflection,
        max_metric_calls=args.max_metric_calls,
        run_dir=str(run_dir),
        seed=0,
        display_progress_bar=True,
    )

    (run_dir / "best_instructions.txt").write_text(
        result.best_candidate[COMPONENT], encoding="utf-8"
    )
    _save_candidates(result, run_dir / "candidates.jsonl")

    holdout_adapter = PropertyGenAdapter(
        writer, args.tests_per_problem, str(run_dir / "rollouts.jsonl"), phase="holdout"
    )
    holdout_batch = holdout_adapter.evaluate(split.holdout, result.best_candidate)
    holdout_records = [
        json.loads(line)
        for line in (run_dir / "rollouts.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line)["phase"] == "holdout"
    ]
    holdout_metrics = _aggregate(holdout_records)
    (run_dir / "holdout_metrics.json").write_text(
        json.dumps(holdout_metrics, indent=2), encoding="utf-8"
    )

    summary = {
        "run_id": args.run_id,
        "dataset": args.dataset,
        "holdout_dataset": args.holdout_dataset,
        "writer_model": MOCK_MODEL if args.mock else args.writer_model,
        "reflection_model": "mock" if args.mock else args.reflection_model,
        "n_candidates": result.num_candidates,
        "best_val_score": max(getattr(result, "val_aggregate_scores", [0.0]) or [0.0]),
        "total_metric_calls": result.total_metric_calls,
        "holdout": holdout_metrics,
        "artifacts": {
            "best_instructions": str(run_dir / "best_instructions.txt"),
            "candidates": str(run_dir / "candidates.jsonl"),
            "rollouts": str(run_dir / "rollouts.jsonl"),
            "holdout_metrics": str(run_dir / "holdout_metrics.json"),
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"  best val score: {summary['best_val_score']:.3f}")
    print(f"  holdout: catch_rate={holdout_metrics['catch_rate']:.3f} "
          f"sound_rate={holdout_metrics['sound_rate']:.3f} (n={holdout_metrics['n_scored']})")
    print(f"  artifacts under {run_dir}/")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="GEPA optimization of the blind-PBT property prompt.")
    p.add_argument("--dataset", default="apps_pool_hard10.json")
    p.add_argument("--holdout-dataset", default="")
    p.add_argument("--writer-model", default="")
    p.add_argument(
        "--writer-reasoning", default="low", choices=[r.value for r in Reasoning]
    )
    p.add_argument("--reflection-model", default="openai/gpt-5")
    p.add_argument(
        "--rpm",
        type=float,
        default=DEFAULT_WRITER_RPM,
        help="writer requests/min ceiling; keep under the provider's free-tier limit (5 for Gemini)",
    )
    p.add_argument(
        "--reflection-rpm",
        type=float,
        default=DEFAULT_REFLECTION_RPM,
        help="reflection-model requests/min ceiling; raise once billing lifts the free-tier limit",
    )
    p.add_argument("--max-metric-calls", type=int, default=150)
    p.add_argument("--tests-per-problem", type=int, default=5)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--run-id", default="gepa")
    p.add_argument("--mock", action="store_true")
    args = p.parse_args()
    if not args.mock and not args.writer_model:
        p.error("--writer-model is required unless --mock is set")
    return args


if __name__ == "__main__":
    main()