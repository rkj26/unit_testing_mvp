# Omar PBT experiment snapshot

This is the `rkj26/unit_testing_mvp` subproject branch `codex/omar-pbt-subproject`, based on `origin/main` at `e0ec76b715d9ae256efbf313e56849665add4f84`. Its `snapshot/` contains the tracked files from historical source branch `codex/omar-pbt-testing-results`, commit `507b0942c91f586f0a3e0375751d56f71cb93edc`. This is a branch-only archival wrapper: it leaves the repository’s main-root files untouched and is not intended for a pull request targeting `main`. The source tree remains authoritative; this branch makes the experiment snapshot inspectable and verifiable.

## Start with the research

- [Start here: local setup, focused tests, and cached results](QUICKSTART.md)
- [Preferred BCB path: one-image four-call smoke](container/README.md)
- [Researcher runbook: independently reproduce the BCB arms](REPRODUCING_EXPERIMENTS.md)
- [AI-agent startup instructions](AGENTS.md) ([Agent.md entrypoint](Agent.md))
- [Local quick-start validation](QUICKSTART_VALIDATION.md)
- [Experiment index](snapshot/docs/omar_pbt_experiment_index.md)
- [Paper draft](snapshot/docs/pbt_paper_methods_results.md)
- [Methods appendix](snapshot/docs/pbt_experiment_methods_appendix.md)
- [BigCodeBench results](snapshot/docs/omar_bcb_meeting_report.md)

The index links the individual reports, notebooks, and retained run artifacts. The separate GLM connectivity check is not an experiment and supports no GLM performance claims.

## Verify the frozen snapshot

Run the verifier from this directory. It reads only the listed snapshot files and the provenance manifest; it does not call models, Docker, or the network.

```powershell
py -3 verify_snapshot.py
```

`PROVENANCE.json` records each included source Git blob by path, mode, and blob ID, as well as the deliberately omitted `.claude/worktrees/pbt-validator-order-fix` gitlink. The verifier hashes file bytes as Git blobs, processing large files in chunks, and prints a compact JSON summary with missing/mismatched paths. GitHub may display warnings for files over 50 MB; those warnings are not evidence of corruption.

## Reproduction boundary

The preferred first live BCB check is the unified image's four-call component smoke in [container/README.md](container/README.md). It runs on one frozen candidate with Terra and a USD 1 buffered-cost ceiling; it is not a population result. This smoke passed for `BCB121_honest`: four calls, all four arms executed ten tests over nine fixed inputs (90/90 passing outcomes), and D retained an exact ten-test subset. Buffered usage was USD 0.258928; USD 0.129464 calculated from reported tokens and published rates is an estimate, not an invoice. This does not validate a full paid study or population rates. Build one `omar-pbt:0.2.0` image and use its immutable image ID for the smoke and any separately authorized full study. The full-study CLI has per-stage `--max-calls` ceilings but no dollar cap; set and authorize a separate external spend budget before paid batches. The older manual notebook route is separate ([REPRODUCING_EXPERIMENTS.md](REPRODUCING_EXPERIMENTS.md)); neither route edits the frozen `snapshot/`.

For local notebook inspection and the original cached notebooks, follow QUICKSTART to create a disposable `local-work/snapshot/` copy, then run project commands from that copied project root—not from this wrapper or the parent repository. Imports and run paths depend on the working directory. The local copy and outputs are gitignored; the published `snapshot/` remains unchanged. The snapshot's requirements are only partly pinned; some absolute/path manifests may refer to the original checkout. Do not silently rewrite source artifacts here.

The combined image built locally, its network-disabled cached analysis completed, the final runner test suite passed (30 tests in 36.29 seconds), and a real Docker preflight plus one saved BCB replay passed on Windows Docker Desktop (Linux containers): 100/100 replay outcomes matched. The four-call paid component smoke also passed as described above. These checks do **not** validate full paid batches, a full independent study, other host configurations, or a registry image. See [container validation](container/VALIDATION.md). Runner Python packages are locked; candidate top-level packages are pinned, while candidate transitive and OS packages are recorded but not fully pinned. The preferred source delivery is the existing GitHub branch; building/installing does not authorize paid calls.

The published fixed inputs and reports are frozen. Paid model launches default to off and must remain off unless a separately authorized experiment explicitly enables them. A September 30, 2026 offline test run from this snapshot reported 63 passing tests and two known Windows-specific failures (SIGALRM and tmux limitations); it did not invoke paid models. This is validation of the test suite in this environment, not a claim that every reproduction path is portable.

On Windows, clone with `git -c core.longpaths=true clone ...` if needed, or use a shorter destination path. Preserve symlink targets when Git and the host support symlinks; some Windows checkouts may materialize the three documented links (`docs/guide.md`, `docs/pipeline.md`, and `docs/protocols.md`) as ordinary text files. Such checkout behavior can affect verification and should be investigated rather than “fixed” by changing source content.
