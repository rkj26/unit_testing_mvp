"""ControlArena BigCodeBench setting, curated down to a subset of tasks that are
solvable with only the Python standard library (no pandas/numpy/tensorflow/etc.),
so the sandbox can stay a lightweight python:3.11-slim image instead of the
official ~multi-GB bigcodebench/bigcodebench-evaluate image, and so the PBT
monitor's Hypothesis-based property tests have clean, primitive-typed arguments
to generate against.

Curation criteria (see the research that picked these): stdlib-only `libs`,
deterministic given the same input (no unseeded randomness), no filesystem/
network/subprocess dependence, and a clean single-purpose docstring.
"""

from pathlib import Path

from control_arena.settings._sandbox_utils import get_compose_sandbox_config
from control_arena.settings.bigcodebench.bigcodebench_setting import (
    BigCodeBenchSetting,
)
from control_arena.settings.bigcodebench.task.dataset import get_dataset

MAIN_TASK_IDS = [
    "BigCodeBench/4",
    "BigCodeBench/97",
    "BigCodeBench/172",
    "BigCodeBench/178",
    "BigCodeBench/254",
    "BigCodeBench/270",
    "BigCodeBench/297",
    "BigCodeBench/358",
    "BigCodeBench/466",
    "BigCodeBench/667",
    "BigCodeBench/1",
    "BigCodeBench/2",
    "BigCodeBench/5",
    "BigCodeBench/8",
    "BigCodeBench/22",
    "BigCodeBench/27",
    "BigCodeBench/256",
    "BigCodeBench/258",
    "BigCodeBench/268",
    "BigCodeBench/271",
    "BigCodeBench/277",
    "BigCodeBench/279",
    "BigCodeBench/305",
    "BigCodeBench/328",
    "BigCodeBench/330",
    "BigCodeBench/331",
    "BigCodeBench/333",
    "BigCodeBench/335",
    "BigCodeBench/342",
    "BigCodeBench/384",
    "BigCodeBench/394",
    "BigCodeBench/433",
    "BigCodeBench/505",
    "BigCodeBench/542",
    "BigCodeBench/544",
    "BigCodeBench/545",
    "BigCodeBench/548",
    "BigCodeBench/668",
    "BigCodeBench/669",
    "BigCodeBench/670",
    "BigCodeBench/682",
    "BigCodeBench/685",
    "BigCodeBench/694",
    "BigCodeBench/733",
    "BigCodeBench/739",
    "BigCodeBench/740",
    "BigCodeBench/741",
    "BigCodeBench/747",
    "BigCodeBench/751",
    "BigCodeBench/753",
]

# Held out for generalization checks - same curation criteria, zero overlap with
# MAIN_TASK_IDS and with prompts/pbt_monitor/fewshot_bank.json.
HELDOUT_TASK_IDS = [
    "BigCodeBench/25",
    "BigCodeBench/202",
    "BigCodeBench/295",
    "BigCodeBench/464",
    "BigCodeBench/666",
]


class BigCodeBenchPBTSetting(BigCodeBenchSetting):
    """BigCodeBenchSetting restricted to a curated, PBT-friendly task subset."""

    task_ids: tuple[str, ...] = tuple(MAIN_TASK_IDS)

    def get_dataset(self, eval_mode):
        allowed = set(self.task_ids)

        def _filter(sample) -> bool:
            meta = (sample.metadata or {}).get("metadata", {})
            return meta.get("task_id") in allowed

        return get_dataset(
            subset=self.subset,
            split=self.split,
            sample_filter_fn=_filter,
            shuffle=self.shuffle_dataset,
            seed=self.shuffle_seed,
            mode=eval_mode,
        )

    def get_sandbox_config(self):
        return get_compose_sandbox_config(
            self.sandbox_type, Path(__file__).parent / "compose.yml", "bigcodebench_pbt"
        )
