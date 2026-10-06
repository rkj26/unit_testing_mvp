"""Mock-boundary tests for the connected four-arm smoke; no provider/Docker calls."""
import ast
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from pbt_runner import __main__ as cli
from pbt_runner import backend as backend
from pbt_runner import smoke


ROOT = Path(__file__).resolve().parents[2]


def _config(path):
    value = {"prefix": "mock-component", "model": smoke.MODEL,
             "docker_image": "sha256:" + "a" * 64}
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _runtime():
    return SimpleNamespace(name=smoke.MODEL, max_tokens=smoke.MAX_OUTPUT,
                           http_retries=0, reasoning_effort=SimpleNamespace(value="low"))


def _test_source(index):
    return f"def test_{index}(run, x):\n    assert run(x) is not None\n"


def _definitions(source):
    lines = source.splitlines(keepends=True)
    result = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            result[node.name] = "".join(lines[node.lineno - 1:node.end_lineno])
    return result


def _args(config, output):
    return SimpleNamespace(config=str(config), output=str(output), allow_paid=True, max_cost_usd=1.0)


def test_connected_smoke_uses_four_mocked_calls_and_binds_all_arms(tmp_path, monkeypatch):
    archive = Path(os.environ.get("PBT_ARCHIVE", ROOT / "snapshot"))
    if not archive.exists():
        archive = Path("/opt/archive/snapshot")
    monkeypatch.setattr(cli, "ARCHIVE", archive)
    monkeypatch.syspath_prepend(str(archive))
    from pipeline import model as model_mod, sandbox
    from pipeline.model import Completion

    # Score methods call resolve to enforce runtime settings. This fake retains the exact
    # runtime object expected by Guard but never constructs an Inspect/provider model.
    monkeypatch.setattr(model_mod, "resolve", lambda runtime: SimpleNamespace(runtime=runtime))
    monkeypatch.setattr(backend, "install_sandbox", lambda: None)
    fake_executions = []

    def sandbox_run(task, code, source, space, **kwargs):
        names = [n.name for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)]
        records = [{"prop": name, "i": index, "outcome": "pass"}
                   for name in names for index in range(len(space))]
        result = {"ok": True, "complete": True, "props": names, "records": records,
                  "n_expected": len(records), "n_records": len(records), "error": None,
                  "bare_run_ok": None}
        fake_executions.append((source, result))
        return result

    monkeypatch.setattr(sandbox, "run_raw", sandbox_run)
    prompts = []

    def completion(model, prompt, kind, schema):
        prompts.append(prompt)
        properties = schema.json_schema.properties
        if "retain_test_ids" in properties:
            text = json.dumps({"rationale": "retain justified originals",
                               "retain_test_ids": [f"test_{i}" for i in range(8)]})
        elif "abstain" in properties:
            text = json.dumps({"abstain": False, "rationale": "specification grounded",
                               "tests": [{"name": f"test_{i}", "source": _test_source(i)}
                                         for i in range(10)]})
        else:
            text = json.dumps({"rationale": "specification grounded",
                               "tests": [{"name": f"test_{i}", "source": _test_source(i)}
                                         for i in range(10)]})
        return Completion(text, "stop", usage={"input_tokens": 100, "output_tokens": 100},
                          response_model="gpt-5.6-terra", response_id=f"mock-{len(prompts)}")

    monkeypatch.setattr(model_mod, "complete_sync", completion)
    monkeypatch.setenv("AZUREAI_API_KEY", "dummy-not-real")
    monkeypatch.setenv("AZUREAI_BASE_URL", "https://example.invalid/openai/v1")
    monkeypatch.setattr(cli, "preflight", lambda config: {"ok": True, "complete": True,
        "n_records": 2, "n_expected": 2, "records": [{"outcome": "pass"}] * 2})

    config = _config(tmp_path / "config.json")
    output = tmp_path / "fresh-smoke"
    result = smoke.run_smoke(_args(config, output))

    assert result == 0
    assert len(prompts) == 4
    attempts = [json.loads(line) for line in (output / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    usage = [json.loads(line) for line in (output / "usage.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [item["arm"] for item in attempts] == ["baseline", "no-feedback", "feedback", "delete-only"]
    assert len(usage) == 4

    bundle = json.loads((output / "component-source-bundle.json").read_text(encoding="utf-8"))
    baseline_source = bundle["baseline"]["tests_src"]
    # Revision payload is JSON-escaped within the rendered prompt.
    encoded_source = json.dumps(baseline_source)[1:-1]
    assert encoded_source in prompts[1] and encoded_source in prompts[2]
    assert "WITHHELD_BY_DESIGN" in prompts[1]
    assert "WITHHELD_BY_DESIGN" not in prompts[2]
    stages = json.loads((output / "smoke-results.json").read_text(encoding="utf-8"))["stages"]
    revisions = [stage["score"] for stage in stages if stage["arm"] in ("no-feedback", "feedback")]
    assert len(revisions) == 2
    assert revisions[0]["source_hashes"] == revisions[1]["source_hashes"] == bundle["provenance"]
    assert revisions[0]["source_bundle_sha256"] == revisions[1]["source_bundle_sha256"]

    deletion = stages[-1]["score"]
    original = _definitions(baseline_source)
    retained = _definitions(deletion["tests_src"])
    assert set(retained) == {f"test_{i}" for i in range(8)}
    assert all(retained[name] == original[name] for name in retained)
    assert json.loads((output / "smoke-results.json").read_text(encoding="utf-8"))["delete_exact_subset_verified"] is True
    assert len(fake_executions) == 4


def test_smoke_missing_authorization_stops_before_init_or_calls(tmp_path, monkeypatch):
    config = _config(tmp_path / "config.json")
    monkeypatch.delenv("AZUREAI_API_KEY", raising=False)
    monkeypatch.delenv("AZUREAI_BASE_URL", raising=False)
    initialized = []
    monkeypatch.setattr(cli, "init", lambda args: initialized.append(args))
    with pytest.raises(ValueError, match="--allow-paid"):
        smoke.run_smoke(SimpleNamespace(config=str(config), output=str(tmp_path / "out"),
                                        allow_paid=False, max_cost_usd=1.0))
    assert initialized == []
    with pytest.raises(ValueError, match="AZUREAI_API_KEY and AZUREAI_BASE_URL"):
        smoke.run_smoke(SimpleNamespace(config=str(config), output=str(tmp_path / "out"),
                                        allow_paid=True, max_cost_usd=1.0))
    assert initialized == []


def test_guard_oversize_and_cost_ceiling_reserve_nothing(tmp_path):
    guard = smoke.Guard(tmp_path / "oversize", 1.0)
    guard.arm = "baseline"
    model = SimpleNamespace(runtime=_runtime())
    sent = []
    with pytest.raises(ValueError, match="byte ceiling"):
        guard.call(lambda *args: sent.append(args), model, "x" * smoke.MAX_REQUEST_BYTES, "property_gen")
    assert sent == [] and guard.count == 0
    assert not (tmp_path / "oversize" / "attempts.jsonl").exists()

    tiny = smoke.Guard(tmp_path / "ceiling", 1e-9)
    tiny.arm = "baseline"
    with pytest.raises(ValueError, match="cost limit"):
        tiny.call(lambda *args: sent.append(args), model, "small prompt", "property_gen")
    assert sent == [] and tiny.count == 0
    assert not (tmp_path / "ceiling" / "attempts.jsonl").exists()


def test_guard_records_a_failed_attempt_once_and_refuses_retry(tmp_path):
    guard = smoke.Guard(tmp_path, 1.0)
    guard.arm = "baseline"
    model = SimpleNamespace(runtime=_runtime())
    calls = []

    def fail_once(*args):
        calls.append(args)
        raise TimeoutError("mock transport failure")

    with pytest.raises(TimeoutError):
        guard.call(fail_once, model, "small prompt", "property_gen")
    assert guard.count == 1 and len(calls) == 1
    attempts = [json.loads(line) for line in (tmp_path / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(attempts) == 1
    assert not (tmp_path / "usage.jsonl").exists()
    with pytest.raises(ValueError, match="ceiling reached"):
        guard.call(fail_once, model, "small prompt", "property_gen")
    assert len(calls) == 1 and guard.count == 1


def test_guard_rejects_unexpected_provider_response_model(tmp_path):
    guard = smoke.Guard(tmp_path, 1.0)
    guard.arm = "baseline"
    model = SimpleNamespace(runtime=_runtime())
    calls = []
    response = SimpleNamespace(usage={"input_tokens": 10, "output_tokens": 10},
                               response_model="gpt-5.6-turbo", response_id="unexpected")

    def complete(*args):
        calls.append(args)
        return response

    with pytest.raises(ValueError, match="different or missing response model"):
        guard.call(complete, model, "small prompt", "property_gen")
    assert len(calls) == 1 and guard.count == 1
    attempt = json.loads((tmp_path / "attempts.jsonl").read_text(encoding="utf-8").strip())
    usage = json.loads((tmp_path / "usage.jsonl").read_text(encoding="utf-8").strip())
    assert attempt["arm"] == usage["arm"] == "baseline"
    assert usage["response_model"] == "gpt-5.6-turbo"


def test_cli_run_rejects_component_smoke_output_reuse(tmp_path, monkeypatch):
    output = tmp_path / "component-output"
    output.mkdir()
    (output / "smoke.lock").write_text("reserved component smoke\n", encoding="utf-8")
    monkeypatch.setattr(cli, "study", lambda path: (output, tmp_path / "project", {"prefix": "mock-component"}))

    with pytest.raises(ValueError, match="component-smoke output cannot become a full study"):
        cli.run(SimpleNamespace(output=str(output), stage="feedback", allow_paid=False, max_calls=0))
    assert sorted(path.name for path in output.iterdir()) == ["smoke.lock"]
