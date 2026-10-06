"""Exercise real protocol linkage with provider and sandbox boundaries mocked only."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import sys

from pbt_runner import __main__ as cli
from pbt_runner import backend as b

ROOT = Path(__file__).resolve().parents[2]


def test_complete_stage_workflow_without_paid_calls(tmp_path, monkeypatch):
    archive = ROOT / 'snapshot'
    if not archive.exists():
        archive = Path('/opt/archive/snapshot')
    monkeypatch.setattr(cli, 'ARCHIVE', archive)
    sys.path.insert(0, str(archive))
    from pipeline import model as model_mod, sandbox
    from pipeline.model import Completion
    calls = []
    def completion(client, prompt, kind, schema):
        calls.append(prompt)
        if 'retain_test_ids' in schema.json_schema.properties:
            answer={'rationale':'retain justified tests','retain_test_ids':[f'test_{i}' for i in range(10)]}
        else:
            answer={'rationale':'Specification justified', 'tests':[
                {'name':f'test_{i}', 'source':f'def test_{i}(run,x):\n    assert run(x) is not None\n'} for i in range(10)]}
            if 'abstain' in schema.json_schema.properties:answer['abstain']=False
        return Completion(json.dumps(answer), 'stop', usage={'output_tokens':50}, response_model='mock-boundary')
    def execution(task, code, source, space, **kwargs):
        names=[n.name for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)]
        records=[{'prop':n,'i':i,'outcome':'pass'} for n in names for i in range(len(space))]
        return {'ok':True,'complete':True,'props':names,'records':records,'n_expected':len(records),
                'n_records':len(records),'error':None,'bare_run_ok':None}
    monkeypatch.setattr(model_mod,'resolve',lambda runtime:object())
    monkeypatch.setattr(model_mod,'complete_sync',completion)
    monkeypatch.setattr(sandbox,'run_raw',execution)
    monkeypatch.setattr(b,'install_sandbox',lambda:None)
    monkeypatch.setattr(cli,'preflight',lambda config:{'ok':True,'complete':True,'n_records':2,'n_expected':2,
        'records':[{'outcome':'pass'},{'outcome':'pass'}]})
    monkeypatch.setenv('AZUREAI_API_KEY','dummy-not-real')
    monkeypatch.setenv('AZUREAI_BASE_URL','https://example.invalid/openai/v1')
    output=tmp_path/'study'; cfg=tmp_path/'config.json'
    cfg.write_text(json.dumps({'prefix':'mock-replica', 'model':'openai-api/azureai/mock',
                              'docker_image':'sha256:'+'a'*64}))
    cli.init(SimpleNamespace(output=str(output),config=str(cfg)))
    def run(stage,n=0):
        cli.run(SimpleNamespace(output=str(output),stage=stage,allow_paid=n>0,max_calls=n))
    run('preflight');run('baseline-smoke',1)
    cli.approve(SimpleNamespace(output=str(output),stage='baseline',note='mock reviewed'))
    run('baseline',51);assert len(calls)==52
    run('baseline',51);assert len(calls)==52 # completed stage idempotence
    run('feedback');run('revision-smoke',2)
    cli.approve(SimpleNamespace(output=str(output),stage='revisions',note='mock reviewed'))
    run('revisions',102);assert len(calls)==156
    run('delete-smoke',1)
    cli.approve(SimpleNamespace(output=str(output),stage='delete',note='mock reviewed'))
    run('delete',51);assert len(calls)==208
    run('replay');run('analyze')
    assert len(cli.strict_lines(output/'attempts.jsonl'))==208
    assert (output/'analysis/metrics.json').exists()
    assert not (output/'active.lock').exists()
    assert all(len(cli.strict_lines(output/'project/runs'/('mock-replica-'+a)/'records.jsonl'))==52
               for a in ['baseline','no-feedback','feedback','delete-only'])
