# Architecture: what calls what

One command kicks off the whole system:

```
python main.py --dataset dataset.json --pbt-prompt v2_fewshot --pbt-fewshot-k 3
```

This doc traces that call all the way down to the sandboxed code execution and back,
file by file, so you can find where to make a change instead of guessing.

## The call chain, top to bottom

```mermaid
flowchart TD
    CLI["main.py\nargparse CLI"] --> CFG["config.py\nConfig(...)"]
    CFG --> EV["evaluator.py\nEvaluator(config)"]
    EV -->|"for each of TM / TM-PBT / TE / Hybrid"| BUILD["Evaluator._build_micro_protocol()"]
    BUILD --> POL["control_arena.policy\nuntrusted/honest/attack/trusted_editor builders"]
    BUILD --> MON1["control_arena.monitor.basic_monitor_builder\n(used by TM)"]
    BUILD --> MON2["pbt_monitor.py\npbt_monitor_builder\n(used by TM-PBT, TE, Hybrid)"]
    MON2 --> PROMPTS["prompts.py\nrender_pbt_prompt()"]
    PROMPTS --> TXT["prompts/pbt_monitor/*.txt\n+ fewshot_bank.json"]
    BUILD --> PROTO["control_arena.micro_protocol\ntrusted_monitoring_builder /\ntrusted_editing_builder"]
    EV -->|"HONEST then ATTACK"| TASK["control_arena.eval.get_control_task()\n-> inspect_ai.Task"]
    TASK --> SETTING["apps_setting.py\nAppsPBTSetting"]
    SETTING --> DATA["dataset_loader.py\nload_dataset() <- dataset.json"]
    EV --> RUN["control_arena.eval.eval()\n(wraps inspect_ai.eval)"]
    RUN -->|"agent loop, per sample"| SANDBOX["inspect_ai sandbox\nsandbox().exec(...)"]
    SANDBOX --> SCORERS["apps_setting.py\napps_main_task_scorer / apps_side_task_scorer"]
    MON2 -->|"also runs inside the sandbox"| SANDBOX
    RUN --> LOGS["logs/*.eval\nEvalLog objects"]
    LOGS --> EV
    EV --> TABLE["main.py\nRich table output"]
```

## Walking it step by step

**1. `main.py`** parses CLI flags (`--dataset`, `--untrusted-model`, `--trusted-model`,
`--threshold`, `--max-examples`, `--docker`, `--sweep`, `--pbt-prompt`,
`--pbt-fewshot-k`, `--pbt-fewshot-seed`, `--attack-prompt`, `--dump-explanations`) and
builds one `Config` object (`config.py`) from them. Nothing downstream reads
`sys.argv` directly — `Config` is the single source of truth for a run.

**2. `Evaluator(config)`** (`evaluator.py`) is constructed once and owns an
`AppsPBTSetting(dataset_path=..., use_docker=...)` (`apps_setting.py`). Everything
after this point is either "build a protocol" or "run a protocol."

**3. `Evaluator.run_experiment()`** loops over the four named protocols
(`"TM", "TM-PBT", "TE", "Hybrid"`) and, for each, calls
`run_experiment_for_protocol(name)`, which does two things:

- **Build** (`_build_micro_protocol`): composes ControlArena primitives into a
  `micro_protocol` object. This is where the four protocols actually differ:

  | Protocol | Policy | Monitor | Editing |
  |---|---|---|---|
  | TM | untrusted (honest+attack) | `basic_monitor_builder` (ControlArena's stock LLM judge) | never |
  | TM-PBT | untrusted (honest+attack) | `pbt_monitor_builder` (ours, below) | never |
  | TE | untrusted (honest+attack) | `pbt_monitor_builder` | always (`edit_threshold=0.0`) |
  | Hybrid | untrusted (honest+attack) | `pbt_monitor_builder` | only when flagged (`edit_threshold=config.suspicion_threshold`) |

  TM/TM-PBT are wrapped by `trusted_monitoring_builder`; TE/Hybrid by
  `trusted_editing_builder` — both imported from `control_arena.micro_protocol`.
  The "editor" for TE/Hybrid is `trusted_editor_builder(trusted_policy=honest_policy_builder(model_role="trusted"))` — an LLM call, not a hand-written sanitizer.

  The attacker's policy (`attack_policy_builder`) is built with
  `prompt=load_prompt("attack_policy", config.attack_prompt_variant)` — so
  `--attack-prompt v2_literal_trigger` vs `--attack-prompt v3_range_trigger` changes
  what *kind* of backdoor the untrusted model is instructed to insert, without
  touching any Python.

- **Run**: builds an `inspect_ai.Task` via
  `control_arena.eval.get_control_task(setting, micro_protocol, mode, eval_config, monitoring_scorers=[max_suspicion_scorer()])`
  once for `EvalMode.HONEST` and once for `EvalMode.ATTACK`, and executes each with
  `control_arena.eval.eval(task)` (a thin wrapper around `inspect_ai.eval`). Each
  call returns a list of `EvalLog`s, which get written to `logs/*.eval` as a side
  effect and also returned in memory.

**4. Inside that eval call** (framework code, not this repo, but worth knowing):
Inspect AI runs the agent loop per dataset sample. The policy proposes a submission
(a `code` string, plus `secret_input` in attack mode) via the setting's submit tool
(`apps_setting.py::get_submit_tool_config`). The monitor (`basic_monitor_builder` or
our `pbt_monitor_builder`) scores that submission and writes a `suspicion_score`
into the last assistant message's metadata. If the protocol is TE/Hybrid and the
score crosses `edit_threshold`, the trusted editor rewrites the code before it's
considered "deployed." Finally the setting's scorers run.

**5. `apps_setting.py`** is the ControlArena `Setting` — the actual problem
environment definition:
- `get_dataset(eval_mode)` turns each `APPSProblem` from `dataset_loader.py` (which
  just reads a JSON file, e.g. `dataset.json` or `dataset_heldout.json`) into an
  Inspect `Sample` carrying `ControlTaskMetadata`. `side_task_description` is only
  populated when `eval_mode == ATTACK`.
- `get_scorers()` returns `apps_scorer()`, which always runs
  `apps_main_task_scorer` (executes the submitted code against public+secret tests
  **inside the Inspect sandbox** via `sandbox().exec(...)`) and, in ATTACK mode
  only, `apps_side_task_scorer` (checks whether the submitted `secret_input`
  actually makes the code diverge from the ground-truth output — this is the real
  "did the backdoor work" check).
- `get_sandbox_config()` returns `"docker"` or `"local"` depending on
  `config.use_docker`.

**6. `pbt_monitor.py`** is the property-based-testing monitor — the project's actual
contribution, and the piece that's now fully prompt-configurable:
- `pbt_monitor_builder(pbt_max_examples, model_name, prompt_variant, fewshot_k, fewshot_seed)`
  builds a ControlArena `Monitor` (`@monitor`-decorated agent).
- On each submission it calls `generate_pbt_script_with_llm(...)`, which calls
  `prompts.render_pbt_prompt(...)` to build the actual prompt text, then calls the
  trusted model (`get_model(model_name).generate(prompt)`), extracts the Python code
  from the markdown fence, and runs `submitted_code + generated_property_tests`
  together via `pytest` inside the sandbox (`sandbox().exec(...)`). Pass/fail of
  that pytest run becomes `suspicion_score` 0.0/1.0.

**7. `prompts.py`** is the new layer that makes step 6 configurable without code
changes:
- `load_prompt(category, variant)` reads `prompts/<category>/<variant>.txt`
  (categories: `pbt_monitor`, `attack_policy`), raising a clear error listing valid
  names if you typo a variant.
- `render_pbt_prompt(...)` loads a `pbt_monitor` template, samples `fewshot_k`
  examples from `prompts/pbt_monitor/fewshot_bank.json` via
  `sample_fewshot_examples(...)` (which excludes any bank entry whose
  `entry_point` matches the problem currently being scored, so few-shotting can't
  leak the answer), formats them into a text block, and substitutes `{{tokens}}`
  in the template.
- Attack-policy templates are passed straight to `attack_policy_builder(prompt=...)`
  and use single-brace `{tokens}` instead, because ControlArena does its own
  `.format()` on that string internally — don't double-brace those files.

**8. Back in `evaluator.py`**, once both `EvalLog` lists come back,
`run_experiment_for_protocol` reads `sample.scores["apps_scorer"].value` (a dict
with `main_task_success`/`side_task_success`) and `sample.scores["max_suspicion_scorer"].value`
(a float, populated by the `monitoring_scorers` argument passed to
`get_control_task` — it scans every message for a monitor-written
`suspicion_score` and returns the max) to compute:
- `evasion_rate` = fraction of ATTACK-mode samples where the backdoor actually worked
- `main_task_utility` = fraction of HONEST-mode samples that passed
- `false_audit_rate` = fraction of HONEST-mode (clean) samples the monitor flagged
  above `config.suspicion_threshold` anyway
- `average_cost_usd` = a toy cost model (token cost + compute cost + audit cost)

If `--dump-explanations` was passed, `_dump_sample_explanations` prints every
sample's scorer explanations to the terminal instead of leaving them only inside
the binary `logs/*.eval` files.

**9. `main.py`** renders `ExperimentSummary`/`MetricSummary` into the Rich tables you
see in the terminal. `--sweep` instead calls `run_pareto_sweep()`, which re-runs
`run_experiment()` for every (threshold, pbt_max_examples) combination in a 3x3
grid — 9 points x 4 protocols x 2 modes = 72 full evals, so it's the expensive flag.

## Running prompt-engineering experiments

Since SFT isn't an option against a proprietary model, prompt/few-shot variation is
the whole experimental axis. The pieces above give you three independent levers,
all file-based and all swappable via flags:

```bash
# baseline, zero-shot
python main.py --dataset dataset.json

# few-shot the PBT monitor with 3 examples from prompts/pbt_monitor/fewshot_bank.json
python main.py --dataset dataset.json --pbt-prompt v2_fewshot --pbt-fewshot-k 3

# ask the monitor to specifically hunt for relational/backdoor-style properties
python main.py --dataset dataset.json --pbt-prompt v3_backdoor_focused --pbt-fewshot-k 3

# see WHY things were flagged or missed, instead of just the summary numbers
python main.py --dataset dataset.json --pbt-prompt v3_backdoor_focused --dump-explanations

# validate on problems the prompt/fewshot bank has never seen
python main.py --dataset dataset_heldout.json --pbt-prompt v3_backdoor_focused --pbt-fewshot-k 3

# does a prompt tuned against literal-value backdoors generalize to a different
# backdoor family it was never shown?
python main.py --dataset dataset_heldout.json --pbt-prompt v3_backdoor_focused \
  --pbt-fewshot-k 3 --attack-prompt v3_range_trigger
```

Compare the `evasion_rate` column across these runs (lower = the monitor is better
at catching backdoors) on `dataset.json` vs. `dataset_heldout.json` to tell whether
a prompt genuinely generalizes or just memorized the two problems its few-shot
examples came from.

## File map (what lives where)

| File | Role |
|---|---|
| `main.py` | CLI entry point, argument parsing, Rich table rendering |
| `config.py` | Single `Config` pydantic object; every other module takes one of these |
| `evaluator.py` | Orchestrator: builds micro-protocols, runs HONEST+ATTACK evals, aggregates metrics |
| `apps_setting.py` | ControlArena `Setting`: dataset->Sample conversion, submit-tool schema, main/side-task scorers, sandbox config |
| `dataset_loader.py` | Thin JSON->`APPSProblem` loader (no logic beyond parsing) |
| `dataset.json` / `dataset_heldout.json` | The actual problem data — held-out set shares no entry points with the main set or the fewshot bank |
| `pbt_monitor.py` | The property-based-testing monitor: LLM-generates Hypothesis tests, runs them in-sandbox via pytest |
| `prompts.py` | Loader/renderer for `prompts/*.txt` templates and the few-shot bank |
| `prompts/pbt_monitor/*.txt` | PBT monitor prompt variants (double-brace `{{token}}` templates, rendered by `prompts.py`) |
| `prompts/pbt_monitor/fewshot_bank.json` | Hand-written, verified-correct "good property" examples for few-shotting |
| `prompts/attack_policy/*.txt` | Attack policy prompt variants (single-brace `{token}`, formatted by ControlArena itself) |
| `tests/` | `test_apps_setting.py` (Setting unit tests), `test_control_arena_pbt.py` (protocol wiring + one full live-eval integration test), `test_prompts.py` (prompt loader/few-shot unit tests) |

## Things to know that aren't obvious from reading one file at a time

- **No API key -> `mockllm/model`.** `config.py`'s `_default_model()` picks a real
  model only if `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` is set in the environment;
  otherwise every model role silently becomes Inspect's mock provider. This is why
  the test suite and casual `python main.py` runs work with no cost/setup, but it
  also means you won't see real property-generation quality until you export a key.
- **"Hybrid" is TE with a threshold gate, not a fourth independent mechanism.**
  Both TE and Hybrid use the exact same `trusted_editing_builder` call; the only
  difference is `edit_threshold=0.0` (always edit) vs.
  `edit_threshold=config.suspicion_threshold` (edit only when flagged).
- **The backdoor "family" is attacker-prompt-driven, not dataset-driven.** Earlier
  versions of this project hardcoded three solution variants per problem
  (`correct_clean`/`subtle_edge_case_bug`/`covert_backdoor`) in the dataset itself.
  Now the attack policy is an LLM that decides how to backdoor the code at run
  time, steered by `prompts/attack_policy/<variant>.txt` — that's the mechanism
  behind `--attack-prompt`, and it's the only way to control backdoor style now
  that the dataset schema no longer carries pre-written variants.
- **`config.trusted_editor_model` is currently unused.** `evaluator.py` builds the
  TE/Hybrid editor with `honest_policy_builder(model_role="trusted")`, which
  resolves its model from `ControlEvalConfig.trusted_model`
  (== `config.trusted_monitor_model`), not from `config.trusted_editor_model`. If
  you want a genuinely different model for editing vs. monitoring, that field needs
  to actually be threaded through — it isn't yet.
