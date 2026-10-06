# Source-only distribution

The selected release method is **GitHub source plus a local Docker build**. No Docker Hub or
GitHub Container Registry account, image upload, or registry token is needed.

Maintainers commit the reviewed wrapper code, Dockerfile, tests, and documentation to
`codex/omar-pbt-subproject` in `rkj26/unit_testing_mvp`. Do not merge into `main` as part of this
release. Never stage `paid.env`, `study.json`, `results/`, `local-work/`, credentials, or modifications
to the frozen `snapshot/`. Review the staged diff and run the archive verifier before pushing.

Readers clone that branch, enter `experiments/omar-pbt`, and follow [README.md](README.md):

```powershell
git -c core.longpaths=true clone --branch codex/omar-pbt-subproject --single-branch https://github.com/rkj26/unit_testing_mvp.git pbt
Set-Location pbt/experiments/omar-pbt
docker build -f container/Dockerfile -t omar-pbt:0.2.0 .
```

This builds one image with the coordinator and an isolated candidate Python environment.
Different restricted containers use the same image; candidate containers do not receive the
coordinator's credentials, Docker socket, source archive, or writable output mount.

Record the source commit and the inspected local image ID with each run. Runner Python packages
are locked; candidate top-level versions are pinned and the resolved inventory is recorded.
OS packages and candidate transitive packages are not fully pinned, so rebuilding later is not
guaranteed to produce the same image digest. [VALIDATION.md](VALIDATION.md) states what was
actually tested. A four-call startup smoke is not a replication of the whole research study.

Registry publication could be added later with separate authorization and redistribution review.
It is not required for this workflow and has not been performed.
