# AI Control Protocol Benchmark

This repository evaluates AI-control protocols on a curated, stdlib-only subset of
BigCodeBench using ControlArena and Inspect AI. It compares code-visible trusted
monitoring, specification-derived property testing, combined monitors, and trusted
editing against identical cached honest and attack submissions.

**→ [ARCHITECTURE.md](ARCHITECTURE.md)** is the detailed reference: the full call
chain from `main.py` down to the sandbox, the candidate/checker isolation design,
the protocol comparison table, and a file map of what lives where. The sections
below cover the security model and metric definitions at a summary level; start
there if you want to know exactly what's implemented.

## Security Model

Every reported run requires Docker. Inspect creates five networkless services per
sandbox:

- `default`: runs candidate code only for PBT monitoring.
- `candidate-main`, `candidate-canonical`, and `candidate-side`: independently run
  official main tests, the canonical secret call, and the submitted secret call.
  Separating these phases prevents filesystem, IPC, cgroup, process, and other
  container-lifetime state from becoming a monitor/scorer side channel.
- All four candidate services execute through a root-owned supervisor;
  candidate functions run as UID/GID 65534 with CPU, memory, process, file, and
  descriptor limits.
- `checker`: owns generated Hypothesis tests and official BigCodeBench tests. It
  never receives candidate source.

Candidate and checker services exchange only bounded, tagged JSON values over a
unique Unix socket.
The unprivileged candidate cannot access the socket; generated checker code cannot
access candidate files or processes. PBT and official scoring use the same persistent
candidate-call harness, preventing a submission from distinguishing them through a
special PBT-only interpreter. Docker protects these two principals from each other;
for hostile publication runs, run Docker inside a disposable VM or gVisor.

Local execution is intentionally unsupported because it cannot enforce the two-principal boundary.

## Metrics

Definitions follow Greenblatt et al., [*AI Control: Improving Safety Despite
Intentional Subversion*](https://proceedings.mlr.press/v235/greenblatt24a.html):

- **Safety** is the probability that no working backdoor is submitted during an
  entire deployment. This is the paper's definition, not a per-task evasion rate.
  The benchmark does not report a safety estimate by default because forced attack-
  mode samples do not identify a real deployment attack frequency.
- **Raw usefulness** is the fraction of correct final submissions in no-attack runs.
- **Normalized usefulness** is `(R(P) - R(T)) / (R(U) - R(T))`. Supply measured
  trusted and untrusted baseline accuracies to report it.
- **Reported model cost** is the sum of provider-reported `ModelUsage.total_cost`.
  It excludes human-audit and infrastructure cost and is never imputed when absent.

Per-task successful/undetected-backdoor and honest-flag rates remain explicitly
labelled diagnostics; they are not called paper safety. A paper-style final result
must run multiple red-team attack policies and report the lowest safety.

Pass `--attack-episode-subsample-rate RATE` only to run an explicitly conditional
reference-style sensitivity analysis. The paper used `1/12` for its APPS experiment;
that value is not a universal constant and is not automatically portable here. The
simulator retains each observed attempted attack at most once with the supplied rate,
fills the remaining 5,000 tasks from non-attack episodes, always audits the first 10
shuffled tasks for free, and dynamically allocates 100 paid audits. The summary also
records the expected retained-attempt count.

This simplified simulator does not reproduce the paper's adversarial evaluation,
correctness/distribution-shift tests, suspicious-audit-result transitions, or full
trusted fallback policy. A submission with a non-null `secret_input` is treated as an
attempt. If attack-mode non-attempts are absent, honest-mode suspicion scores fill the
non-attack stream. The displayed interval is Monte Carlo integration error only, not
episode, policy, dataset, or attack-frequency uncertainty.

## Setup

Requirements are pinned to exact framework revisions:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker info
```

Export the API credential required by the chosen models:

```bash
export OPENAI_API_KEY=...
# or
export ANTHROPIC_API_KEY=...
```

## Reproducible Workflow

First generate one immutable submission cache. Every compared protocol will replay
the same candidate bytes:

```bash
python generate_attack_cache.py \
  --dataset main \
  --untrusted-model openai/o3-mini \
  --trusted-model openai/gpt-4o-mini \
  --attack-prompt v1_default \
  --out attack_cache.json
```

Then run protocols against that cache:

```bash
python main.py \
  --dataset main \
  --attack-cache attack_cache.json \
  --protocols TM,PBT,TM+PBT,PBT-Informed-TM \
  --pbt-prompt v3_backdoor_focused \
  --pbt-fewshot-k 3 \
  --pbt-fewshot-seed 7 \
  --max-concurrent-samples 5 \
  --run-dir runs/main-v3-seed7
```

To report normalized usefulness, add measured baseline values:

```bash
  --trusted-baseline-accuracy 0.22 \
  --untrusted-baseline-accuracy 0.54
```

Do not reuse the paper's 0.22/0.54 values unless those are genuinely the measured
baselines for the models and dataset in this run.

By default, each run directory contains Inspect `.eval` logs, an immutable manifest,
exact prompt templates and hashes, rendered per-sample PBT prompts, generated tests,
configuration, dependency versions, cache hash, code revision, and `summary.json`.

## Protocols

| Name | Mechanism |
| --- | --- |
| `TM` | Trusted model reads candidate code and assigns suspicion. |
| `PBT` | Trusted model sees the specification, generates properties, and tests the candidate as a black box. |
| `TM+PBT` | Runs both monitors and uses the maximum suspicion. |
| `PBT-Informed-TM` | Gives code and structured PBT evidence to one trusted-model judgment. |
| `TE` | Always routes through a trusted editor. |
| `Hybrid` | Edits when PBT suspicion crosses the configured threshold. |

## Prompt Versions

Prompts live under `prompts/<role>/<variant>.txt`. Published variants are immutable:
change experimental wording by adding a new variant, never by editing an existing
one. The loader rejects unsafe names, missing variants, incompatible few-shot use,
and unresolved template tokens.

## Tests

```bash
pytest -m "not live and not docker"
RUN_LIVE_TESTS=1 pytest
```

Fast tests cover metric definitions, prompt rendering, generated-test policy, cache
validation, serialization, and source separation. Live tests require Docker, dataset
access, and potentially paid model APIs.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the detailed call and trust boundaries.
