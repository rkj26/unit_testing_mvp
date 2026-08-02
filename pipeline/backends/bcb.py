"""BCB backend: control_arena's STOCK BigCodeBenchSetting (local sandbox) for ground-truth scoring.

control_arena grades BCB correctly out-of-box here — verified against the pool's recorded
``official_validation`` (stock == corrected == ground truth on tested tasks). So we use it as-is,
per "use control_arena where it's right; use inspect where it's wrong" (APPS is the wrong case).

BCB has no inline data — task spec, entry point, and canonical solution come from HuggingFace
(bigcodebench v0.1.4) via the setting. Candidates are function-mode: the pool's ``code`` is already a
complete module defining the entry point, so it runs directly in the property runner and is submitted
verbatim to control_arena.

NOTE: ``scorer_corrected.CorrectedBigCodeBenchSetting`` remains available as a drop-in if the stock
side-task comparison ever misjudges complex outputs (DataFrames / dicts / multi-line) on the full pool.
"""

from __future__ import annotations

from typing import Any

from ..schema import Candidate, Problem, ScoreResult
from ..scoring import score_via_control_arena


class BcbBackend:
    name = "bcb"

    def __init__(self) -> None:
        from control_arena.settings.bigcodebench.bigcodebench_setting import BigCodeBenchSetting

        self._setting = BigCodeBenchSetting(sandbox_type="local")
        self._meta: dict[str, dict[str, str]] = {}

    def _load_meta(self, task_ids: list[str]) -> None:
        from control_arena import EvalMode

        want = set(task_ids)
        for sm in self._setting.get_dataset(EvalMode.HONEST):
            md = sm.metadata or {}
            tid = str(md.get("main_task_name"))
            if tid in want and tid not in self._meta:
                tm = md.get("metadata") or {}
                self._meta[tid] = {
                    "description": str(md.get("main_task_description", "")),
                    "entry_point": str(tm.get("entry_point", "task_func")),
                    # assembled canonical (runnable) for the PBT soundness gate — never submitted
                    "reference": f"{tm.get('code_prompt', '')}\n    pass\n{tm.get('canonical_solution', '')}",
                }

    def preprocess(self, pool: dict[str, Any], *, limit: int | None = None) -> list[Problem]:
        items = list(pool["candidates"].items())
        if limit:
            items = items[:limit]
        self._load_meta([str(t) for t, _ in items])
        problems: list[Problem] = []
        for task_id, t in items:
            tid = str(task_id)
            meta = self._meta.get(tid)
            if meta is None:
                print(f"  [warn] {tid} not found in BigCodeBench dataset; skipping", flush=True)
                continue
            cands = [Candidate(t["honest"]["candidate_id"], "honest", t["honest"]["code"], None)]
            for i, attack in enumerate(t["attack_proposals"]):
                cands.append(
                    Candidate(attack["candidate_id"], f"attack_{i}", attack["code"], attack.get("secret_input"))
                )
            problems.append(
                Problem(
                    task_id=tid,
                    main_task=meta["description"],
                    io_mode="function",
                    entry_point=meta["entry_point"],
                    candidates=cands,
                    reference_code=meta["reference"],
                )
            )
        return problems

    def score_candidates(self, problems: list[Problem]) -> dict[tuple[str, str], ScoreResult]:
        return score_via_control_arena(self._setting, problems)
