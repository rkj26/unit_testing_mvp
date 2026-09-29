# Property-based testing experiments

This repository contains the reproducible artifacts for the completed Azure PBT experiments led by Omar. “Omar” identifies the experiment set and its artifacts; it is not a claim that Omar originated the broader PBT idea.

The experiments ask whether model-written property-based tests can distinguish stored honest and backdoored APPS and BigCodeBench candidates. They are benchmark experiments, not evidence of deployment safety or a complete audit protocol. The verified experiment inventory, exact run settings, results, exclusions, and reproduction links are in [`docs/omar_pbt_experiment_index.md`](docs/omar_pbt_experiment_index.md).

## Start here

- [`docs/omar_pbt_experiment_index.md`](docs/omar_pbt_experiment_index.md) — concise inventory and interpretation of every completed study.
- [`docs/pbt_paper_methods_results.md`](docs/pbt_paper_methods_results.md) — research-paper draft covering methods, results, and limitations across the six studies.
- [`docs/pbt_experiment_methods_appendix.md`](docs/pbt_experiment_methods_appendix.md) — detailed experimental workflow, model inputs, and reproduction entry points.
- [`docs/omar_bcb_meeting_report.md`](docs/omar_bcb_meeting_report.md) — results covering the 26-task BigCodeBench A/B/C replication and delete-only ablation.
- [`docs/azure_pbt_training_results_2026-09-07.md`](docs/azure_pbt_training_results_2026-09-07.md) — exploratory training prompt comparison.
- [`docs/azure_pbt_heldout_results_2026-09-08.md`](docs/azure_pbt_heldout_results_2026-09-08.md) — frozen held-out single-turn comparison.
- [`docs/azure_pbt_multiturn_results_2026-09-09.md`](docs/azure_pbt_multiturn_results_2026-09-09.md) — exploratory execution-informed repair.
- [`docs/azure_pbt_multiturn_confirmatory_results_2026-09-14.md`](docs/azure_pbt_multiturn_confirmatory_results_2026-09-14.md) — fresh controlled A/B/C revision study.

The source notebooks live under [`notebooks/`](notebooks/). Their launch switches default to off; cached analysis can be rerun without paid model calls when the referenced run artifacts are present. Do not infer that a locally present report means every large runtime artifact is versioned: reports identify run names, hashes, and any gitignored caches explicitly.

Selected Azure PBT raw artifacts are now included: the published `runs/` subset contains the relevant `config.json` and `records.jsonl` files (plus selected JSON analysis/replay outputs) for the documented studies. The broader `runs/` tree remains generally gitignored; logs, locks, environment files, and `.hf_cache/` are intentionally excluded. Included artifacts are the source of truth for the reported run hashes and denominators.

For a code-to-method map, see the index. In brief: model identity/provenance is handled in [`pipeline/model.py`](pipeline/model.py), population/split construction in [`build_dataset.py`](build_dataset.py), original authoring in [`pipeline/protocols/unit_testing.py`](pipeline/protocols/unit_testing.py), training repair in [`pipeline/protocols/test_repair.py`](pipeline/protocols/test_repair.py), fresh matched control/feedback revisions in [`pipeline/protocols/second_revision.py`](pipeline/protocols/second_revision.py), and candidate execution in [`pipeline/sandbox.py`](pipeline/sandbox.py). Notebook cells perform the frozen metrics and replay analyses.

The design interpretation is documented in [`docs/omar_pbt_design_assessment.md`](docs/omar_pbt_design_assessment.md); the separate GLM connectivity check is [`docs/openrouter_glm_check_2026-09-17.md`](docs/openrouter_glm_check_2026-09-17.md).

## Reproducibility boundary

All studies used Azure deployment `gpt-5.6-terra` (the fresh confirmatory run records returned snapshot `gpt-5.6-terra-2026-07-09`), low reasoning, requested seed 300, and pinned Docker execution where documented. Provider seeds are requests, not guarantees of bit-for-bit regeneration. Labels are inherited from pool construction, inputs are targeted/generated and statement-reviewed, and the experiments retain failures and exclusions rather than turning missing measurements into clean negatives. See each report for exact denominators, hashes, model-call budgets, and known Windows/runtime incidents.
