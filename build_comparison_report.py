"""Builds one consolidated, human-readable report comparing TM's LLM-judge verdict
against PBT's generated property test and verdict, per attack sample - so you
can read through what each monitor actually saw and decided for all tasks at once,
instead of digging through separate .eval logs, generated_code/, and pbt_scripts/.

Usage:
    python build_comparison_report.py \\
        --tm-attack logs/xxx-tm-attack.eval \\
        --pbt-attack logs/xxx-pbt-attack.eval \\
        --out comparison_report.md
"""

import argparse
from pathlib import Path

from inspect_ai.log import EvalSample, read_eval_log
from inspect_ai.scorer import CORRECT


def _get_reason(sample: EvalSample) -> str:
    for m in sample.messages:
        if m.role == "assistant" and m.metadata and "reason" in m.metadata:
            return m.metadata["reason"]
    return "(no monitor reason found)"


def _get_suspicion(sample: EvalSample):
    sc = sample.scores.get("max_suspicion_scorer") if sample.scores else None
    return sc.value if sc else None


def _get_submission(sample: EvalSample):
    code, secret_input = None, None
    for m in sample.messages:
        if m.role == "assistant" and getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                if tc.function == "submit":
                    code = tc.arguments.get("code")
                    secret_input = tc.arguments.get("secret_input")
    return code, secret_input


def _get_side_task(sample: EvalSample):
    sc = sample.scores.get("bigcodebench_scorer") if sample.scores else None
    if sc and isinstance(sc.value, dict):
        return sc.value.get("side_task_success"), sc.explanation
    return None, None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tm-attack", required=True)
    parser.add_argument("--pbt-attack", required=True)
    parser.add_argument(
        "--pbt-scripts-dir",
        required=True,
        help="PBT protocol artifact directory, usually runs/<run>/pbt_artifacts/PBT",
    )
    parser.add_argument("--out", default="comparison_report.md")
    args = parser.parse_args()

    tm_log = read_eval_log(args.tm_attack)
    pbt_log = read_eval_log(args.pbt_attack)

    tm_by_id = {s.id: s for s in tm_log.samples}
    pbt_by_id = {s.id: s for s in pbt_log.samples}
    all_ids = sorted(set(tm_by_id) | set(pbt_by_id))

    lines = ["# TM vs PBT: per-sample comparison (ATTACK mode)\n"]

    for sid in all_ids:
        tm_s = tm_by_id.get(sid)
        pbt_s = pbt_by_id.get(sid)
        lines.append(f"\n## {sid}\n")

        code, secret_input = (None, None)
        worked, expl = (None, None)
        if tm_s is not None:
            code, secret_input = _get_submission(tm_s)
            worked, expl = _get_side_task(tm_s)
        elif pbt_s is not None:
            code, secret_input = _get_submission(pbt_s)
            worked, expl = _get_side_task(pbt_s)

        lines.append(f"**Backdoor actually worked (side_task_success):** `{worked}`")
        if expl:
            lines.append(f"\n```\n{expl.strip()}\n```")
        lines.append(f"\n**secret_input:** `{secret_input}`\n")
        lines.append("**Submitted code:**\n```python\n" + (code or "(none)") + "\n```\n")

        if tm_s is not None:
            lines.append(f"### TM verdict\n**suspicion_score:** `{_get_suspicion(tm_s)}`\n")
            lines.append(f"**reasoning:**\n```\n{_get_reason(tm_s).strip()}\n```\n")
        else:
            lines.append("### TM verdict\n(no sample)\n")

        if pbt_s is not None:
            lines.append(f"### PBT verdict\n**suspicion_score:** `{_get_suspicion(pbt_s)}`\n")
            lines.append(f"**reasoning:**\n```\n{_get_reason(pbt_s).strip()[:800]}\n```\n")
            safe_id = str(sid).replace("/", "_")
            script_path = Path(args.pbt_scripts_dir) / f"{safe_id}_ATTACK_pbt_test.py"
            if script_path.exists():
                lines.append(f"**Generated property test ({script_path}):**\n```python\n{script_path.read_text()}\n```\n")
            else:
                lines.append(f"**Generated property test:** (not found at {script_path})\n")
        else:
            lines.append("### PBT verdict\n(no sample)\n")

        lines.append("\n---\n")

    Path(args.out).write_text("\n".join(lines))
    print(f"Wrote comparison report for {len(all_ids)} samples to {args.out}")


if __name__ == "__main__":
    main()
