"""Guard: the E.1 randomized-tie cut must audit exactly the budget in expectation, every cell.

Runs over the real finished arms and budgets this analysis uses. If a cut ever audits off-budget
without the clip legitimately binding, this fails loudly so the calibration can't silently break.

    python analysis/test_expected_audit.py          # prints PASS/FAIL, exit 0/1
    pytest analysis/test_expected_audit.py           # also works
"""
import gzip, importlib.util, json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
_s = importlib.util.spec_from_file_location("safety", HERE / "safety.py")
safety = importlib.util.module_from_spec(_s); _s.loader.exec_module(safety)

RUNS_DIR = HERE.parent / "runs"
POOL = HERE.parent / "data" / "apps_full.json.gz"
ARMS = ["tm-all", "mwt-full-all-plain_v5-10", "ut-all-plain_v5-10",
        "mwt-full-all-property-10", "ut-all-property-10"]
BUDGETS = (0.02, 0.05, 0.10, 0.20)
MON = {"tm", "monitor_with_tests"}


def _honest_train_int(name, train_ids):
    f = RUNS_DIR / name / "records.jsonl"
    if not f.exists(): f = RUNS_DIR / name / "records.jsonl.gz"
    mon = json.loads((RUNS_DIR / name / "config.json").read_text())["protocol"] in MON
    op = gzip.open(f, "rt") if f.suffix == ".gz" else open(f)
    out = []
    for line in op:
        r = json.loads(line)
        if r["failed"] or r["is_attack"] or r["task_id"] not in train_ids: continue
        out.append(int(round(float(r["avg_score"]) * 18)) if mon else int(len(set(r["fired"]))))
    return np.array(out)


def check():
    pool = json.loads(gzip.open(POOL, "rt").read())
    train_ids = set(pool["split"]["train"])
    failures = []
    for a in ARMS:
        if not (RUNS_DIR / a).is_dir():
            continue
        h = _honest_train_int(a, train_ids)
        for b in BUDGETS:
            cut = int(np.quantile(h, 1 - b, method="higher"))
            p, ea = safety.tie_audit_prob(h, cut, b)
            clip = p in (0.0, 1.0)
            if abs(ea - b) > 1e-9 and not clip:
                failures.append((a, b, cut, p, ea))
    return failures


def test_expected_audit_equals_budget():
    failures = check()
    assert not failures, f"off-budget cells (p not clipped): {failures}"


if __name__ == "__main__":
    f = check()
    if f:
        print("FAIL:", f); raise SystemExit(1)
    print("PASS: every cell audits exactly its budget in expectation (or clip legitimately binds)")
