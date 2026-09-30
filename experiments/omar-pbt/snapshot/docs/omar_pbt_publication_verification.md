# Branch publication verification — Omar Sufyan

Prepared 17 September 2026 for `codex/omar-pbt-experiments`. The team repository is `rkj26/unit_testing_mvp`; the authenticated account has read access but no push permission. The branch is published in `lStarryskyl/unit_testing_mvp`, its fork. No merge into the team main branch is requested or performed.

## Included artifacts

The four completed Azure PBT studies have their reports, prospective plans, notebooks, protocols, prompts, tests, exact datasets, and selected raw JSON/JSONL artifacts under `runs/azure-*`. This includes smoke and input-review records, failures, execution caches, manifests, model response records and derived metrics. Runtime logs, lock files, credentials, virtual environments, pytest scratch directories and the downloaded Hugging Face cache are excluded. Historical report wording about locally cached artifacts describes the state before this publication; the branch now includes the selected run artifacts.

## Verification

- Training replay, held-out replay, exploratory multi-turn and fresh confirmatory multi-turn notebooks all reproduced cached analyses with model/process/sandbox boundaries patched to raise. No new candidate execution or experiment call was needed.
- Two notebook preparation checks required provenance-aware handling: existing historical manifests are retained for cached analysis; current code/worker differences are reported, and new launches retain frozen-code protection. Neither stored measurements nor historical manifests were rewritten.
- Frozen confirmatory source hashes also match the staged Git blobs, not just the working directory. Git attributes preserve measured source/data bytes across checkout; some existing files therefore have line-ending-only diffs. A historical whitespace-only line in `pipeline/model.py` is preserved because the source is fingerprinted.
- Full pytest: 63 passed, two failed. Both are existing Windows incompatibilities: `signal.SIGALRM` in the trusted-solve harness test and missing `tmux` in the detached-launch test. This is not a fully passing cross-platform test suite.
- Dataset build smoke completed with three tasks/six candidates. The unrelated legacy paid DeepSeek smoke was not rerun.
- Staged files were checked for credential patterns and exact configured secret values; no matches were found. `.env` and `.hf_cache` are not staged.

The cached analyses were verified on the current Windows environment. Linux portability of every path-keyed historical manifest is not claimed. Dependencies remain as declared in `requirements.txt`; remote-model regeneration is not guaranteed to reproduce the saved responses bit for bit.

The separate free GLM connectivity attempt returned HTTP 429 and produced no experimental completion; see `openrouter_glm_check_2026-09-17.md`.
