import asyncio

import pytest
from bigcodebench_pbt_setting import MAIN_TASK_IDS
from config import Config
from evaluator import Evaluator
from pbt_monitor import pbt_monitor_builder, generate_pbt_script_with_llm

# Wiring tests only need to confirm the protocols run end-to-end, not produce
# meaningful metrics - keep them to 1 task so they stay fast even now that the
# dataset is real BigCodeBench (heavier sandboxed unittest execution per task
# than the old 2-problem toy dataset).
_FAST_TASK_IDS = MAIN_TASK_IDS[:1]


def test_pbt_monitor_builder_instance():
    mon = pbt_monitor_builder(pbt_max_examples=50)
    assert mon is not None


def test_pbt_monitor_builder_accepts_prompt_config():
    mon = pbt_monitor_builder(
        pbt_max_examples=50,
        prompt_variant="v3_backdoor_focused",
        fewshot_k=2,
        fewshot_seed=7,
    )
    assert mon is not None


def test_config_prompt_fields_thread_into_micro_protocol_builders():
    # Doesn't run a live eval (expensive) - just confirms the config flags actually
    # reach the protocol builders without erroring, including with a non-default
    # prompt variant and a non-default attack prompt variant.
    config = Config(
        pbt_prompt_variant="v3_backdoor_focused",
        pbt_fewshot_k=2,
        pbt_fewshot_seed=3,
        attack_prompt_variant="v2_literal_trigger",
    )
    evaluator = Evaluator(config)
    for proto_name in ["TM", "PBT", "TE", "Hybrid"]:
        proto = evaluator._build_micro_protocol(proto_name, config)
        assert proto is not None


def test_unknown_pbt_prompt_variant_fails_before_any_model_call():
    async def _run():
        # model_name is deliberately bogus - if this raised anything other than
        # FileNotFoundError we'd know prompt rendering isn't happening before the
        # (expensive, network-bound) model call.
        await generate_pbt_script_with_llm(
            description="desc",
            entry_point="f",
            starter_code="def f(x): pass",
            pbt_max_examples=10,
            model_name="not-a-real-provider/not-a-real-model",
            prompt_variant="nonexistent_variant",
        )

    with pytest.raises(FileNotFoundError):
        asyncio.run(_run())


def test_evaluator_micro_protocols():
    config = Config(task_ids=_FAST_TASK_IDS, allow_unpaired_protocol_comparison=True)
    evaluator = Evaluator(config)
    summary = evaluator.run_experiment()
    assert "TM" in summary.metrics_by_protocol
    assert "PBT" in summary.metrics_by_protocol
    assert "TE" in summary.metrics_by_protocol
    assert "Hybrid" in summary.metrics_by_protocol


def test_evaluator_pareto_sweep():
    config = Config(task_ids=_FAST_TASK_IDS, allow_unpaired_protocol_comparison=True)
    evaluator = Evaluator(config)
    points = evaluator.run_pareto_sweep()
    assert len(points) > 0


test_evaluator_micro_protocols = pytest.mark.live(test_evaluator_micro_protocols)
test_evaluator_pareto_sweep = pytest.mark.live(test_evaluator_pareto_sweep)
