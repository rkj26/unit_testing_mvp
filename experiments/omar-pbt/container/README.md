# Container runner guide

The runner is version **0.2.1**. Build one local image from the wrapper repository root; there is
no published image. The preferred first paid check is a bounded, four-call component smoke, not a
full study. It reuses one frozen BigCodeBench (BCB) candidate and must not be reported as a
population result. Full staged replication is documented separately below and is never started
automatically by the smoke.

## Versioned startup fix: self-contained test functions

Version 0.2.1 defaults the `smoke` command to `--test-contract self-contained-v1`.
It explicitly tells A/B/C that tests execute separately from candidate code, so each test must
include its own imports and helpers. Both rewrite arms receive identical added instructions;
delete-only still selects exact original functions and does not rewrite them. Prompts as sent,
the contract version/hash, and static missing-name diagnostics are saved in the smoke artifacts.
The runner never silently inserts imports, weakens tests, or retries a failed generation.

The delete-only validator also checks exact function text and original order, not line numbers.
Deleting an earlier function can shift later lines without changing the retained tests.

This is a **new startup prompt condition**, not the original paper experiment. Use
`--test-contract legacy` to repeat the original smoke contract. The separate full-study `run`
commands and frozen `snapshot/` continue using their original prompts; the new contract is not
silently applied to those experiments. Missing-name checks are supplementary, not a substitute
for executing generated tests in Docker. A failed baseline blocks all three dependent calls.

An uncached Windows build exposed why this matters: a raw model response used `pd` without
importing pandas. Pandas was installed, and the parser preserved the response correctly.
The failed record remains preserved; successful earlier smokes do not guarantee every future
model generation will be usable.

## What is inside, and what do I install once?

There is one combined runner/candidate image, not a runner image plus a separately rebuilt image
for each arm:

| Component | Contains / does | Does not contain |
|---|---|---|
| `omar-pbt:0.2.1` | Python 3.12, locked runner packages, Docker CLI, frozen project code/prompts/data/results, staged CLI, and isolated candidate Python at `/opt/bcb-venv/bin/python` | Model weights, your API key, or a running Docker daemon |

Install Git and Docker with Linux-container support on the host, get this subproject's source,
then build the one image below. You do **not** install host Python or rebuild an image for each arm.
This guide, the config template, and tests live in the source checkout; they are not a graphical
installer inside the image. An API deployment is a remote service, not bundled into Docker.

For the bounded component smoke, build once, fill config/credentials, and invoke `smoke` once with
a fresh output path and explicit cost cap. Full runs use a separate init/preflight and
smoke/approval workflow. Both use the same image and frozen inputs.

## Settings and placeholders

| Setting | Where | What to enter |
|---|---|---|
| `prefix` | `study.json` copied from `container/study.example.json` | A unique lowercase name, e.g. `smoke-<new-guid>`; choose a new one for every fresh smoke/study |
| `model` | `study.json` | `openai-api/azureai/gpt-5.6-terra` (required by the four-call smoke) |
| `docker_image` | `study.json` | The full immutable ID of the one locally built `omar-pbt:0.2.1` image |
| `AZUREAI_BASE_URL` | Local, ignored `paid.env` | Your resource URL ending in `/openai/v1`, **not** `/openai/v1/responses` |
| `AZUREAI_API_KEY` | Local, ignored `paid.env` | Your key; never include it in source or an image |
| `$ResultsPath`, `$ConfigPath`, `$PaidEnvPath` | PowerShell helper below | Local paths; the example resolves them from your current wrapper directory |
| `--max-cost-usd` | Four-call smoke | Buffered cost ceiling, at most USD 1; not an invoice guarantee |
| `--max-calls` | Full paid stages | Logical-call ceiling only; there is no full-run dollar cap |

The Azure deployment named `gpt-5.6-terra` must exist and accept requests; the config only names
it and does not prove access. The runner reads `model` from `study.json` and expects `AZUREAI_*`
credential names, so `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_ENDPOINT` alone are insufficient.
Use the same Terra deployment for all smoke arms and matched A/B/C full-study arms; do not silently
fall back or switch models midway. Use a new prefix/output for every fresh smoke; never alter an
initialized study's config.

## Preferred first paid check: one-candidate four-call smoke

The smoke executes one candidate (`BCB121_honest`) through four connected components: baseline
test generation, no-feedback revision, feedback revision, and delete-only selection. It runs a
Docker preflight automatically and permits at most four provider requests, one per arm, with HTTP
retries disabled. The runner enforces `--max-cost-usd` from a conservative token-byte reserve using
buffered rates; USD 1 is the maximum accepted cap. This is a budget guard, not a guaranteed Azure
invoice amount.

From the wrapper root, build the unified image once and inspect its immutable ID:

```powershell
docker build -f container/Dockerfile -t omar-pbt:0.2.1 .
$imageId = (docker image inspect omar-pbt:0.2.1 --format '{{.Id}}').Trim()
if ($LASTEXITCODE -ne 0 -or $imageId -notmatch '^sha256:[0-9a-f]{64}$') { throw 'Could not inspect the unified image; stop.' }
```

Copy the config template, use Terra, give it a fresh lowercase prefix, and insert `$imageId` as
`docker_image`. Create a fresh, empty results directory and a protected local `paid.env` with
`AZUREAI_BASE_URL=https://<your-resource>.services.ai.azure.com/openai/v1` and
`AZUREAI_API_KEY=<your-key>`. Never put the key in the config, shell command, source, or image.
The URL must end in `/openai/v1`, not `/openai/v1/responses`.

```powershell
Copy-Item container/study.example.json .\smoke-study.json
$study = Get-Content -Raw .\smoke-study.json | ConvertFrom-Json
$study.prefix = 'smoke-' + [guid]::NewGuid().ToString('N')
$study.model = 'openai-api/azureai/gpt-5.6-terra'
$study.docker_image = $imageId
[IO.File]::WriteAllText((Resolve-Path .\smoke-study.json).Path,
    ($study | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
$imageId = $study.docker_image
New-Item -ItemType Directory -Force .\results | Out-Null
$ResultsPath = (Resolve-Path .\results).Path
$ConfigPath = (Resolve-Path .\smoke-study.json).Path
$PaidEnvPath = (Resolve-Path .\paid.env).Path
```

After explicit authorization for this four-call, at-most-USD-1 smoke, invoke it once with a new
output directory (the `smoke-*` prefix above can also name the output):

```powershell
$SmokeId = $study.prefix
docker run --rm `
  --mount "type=bind,source=$ResultsPath,target=/results" `
  --mount "type=bind,source=$ConfigPath,target=/config/study.json,readonly" `
  --mount 'type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock' `
  --env-file $PaidEnvPath `
  $imageId smoke --output "/results/$SmokeId" `
  --config /config/study.json --allow-paid --max-cost-usd 1 --test-contract self-contained-v1
if ($LASTEXITCODE -ne 0) { throw 'Smoke failed. Keep the saved results and lock; inspect them before any new paid run.' }
```

The socket is mounted only into the trusted runner (Docker access is host-root-equivalent); use a
dedicated disposable Docker host. Candidate execution is isolated in child containers with no
network, no keys/socket/host mounts, bounded resources/time, and the image's `/opt/bcb-venv`.
### Where results are saved automatically

The command above saves to `results/<SmokeId>/` on **your computer**, not just inside Docker.
You do not need to copy files out of the container. `--rm` removes the container, not this folder.
Keep the `--mount ... target=/results` option in the command.

| File / folder | Saved when | Contains |
|---|---|---|
| `study.json`, `manifest.json`, dependency inventories | During initialization, before paid calls | Configuration, code hashes, environment versions |
| `attempts.jsonl` | Before each paid call | Request reservation and prompt hash |
| `usage.jsonl` | After each returned response | Model metadata, token usage, buffered cost |
| `components/` | Configuration before each arm; results after it finishes | Prompts, responses, generated tests, execution outcomes |
| `component-source-bundle.json` | After a usable baseline | Shared baseline, inputs, and feedback used by later arms |
| `smoke-results.json` | On completion or a handled run failure | Arm results, completion status, error information, cost accounting |

Read the summary after the command returns:

```powershell
Get-Content (Join-Path $ResultsPath "$SmokeId/smoke-results.json") -Raw | ConvertFrom-Json |
  Select-Object completed, attempts, accounted_usd_at_buffered_rates, error_type, error
```

A forced shutdown can leave no final summary or an unfinished response. Previously saved files
remain; the attempt ledger does not prove that a response finished. Do not delete locks or rerun
into that folder. The four-call smoke does not support automatic retries/resumption. A separately
authorized new attempt needs a new prefix and output folder. Saving is automatic; external backup
and GitHub upload are not. Full studies similarly save beneath their chosen host output folder.

**Interpretation boundary:** the component binds baseline/revision calls to only `BCB121_honest`;
it intentionally does not exercise the full `SecondRevision.prepare` population/linkage gate. It
is not a full 52-candidate run, a fresh sample, or a basis for FPR/catch-rate/population claims.
Version 0.2.1 passed two fresh four-call smoke runs: 360/360 execution pairs passed in each run,
and delete-only retained all ten tests in both. The provider reported
`gpt-5.6-terra-2026-07-09`. All 42 runner regression tests also passed inside the image.
These are startup checks, not evidence that one arm improves population FPR or attack detection.
See [the existing validation record](VALIDATION.md) for failures, costs, and image identity.

## How the individual arms start

After the common setup and preflight, the following are the actual CLI stages. The full commands
and human approval steps appear below; this table is a map, **not permission to run paid batches**.

| Arm / step | Smoke stage | Full stage | Prerequisite |
|---|---|---|---|
| A: generate original tests | `baseline-smoke` (up to 1 call) | `baseline` (up to 51 remaining calls) | Successful preflight; full stage also needs reviewed smoke approval |
| Build execution-feedback bundle | None; zero calls | `feedback` | Completed baseline batch |
| B: rewrite without feedback | Part of `revision-smoke` | Part of `revisions` | Completed feedback bundle |
| C: rewrite with feedback | Part of `revision-smoke` | Part of `revisions` | Same source suite and bundle as B |
| D: retain/delete original tests only | `delete-smoke` (up to 1 call) | `delete` (up to 51 remaining calls) | Completed feedback bundle and revision batch |
| Honest-twin replay and report | Zero calls | `replay`, then `analyze` | Completed A/B/C; includes D if it was run |

B and C are deliberately **paired in one command**: `revision-smoke` permits up to two calls
(one per arm); `revisions` permits up to 102 remaining calls across both. They still produce
separate `<prefix>-no-feedback` and `<prefix>-feedback` run directories. There is currently no
separate B-only or C-only CLI switch. A and D have their own commands. The `feedback` stage is
source-diagnostic preparation, not the C model-generation arm. D selects from A's original tests,
not from the rewritten tests, even though the current orchestration waits for revisions first.

The stage-level smokes below are components of the **full-study sequence**, not the four-call smoke
above: revisions require a complete baseline, and deletion requires completed revisions. Never run
full batches merely to satisfy a request for the bounded one-candidate smoke.

## How repeatable is startup today?

The intended normal path is configuration, not editing Python. Build/setup issues found during
local validation were fixed. The current 42-test suite and two fresh four-call smokes passed.
Earlier checks also passed cached analysis, real Docker preflight, and an archived 100-outcome replay; see
[VALIDATION.md](VALIDATION.md). These checks do not establish a full paid end-to-end study. The
local image is not published to a registry.
Different Docker hosts and Azure resources still need checks.

Routine reruns should reuse the same immutable image with a new output directory and prefix.
Do not rebuild per arm or alter prompts to make a smoke pass. Missing deployment/credentials,
incomplete outputs, or a failed-stage lock require diagnosis; do not delete locks or automatically
retry paid calls. Completed stages may be rerun as validated no-ops. A failed stage is not claimed
to have generic automatic recovery. This is a tested local research runner, not yet a promise of
one-click, maintenance-free deployment on every teammate's device.

## Build the unified image

Build once from the wrapper root. The Dockerfile installs the locked runner dependencies and the
BCB execution environment at `/opt/bcb-venv/bin/python`, records system package versions, and
verifies the archived source snapshot. OS packages are recorded but not fully version-pinned.

```powershell
docker build -f container/Dockerfile -t omar-pbt:0.2.1 .
docker image inspect omar-pbt:0.2.1 --format '{{.Id}}'
```

Use the full `sha256:...` ID, not the tag, as `docker_image`. Keep the locally built image for all
arms; do not build a second candidate image or rebuild per arm. This single combined image is a
different runtime artifact from the historical recorded `omar-bcb-pbt@sha256:fd7deb31…` image.
No container-registry image is published; source changes belong on the existing GitHub branch.

## Cached analysis

Cached analysis is read-only with respect to the frozen study, needs no credentials or Docker
socket, and writes `metrics.json` to the chosen output directory. Mount a fresh host directory at
`/results`; the runner's output directory must be empty.

```powershell
New-Item -ItemType Directory -Force .\results\cached | Out-Null
$CachedPath = (Resolve-Path .\results).Path
docker run --rm --network none `
  --mount "type=bind,source=$CachedPath,target=/results" `
  omar-pbt:0.2.1 cached --output /results/cached
```

## Fresh, staged workflow

Fresh runs require a new output folder and config. Make a copy of `container/study.example.json`
and review its three fields: choose a new lowercase `prefix` (never the archived prefix),
keep the configured Terra `model` for this study, and enter the full immutable
`docker_image` ID from the unified-image build above. Never put credentials in this config.
For example, from the wrapper root:

```powershell
Copy-Item container/study.example.json .\study.json
New-Item -ItemType Directory -Force .\results | Out-Null
# Edit .\study.json now; give it a new prefix, your deployment, and the inspected image ID.
```

The runner needs access to a Docker daemon to create candidate containers. This is highly
privileged—Docker socket access is effectively host-root access. Use a dedicated disposable Linux
VM or similarly isolated host, not a workstation containing valuable data or credentials. The
commands below assume a Linux Docker host with `/var/run/docker.sock`; this socket mount passed
the zero-API preflight and one archived replay on Windows Docker Desktop using Linux containers.
Other Docker configurations still need their own preflight. The socket is mounted only
into the trusted runner, never into candidate containers. Candidate execution uses disposable
containers with network disabled, no keys, resource/time limits, and streamed code (not host
bind mounts). The trusted runner itself retains outbound network access for approved Azure calls.

Only when ready to authorize a paid stage, create an untracked local `paid.env` containing these
two values (the example endpoint shown here is a placeholder):

```text
AZUREAI_BASE_URL=https://<your-resource>.services.ai.azure.com/openai/v1
AZUREAI_API_KEY=<your-key>
```

Protect that file, keep it outside version control, and use `--env-file` only for paid stages. Do
not pass either value to candidate containers. In PowerShell, after creating the config, empty
output directory, and `paid.env`, define this helper from the wrapper root:

```powershell
$ResultsPath = (Resolve-Path .\results).Path
$ConfigPath = (Resolve-Path .\study.json).Path
$PaidEnvPath = Join-Path $PWD 'paid.env'
$configuredImage = (Get-Content -Raw $ConfigPath | ConvertFrom-Json).docker_image
$inspectedImage = (docker image inspect $configuredImage --format '{{.Id}}').Trim()
if ($LASTEXITCODE -ne 0 -or $inspectedImage -ne $configuredImage) { throw 'Configured immutable image ID is not available locally; stop.' }

function Invoke-PbtRunner {
    param(
        [Parameter(Mandatory)][string[]]$RunnerArgs,
        [switch]$Paid
    )
    $DockerArgs = @(
        'run', '--rm',
        '--mount', "type=bind,source=$ResultsPath,target=/results",
        '--mount', "type=bind,source=$ConfigPath,target=/config/study.json,readonly",
        '--mount', 'type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock'
    )
    if ($Paid) {
        if (-not (Test-Path $PaidEnvPath)) { throw 'Create protected paid.env before requesting a paid stage.' }
        $DockerArgs += @('--env-file', $PaidEnvPath)
    } else {
        $DockerArgs += @('--network', 'none')
    }
    $DockerArgs += @($configuredImage) + $RunnerArgs
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Runner exited with code $LASTEXITCODE; inspect status and artifacts before proceeding." }
}
```

This helper runs one stage per container invocation and mounts results back to the host so you can
inspect them. The config mount and Docker socket are not needed for cached analysis. Create a
genuinely new, empty `results` folder for each study. Run the commands in
order; each smoke/approval boundary is an intentional human pause:

```powershell
# Initialize a separate study copy; no model calls.
Invoke-PbtRunner @('init', '--output', '/results/study', '--config', '/config/study.json')

# Required infrastructure/image/input preflight; zero model calls, but uses the Docker socket.
Invoke-PbtRunner @('run', '--output', '/results/study', '--stage', 'preflight')
Invoke-PbtRunner @('status', '--output', '/results/study')

# Baseline smoke: at most 1 paid call. Inspect its saved record before approving.
Invoke-PbtRunner @('run', '--output', '/results/study', '--stage', 'baseline-smoke', '--allow-paid', '--max-calls', '1') -Paid
Invoke-PbtRunner @('status', '--output', '/results/study')
Invoke-PbtRunner @('approve', '--output', '/results/study', '--stage', 'baseline', '--note', 'Reviewed baseline smoke artifacts and approve continuation.')

# Baseline remainder: conservative upper bound 51 calls (already-recorded/skipped candidates can reduce actual calls).
Invoke-PbtRunner @('run', '--output', '/results/study', '--stage', 'baseline', '--allow-paid', '--max-calls', '51') -Paid

# Feedback/source bundle: zero model calls; performs cached candidate execution.
Invoke-PbtRunner @('run', '--output', '/results/study', '--stage', 'feedback')

# Paired revision smoke: upper bound 2 calls. Inspect both saved records before approval.
Invoke-PbtRunner @('run', '--output', '/results/study', '--stage', 'revision-smoke', '--allow-paid', '--max-calls', '2') -Paid
Invoke-PbtRunner @('status', '--output', '/results/study')
Invoke-PbtRunner @('approve', '--output', '/results/study', '--stage', 'revisions', '--note', 'Reviewed both paired revision smoke records and approve continuation.')

# Full revisions: upper bound 102 calls across the no-feedback and feedback arms.
Invoke-PbtRunner @('run', '--output', '/results/study', '--stage', 'revisions', '--allow-paid', '--max-calls', '102') -Paid

# Delete-only smoke: at most 1 call. Inspect its eligible-candidate record before approval.
Invoke-PbtRunner @('run', '--output', '/results/study', '--stage', 'delete-smoke', '--allow-paid', '--max-calls', '1') -Paid
Invoke-PbtRunner @('status', '--output', '/results/study')
Invoke-PbtRunner @('approve', '--output', '/results/study', '--stage', 'delete', '--note', 'Reviewed delete-only smoke artifacts and approve continuation.')

# Delete-only remainder: conservative upper bound 51 calls.
Invoke-PbtRunner @('run', '--output', '/results/study', '--stage', 'delete', '--allow-paid', '--max-calls', '51') -Paid

# Saved-artifact stages: zero model calls.
Invoke-PbtRunner @('run', '--output', '/results/study', '--stage', 'replay')
Invoke-PbtRunner @('run', '--output', '/results/study', '--stage', 'analyze')
Invoke-PbtRunner @('status', '--output', '/results/study')
```

The `--max-calls` values above are conservative stage ceilings, not promises that every candidate
will receive a call. They include candidates later skipped as ineligible/already recorded; the
runner fails closed when the allowance is too small. `approve` records your review note and hashes
of the smoke artifacts; it does not perform the review for you. Inspect the corresponding stage
records and `status` output before approving. Do not copy the example approval notes without doing
that inspection.

The USD 1 buffered cost cap applies **only** to the four-call component smoke. Full-study stages
accept `--max-calls`, not a dollar cap; the runner does not enforce a full-run spend ceiling.
Before any full paid batch, verify current deployment pricing and approve an external spend budget
separately. Full stages disable pipeline HTTP retries and record each attempted call before dispatch.

See [VALIDATION.md](VALIDATION.md) for checks actually performed, known limits, and the offline
test command. [PUBLISHING.md](PUBLISHING.md) describes the source-only GitHub branch workflow.

Completed stages are no-ops if invoked again. Active locks, failed-stage locks, and ambiguous paid
attempts persist for manual review; never remove a lock, reuse an output/prefix, or automatically
retry a failed/ambiguous stage. Use a separate new output folder and prefix for a separately
authorized study. Mock tests validate CLI workflow logic but are not evidence that paid Azure
stages or end-to-end reproduction succeeded.
