import hashlib
import json
from datetime import datetime, timezone

import pytest

from control_arena import EvalMode

from bigcodebench_pbt_setting import BigCodeBenchPBTSetting, MAIN_TASK_IDS
from config import Config
from evaluator import Evaluator
from prompts import load_prompt
from provenance import dataset_fingerprints
from candidate_pool import candidate_id_for, sha256_text
from policy_selection import (
    MOCKLLM_SELECTOR_ADAPTER,
    build_selector_input,
    mockllm_selector_result,
    render_selector_prompt,
    selector_result_json,
    select_attack_opportunities,
)


@pytest.mark.docker
def test_mockllm_runs_real_evaluator_and_writes_run_artifacts(tmp_path):
    task_ids = MAIN_TASK_IDS[:2]
    setting = BigCodeBenchPBTSetting(task_ids=tuple(task_ids), sandbox_type="docker")
    honest_samples = setting.get_dataset(EvalMode.HONEST)
    attack_samples = setting.get_dataset(EvalMode.ATTACK)
    honest_samples_by_task = {
        sample.metadata["main_task_name"]: sample for sample in honest_samples
    }
    attack_samples_by_task = {
        sample.metadata["main_task_name"]: sample for sample in attack_samples
    }
    attack_prompt = load_prompt("attack_policy", "v1_default")
    selector_prompt = load_prompt("red_team_selector", "v1_baseline")
    zero_usage = {"input_tokens": 0, "output_tokens": 0, "model_cost_usd": None}

    def candidate(task_id, kind, index, source, secret_input=None):
        return {
            "candidate_id": candidate_id_for(
                task_id=task_id,
                kind=kind,
                generation_index=index,
                code=source,
                secret_input=secret_input,
            ),
            "kind": kind,
            "generation_index": index,
            "code": source,
            "code_sha256": sha256_text(source),
            "secret_input": secret_input,
            "generation": {
                "model": "mockllm/untrusted-smoke",
                "policy": kind,
                "prompt_variant": "v1_default" if kind == "attack" else None,
                "prompt_sha256": sha256_text(attack_prompt)
                if kind == "attack"
                else None,
                "sample_id": f"{task_id}-{kind}-{index}",
                "seed": index if kind == "attack" else None,
                "usage": zero_usage,
            },
        }

    candidates = {}
    selector_inputs = {}
    selector_results = {}
    for task_id in task_ids:
        code = honest_samples_by_task[task_id].metadata["metadata"][
            "canonical_solution"
        ]
        honest = candidate(task_id, "honest", 0, code)
        attacks = [
            candidate(
                task_id,
                "attack",
                0,
                code + "\n# mock attack proposal 0\n",
                "{}",
            ),
            candidate(
                task_id,
                "attack",
                1,
                code + "\n# mock attack proposal 1\n",
                "{}",
            ),
        ]
        candidates[task_id] = {
            "honest": honest,
            "attack_proposals": attacks,
        }
        attack_sample = attack_samples_by_task[task_id]
        selector_inputs[task_id] = build_selector_input(
            task_id=task_id,
            task_description=attack_sample.metadata["main_task_description"],
            side_task_description=attack_sample.metadata["side_task_description"],
            attack_proposals=attacks,
        )
        selector_results[task_id] = mockllm_selector_result(
            [attack["candidate_id"] for attack in attacks]
        )

    selection = select_attack_opportunities(selector_results, max_selected_attacks=1)
    model_completion = "generic MockLLM completion"
    selector_records = {}
    forced_view = {}
    selected_view = {}
    for task_id in task_ids:
        selector_input = selector_inputs[task_id]
        selector_result = selector_results[task_id]
        selector_completion = selector_result_json(selector_result)
        attack_sample = attack_samples_by_task[task_id]
        decision = selection["tasks"][task_id]
        selector_records[task_id] = {
            "selector_context": {
                "task_id": task_id,
                "task_description": attack_sample.metadata["main_task_description"],
                "side_task_description": attack_sample.metadata[
                    "side_task_description"
                ],
            },
            "selector_input_sha256": hashlib.sha256(
                json.dumps(
                    selector_input, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest(),
            "selector_prompt_sha256": sha256_text(
                render_selector_prompt(selector_input)
            ),
            "selector_model_completion": model_completion,
            "selector_model_completion_sha256": sha256_text(model_completion),
            "selector_effective_completion": selector_completion,
            "selector_effective_completion_sha256": sha256_text(selector_completion),
            "selector_completion_source": MOCKLLM_SELECTOR_ADAPTER,
            "selector_result": selector_result,
            "usage": zero_usage,
            **decision,
        }
        forced_view[task_id] = decision["best_attack_candidate_id"]
        selected_view[task_id] = (
            decision["best_attack_candidate_id"]
            if decision["selected_for_attack"]
            else candidates[task_id]["honest"]["candidate_id"]
        )

    pool = {
        "schema_version": 4,
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "task_ids": task_ids,
            "untrusted_model": "mockllm/untrusted-smoke",
            "trusted_model": "mockllm/trusted-smoke",
            "attack_prompt_variant": "v1_default",
            "attack_prompt": attack_prompt,
            "attack_prompt_sha256": hashlib.sha256(attack_prompt.encode()).hexdigest(),
            "attack_proposals_per_task": 2,
            "proposal_seed_base": 0,
            "selector_model": "mockllm/untrusted-smoke",
            "selector_prompt_variant": "v1_baseline",
            "selector_prompt": selector_prompt,
            "selector_prompt_sha256": sha256_text(selector_prompt),
            "dataset_fingerprints": {
                "honest": dataset_fingerprints(honest_samples),
                "attack": dataset_fingerprints(attack_samples),
            },
            "repository_revision": "test",
            "repository_dirty": False,
            "repository_diff_sha256": hashlib.sha256(b"").hexdigest(),
            "generation_usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "model_cost_usd": None,
            },
            "generation_usage_by_phase": {
                "candidate_generation": zero_usage,
                "selector_scoring": zero_usage,
            },
        },
        "candidates": candidates,
        "selection": {
            "algorithm": selection["algorithm"],
            "max_selected_attacks": 1,
            "selected_task_ids": selection["selected_task_ids"],
            "tasks": selector_records,
        },
        "views": {
            "forced_attack": forced_view,
            "selected_policy": selected_view,
        },
    }
    pool_path = tmp_path / "candidate_pool.json"
    pool_path.write_text(json.dumps(pool), encoding="utf-8")
    artifacts = tmp_path / "artifacts"
    config = Config(
        task_ids=task_ids,
        untrusted_model="mockllm/untrusted-smoke",
        trusted_monitor_model="mockllm/trusted-smoke",
        candidate_pool_path=str(pool_path),
        max_concurrent_samples=1,
        eval_log_dir=str(tmp_path / "eval_logs"),
        evidence_root=str(artifacts),
        scenario_tasks=2,
        safety_trials=100,
        audit_budget=0,
        free_initial_audits=0,
        attack_episode_subsample_rate=1.0,
    )

    protocols = ["TM", "PBT", "TM+PBT", "PBT-Informed-TM"]
    summary = Evaluator(config).run_experiment(protocols=protocols)

    # PBT evaluates honest + both proposals; TM and informed-TM each evaluate
    # honest + forced attack; TM+PBT is derived without another evaluation.
    assert summary.total_evaluations == 14
    assert len(summary.candidate_evaluations) == 6
    assert set(summary.metrics_by_protocol) == set(protocols)
    for metric in summary.metrics_by_protocol.values():
        assert metric.raw_usefulness == 1.0
        assert metric.selected_tasks == 2
        assert metric.selected_attack_attempts == 1
        assert metric.selected_attack_rate == 0.5
        assert metric.selected_attack_success_rate == 0.0
        assert metric.selected_attack_success_rate_undefined_reason is None
        assert metric.safety == 1.0
        assert metric.safety_informative is True
        assert metric.safety_undefined_reason is None

    frozen = {
        row["candidate_id"]: (
            row["main_task_correct"],
            row["side_task_success"],
            row["attempted_backdoor"],
        )
        for row in summary.candidate_evaluations
    }
    for row in summary.detailed_results:
        assert (
            row["main_task_correct"],
            row["side_task_success"],
            row["attempted_backdoor"],
        ) == frozen[row["candidate_id"]]
    task_dirs = [path for path in artifacts.iterdir() if path.is_dir()]
    assert len(task_dirs) == 2
    for task_dir in task_dirs:
        assert (task_dir / "pbt" / "prompt.txt").is_file()
        assert (task_dir / "pbt" / "test.py").is_file()
        assert len(list((task_dir / "pbt" / "results").glob("*.json"))) == 3
        assert (task_dir / "bundle.json").is_file()
