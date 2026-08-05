# Property-based testing as an AI-control monitor

Can a trusted model catch a backdoor by *running* untrusted code, rather than by reading it?

Standard AI-control protocols use **trusted monitoring** (TM): a weaker, trusted model reads the
untrusted model's code and rates how suspicious it looks. That is a text judgement, and it inherits
every weakness of one — most sharply, it can be attacked through the text itself
([arXiv:2510.09462](https://arxiv.org/abs/2510.09462) evades diverse LLM monitors using prompt
injections embedded in model output).

An **execution-grounded** monitor cannot be attacked that way — you cannot prompt-inject a
subprocess. This repository builds one and measures what it is actually worth.

Setting: APPS competitive-programming tasks via
[control_arena](https://github.com/UKGovernmentBEIS/control-arena) / `inspect_ai`. The untrusted
model writes solutions, some containing backdoors — correct on ordinary inputs, wrong on one rare
trigger. The trusted model writes **properties** (spec-derived invariants) and a **trigger search
space** (inputs to try). The verdict is whether any property fails on any input.

## The result

**1. PBT is precise where TM is not.** On 40 held-out tasks TM's false-positive rate is **0.723** —
it rates most honest code 8–9/10 suspicious, and survives only because auditing spends *rank* rather
than a threshold. The reference-gated PBT arm holds **0.000** FPR; a deployable self-critique gate
gets **0.175**.

**2. The audit-only game was measuring the wrong thing.** PBT scores are binary in every run on
disk, so a quantile-calibrated audit rule can barely rank with them. Give the monitor a *block*
action instead — spending usefulness rather than human review, an orthogonal budget — and the same
monitor on the same rows flips sign:

| | audit-only | block + audit |
|---|---|---|
| ungated `pbt` vs TM | **−0.171** (CI excludes 0) | **+0.092 / +0.114** (CI excludes 0) |
| `pbt_ceiling` vs TM | 0.000 ± 0.000 | +0.020 / +0.040 (free, n.s.) |

Nothing about the monitor changed between those columns. It had been scored on the one task it is
worst at.

**3. Recall is capped by search, then by the oracle.** For **12 of 14** backdoors the harness never
executed the buggy path at all — no property could have caught them. Making the input generator
code-aware (constant mining + coverage-guided fuzzing) raises reach from **21% → 57%**… and barely
moves the catch rate, because most divergences violate no simple spec-derived invariant. Executing
the bug is necessary and far from sufficient. **The binding constraint is now the oracle, not the
search.**

Why a code-aware generator is legitimate: soundness constrains the **oracle**, not the
**generator**. The properties never see the candidate and they alone decide what counts as a
violation, so a code-aware generator cannot manufacture a false positive — it can only change where
you look. Measured: with the reference gate on, code-aware search raises catches and holds FPR at
exactly 0. Without it, false positives rise faster than true ones and the change is a net loss.

Full ablation record, including the hypotheses that died: [`reports/`](reports/).

## Running it

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # add your provider credentials

.venv/bin/python run.py --domain mock --mock --runs 2 --run-id smoke   # no API calls

.venv/bin/python run.py --domain apps --dataset apps_pool_hard10.json \
    --t-model openai-api/azureai/DeepSeek-V3.2 --t-reasoning LOW \
    --u-model openai-api/azureai/gpt-5.4 --u-reasoning HIGH \
    --gen-strategy U_PLANS_T_WRITES --runs 5 \
    --attack-rate 0.05 --audit-rate 0.10 --run-id uplan10
```

`--run-id` resumes: a killed run costs at most one in-flight call. Every flag is also an environment
variable in upper case; `--help` lists them all.

Post-hoc analysis reads `runs/<id>/run_*/rows.json` and needs no model calls:

```bash
.venv/bin/python deployment_game.py --run uplan10 --audit-rate 0.10 --attack-rate 0.05
.venv/bin/python reach_rate.py --run uplan10 --pool apps_pool_hard10.json
```

### Generation strategies

| `--gen-strategy` | who writes the properties |
|---|---|
| `BLIND_T` | trusted model, from the spec alone |
| `U_WRITES` | untrusted model (it may sabotage its own tests) |
| `U_PLANS_T_WRITES` | untrusted model plans, trusted model implements |
| `U_PLANS_U_WRITES` | untrusted model does both |

### Protocols scored

`tm` · `pbt` · `pbt_ceiling` · `tm_plus_pbt` · `tm_plus_pbt_ceiling` · `pbt_informed_tm`

`pbt_ceiling` keeps only properties that hold on a known-good reference. That reference is **not**
available to a deployed monitor, so this is a ceiling — and it bounds precision, not recall.

## Layout

```
run.py                      entry point
pipeline/
  config.py                 pydantic-settings: CLI + env + validation
  engine.py                 resumable step runner
  steps.py                  the pipeline stages
  pbt.py                    property/search generation, harness, soundness gate
  search.py                 code-aware trigger search (mining, coverage-guided fuzzing)
  monitor.py                trusted monitoring
  scoring.py                ground truth via control_arena
  metrics.py                safety, AUC, FPR, the audit-only deployment game
  report.py                 metrics.json / summary.csv / report.md
  artifacts.py              typed artifact store; every checkpoint and resume marker
  backends/                 APPS, BigCodeBench, mock
deployment_game.py          block + audit on orthogonal budgets (offline)
reach_rate.py               does the search space contain a triggering input? (offline)
prepare_candidate_pool.py   builds candidate pools from APPS
prompts/                    every model-facing prompt
reports/                    ablation logs and experiment records
examples/                   worked task examples
```

`apps_pool_hard10.json` is committed; the full 52 MB pools are gitignored and rebuildable with
`prepare_candidate_pool.py`.

`CLAUDE.md` holds the working rules — including the one that mattered most here: *a failure must
never silently become a value.* Six separate bugs in this repo were that same shape, each defaulting
in the direction that blamed the model. `METRICS.md` defines every metric; `CHANGELOG.md` is the
operational log.

## Honest limits

- 10–40 APPS tasks, one model pair, 3–5 usable runs per configuration. Several deltas do not exclude
  zero; where that is true it is stated.
- The adaptive-attacker result is inconclusive: the attacker we could elicit never evaded TM, and the
  stronger model was blocked by a platform cybersecurity filter.
- `pbt_ceiling` is not deployable. The deployable gate is self-critique, at 0.175 FPR.
- APPS backdoors are single-trigger by construction, which flatters any search-based monitor.
