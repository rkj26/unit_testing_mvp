import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from pbt_runner import __main__ as cli
from pbt_runner import backend


def config():
    return {'prefix':'replica-test', 'model':'openai-api/azureai/test', 'docker_image':'sha256:'+'a'*64}


@pytest.mark.parametrize('field,value', [('prefix','../escape'),('prefix',backend.ORIGINAL_PREFIX),
    ('docker_image','python:latest'),('model','openai-api/azureai/YOUR_DEPLOYMENT')])
def test_bad_config(field, value):
    c=config();c[field]=value
    with pytest.raises(ValueError): cli.validate_config(c)


def test_immutable(tmp_path):
    p=tmp_path/'record.json';cli.write_new(p, {'x':1});cli.write_new(p, {'x':1})
    with pytest.raises(ValueError):cli.write_new(p, {'x':2})
    assert json.loads(p.read_text())=={'x':1}


def test_truncated_tail_not_erased(tmp_path):
    p=tmp_path/'records.jsonl';p.write_text('{"a":1}\n{"b":')
    before=p.read_bytes()
    with pytest.raises(ValueError):cli.strict_lines(p)
    assert p.read_bytes()==before


def test_no_paid_launch_without_authorization(tmp_path, monkeypatch):
    monkeypatch.setattr(cli,'study',lambda p:(tmp_path,tmp_path,config()))
    args=SimpleNamespace(output=str(tmp_path),stage='baseline-smoke',allow_paid=False,max_calls=1)
    with pytest.raises(ValueError,match='requires'):cli.run(args)
    assert not list(tmp_path.glob('*.lock'))


def test_full_stage_does_not_start_with_insufficient_allowance(tmp_path, monkeypatch):
    monkeypatch.setattr(cli,'study',lambda p:(tmp_path,tmp_path,config()))
    monkeypatch.setenv('AZUREAI_API_KEY','dummy');monkeypatch.setenv('AZUREAI_BASE_URL','https://example.invalid/openai/v1')
    (tmp_path/'preflight.done.json').write_text('{}')
    monkeypatch.setattr(cli,'validate_done',lambda *a: {})
    args=SimpleNamespace(output=str(tmp_path),stage='baseline',allow_paid=True,max_calls=1)
    with pytest.raises(ValueError,match='at least 52'):cli.run(args)
    assert not list(tmp_path.glob('*.lock'))


def test_failed_smoke_cannot_be_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(cli,'study',lambda p:(tmp_path,tmp_path,config()))
    (tmp_path/'baseline-smoke.done.json').write_text(json.dumps({'smoke_records':[{'failed':True}]}))
    monkeypatch.setattr(cli,'validate_done',lambda *a: {'smoke_records':[{'failed':True}]})
    with pytest.raises(ValueError,match='smoke failed'):
        cli.approve(SimpleNamespace(output=str(tmp_path),stage='baseline',note='reviewed'))


def test_literal_only_does_not_execute_notebook(tmp_path):
    p=tmp_path/'fixture.ipynb'
    p.write_text(json.dumps({'cells':[{'cell_type':'code','source':['SAFE = "hello"\nraise RuntimeError("must not execute")']}]}))
    assert backend.literal(p,'SAFE')=='hello'


def test_empty_preflight_marker_cannot_authorize_calls(tmp_path):
    (tmp_path/'preflight.done.json').write_text('{}')
    with pytest.raises(ValueError,match='marker'):cli.validate_done(tmp_path,config(),'preflight')


def test_changed_feedback_bundle_invalidates_completion(tmp_path):
    cli.write_new(tmp_path/'manifest.json',{'test':1})
    cli.write_new(tmp_path/'bundle.json',{'diagnostic':'original'})
    cli.write_new(tmp_path/'feedback.done.json',{'stage':'feedback', 'config_sha256':backend.object_hash(config()),
        'manifest_sha256':backend.file_hash(tmp_path/'manifest.json'),
        'final_record_sha256':{'bundle.json':backend.file_hash(tmp_path/'bundle.json')}})
    cli.validate_done(tmp_path,config(),'feedback')
    (tmp_path/'bundle.json').write_text('{"diagnostic":"changed"}')
    with pytest.raises(ValueError,match='records changed'):cli.validate_done(tmp_path,config(),'feedback')
