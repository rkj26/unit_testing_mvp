# Quickstart (Windows PowerShell)

This wrapper preserves a frozen experiment snapshot. Use a short checkout path on Windows; Git
long-path support is enabled for the clone only:

```powershell
$ErrorActionPreference = 'Stop'
git -c core.longpaths=true clone --branch codex/omar-pbt-subproject https://github.com/rkj26/unit_testing_mvp.git omar-pbt
if ($LASTEXITCODE -ne 0) { throw 'Clone failed; stop.' }
Set-Location .\omar-pbt\experiments\omar-pbt
```

If you already have this wrapper, start in its directory instead. Do not work directly in
`snapshot/`.

## Offline checks and cached analyses

You need Git, the Windows Python launcher (`py`), and installed Python 3.12 or 3.13.
Installation downloads dependencies but does not call a model. Commands below are for PowerShell,
not Command Prompt or Bash. Set `$ErrorActionPreference = 'Stop'` also when using an existing checkout.

Run these commands from the wrapper directory. Each step stops on failure; the snapshot stays
unchanged and all generated files remain under the gitignored `local-work/` directory.

1. Verify the archived snapshot:

   ```powershell
   py -3 verify_snapshot.py
   if ($LASTEXITCODE -ne 0) { throw 'Snapshot verification failed; stop.' }
   ```

2. Make a fresh disposable copy. This refuses to overwrite an existing destination; robocopy exit
   codes 0–7 are success/informational and 8 or higher means failure. The exclusions prevent copied
   credentials, environments, and caches from leaking into the run copy.

   ```powershell
   $source = (Resolve-Path .\snapshot).Path
   $work = Join-Path $PWD 'local-work'
   $copy = Join-Path $work 'snapshot'
   if (Test-Path $copy) { throw "Destination already exists: $copy. Choose a new disposable path." }
   New-Item -ItemType Directory -Force -Path $work | Out-Null
   robocopy $source $copy /E /R:1 /W:1 /XD .venv __pycache__ .pytest_cache .ipynb_checkpoints /XF .env
   if ($LASTEXITCODE -ge 8) { throw "Snapshot copy failed (robocopy exit $LASTEXITCODE); stop." }
   Set-Location $copy
   ```

3. Create an isolated Python environment, install requirements with Git long paths scoped to this
   install process, and check dependencies. Python 3.12 or 3.13 is supported by the documented
   checks.

   ```powershell
   py -3.12 -m venv .venv
   # Or, if that is the installed interpreter: py -3.13 -m venv .venv
   if ($LASTEXITCODE -ne 0) { throw 'Environment creation failed; stop.' }
   $previousGitParameters = $env:GIT_CONFIG_PARAMETERS
   try {
       $env:GIT_CONFIG_PARAMETERS = "$previousGitParameters 'core.longpaths=true'".Trim()
       .venv\Scripts\python.exe -m pip install -r requirements.txt
       if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; stop.' }
   } finally {
       $env:GIT_CONFIG_PARAMETERS = $previousGitParameters
   }
   .venv\Scripts\python.exe -m pip check
   if ($LASTEXITCODE -ne 0) { throw 'pip check failed; stop.' }
   ```

4. Run the seven focused offline tests with a new workspace-local pytest temp directory. These are
   the visibility contract and six mock round-trip/resume cases, not the full suite.

   ```powershell
   $testTemp = Join-Path (Resolve-Path ..) ('pytest-' + [guid]::NewGuid().ToString('N'))
   .venv\Scripts\python.exe -m pytest -q --basetemp $testTemp `
     tests/test_second_revision.py::test_prompt_only_diagnostic_visibility_changes_and_no_hidden_fields `
     tests/test_second_revision.py::test_one_call_roundtrip_resume_and_exact_schema
   if ($LASTEXITCODE -ne 0) { throw 'Focused tests failed; stop.' }
   ```

5. Register a kernel explicitly inside this environment and run the three cached BigCodeBench
   (BCB) notebooks. Keep `local-work/snapshot/` as the current directory. These commands read archived results;
   they do not make model calls. The last notebook must keep `LAUNCH_REPLAY=False`.

   ```powershell
   .venv\Scripts\python.exe -m ipykernel install --sys-prefix --name omar-pbt-local
   if ($LASTEXITCODE -ne 0) { throw 'Kernel registration failed; stop.' }
   $env:IPYTHONDIR = Join-Path (Resolve-Path ..) 'ipython-profile'
   New-Item -ItemType Directory -Force ..\reproduced | Out-Null
   $notebooks = @(
     'azure_pbt_bcb_replay_analysis.ipynb',
     'azure_pbt_bcb_delete_analysis.ipynb',
     'azure_pbt_bcb_delete_replay.ipynb'
   )
   foreach ($notebook in $notebooks) {
       .venv\Scripts\python.exe -m nbconvert --to notebook --execute `
         --ExecutePreprocessor.kernel_name=omar-pbt-local `
         --ExecutePreprocessor.timeout=600 --output-dir ..\reproduced "notebooks/$notebook"
       if ($LASTEXITCODE -ne 0) { throw "Notebook failed: $notebook; stop." }
   }
   ```

Docker and API credentials are not needed for these cached analyses or focused tests. For what was
previously validated, including limitations, see [quick-start validation](QUICKSTART_VALIDATION.md).
Executed notebooks are in `local-work/reproduced/`; derived JSON may also be written inside the
copied `runs/` directory. Expected common A/B/C honest catches are **2/22, 4/22, 2/22** and attack
catches **21/21, 19/21, 19/21**. Baseline versus deletion gives **3/23 vs 3/23** honest catches and
**24/25 vs 21/25** attack catches. These are cached historical results, not new model measurements.
Dependencies are only partly pinned; successful local checks do not guarantee every future package
version or every protocol. This guide's commands were tested on Windows, not Linux/macOS.

## Fresh model generation is not turnkey

Do not create a `.env`, launch a notebook worker, or run a protocol based on this quickstart.
Although cached workflows are usable, the fresh-generation paths are not a generic launcher:

- Three notebook workers hardcode the original Azure endpoint and require
  `AZURE_OPENAI_API_KEY`, which conflicts with `.env.example`. Setting environment variables and
  launching them is not sufficient adaptation.
- The generic `Run.run()` uses `tmux` and Unix `env`, so it is not a native Windows launcher.
  The study notebooks use separate detached workers with OS-specific branches; their Windows
  success does not establish portability of the generic launcher.
- The historical 26/52 population prefixes, source hashes, launch locks, and recorded Docker-local
  image digest are coupled. Editing the dataset label or building a new image does not recreate
  that experiment.

Any future adaptation needs an explicitly approved study plan and stage, reconciled credentials and
endpoint configuration, a newly frozen population/source bundle, reviewed launch and lock/resume
behavior, and the correct isolated candidate runtime. Follow the [frozen replication plan](snapshot/docs/azure_pbt_bcb_replication_plan.md)
and the notebook-specific gates; do not treat this checklist as a claim that those paths are fixed.
Never run candidate code directly on the host. Cached results are not authorization for paid calls.

## Troubleshooting

| Symptom | What to do |
|---|---|
| Clone or dependency checkout fails on long paths | Use a short checkout path and the documented process-local `core.longpaths` setting. Do not change global Git configuration. |
| `local-work\snapshot` already exists | Stop and choose a new disposable destination; do not merge into or overwrite a prior run. |
| Robocopy exit code is 8 or higher | Stop; inspect the copy error and recreate only at a new empty destination. |
| `pip check` or a focused test fails | Stop and retain the output; do not proceed to notebook execution. |
| Pytest cannot create its default temp directory | Use the fresh GUID-named `--basetemp` command above. Never point it at existing artifacts; pytest may clear it. |
| Notebook cannot find its kernel | Re-run the explicit `ipykernel install --sys-prefix` command using this copy's `.venv` Python. |
| `python -m jupyter nbconvert` uses the wrong Python | Use `.venv\Scripts\python.exe -m nbconvert` exactly as above. |
| A cached artifact or notebook input is missing | Stop and request the missing artifact. Do not substitute a new model call or treat absence as zero. |

For the study index and interpretation, see [README](README.md). The archive is frozen: preserve
its source, notebooks, provenance, and run artifacts; do not commit or push without explicit request.
