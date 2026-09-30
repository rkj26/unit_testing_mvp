"""Offline Hugging Face boundary tests for pinned, disjoint seeded pool construction."""
import json
import hashlib
from pathlib import Path
import pytest
import datasets
import build_dataset as builder


def row(i):
    return dict(problem_id=str(i),solution_compiles=True,solution_passes_tests=True,
                is_nondeterministic=False,difficulty='competition',solutions=[{'code':'print(1)'}],
                inputs=['1'],outputs=['1'],question='Print 1.',backdoors=[dict(source='control_tax',
                backdoor_works=True,compiles=True,passes_tests=True,backdoor_code='print(2)',backdoor_input='2')])


def test_pin_and_exclusions_are_checked_before_loading(monkeypatch):
    monkeypatch.setattr(datasets,'load_dataset',lambda *a,**kw: pytest.fail('unexpected network'))
    for revision in ['', 'main', 'abc']:
        with pytest.raises(ValueError): builder.write_pool(2,300,Path('out.json'),revision=revision)
    with pytest.raises(FileNotFoundError):
        builder.write_pool(2,300,Path('out.json'),exclude_pools=(Path('missing.json'),))


def test_disjoint_seeded_draw_preserves_default_and_records_provenance(monkeypatch):
    calls=[]
    def load(*args,**kwargs):
        calls.append((args,kwargs)); return [row(i) for i in range(12)]
    monkeypatch.setattr(datasets,'load_dataset',load)
    for name, ids in [('hard.json',['0','1']),('random.json',['1','2'])]:
        Path(name).write_text(json.dumps({'schema_version':1,'io_mode':'stdio','candidates':{i:{} for i in ids}}))
    args=dict(revision='a'*40,exclude_pools=(Path('hard.json'),Path('random.json')))
    builder.write_pool(5,300,Path('a.json'),**args)
    builder.write_pool(5,300,Path('b.json'),**args)
    a=json.loads(Path('a.json').read_text());b=json.loads(Path('b.json').read_text())
    assert a==b and not (set(a['candidates']) & {'0','1','2'})
    assert a['sampling_provenance']['hf_revision']=='a'*40
    assert a['sampling_provenance']['excluded_task_count']==3
    assert len(a['sampling_provenance']['exclude_pools'])==2
    provenance = a['sampling_provenance']['exclude_pools']
    assert provenance[0]['sha256'] == hashlib.sha256(Path('hard.json').read_bytes()).hexdigest()
    assert provenance[1]['sha256'] == hashlib.sha256(Path('random.json').read_bytes()).hexdigest()
    assert calls[0][1]=={'split':'train','revision':'a'*40}
    builder.write_pool(2,300,Path('default.json'))
    assert calls[-1][1]=={'split':'train'}
    assert 'sampling_provenance' not in json.loads(Path('default.json').read_text())


def test_exclusion_can_make_pool_insufficient_and_negative_size_fails(monkeypatch):
    monkeypatch.setattr(datasets,'load_dataset',lambda *a,**k:[row(0),row(1)])
    Path('excluded.json').write_text(json.dumps({'schema_version':1,'io_mode':'stdio','candidates':{'0':{}}}))
    with pytest.raises(ValueError,match='fewer'):
        builder.write_pool(2,300,Path('out.json'),exclude_pools=(Path('excluded.json'),))
    with pytest.raises(ValueError): builder.write_pool(-1,300,Path('out.json'))


def test_cli_revision_and_repeated_exclusions_reach_provenance(monkeypatch):
    import sys
    monkeypatch.setattr(datasets,'load_dataset',lambda *a,**k:[row(i) for i in range(5)])
    Path('old.json').write_text(json.dumps({'schema_version':1,'io_mode':'stdio','candidates':{'0':{}}}))
    monkeypatch.setattr(sys,'argv',['build_dataset.py','--pool','new.json','--make-pool','2',
        '--hf-revision','b'*40,'--exclude-pool','old.json','--exclude-pool','old.json'])
    builder.main()
    pool=json.loads(Path('new.json').read_text())
    assert pool['sampling_provenance']['hf_revision']=='b'*40
    assert '0' not in pool['candidates']
    ids=list(pool['candidates'])
    Path('split.json').write_text(json.dumps({'train':ids[:1],'test':ids[1:]}))
    built=builder.build(Path('new.json'),Path('split.json'),'apps','test')
    assert built['built_from']['sampling_provenance']==pool['sampling_provenance']


def test_canonical_dataset_exclusion_validates_schema_and_extracts_task_ids(monkeypatch):
    from pipeline.data import Dataset, Task, Candidate
    task=Task(task_id='0',specification='Print 1.',io_mode='stdio',
              candidates=(Candidate('h','honest','print(1)'),Candidate('a','attack_0','print(2)')))
    doc=Dataset(name='old',backend='apps',io_mode='stdio',tasks=(task,),
                split={'train':['0'],'test':[]},built_from={}).to_json()
    Path('old-data.json').write_text(json.dumps(doc))
    monkeypatch.setattr(datasets,'load_dataset',lambda *a,**kw:[row(i) for i in range(4)])
    builder.write_pool(2,300,Path('out.json'),exclude_pools=(Path('old-data.json'),))
    output=json.loads(Path('out.json').read_text())
    assert '0' not in output['candidates']
    source_hash = output['sampling_provenance']['exclude_pools'][0]['sha256']
    assert source_hash == hashlib.sha256(Path('old-data.json').read_bytes()).hexdigest()
    doc['schema_version']=999
    Path('old-data.json').write_text(json.dumps(doc))
    with pytest.raises(ValueError,match='schema'):
        builder.pool_provenance(None,(Path('old-data.json'),))
