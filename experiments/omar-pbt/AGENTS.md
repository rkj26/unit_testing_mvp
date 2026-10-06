# Agent guide

## Purpose and working directory

This directory is an archival wrapper for a completed PBT experiment snapshot, not a general-purpose launcher. The frozen project is `snapshot/`; follow QUICKSTART to create a disposable `local-work/snapshot/` copy and use that copied project root for commands because imports and run paths depend on CWD. The wrapper's `verify_snapshot.py` is run from this directory against the original archive.

Read `QUICKSTART.md` before reproduction work and `README.md` for the study index and interpretation. The snapshot's own `snapshot/AGENTS.md` describes its historical project workflow; it is context, not authorization to launch a study. In particular, its smoke command describes paid work and does not authorize model calls now.

## Preserve the archive

- Treat `snapshot/` and its published inputs/results as frozen. Do not edit snapshot source, notebooks, provenance, or archived run artifacts as part of ordinary analysis or tests.
- For analyses that write derived files, make a disposable copy of the snapshot and keep outputs separate. The cached BCB notebooks can write under `runs/` as well as to their executed notebook output; follow the QUICKSTART's documented destinations.
- Never reuse an archived run name, delete or bypass a launch lock, or remove request/lock artifacts to retry a stage. Missing cached inputs are missing measurements: stop and request the artifact; do not substitute a new model call or report zero.
- Preserve secrets. Keep credentials only in a local untracked `.env`; never paste them into tracked files, notebooks, reports, chat, or commits.
- Do not commit or push unless explicitly requested.

## Paid calls and execution

Default to offline work. Cached analysis and focused tests are not permission for fresh provider calls. Any fresh model run requires explicit authorization for that experiment and stage; then follow its preparation, frozen-population review, bounded smoke, result inspection, and separately approved full-stage gates in QUICKSTART and the specific notebook. Do not infer authorization from the old nested instructions, an enabled-looking cell, or existing credentials. Do not run candidate code on the host; reproduction instructions require the documented isolated, network-disabled runtime.

Never claim universal portability or bit-for-bit reproducibility. Dependencies are not fully locked, Windows has documented limitations, provider seeds are not guarantees, and some paths rely on archived absolute/path manifests. Report only checks actually performed in the current environment, distinguishing historical results from fresh validation.

## Focused verification

For the controlled SecondRevision diagnostic-visibility contract, the focused offline test is:

```powershell
Set-Location local-work/snapshot
$testTemp = Join-Path (Resolve-Path ..) ('pytest-' + [guid]::NewGuid().ToString('N'))
.venv\Scripts\python.exe -m pytest tests/test_second_revision.py::test_prompt_only_diagnostic_visibility_changes_and_no_hidden_fields -q --basetemp $testTemp
```

Use a validated project environment; Python 3.12.14 and 3.13.14 passed the documented focused checks.
This test is a narrow contract check, not validation of the full experiment. Run a broader test scope
only when the task calls for it; the full suite is not a default quick check and has historical
Windows-specific failures. State exactly which command ran and its result. Launch cached notebooks
with `python -m nbconvert`, not the PATH-dispatched `python -m jupyter nbconvert`.

The temporary path must be new and disposable: pytest can clear `--basetemp`. Never point it at the
workspace root or existing artifacts. The seven-case mock round-trip check and cached notebook
commands are in QUICKSTART.md; locally observed results and limitations are in QUICKSTART_VALIDATION.md.

For authorized resumption of a new study, inspect its saved records, active process, hashes, and
launch contract before invoking the documented resume mechanism. Never create a second worker for
the same pending stage, replay a recorded failure to improve results, or bypass a lock. If the
stage has no safe documented resume path, stop and request a decision.

## Interpreting results

Do not silently turn missing, failed, or incomplete measurements into clean outcomes or zeros. In particular, exclusions are not zero-valued observations, and an incomplete grid cannot establish a clean negative. Keep denominators, failures, and exclusion reasons visible; never describe an absent cache as a pass. Preserve model/deployment provenance and do not make claims about a model from metadata that the artifacts do not support.
