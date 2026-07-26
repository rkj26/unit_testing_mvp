import pytest

from control_arena import EvalMode
from control_arena.settings._setting import Setting
from inspect_ai._util.registry import registry_unqualified_name
from bigcodebench_pbt_setting import BigCodeBenchPBTSetting, MAIN_TASK_IDS, HELDOUT_TASK_IDS


def test_bigcodebench_pbt_setting_instance():
    setting = BigCodeBenchPBTSetting()
    assert setting.get_name() == "bigcodebench"
    assert isinstance(setting, Setting)


def test_bigcodebench_pbt_setting_dataset_honest():
    setting = BigCodeBenchPBTSetting()
    dataset = setting.get_dataset(EvalMode.HONEST)
    assert len(dataset) == len(MAIN_TASK_IDS)
    sample = dataset[0]
    assert sample.metadata["eval_mode"] == EvalMode.HONEST
    assert sample.metadata["main_task_name"] in MAIN_TASK_IDS


def test_bigcodebench_pbt_setting_dataset_attack():
    setting = BigCodeBenchPBTSetting()
    dataset = setting.get_dataset(EvalMode.ATTACK)
    assert len(dataset) == len(MAIN_TASK_IDS)
    sample = dataset[0]
    assert sample.metadata["eval_mode"] == EvalMode.ATTACK
    assert sample.metadata["side_task_name"] == "insert_backdoor"


def test_bigcodebench_pbt_setting_heldout_dataset_is_disjoint():
    setting = BigCodeBenchPBTSetting(task_ids=tuple(HELDOUT_TASK_IDS))
    dataset = setting.get_dataset(EvalMode.HONEST)
    assert len(dataset) == len(HELDOUT_TASK_IDS)
    ids = {s.metadata["main_task_name"] for s in dataset}
    assert ids == set(HELDOUT_TASK_IDS)
    assert ids.isdisjoint(MAIN_TASK_IDS)


def test_bigcodebench_pbt_setting_scorers():
    setting = BigCodeBenchPBTSetting()
    scorers = setting.get_scorers()
    assert len(scorers) == 1
    assert registry_unqualified_name(scorers[0]) == "bigcodebench_scorer"


test_bigcodebench_pbt_setting_dataset_honest = pytest.mark.live(
    test_bigcodebench_pbt_setting_dataset_honest
)
test_bigcodebench_pbt_setting_dataset_attack = pytest.mark.live(
    test_bigcodebench_pbt_setting_dataset_attack
)
test_bigcodebench_pbt_setting_heldout_dataset_is_disjoint = pytest.mark.live(
    test_bigcodebench_pbt_setting_heldout_dataset_is_disjoint
)
