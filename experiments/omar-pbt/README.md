# Omar PBT experiment snapshot

This is the `rkj26/unit_testing_mvp` subproject branch `codex/omar-pbt-subproject`, based on `origin/main` at `e0ec76b715d9ae256efbf313e56849665add4f84`. Its `snapshot/` contains the tracked files from historical source branch `codex/omar-pbt-testing-results`, commit `507b0942c91f586f0a3e0375751d56f71cb93edc`. This is a branch-only archival wrapper: it leaves the repository’s main-root files untouched and is not intended for a pull request targeting `main`. The source tree remains authoritative; this branch makes the experiment snapshot inspectable and verifiable.

## Start with the research

- [Start here: local setup, focused tests, and cached results](QUICKSTART.md)
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

Follow QUICKSTART to create a disposable `local-work/snapshot/` copy, then run project commands from that copied project root—not from this wrapper or the parent repository. Imports and run paths depend on the working directory. The local copy and outputs are gitignored; the published `snapshot/` remains unchanged. Requirements are not fully locked, so this is not a promise of a standalone, bit-for-bit rerun; some absolute/path manifests may refer to the original checkout. Do not silently rewrite source artifacts here.

The supported quickstart runs focused offline tests and reproduces cached BCB analyses, without credentials or Docker. Fresh paid generation requires further adaptation: the historical notebook workers override Azure settings, the generic launcher uses Unix tools, and the study binds its original population and image. Installing successfully is not authorization or proof of readiness for a new paid run.

The published fixed inputs and reports are frozen. Paid model launches default to off and must remain off unless a separately authorized experiment explicitly enables them. A September 30, 2026 offline test run from this snapshot reported 63 passing tests and two known Windows-specific failures (SIGALRM and tmux limitations); it did not invoke paid models. This is validation of the test suite in this environment, not a claim that every reproduction path is portable.

On Windows, clone with `git -c core.longpaths=true clone ...` if needed, or use a shorter destination path. Preserve symlink targets when Git and the host support symlinks; some Windows checkouts may materialize the three documented links (`docs/guide.md`, `docs/pipeline.md`, and `docs/protocols.md`) as ordinary text files. Such checkout behavior can affect verification and should be investigated rather than “fixed” by changing source content.
