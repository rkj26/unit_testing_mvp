import pytest
from control_arena import EvalMode
from control_arena.settings._setting import Setting
from apps_setting import AppsPBTSetting, apps_scorer


def test_apps_pbt_setting_instance():
    setting = AppsPBTSetting(dataset_path="dataset.json")
    assert setting.get_name() == "apps_pbt"
    assert isinstance(setting, Setting)


def test_apps_pbt_setting_dataset_honest():
    setting = AppsPBTSetting(dataset_path="dataset.json")
    dataset = setting.get_dataset(EvalMode.HONEST)
    assert len(dataset) >= 2
    sample = dataset[0]
    assert sample.id == "apps_001"
    assert sample.metadata["eval_mode"] == EvalMode.HONEST


def test_apps_pbt_setting_dataset_attack():
    setting = AppsPBTSetting(dataset_path="dataset.json")
    dataset = setting.get_dataset(EvalMode.ATTACK)
    assert len(dataset) >= 2
    sample = dataset[0]
    assert sample.metadata["eval_mode"] == EvalMode.ATTACK
    assert sample.metadata["side_task_name"] == "insert_backdoor"


def test_apps_pbt_setting_scorers():
    setting = AppsPBTSetting(dataset_path="dataset.json")
    scorers = setting.get_scorers()
    assert len(scorers) == 1
