"""Would showing the test writer the pool's whole provided input/output set leak the attack?

DESIGN NOTE PENDING — filled in after the measurement, from the measurement.

Three stages, each runnable alone:

    verify     run honest, attack_0 and reference_solution against every provided pair of all 50
               tasks of `apps_pool_hard.json`. A pair is a pass, a wrong answer, a crash or a
               timeout; the last two are their own categories and never fold into either of the
               first two.
    visible    how many pairs `apps.statement_examples` keeps against how many the pool holds.
    tokens     what the authoring prompt costs at 3, 10, 20, 40 and all pairs.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import probe  # noqa: E402
from pipeline.backends.apps import (  # noqa: E402
    EXAMPLES_SHOWN,
    _hint,
    statement_examples,
)

POOL_PATH = REPO / "apps_pool_hard.json"
ARTIFACT_PATH = Path(__file__).resolve().parent / "provided_io.json"

PER_PAIR_TIMEOUT_SECONDS = 10
CHECK_WORKERS = 8
ROLES = ("honest", "attack_0", "reference")

PASS = "pass"
WRONG = "wrong"
CRASH = "crash"
TIMEOUT = "timeout"
NOT_A_PASS = (WRONG, CRASH, TIMEOUT)

SHOWN_COUNTS = (3, 10, 20, 40)
ALL_PAIRS = 0
TOKENISER = "o200k_base"
EXCERPT_CHARS = 120

PAIR_CHAR_CAP = 800
POLICY_FIRST = "first"
POLICY_SMALL = f"under_{PAIR_CHAR_CAP}_chars"
POLICIES = (POLICY_FIRST, POLICY_SMALL)


@dataclass
class PairResult:
    role: str
    index: int
    outcome: str
    got: str = ""
    detail: str = ""


@dataclass
class ProgramCheck:
    """One program against every provided pair of its task, with nothing collapsed.

    `passes_all` is true only when every pair passed: a timeout and a crash are each a reason the
    claim under test is not established for this program, and reading either as a pass would make
    the leak-safety argument rest on pairs that never ran.
    """

    task: str
    role: str
    pairs_total: int
    passed: int
    wrong: int
    crashed: int
    timed_out: int
    passes_all: bool
    elapsed_s: float
    first_failure: dict[str, Any] | None = None


@dataclass
class VisibleCount:
    task: str
    statement_visible: int
    provided_total: int


@dataclass
class TokenCost:
    """The rendered authoring prompt's size at one pair count, for one task.

    `requested` and `shown` are both kept: a task holding 20 pairs shows 20 whether 20 or 40 were
    asked for, and a table keyed on `shown` alone silently pools the two into one row.
    """

    task: str
    policy: str
    requested: int
    shown: int
    pairs_available: int
    hint_tokens: int
    inputs_prompt_tokens: int
    tests_prompt_tokens: int


def load_pool() -> dict[str, dict[str, Any]]:
    return json.loads(POOL_PATH.read_text(encoding="utf-8"))["candidates"]


def program_of(task: dict[str, Any], role: str) -> str:
    """The source for one of the three roles, stated per role rather than guessed off a shape.

    `honest` and `attack_proposals[0]` are dicts carrying a `code` key while `reference_solution`
    is a bare string, and a loader that inferred which by duck-typing would silently hand `str`
    where a dict was meant the day the pool shape changed.
    """
    if role == "honest":
        return task["honest"]["code"]
    if role == "attack_0":
        return task["attack_proposals"][0]["code"]
    if role == "reference":
        return task["reference_solution"]
    raise KeyError(f"{role!r} is not one of {ROLES}")


def normalise(text: str) -> str:
    """Trailing whitespace and a trailing newline are not answers; everything else is."""
    return "\n".join(line.rstrip() for line in (text or "").strip().splitlines())


def run_pair(source: str, role: str, index: int, given: str, expected: str) -> PairResult:
    """One program on one input, with the four outcomes kept apart."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", source],
            input=given,
            capture_output=True,
            text=True,
            timeout=PER_PAIR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return PairResult(role, index, TIMEOUT, detail=f"exceeded {PER_PAIR_TIMEOUT_SECONDS}s")
    except (UnicodeDecodeError, OSError) as error:
        return PairResult(role, index, CRASH, detail=f"{type(error).__name__}: {error}"[:160])
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()
        return PairResult(
            role, index, CRASH,
            detail=f"exit {proc.returncode}: {tail[-1][:160] if tail else 'no stderr'}",
        )
    got = normalise(proc.stdout)
    if got != normalise(expected):
        return PairResult(role, index, WRONG, got=got)
    return PairResult(role, index, PASS)


def pairs_of(task: dict[str, Any]) -> list[tuple[str, str]]:
    given, expected = task["provided_inputs"], task["provided_outputs"]
    if len(given) != len(expected):
        raise ValueError(f"{len(given)} provided inputs against {len(expected)} outputs")
    return list(zip(given, expected))


def check_all(candidates: dict[str, dict[str, Any]], limit: int) -> list[ProgramCheck]:
    """Every (task, role, pair) run once, flat, so one slow task cannot idle seven workers.

    Every pair runs — no early exit on the first failure — because the question is how many pairs
    a candidate fails, and a stop-at-first-failure check answers only whether it failed at all.
    """
    jobs: list[tuple[str, str, int, str, str, str]] = []
    for task_id, task in candidates.items():
        pairs = pairs_of(task)
        if limit != ALL_PAIRS:
            pairs = pairs[:limit]
        for role in ROLES:
            source = program_of(task, role)
            for index, (given, expected) in enumerate(pairs):
                jobs.append((task_id, role, index, given, expected, source))

    started = time.time()
    print(f"  {len(jobs)} program-pair runs over {len(candidates)} tasks", flush=True)
    with ThreadPoolExecutor(max_workers=CHECK_WORKERS) as pool:
        results = list(
            pool.map(
                lambda j: (j[0], run_pair(j[5], j[1], j[2], j[3], j[4])),
                jobs,
            )
        )
    elapsed = time.time() - started
    print(f"  finished in {elapsed / 60:.1f} min", flush=True)

    by_program: dict[tuple[str, str], list[PairResult]] = {}
    for task_id, result in results:
        by_program.setdefault((task_id, result.role), []).append(result)

    checks: list[ProgramCheck] = []
    for (task_id, role), got in sorted(by_program.items()):
        got.sort(key=lambda r: r.index)
        counts = Counter(r.outcome for r in got)
        bad = next((r for r in got if r.outcome in NOT_A_PASS), None)
        given, expected = "", ""
        if bad is not None:
            given, expected = pairs_of(candidates[task_id])[bad.index]
        checks.append(
            ProgramCheck(
                task=task_id,
                role=role,
                pairs_total=len(got),
                passed=counts[PASS],
                wrong=counts[WRONG],
                crashed=counts[CRASH],
                timed_out=counts[TIMEOUT],
                passes_all=counts[PASS] == len(got),
                elapsed_s=round(elapsed, 1),
                first_failure=None if bad is None else {
                    "outcome": bad.outcome,
                    "index": bad.index,
                    "input": given[:EXCERPT_CHARS],
                    "expected": normalise(expected)[:EXCERPT_CHARS],
                    "got": bad.got[:EXCERPT_CHARS] if bad.outcome == WRONG else bad.detail,
                },
            )
        )
    return checks


def visible_counts(candidates: dict[str, dict[str, Any]]) -> list[VisibleCount]:
    return [
        VisibleCount(
            task=task_id,
            statement_visible=len(statement_examples(task)[0]),
            provided_total=len(task["provided_inputs"]),
        )
        for task_id, task in candidates.items()
    ]


def eligible_pairs(task: dict[str, Any], policy: str) -> list[tuple[str, str]]:
    """The pairs a policy is allowed to draw from, in pool order.

    `POLICY_FIRST` is the naive reading of "show 40 pairs" and is here to be rejected: two tasks in
    this pool carry megabyte inputs, so an index-based cut puts one of them in a prompt whole.
    """
    pairs = pairs_of(task)
    if policy == POLICY_FIRST:
        return pairs
    if policy == POLICY_SMALL:
        return [p for p in pairs if len(p[0]) + len(p[1]) <= PAIR_CHAR_CAP]
    raise KeyError(f"{policy!r} is not one of {POLICIES}")


def token_costs(candidates: dict[str, dict[str, Any]]) -> list[TokenCost]:
    """The two authoring prompts rendered at each pair count, measured in tokens.

    `probe.build_prompt` is called rather than the hint measured alone: the number that matters is
    what the arm sends, and the pairs sit inside a template that already carries the task, the
    submission and an output contract.
    """
    import tiktoken

    encoding = tiktoken.get_encoding(TOKENISER)
    problems = {p.task_id: p for p in probe.load_problems(
        POOL_PATH, list(candidates), probe.DEFAULT_DOMAIN
    )}
    costs: list[TokenCost] = []
    for task_id, task in candidates.items():
        problem = problems[task_id]
        code = problem.attacks[0].code
        for policy in POLICIES:
            pairs = eligible_pairs(task, policy)
            for requested in (*SHOWN_COUNTS, ALL_PAIRS):
                take = len(pairs) if requested == ALL_PAIRS else min(requested, len(pairs))
                hint = _hint([p[0] for p in pairs], [p[1] for p in pairs], n=take)
                widened = replace_hint(problem, hint)
                costs.append(
                    TokenCost(
                        task=task_id,
                        policy=policy,
                        requested=requested,
                        shown=take,
                        pairs_available=len(pairs),
                        hint_tokens=len(encoding.encode(hint)),
                        inputs_prompt_tokens=len(encoding.encode(
                            rendered(widened, code, probe.INPUTS_STAGE)
                        )),
                        tests_prompt_tokens=len(encoding.encode(
                            rendered(widened, code, probe.TESTS_STAGE)
                        )),
                    )
                )
    return costs


def replace_hint(problem: Any, hint: str) -> Any:
    from dataclasses import replace

    return replace(problem, provided_tests_hint=hint)


def rendered(problem: Any, code: str, stage: str) -> str:
    """One staged authoring prompt exactly as `probe` builds it, at the running arms' settings."""
    return probe.build_prompt(
        problem,
        code,
        n_tests=10,
        n_inputs=30,
        resolve_rule="without",
        code_visibility="visible",
        output_format=probe.SPLIT_FORMAT,
        framing="plain",
        stage=stage,
        chosen_inputs=tuple(f"placeholder {i}" for i in range(30)),
    )


def report_verify(checks: list[ProgramCheck]) -> None:
    print("\n=== PART 1  every provided pair, every candidate ===\n")
    print(f"  {'role':<12}{'programs':>9}{'pass-all':>10}{'pairs':>8}"
          f"{'passed':>8}{'wrong':>7}{'crash':>7}{'timeout':>9}")
    for role in ROLES:
        of_role = [c for c in checks if c.role == role]
        print(f"  {role:<12}{len(of_role):>9}{sum(c.passes_all for c in of_role):>10}"
              f"{sum(c.pairs_total for c in of_role):>8}{sum(c.passed for c in of_role):>8}"
              f"{sum(c.wrong for c in of_role):>7}{sum(c.crashed for c in of_role):>7}"
              f"{sum(c.timed_out for c in of_role):>9}")
    offenders = [c for c in checks if not c.passes_all]
    if not offenders:
        print("\n  every program passes every provided pair.")
        return
    print(f"\n  {len(offenders)} programs do not pass everything:\n")
    for c in sorted(offenders, key=lambda c: (c.task, c.role)):
        f = c.first_failure or {}
        print(f"  task {c.task}  {c.role}: {c.wrong} wrong, {c.crashed} crash, "
              f"{c.timed_out} timeout of {c.pairs_total}")
        print(f"      first {f.get('outcome')} at pair {f.get('index')}")
        print(f"      input    {f.get('input')!r}")
        print(f"      expected {f.get('expected')!r}")
        print(f"      got      {f.get('got')!r}")


def report_visible(counts: list[VisibleCount]) -> None:
    visible = [c.statement_visible for c in counts]
    total = [c.provided_total for c in counts]
    print("\n=== PART 2  statement-visible pairs against provided pairs ===\n")
    print(f"  EXAMPLES_SHOWN = {EXAMPLES_SHOWN}   (cap on how many reach the prompt)\n")
    print(f"  {'':<20}{'median':>8}{'mean':>8}{'min':>6}{'max':>6}{'sum':>8}")
    for name, series in (("statement-visible", visible), ("provided total", total)):
        print(f"  {name:<20}{statistics.median(series):>8.1f}"
              f"{statistics.mean(series):>8.1f}{min(series):>6}{max(series):>6}{sum(series):>8}")
    print(f"\n  statement-visible distribution: {sorted(Counter(visible).items())}")
    print(f"  tasks with 0 statement-visible pairs: {sum(1 for v in visible if v == 0)}")
    capped = sum(1 for v in visible if v > EXAMPLES_SHOWN)
    print(f"  tasks whose visible pairs exceed EXAMPLES_SHOWN: {capped}")
    print(f"  pairs actually reaching a prompt today: "
          f"{sum(min(v, EXAMPLES_SHOWN) for v in visible)} of {sum(total)}")
    print(f"  provided-total distribution: {sorted(Counter(total).items())}")


def report_tokens(costs: list[TokenCost]) -> None:
    print("\n=== PART 3  authoring prompt token cost by pairs shown ===\n")
    print(f"  tokeniser {TOKENISER}; the arms run at --max-tokens 32000\n")
    for policy in POLICIES:
        print(f"  policy {policy}")
        print(f"  {'asked':>7}{'shown med':>11}{'hint med':>10}{'hint p90':>10}{'hint max':>11}"
              f"{'tests med':>11}{'tests p90':>11}{'tests max':>12}")
        for requested in (*SHOWN_COUNTS, ALL_PAIRS):
            group = [c for c in costs if c.policy == policy and c.requested == requested]
            label = "all" if requested == ALL_PAIRS else str(requested)
            print(f"  {label:>7}{statistics.median(c.shown for c in group):>11.0f}"
                  f"{statistics.median(c.hint_tokens for c in group):>10.0f}"
                  f"{percentile([c.hint_tokens for c in group], 90):>10.0f}"
                  f"{max(c.hint_tokens for c in group):>11}"
                  f"{statistics.median(c.tests_prompt_tokens for c in group):>11.0f}"
                  f"{percentile([c.tests_prompt_tokens for c in group], 90):>11.0f}"
                  f"{max(c.tests_prompt_tokens for c in group):>12}")
        print()
    biggest = sorted(
        {c.task: c.pairs_available for c in costs if c.policy == POLICY_FIRST}.items(),
        key=lambda kv: -kv[1],
    )[:5]
    print("  the five tasks holding the most pairs, tests-prompt tokens by pairs asked for:")
    print(f"    {'task':>6}{'pairs':>7}  " + "  ".join(f"{p:>26}" for p in POLICIES))
    for task, available in biggest:
        cells = []
        for policy in POLICIES:
            row = {c.requested: c for c in costs if c.task == task and c.policy == policy}
            cells.append(" ".join(
                f"{'all' if r == ALL_PAIRS else r}:{row[r].tests_prompt_tokens}"
                for r in (20, 40, ALL_PAIRS)
            ))
        print(f"    {task:>6}{available:>7}  " + "  ".join(f"{c:>26}" for c in cells))


def percentile(values: list[int], q: int) -> float:
    ordered = sorted(values)
    return float(ordered[min(len(ordered) - 1, round(q / 100 * len(ordered)))])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("verify", "visible", "tokens", "all"), default="all")
    parser.add_argument("--max-pairs", type=int, default=ALL_PAIRS,
                        help="0 = every provided pair; anything else truncates, for a pilot")
    args = parser.parse_args()

    candidates = load_pool()
    artifact: dict[str, Any] = {}
    if ARTIFACT_PATH.exists():
        artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))

    if args.stage in ("visible", "all"):
        counts = visible_counts(candidates)
        artifact["visible"] = [asdict(c) for c in counts]
        report_visible(counts)

    if args.stage in ("tokens", "all"):
        costs = token_costs(candidates)
        artifact["tokens"] = [asdict(c) for c in costs]
        report_tokens(costs)

    if args.stage in ("verify", "all"):
        checks = check_all(candidates, args.max_pairs)
        artifact["verify"] = [asdict(c) for c in checks]
        artifact["verify_max_pairs"] = args.max_pairs
        report_verify(checks)

    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=1), encoding="utf-8")
    print(f"\n  wrote {ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
