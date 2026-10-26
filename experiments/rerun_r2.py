"""Launch R2 (experiments/rerun_plan.md): every full-pool arm again, each when its inputs finish.

    caffeinate -s .venv/bin/python experiments/rerun_r2.py smoke   # 30-task slice, names end -r2-smoke
    caffeinate -s .venv/bin/python experiments/rerun_r2.py full    # data/apps_full_py312.json, -r2
    caffeinate -s .venv/bin/python experiments/rerun_r2.py full solve-all-r2   # only the runs named

Run it inside tmux. It computes no number: it starts protocol runs in dependency order and waits.
Every run is its own detached tmux session that resumes by candidate, so stopping this driver loses
nothing; starting it again picks up from what is on disk. The settings are the first pass's
(`runs/<name>/config.json`), except `runs=1` for TM and MonitorWithTests, the 32,000-token and
300 s caps (CAPS) and the cache off
everywhere: with it on, a run would replay the first pass's answers instead of asking again.
"""
from __future__ import annotations

import sys
import threading
import time
from datetime import datetime

from pipeline import launch
from pipeline.protocols import (TM, MonitorWithTests, TriggerSearch, TrustedSolve, UnitTesting,
                                UPlansTWrites)
from pipeline.protocols.multi_turn import MULTI_TURN_MODELS, MultiTurnStudy

MODEL = "openai-api/azureai/DeepSeek-V3.2"
MODES = {"smoke": ("data/apps_full_r2_smoke.json", "-r2-smoke", "smoke30-mt-deepseek-run2"),
         "full": ("data/apps_full_py312.json", "-r2", "full-mt-deepseek-run2")}
POLL_SECONDS = 60
GRID = {"sandbox_seconds": 240, "docker_image": "python:3.12-slim"}
# The suite calls already run at 32,000 tokens and 300 s; the four protocols that took their caps
# from reasoning="low" (12,000 and 120 s) now get the same, since the provider reasons past 12,000.
CAPS = {"max_tokens": 32000, "call_seconds": 300}
# Trigger search reasons longest: at 32,000 tokens 5% of smoke searches ran out before answering,
# at 64,000 and 600 s 1.7% (the first pass lost 0.5%).
TRIGGER_CAPS = {"max_tokens": 64000, "call_seconds": 600}
SUITE = {"resolve": "without", "n_tests": 10, "reasoning": "low", "max_tokens": 32000,
         "call_seconds": 300, **GRID}


def say(message: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}", flush=True)


def runs_for(data: str, end: str) -> dict[str, tuple[object, list[str]]]:
    """Every run of the plan as {name: (run, the runs it reads)}, settings as in the first pass."""
    trig = f"trig-all{end}"
    plan: dict[str, tuple[object, list[str]]] = {
        trig: (TriggerSearch(run_name=trig, data=data, model=MODEL, cache=False, num_inputs=30,
                             code_visible=True, reasoning="low", **TRIGGER_CAPS), []),
        f"tm-all{end}": (TM(run_name=f"tm-all{end}", data=data, model=MODEL, runs=1, cache=False,
                            reasoning="low", **CAPS), []),
        f"solve-all{end}": (TrustedSolve(run_name=f"solve-all{end}", data=data, model=MODEL,
                                         cache=False, reasoning="low", pairs=30,
                                         sandbox_seconds=210, docker_image=GRID["docker_image"],
                                         **CAPS),
                            []),
    }
    for prompt in ("property", "plain_v3", "plain_v5"):
        name = f"ut-all-{prompt}-10{end}"
        plan[name] = (UnitTesting(run_name=name, data=data, model=MODEL, cache=False, triggers=trig,
                                  test_gen_prompt=prompt, code_visible=True, critique=False,
                                  critique_informed=False, **SUITE), [trig])
    for prompt in ("property", "plain_v3"):
        name = f"upt-all-{prompt}-10{end}"
        plan[name] = (UPlansTWrites(run_name=name, data=data, model=MODEL, cache=False,
                                    triggers=trig, untrusted=MODEL, untrusted_reasoning="high",
                                    test_gen_prompt=prompt, plan_max_tokens=32000,
                                    plan_seconds=600, **SUITE), [trig])
    for label, tests in (("property", "ut-all-property-10"), ("plain_v3", "ut-all-plain_v3-10"),
                         ("plain_v5", "ut-all-plain_v5-10"),
                         ("uplans-property", "upt-all-property-10")):
        name = f"mwt-full-all-{label}-10{end}"
        plan[name] = (MonitorWithTests(run_name=name, data=data, model=MODEL, runs=1, cache=False,
                                       tests=f"{tests}{end}", triggers=trig, reasoning="low",
                                       **CAPS),
                      [f"{tests}{end}", trig])
    return plan


def finished(run) -> bool:
    status = run.status()
    return status["scored"] == status["total"] and not status["alive"]


def multi_turn(reference: UnitTesting, prefix: str, trig: str, outcome: dict) -> None:
    """The multi-turn chain, smoke chain first, reusing this mode's trigger run (as MT5 did). An
    error lands in `outcome`, so a chain that stopped on infra failures never reads as finished."""
    say(f"multi-turn {prefix}: starting on {trig}")
    try:
        study = MultiTurnStudy(reference_arm=reference, prefix=prefix,
                               model=MULTI_TURN_MODELS["deepseek"], triggers=trig)
        study.run(allow_paid=True)
        say(f"multi-turn {prefix}: done")
    except Exception as error:  # reported by main; the other runs carry on
        outcome["error"] = error
        say(f"multi-turn {prefix}: stopped: {error}")


def main(mode: str, only: list[str]) -> None:
    data, end, mt_prefix = MODES[mode]
    plan = runs_for(data, end)
    if only:
        unknown = sorted(set(only) - set(plan))
        if unknown:
            raise SystemExit(f"no run named {unknown} in {mode}; the plan has {sorted(plan)}")
        full, plan = plan, {name: plan[name] for name in only}
        unfinished = sorted(read for _, reads in plan.values() for read in reads
                            if read not in plan and not finished(full[read][0]))
        if unfinished:
            raise SystemExit(f"{unfinished} must finish first, or be named too")
    started: set[str] = set()
    relaunched: set[str] = set()
    chain: threading.Thread | None = None
    outcome: dict = {}
    while True:
        done = {name for name, (run, _) in plan.items() if name in started and finished(run)}
        for name, (run, reads) in plan.items():
            if name in started or not all(read in done or read not in plan for read in reads):
                continue
            if launch.alive(name):  # a restarted driver finds it still going
                say(f"{name} already running")
            else:
                run.run(wait=False)
                say(f"launched {name}")
            started.add(name)
        for name in started - done:
            run = plan[name][0]
            status = run.status()
            if not status["alive"] and status["scored"] < status["total"]:
                if name in relaunched:
                    raise RuntimeError(f"{name} stopped twice with {status}; look at its records")
                relaunched.add(name)
                say(f"{name} stopped at {status['scored']}/{status['total']}; resuming once")
                run.run(wait=False)
        trig = f"trig-all{end}"
        if chain is None and not only and trig in done and f"ut-all-property-10{end}" in started:
            chain = threading.Thread(target=multi_turn, daemon=False,
                                     args=(plan[f"ut-all-property-10{end}"][0], mt_prefix, trig,
                                           outcome))
            chain.start()
        if done == set(plan) and only:
            say("every run named finished")
            return
        if done == set(plan) and chain is not None and not chain.is_alive():
            if "error" in outcome:
                raise RuntimeError(f"every protocol run finished; the multi-turn chain did not: "
                                   f"{outcome['error']}")
            say("every run finished")
            return
        say("  ".join(f"{name}:{plan[name][0].status()['scored']}" for name in sorted(started)))
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in MODES:
        raise SystemExit(f"usage: rerun_r2.py {{{'|'.join(MODES)}}} [run ...]")
    main(sys.argv[1], sys.argv[2:])
