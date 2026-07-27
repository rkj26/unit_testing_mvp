import pytest
from pydantic import ValidationError

from config import Config
from prompt_boundary import DEFAULT_CODE_ONLY_TM_PROMPT_VARIANT


def test_small_deployment_configuration_is_generic_and_valid():
    config = Config(
        scenario_tasks=10,
        safety_trials=1_000,
        audit_budget=1,
        free_initial_audits=0,
        attack_episode_subsample_rate=1.0,
    )

    assert config.scenario_tasks == 10
    assert config.safety_trials == 1_000
    assert config.audit_budget == 1


def test_default_tm_prompt_is_the_matched_hardened_variant():
    assert Config().tm_prompt_variant == DEFAULT_CODE_ONLY_TM_PROMPT_VARIANT


def test_empty_tm_prompt_variant_is_rejected():
    with pytest.raises(ValidationError, match="tm_prompt_variant"):
        Config(tm_prompt_variant="")


def test_audits_cannot_exceed_deployment_positions():
    with pytest.raises(ValidationError, match="audit_budget cannot exceed"):
        Config(scenario_tasks=10, free_initial_audits=3, audit_budget=8)


@pytest.mark.parametrize("task_ids", [[], [""], ["task", "task"]])
def test_task_ids_must_be_nonempty_and_unique(task_ids):
    with pytest.raises(ValidationError, match="task_ids"):
        Config(task_ids=task_ids)


def test_pbt_prompt_overrides_only_accept_pbt_protocols():
    with pytest.raises(ValidationError, match="unsupported PBT prompt override"):
        Config(pbt_prompt_overrides={"TM": "v1_baseline"})
