"""Matched second-call round trips; only provider and Docker are doubled."""
import json
from pathlib import Path
import pytest
from test_test_repair import cached_sources, answer, digest
from pipeline.protocols.second_revision import SecondRevision, revision_prompt
from pipeline.protocols.unit_testing import UnitTesting, suite_source
from pipeline import model as model_mod, sandbox
from pipeline.model import Completion
from pipeline.data import Dataset, load_records


@pytest.fixture
def fresh_sources(cached_sources):
    document = json.loads(Path('mini.json').read_text())
    document['split'] = {'train': [], 'test': ['synthetic']}
    Path('mini.json').write_text(json.dumps(document))
    records = load_records('source')
    for row in records:
        row['split'] = 'test'
        row['tests_src'] = suite_source(row['calls'][0]['raw'])[0]
    source_path = Path('runs/source/records.jsonl')
    source_path.write_text(''.join(json.dumps(row)+'\n' for row in records))
    input_path = Path('runs/inputs/records.jsonl')
    input_records = load_records('inputs')
    for row in input_records:
        row['split'] = 'test'
    input_path.write_text(''.join(json.dumps(row)+'\n' for row in input_records))
    baseline = UnitTesting(run_name='source', data='mini.json', model='mockllm/model',
                           triggers='inputs', n_tests=10, test_gen_prompt='traceable_v1',
                           resolve='with', code_visible=True, max_tokens=8192)
    Path('runs/source/config.json').write_text(json.dumps(baseline.config()))
    envelope = json.loads(Path('feedback.json').read_text())
    envelope['dataset_sha256'] = digest(Path('mini.json').read_bytes())
    envelope['source_config_sha256'] = digest(Path('runs/source/config.json').read_bytes())
    envelope['source_records_sha256'] = digest(source_path.read_bytes())
    envelope['input_records_sha256'] = digest(input_path.read_bytes())
    for row in records:
        envelope['candidates'][row['candidate_id']]['source_record_sha256'] = digest(row)
        envelope['candidates'][row['candidate_id']]['suite_sha256'] = digest(row['tests_src'].encode())
    Path('feedback.json').write_text(json.dumps(envelope))
    return dict(run_name='second', data='mini.json', model='mockllm/model', baseline_run='source',
                triggers='inputs', source_bundle='feedback.json',
                source_bundle_sha256=digest(Path('feedback.json').read_bytes()),
                max_candidates=2, feedback_visible=True)


def test_prompt_only_diagnostic_visibility_changes_and_no_hidden_fields(fresh_sources):
    task = Dataset.load('mini.json').tasks[0]
    diagnostic = {'complete': True, 'tests': [{'test': 'test_0', 'events': [
        {'prop':'test_0','i':0,'outcome':'catch','msg':'SOURCE_CANARY_A'}]}]}
    a = revision_prompt(task, 'SAME_INITIAL_SUITE', ['1\n'], diagnostic, True)
    b = revision_prompt(task, 'SAME_INITIAL_SUITE', ['1\n'], diagnostic, False)
    left = a.split('REVISION INPUT (JSON)\n')[1]
    right = b.split('REVISION INPUT (JSON)\n')[1]
    x,y = json.loads(left),json.loads(right)
    assert x.pop('execution_diagnostics') != y.pop('execution_diagnostics')
    assert x['static_validation']==y['static_validation']
    assert x['static_validation']['requested_test_count']==10
    assert x == y and a.split('REVISION INPUT')[0] == b.split('REVISION INPUT')[0]
    for bad in ['SOURCE_CANARY', 'REFERENCE_CANARY', 'HIDDEN_TRIGGER', 'HIDDEN_GRADING', 'synthetic_honest']:
        assert bad not in a and bad not in b


@pytest.mark.parametrize('feedback', [False, True])
@pytest.mark.parametrize('response', [answer(), answer(abstain=True), 'broken'])
def test_one_call_roundtrip_resume_and_exact_schema(fresh_sources, monkeypatch, feedback, response):
    calls, executions = [], []
    class Client:
        def __init__(self,runtime): self.runtime=runtime
        async def completion(self,prompt,kind,schema):
            calls.append(prompt)
            assert self.runtime.http_retries == 0
            assert schema.json_schema.properties['abstain'].type == 'boolean'
            return Completion(response, 'stop', usage={'output_tokens':20})
    def execute(task,code,source,space,**kw):
        executions.append(source)
        names=[f'test_{i}' for i in range(10)]
        pairs=[{'prop':p,'i':i,'outcome':'catch'} for p in names for i in range(len(space))]
        return dict(ok=True,complete=True,props=names,records=pairs,n_records=len(pairs),n_expected=len(pairs),error='')
    monkeypatch.setattr(model_mod,'resolve',Client)
    monkeypatch.setattr(sandbox,'run_raw',execute)
    run=SecondRevision(**(fresh_sources | {'feedback_visible':feedback}))
    run.write_config()
    assert SecondRevision.attach('second').config()==run.config()
    assert run.execute()==2
    rows=load_records('second')
    assert len(calls)==2
    assert all(len(r['calls'])==1 and r['source_hashes']['suite_sha256'] for r in rows)
    assert all(r['failed']==(response!=answer()) for r in rows)
    assert all(r['catches'] is None for r in rows) if response!=answer() else len(executions)==2
    assert run.execute()==0 and len(calls)==2


@pytest.mark.parametrize('change', ['bundle','source','config','inputs'])
def test_immutable_source_link_refuses_change_before_provider(fresh_sources,monkeypatch,change):
    paths={'bundle':'feedback.json','source':'runs/source/records.jsonl',
           'config':'runs/source/config.json','inputs':'runs/inputs/records.jsonl'}
    path=Path(paths[change]); path.write_text(path.read_text()+' ')
    monkeypatch.setattr(model_mod,'resolve',lambda *a: pytest.fail('provider before validation'))
    run=SecondRevision(**fresh_sources)
    with pytest.raises(ValueError,match='hash'): run.prepare(run.data)


@pytest.mark.parametrize('change',[{'code_visible':True},{'n_tests':9},{'critique':True},{'runs':2},{'max_candidates':1}])
def test_fixed_design_rejects_other_interventions(fresh_sources,change):
    with pytest.raises(ValueError): SecondRevision(**(fresh_sources|change))


@pytest.mark.parametrize('failure',['exception','missing_test','wrong_shape'])
def test_revision_failure_preserves_paid_response_and_never_falls_back(fresh_sources,monkeypatch,failure):
    attempted=[]
    class Client:
        def __init__(self,runtime):self.runtime=runtime
        async def completion(self,prompt,kind,schema):
            obj=json.loads(answer())
            if failure=='wrong_shape':obj['tests']=obj['tests'][:9]
            return Completion(json.dumps(obj),'stop',usage={'output_tokens':17})
    def execute(*args,**kwargs):
        attempted.append(1)
        if failure=='exception':raise OSError('Docker unavailable')
        return dict(ok=True,complete=True,props=['test_0'],records=[],n_records=0,n_expected=0,error='')
    monkeypatch.setattr(model_mod,'resolve',Client)
    monkeypatch.setattr(sandbox,'run_raw',execute)
    run=SecondRevision(**fresh_sources);run.write_config();run.execute()
    records=load_records('second')
    assert len(attempted)==(0 if failure=='wrong_shape' else 2)
    assert all(r['failed'] and r['catches'] is None and len(r['calls'])==1 for r in records)
    assert all(r['calls'][0]['usage']['output_tokens']==17 for r in records)
    assert all(r['source_hashes']['suite_sha256'] for r in records)
    assert run.execute()==0


def test_function_mode_uses_function_example_and_excludes_reference(fresh_sources):
    from pipeline.data import Task, Candidate
    task=Task(task_id='function',specification='Return the integer.',io_mode='function',entry_point='identity',
              candidates=(Candidate('h','honest','SOURCE_CANARY'),Candidate('a','attack_0','SOURCE_CANARY')),
              reference_solution='REFERENCE_CANARY')
    prompt=revision_prompt(task,'def test_a(run,x): pass',[{'x':1}],
                           {'parse_error':'bad','tests':None,'complete':None},True)
    assert 'SOURCE_CANARY' not in prompt and 'REFERENCE_CANARY' not in prompt
    assert 'identity' in prompt and 'keyword' in prompt


def test_static_parse_failure_is_visible_in_both_arms(fresh_sources):
    task=Dataset.load('mini.json').tasks[0]
    diagnostic={'parse_error':'SyntaxError','tests':None,'complete':None}
    values=[json.loads(revision_prompt(task,'invalid suite',['1'],diagnostic,v).split('REVISION INPUT (JSON)\n')[1])
            for v in (False,True)]
    assert values[0]['static_validation']==values[1]['static_validation']
    assert values[0]['static_validation']['source_parse_failed'] is True
    assert values[0]['static_validation']['parsed_test_count'] is None
