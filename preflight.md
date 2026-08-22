# Pre-flight audit — `apps-22nd.ipynb`, before the first paid run

Four independent readers over the notebook, the prompt/parser contracts, the provider path and the
metric definitions; every finding then handed to a refuter. **29 raised, 20 survived, 9 refuted.**

Nothing here was found by running the notebook — it has still never been executed. These are all
static, and the ones marked *silent* are the ones that would have produced a number rather than a
crash.

| # | status | severity | where | what |
|---|---|---|---|---|
| 1 | fixed | blocks | notebook cell 10 | `MODEL = "DeepSeek-V3.2"` has no provider prefix |
| 2 | fixed | blocks | `pipeline/protocols/base.py` `main()` | nothing loads `.env`, so the tmux subprocess has no credentials |
| 3 | fixed | wrong number | notebook cell 41 | `TM_CUT = 0.889` excludes the fitted cut `8/9`; no train fit anywhere, `BUDGET` dead |
| 4 | fixed | wrong number | `unit_testing.py:42` | `max_connections=1` serialises all 8 workers onto one slot |
| 5 | fixed | wrong number | notebook cells 33 / 41 | an unjudged candidate is dropped in one table and scored not-caught in the other |
| 6 | fixed | wrong number | notebook cell 41 | strata table compares TM at a fixed cut against PBT at drifting strictness, with no FPR column |
| 7 | fixed | wrong number | `pipeline/parse.py:29` | longest fenced block, not the last python-tagged one |
| 8 | fixed | wrong number | notebook cells 24 / 31 | derived caches keyed on filename alone; a partial run bakes in silently |
| 9 | fixed | minor | notebook cell 28 | `suite_on` is dead code, so "fires on reference" — a stated prediction — is unscoreable |
| 10 | fixed | minor | notebook cell 50 | `"ut-without-property".replace("ut-", "")` → `"withoproperty"` |
| 11 | fixed | minor | notebook cell 30 | the agreement set is arm-invariant but recomputed per arm: 7 200 sandbox launches instead of 3 600 |
| 12 | fixed | minor | `prompts/example_audit_inputs_*.txt` | the `targets` sentence describes a schema `TriggerSearch` no longer uses |
| 13 | fixed | minor | `unit_testing.py:149` | one stray fence in any entry drops the other nine tests |
| 14 | **open** | minor | `base.py:292` | `pending()` counts an infra-failed record as scored, so a resume never retries it |

**#14 is left open deliberately.** The repo's own rule is that `blame="infra"` is noise to retry, so
the code contradicts it — but retrying appends a second record for a candidate that already has one,
and `load_records` keeps both, which double-counts it in every denominator. The honest fix is
"the record for a candidate is its latest attempt", and that is a change to the artifact contract,
not a patch. Mitigated for now: the status cell prints failed counts per blame, so an all-infra run
cannot read as a complete one.

## The two worth understanding, not just fixing

**#2 is a regression this rewrite introduced.** The deleted `probe.py` called `load_dotenv()` at its
line 1699. `base.main()` did not, and a tmux session started before the shell exported anything
inherits nothing — so `_require_azure_credentials` would have raised in `prepare()`, in the
subprocess, where the notebook sees `LaunchFailed` and not the reason.

**#3 is prose rounding turning into a different experiment.** `avg_score` is the mean over reps of
`(rating - 1) / 9`, so with `runs=2` it lands on an 18ths grid. The fitted operating point is
`8/9 = 0.888…`, written up as "cut 0.889". Read back as a float, `0.889 > 8/9`, and the grid has
nothing between `0.888889` and `0.944444` — so the cut admits only rep-pairs `(9,10)` and `(10,10)`.
The transcription silently tightened TM by a whole rating level, and `BUDGET = 0.10` sat defined and
unused two cells above. Fixed by fitting on train and printing the cut, which is what the notebook's
own standing-traps cell already demands.

## Refuted (9)

Claims that did not survive their refuter, kept so they are not re-raised: `data=` as a string path
is accepted by `Run.__init__`; `runs > 1` on `UnitTesting` is refused at construction, not silently;
`parse_search_space` does handle a trailing comma; the `outcome == "catch"` check is correct in both
the protocol and the notebook; `task.blind()` does not leak the reference; the arm prompt names do
resolve to real files.
