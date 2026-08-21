# `tests/`

Run with `.venv/bin/python -m pytest -q`. `pytest.ini` sets `pythonpath = .`, so imports are the same
here as at the repo root.

## What `conftest.py` already does for you

Two autouse fixtures, so you do not write either by hand:

- `isolate_working_directory` chdirs every test into its own `tmp_path`. Artifact paths are resolved
  against the CWD — `probe` writes `Path("runs") / run_id`, `audit` and `deployment_game` read
  `runs/<id>/probe.json` — so without this a test writes into the real `runs/` and the next
  invocation resumes its own leftovers.
- `restore_environment` snapshots and restores `os.environ`, because `model.resolve` calls
  `os.environ.setdefault` on six credential variables and that outlives the test that triggered it.

Take `settings_from_cli` rather than constructing `Settings()` directly: `Settings.model_config` sets
`cli_parse_args=True`, so a bare `Settings()` under pytest parses *pytest's* argv and exits.

## What to test, and where the double lives

- **A test double belongs in the test that uses it.** `pipeline/backends/mock.py` is the counterexample
  still sitting in the library with no live caller: it was the deleted orchestrator's offline model and
  now only exists to be imported by a test. Scripted models and stub sandboxes go in the test file.
- **Do not test scipy or sklearn.** Statistics go through them by convention, so a test asserting an
  AUROC value is asserting sklearn's arithmetic. Test the wiring instead: which rows were passed in,
  which were excluded, what got written to the artifact.
- **Tests are written before the feature lands**, so a red baseline can be deliberate. Read the module
  docstring before deleting a failing case — it will say if the case is specifying something unbuilt.
- Name the contract in the test name. `test_a_candidate_that_reached_both_verdicts_carries_no_unknown`
  says what breaks; `test_verdict_2` does not.
