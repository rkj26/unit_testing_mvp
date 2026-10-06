"""Reuse frozen protocol/prompt code; replace orchestration, not experimental interventions."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path

INPUTS = 'azure-terra-pbt-bcb26-s300-v1-reviewed-inputs'
DATA = 'data/bcb_replication26_eval.json'
ORIGINAL_PREFIX = 'azure-terra-pbt-bcb26-s300-v1'


def byte_hash(raw):
    return hashlib.sha256(raw).hexdigest()


def object_hash(value):
    return byte_hash(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def file_hash(path):
    return byte_hash(Path(path).read_bytes())


def literal(notebook, name):
    """Extract a named literal only; never run notebook top-level launch cells."""
    found = []
    for cell in json.loads(Path(notebook).read_text(encoding='utf-8'))['cells']:
        if cell['cell_type'] != 'code':
            continue
        for node in ast.parse(''.join(cell['source'])).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                found.append(ast.literal_eval(node.value))
    if len(found) != 1 or not isinstance(found[0], str):
        raise ValueError(f'expected exactly one string literal: {name}')
    return found[0]


def install_sandbox():
    from pipeline import sandbox
    from .sandbox_bridge import run_raw
    scope = {}
    exec(literal('notebooks/azure_pbt_bcb_replication.ipynb', 'BCB_WRAPPER_SOURCE'), scope)
    scope['install_bcb_harness']()
    sandbox.run_raw = run_raw


def common(config):
    return dict(data=DATA, model=config['model'], seed=300, runs=1, cache=False,
                triggers=INPUTS, n_tests=10, reasoning='low', max_tokens=8192,
                call_seconds=300, sandbox_seconds=120, docker_image=config['docker_image'],
                resolve='with', test_gen_prompt='traceable_v1', critique=False, critique_informed=False)


def validate_inputs():
    from pipeline.data import Dataset
    from pipeline.protocols.unit_testing import spaces_from
    data = Dataset.load(DATA)
    if len(data.tasks) != 26 or data.train or len(data.test) != 26:
        raise ValueError('runner only supports the frozen 26-task all-evaluation population')
    wanted = {c.candidate_id for _, c in data.candidates()}
    spaces, bad = spaces_from(INPUTS, data)
    review = json.loads((Path('runs') / INPUTS / 'statement-review-v1.json').read_text(encoding='utf-8'))
    if (len(wanted) != 52 or bad or set(spaces) != wanted or
        review['dataset_sha256'] != file_hash(DATA) or
        review['input_records_sha256'] != file_hash(Path('runs') / INPUTS / 'records.jsonl') or
        review['all_candidates_resolved'] is not True or set(review['candidate_input_sha256']) != wanted):
        raise ValueError('fixed input review/population mismatch')
    for cid, space in spaces.items():
        if not 1 <= len(space) <= 10 or review['candidate_input_sha256'][cid] != object_hash(space):
            raise ValueError(f'input hash/count mismatch: {cid}')
    return data, spaces


def read_complete(name, data):
    from pipeline.data import load_records
    rows = load_records(name)
    ids = [r['candidate_id'] for r in rows]
    if len(ids) != len(set(ids)) or set(ids) != {c.candidate_id for _, c in data.candidates()}:
        raise ValueError(f'incomplete or duplicate run: {name}')
    return {r['candidate_id']: r for r in rows}


def bundle_path(config):
    return Path('runs') / (config['prefix'] + '-study') / 'source-bundle-v1.json'


def make_bundle(config):
    from pipeline import sandbox
    from pipeline.protocols.unit_testing import suite_source
    data, spaces = validate_inputs()
    baseline = config['prefix'] + '-baseline'
    rows = read_complete(baseline, data)
    result = {'schema_version': 1, 'dataset_sha256': file_hash(DATA),
              'source_config_sha256': file_hash(Path('runs') / baseline / 'config.json'),
              'source_records_sha256': file_hash(Path('runs') / baseline / 'records.jsonl'),
              'input_records_sha256': file_hash(Path('runs') / INPUTS / 'records.jsonl'), 'candidates': {}}
    for task, candidate in data.candidates():
        row = rows[candidate.candidate_id]
        raw = row['calls'][0]['raw'] if row['calls'] else ''
        source, error = suite_source(raw)
        execution = None
        if source is not None:
            # A sandbox failure stops this stage instead of becoming an empty diagnostic.
            execution = sandbox.run_raw(task, candidate.code, source, spaces[candidate.candidate_id],
                                        timeout_s=120, isolation=sandbox.Isolation.DOCKER,
                                        docker_image=config['docker_image'])
        result['candidates'][candidate.candidate_id] = {
            'source_record_sha256': object_hash(row), 'inputs_sha256': object_hash(spaces[candidate.candidate_id]),
            'code_sha256': byte_hash(candidate.code.encode()),
            'suite_sha256': None if source is None else byte_hash(source.encode()), 'result': execution}
    return result


def protocol(config, arm):
    from pipeline.protocols import UnitTesting, SecondRevision
    name = config['prefix'] + '-' + arm
    if arm == 'baseline':
        return UnitTesting(run_name=name, code_visible=True, **common(config))
    if arm in ('no-feedback', 'feedback'):
        path = bundle_path(config)
        return SecondRevision(run_name=name, baseline_run=config['prefix'] + '-baseline',
                              source_bundle=str(path), source_bundle_sha256=file_hash(path),
                              feedback_visible=arm == 'feedback', max_candidates=52,
                              code_visible=False, **common(config))
    if arm != 'delete-only':
        raise ValueError(arm)
    return deletion(config)


def delete_definitions():
    """Load trusted frozen selector code once; shared by full study and component smoke."""
    from pipeline.protocols.base import REGISTRY
    scope = {}
    if 'bcb_delete_only' in REGISTRY:
        DeleteOnly = REGISTRY['bcb_delete_only']
        # extract helpers without re-registering the class
        source = literal('notebooks/azure_pbt_bcb_delete_only.ipynb', 'DELETE_ONLY_SOURCE')
        tree = ast.parse(source); tree.body = [n for n in tree.body if not isinstance(n, ast.ClassDef)]
        exec(compile(tree, '<frozen-delete-helpers>', 'exec'), scope)
    else:
        exec(literal('notebooks/azure_pbt_bcb_delete_only.ipynb', 'DELETE_ONLY_SOURCE'), scope)
        DeleteOnly = scope['DeleteOnly']
    return DeleteOnly, scope


def deletion(config):
    from pipeline.protocols.test_repair import feedback_summary
    from pipeline.protocols.unit_testing import suite_source
    data, spaces = validate_inputs()
    rows = read_complete(config['prefix'] + '-baseline', data)
    bundle = json.loads(bundle_path(config).read_text(encoding='utf-8'))
    if (bundle['dataset_sha256'] != file_hash(DATA) or
        bundle['source_records_sha256'] != file_hash(Path('runs') / (config['prefix'] + '-baseline') / 'records.jsonl') or
        bundle['source_config_sha256'] != file_hash(Path('runs') / (config['prefix'] + '-baseline') / 'config.json') or
        bundle['input_records_sha256'] != file_hash(Path('runs') / INPUTS / 'records.jsonl')):
        raise ValueError('deletion source bundle mismatch')
    DeleteOnly, scope = delete_definitions()
    context = {}
    for task, candidate in data.candidates():
        cid = candidate.candidate_id; row = rows[cid]; item = bundle['candidates'][cid]
        if item['source_record_sha256'] != object_hash(row) or item['inputs_sha256'] != object_hash(spaces[cid]) or item['code_sha256'] != byte_hash(candidate.code.encode()):
            raise ValueError('deletion candidate linkage mismatch')
        raw = row['calls'][0]['raw'] if len(row['calls']) == 1 else ''
        source, error = suite_source(raw)
        if source is None:
            context[cid] = {'eligible': False, 'reason': 'baseline source parse failure: ' + str(error)}
            continue
        tests = scope['exact_tests'](source)
        if len(tests) != 10:
            raise ValueError(f'{cid}: deletion requires ten original tests; review changed source population')
        if item['suite_sha256'] != byte_hash(source.encode()):
            raise ValueError('deletion suite hash mismatch')
        diagnostic = feedback_summary(item['result'], None, source, spaces[cid])
        visible = {k: diagnostic[k] for k in ('complete', 'n_records', 'n_expected') if k in diagnostic}
        visible['tests'] = None if diagnostic['tests'] is None else [
            {'test': r['test'], 'counts': r.get('counts'), 'events': [{k: e[k] for k in ('prop', 'i', 'outcome')} for e in r['events']]}
            for r in diagnostic['tests']]
        context[cid] = {'eligible': True, 'source': source, 'source_sha256': item['suite_sha256'],
                        'tests': sorted(tests), 'space': spaces[cid], 'diagnostic': visible}
    return DeleteOnly(run_name=config['prefix'] + '-delete-only', source_context=context,
                      code_visible=False, **common(config))
