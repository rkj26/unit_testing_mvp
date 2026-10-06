"""Explicitly gated fixed-input reproduction CLI. No model call occurs on import/init/cached."""
from __future__ import annotations
import argparse
import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from . import __version__
from . import backend as b

ARCHIVE = Path(os.environ.get('PBT_ARCHIVE', '/opt/archive/snapshot'))
PAID = {'baseline-smoke', 'baseline', 'revision-smoke', 'revisions', 'delete-smoke', 'delete'}
STAGES = sorted(PAID | {'feedback', 'replay', 'analyze', 'preflight'})


def write_new(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True, indent=2) + '\n'
    if path.exists():
        if path.read_text(encoding='utf-8') != raw:
            raise ValueError(f'immutable artifact already exists: {path}')
        return
    with path.open('x', encoding='utf-8') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def strict_lines(path):
    path = Path(path)
    if not path.exists():
        return []
    raw = path.read_text(encoding='utf-8')
    if raw and not raw.endswith('\n'):
        raise ValueError(f'truncated artifact; preserve and review before resuming: {path}')
    return [json.loads(line) for line in raw.splitlines()]


def append(path, value):
    with Path(path).open('a', encoding='utf-8') as f:
        f.write(json.dumps(value, sort_keys=True) + '\n'); f.flush(); os.fsync(f.fileno())


def validate_config(config):
    if set(config) != {'prefix', 'model', 'docker_image'}:
        raise ValueError('config requires exactly prefix, model, docker_image')
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', config['prefix']) or config['prefix'].startswith('azure-terra-'):
        raise ValueError('use a new lowercase prefix up to 48 characters, never the archive prefix')
    if not config['model'].startswith('openai-api/azureai/') or 'YOUR_' in config['model']:
        raise ValueError('model must name your Azure deployment')
    if not re.fullmatch(r'(?:sha256:|[^\s]+@sha256:)[0-9a-f]{64}', config['docker_image']):
        raise ValueError('docker_image must be an immutable full sha256 reference')


def inventory(project):
    files = [Path(b.DATA)]
    files += [p.relative_to(project) for folder in ('pipeline', 'prompts', 'notebooks')
              for p in (project / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [Path('runs') / b.INPUTS / n for n in ('config.json', 'records.jsonl', 'statement-review-v1.json')]
    return {p.as_posix(): b.file_hash(project / p) for p in sorted(files)}


def prepare_copy(destination):
    if destination.exists():
        raise ValueError('destination already exists; never overwrite an experiment')
    shutil.copytree(ARCHIVE, destination, ignore=shutil.ignore_patterns(
        '.env', '.venv', '__pycache__', '.pytest_cache', '.ipynb_checkpoints'))


@contextlib.contextmanager
def project_context(project):
    old = Path.cwd(); old_path = sys.path[:]
    os.chdir(project); sys.path.insert(0, str(project))
    try:
        yield
    finally:
        os.chdir(old); sys.path[:] = old_path


def init(args):
    config = read_json(args.config); validate_config(config)
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('init requires an empty output directory')
    output.mkdir(parents=True, exist_ok=True)
    project = output / 'project'; prepare_copy(project)
    with project_context(project):
        b.validate_inputs()
    write_new(output / 'study.json', config)
    write_new(output / 'manifest.json', {'runner_version': __version__, 'config_sha256': b.object_hash(config),
              'source_files': inventory(project), 'runner_files': {p.name: b.file_hash(p) for p in Path(__file__).parent.glob('*.py')},
              'fixed_inputs_reused': True, 'population_tasks': 26, 'logical_call_ceiling': 208})
    deps = Path('/opt/runner-dependencies.txt')
    if deps.exists():
        shutil.copyfile(deps, output / 'runner-dependencies.txt')
    candidate_deps = Path('/opt/candidate-dependencies.txt')
    if candidate_deps.exists():
        shutil.copyfile(candidate_deps, output / 'candidate-dependencies.txt')
    print(json.dumps({'initialized': str(output), 'model_calls': 0, 'next': 'run --stage preflight'}))


def study(output):
    output = Path(output).resolve(); config = read_json(output / 'study.json')
    validate_config(config); manifest = read_json(output / 'manifest.json')
    project = output / 'project'
    if b.object_hash(config) != manifest['config_sha256'] or inventory(project) != manifest['source_files']:
        raise ValueError('frozen config/source inputs changed; create a separate study')
    if {p.name: b.file_hash(p) for p in Path(__file__).parent.glob('*.py')} != manifest['runner_files']:
        raise ValueError('runner changed since initialization; use the original image')
    return output, project, config


def saved_rows(run):
    rows = strict_lines(run.records_path)
    ids = [r['candidate_id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate candidate records')
    return rows


def completed_run(config, arm):
    from pipeline.data import Dataset
    return b.read_complete(config['prefix'] + '-' + arm, Dataset.load(b.DATA))


def run_candidates(run, pairs, output, stage, allowance):
    """Sequential durable calls; an ambiguous attempt is never re-paid automatically."""
    from pipeline import model as model_mod
    run.write_config(); run.prepare(run.data)
    existing = {r['candidate_id'] for r in saved_rows(run)}
    attempts = strict_lines(output / 'attempts.jsonl')
    uncertain = {(x['run_name'], x['candidate_id']) for x in attempts}
    original = model_mod.complete_sync
    for task, candidate in pairs:
        cid = candidate.candidate_id
        if cid in existing:
            continue
        if (run.run_name, cid) in uncertain:
            raise ValueError(f'previous unrecorded/ambiguous model attempt for {cid}; manual review required')
        used_for_candidate = False
        def guarded(*pos, **kw):
            nonlocal used_for_candidate
            if used_for_candidate or allowance['left'] <= 0 or len(strict_lines(output / 'attempts.jsonl')) >= 208:
                # BaseException bypasses Run's ordinary infra-record catch: fail closed, do not consume candidate.
                raise SystemExit('call budget exhausted; preserve lock and review, never silently record a negative')
            append(output / 'attempts.jsonl', {'stage': stage, 'run_name': run.run_name,
                    'candidate_id': cid, 'reserved_at': time.time(), 'model': run.model,
                    'prompt_sha256': b.byte_hash(str(pos[1]).encode())})
            used_for_candidate = True; allowance['left'] -= 1
            return original(*pos, **kw)
        model_mod.complete_sync = guarded
        try:
            record = run._record_for(task, candidate)
            append(run.records_path, record)
            print(json.dumps({'arm': run.run_name, 'candidate_id': cid, 'failed': record['failed']}), flush=True)
        finally:
            model_mod.complete_sync = original


def approval(output, stage):
    value = read_json(output / f'approval-{stage}.json')
    smoke = {'baseline': 'baseline-smoke', 'revisions': 'revision-smoke', 'delete': 'delete-smoke'}[stage]
    if value['smoke_sha256'] != b.file_hash(output / f'{smoke}.done.json'):
        raise ValueError('approval does not match the completed smoke')
    for path, expected in value['record_sha256'].items():
        if b.file_hash(output / path) != expected:
            raise ValueError('smoke records changed since approval')


def validate_done(output, config, stage):
    value = read_json(output / f'{stage}.done.json')
    if (value.get('stage') != stage or value.get('config_sha256') != b.object_hash(config) or
        value.get('manifest_sha256') != b.file_hash(output / 'manifest.json')):
        raise ValueError('stage completion marker is corrupt or belongs to another configuration')
    if stage == 'preflight':
        result = value.get('preflight_result')
        if (not isinstance(result, dict) or not result.get('ok') or not result.get('complete') or
            result.get('n_records') != 2 or result.get('n_expected') != 2 or
            len(result.get('records', [])) != 2 or any(r.get('outcome') != 'pass' for r in result['records'])):
            raise ValueError('preflight marker does not contain a successful sandbox test')
    for path, expected in value.get('final_record_sha256', {}).items():
        if b.file_hash(output / path) != expected:
            raise ValueError('completed-stage records changed')
    for smoke in value.get('smoke_records', []):
        path = output / 'project' / 'runs' / smoke['run_name'] / 'records.jsonl'
        matches = [r for r in strict_lines(path) if r['candidate_id'] == smoke['candidate_id']]
        if matches != [smoke]:
            raise ValueError('saved smoke record changed or is absent')
    return value


def approve(args):
    output, project, config = study(args.output)
    smoke = {'baseline': 'baseline-smoke', 'revisions': 'revision-smoke', 'delete': 'delete-smoke'}[args.stage]
    if not args.note.strip():
        raise ValueError('review note required')
    done = validate_done(output, config, smoke)
    if not done['smoke_records'] or any(r['failed'] for r in done['smoke_records']):
        raise ValueError('smoke failed or has no measured record; do not approve automatically')
    for row in done['smoke_records']:
        counts = row.get('n_pairs_by_outcome')
        if (not isinstance(counts, dict) or row.get('n_pairs_expected', 0) <= 0 or
            row.get('n_pairs_run') != row['n_pairs_expected'] or
            counts.get('prop_error') != 0 or counts.get('candidate_crash') != 0):
            raise ValueError('smoke grid is incomplete or contains execution errors')
    hashes = {p: b.file_hash(output / p) for p in done['record_paths']}
    write_new(output / f'approval-{args.stage}.json', {'smoke_sha256': b.file_hash(output / f'{smoke}.done.json'),
              'record_sha256': hashes, 'review_note': args.note})
    print(json.dumps({'approved': args.stage, 'model_calls': 0}))


def preflight(config):
    from pipeline import sandbox
    data, _ = b.validate_inputs()
    subprocess.run(['docker', 'image', 'inspect', config['docker_image']], check=True, stdout=subprocess.DEVNULL)
    result = sandbox.run_raw(data.tasks[0], 'def task_func(values):\n n=len(values); values.append(99); return n',
        'def test_one(run,x): assert run(x)==1\ndef test_two(run,x): assert run(x)==1', [{'values':[1]}],
        timeout_s=30, isolation=sandbox.Isolation.DOCKER, docker_image=config['docker_image'])
    if not result['ok'] or not result['complete'] or len(result['records']) != 2 or any(r['outcome'] != 'pass' for r in result['records']):
        raise ValueError(f'sandbox/deepcopy smoke failed: {result}')
    return result


def replay(config):
    from pipeline import sandbox
    data, spaces = b.validate_inputs()
    root = Path('runs') / (config['prefix'] + '-study')
    for arm in ('baseline', 'no-feedback', 'feedback', 'delete-only'):
        name = config['prefix'] + '-' + arm
        if not (Path('runs') / name / 'records.jsonl').exists():
            if arm == 'delete-only': continue
            raise ValueError('A/B/C must complete before replay')
        rows = completed_run(config, arm)
        for task in data.tasks:
            row = rows[task.attack.candidate_id]; source = row.get('tests_src')
            identity = {'dataset_sha256': b.file_hash(b.DATA),
                        'source_config_sha256': b.file_hash(Path('runs') / name / 'config.json'),
                        'source_record_sha256': b.object_hash(row), 'inputs_sha256': b.object_hash(spaces[task.attack.candidate_id]),
                        'honest_code_sha256': b.byte_hash(task.honest.code.encode()),
                        'suite_sha256': None if source is None else b.byte_hash(source.encode()),
                        'docker_image': config['docker_image'], 'timeout_seconds': 120}
            path = root / 'same-input-honest-replay-v1' / name / (task.task_id + '.json')
            if path.exists():
                if read_json(path)['identity'] != identity: raise ValueError('replay identity mismatch')
                continue
            result = None; failure = 'no saved parseable suite' if source is None else None
            if source is not None:
                try:
                    result = sandbox.run_raw(task, task.honest.code, source, spaces[task.attack.candidate_id],
                                            timeout_s=120, isolation=sandbox.Isolation.DOCKER, docker_image=config['docker_image'])
                except Exception as error:
                    failure = type(error).__name__ + ': ' + str(error)
            write_new(path, {'identity': identity, 'result': result, 'failure': failure})


def run(args):
    output, project, config = study(args.output); stage = args.stage
    if (output / 'smoke.lock').exists():
        raise ValueError('component-smoke output cannot become a full study; use a separate new output')
    done_path = output / f'{stage}.done.json'
    if done_path.exists():
        validate_done(output, config, stage)
        print(json.dumps({'already_complete': stage, 'model_calls': 0})); return
    if stage in PAID:
        if not args.allow_paid or args.max_calls is None or args.max_calls < 1:
            raise ValueError('paid stage requires --allow-paid and positive --max-calls')
        if not os.environ.get('AZUREAI_API_KEY') or not os.environ.get('AZUREAI_BASE_URL'):
            raise ValueError('provide AZUREAI_API_KEY and AZUREAI_BASE_URL at runtime')
        if not (output / 'preflight.done.json').exists(): raise ValueError('run preflight first')
        validate_done(output, config, 'preflight')
        arms = ['baseline'] if stage.startswith('baseline') else ['no-feedback','feedback'] if stage.startswith('revision') else ['delete-only']
        reserve = len(arms) if stage.endswith('smoke') else sum(
            52 - len(strict_lines(project / 'runs' / (config['prefix'] + '-' + a) / 'records.jsonl')) for a in arms)
        if args.max_calls < reserve:
            raise ValueError(f'approve a conservative allowance of at least {reserve} calls for this stage; no calls started')
    if stage in ('baseline', 'revisions', 'delete'): approval(output, stage)
    prerequisites = {'feedback':['baseline'], 'revision-smoke':['feedback'], 'revisions':['feedback'],
        'delete-smoke':['feedback','revisions'], 'delete':['feedback','revisions'],
        'replay':['baseline','revisions'], 'analyze':['replay']}
    for previous in prerequisites.get(stage, []): validate_done(output, config, previous)
    # Persistent lock is intentional: a stopped/ambiguous worker cannot be mistaken for a fresh launch.
    active_lock = output / 'active.lock'
    with active_lock.open('x') as f: f.write(json.dumps({'pid': os.getpid(), 'stage': stage}))
    with (output / f'{stage}.lock').open('x') as f: f.write(str(os.getpid()))
    with project_context(project):
        from pipeline import model as model_mod
        from pipeline.protocols import unit_testing
        model_mod.INSPECT_HTTP_RETRIES = 0; unit_testing.INSPECT_HTTP_RETRIES = 0
        b.install_sandbox()
        data, spaces = b.validate_inputs(); smoke_records = []; paths = []
        allowance = {'left': args.max_calls or 0}; preflight_result = None
        if stage == 'preflight': preflight_result = preflight(config)
        elif stage == 'feedback':
            write_new(b.bundle_path(config), b.make_bundle(config))
            paths.append(str((project / b.bundle_path(config)).relative_to(output)))
        elif stage == 'replay':
            replay(config)
            paths += [str(p.relative_to(output)) for p in
                (project / 'runs' / (config['prefix'] + '-study') / 'same-input-honest-replay-v1').rglob('*.json')]
        elif stage == 'analyze':
            from .analysis import analyze
            include_delete = (Path('runs') / (config['prefix'] + '-delete-only') / 'records.jsonl').exists()
            analyze(project, config['prefix'], b.INPUTS, output / 'analysis' / 'metrics.json', include_delete)
            paths.append('analysis/metrics.json')
        else:
            if stage.startswith('baseline'): arms = ['baseline']
            elif stage.startswith('revision'): arms = ['no-feedback', 'feedback']
            else: arms = ['delete-only']
            protocols = [b.protocol(config, arm) for arm in arms]
            candidates = list(data.candidates())
            if stage.endswith('smoke'):
                if stage == 'delete-smoke':
                    candidates = [x for x in candidates if protocols[0].source_context[x[1].candidate_id]['eligible']]
                    if not candidates: raise ValueError('no eligible deletion source')
                candidates = candidates[:1]
            # Preserve alternating B/C order; execute at most one provider request per candidate per arm.
            for index, pair in enumerate(candidates):
                for protocol in (protocols if index % 2 == 0 else protocols[::-1]):
                    run_candidates(protocol, [pair], output, stage, allowance)
            for protocol in protocols:
                rows = saved_rows(protocol)
                if stage.endswith('smoke'):
                    smoke_records += [r for r in rows if r['candidate_id'] == candidates[0][1].candidate_id]
                else: completed_run(config, protocol.run_name.removeprefix(config['prefix'] + '-'))
                paths.append(str((project / protocol.records_path).relative_to(output)))
        write_new(done_path, {'stage': stage, 'smoke_records': smoke_records, 'record_paths': paths,
                              'new_attempts': (args.max_calls or 0) - allowance['left'],
                              'config_sha256': b.object_hash(config), 'manifest_sha256': b.file_hash(output / 'manifest.json'),
                              'preflight_result': preflight_result,
                              'final_record_sha256': {} if stage.endswith('smoke') else {p: b.file_hash(output / p) for p in paths}})
    active_lock.unlink()
    print(json.dumps({'stage_complete': stage, 'new_attempts': (args.max_calls or 0) - allowance['left']}))


def cached(args):
    from .analysis import analyze
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()): raise ValueError('cached output directory must be empty')
    output.mkdir(parents=True, exist_ok=True)
    # Pure read-only artifact analysis; no credentials, protocol imports, candidate execution or Docker.
    result = analyze(ARCHIVE, b.ORIGINAL_PREFIX, b.INPUTS, output / 'metrics.json', True)
    print(json.dumps(result, indent=2))


def status(args):
    output, project, config = study(args.output)
    print(json.dumps({'prefix': config['prefix'], 'reserved_calls': len(strict_lines(output / 'attempts.jsonl')),
        'completed': [p.name for p in output.glob('*.done.json')],
        'unresolved_locks': [p.name for p in output.glob('*.lock') if not p.with_suffix('.done.json').exists()]}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('cached', 'init', 'run', 'approve', 'status'):
        item = sub.add_parser(command); item.add_argument('--output', required=True)
        if command == 'init': item.add_argument('--config', required=True)
        if command == 'run':
            item.add_argument('--stage', choices=STAGES, required=True)
            item.add_argument('--allow-paid', action='store_true'); item.add_argument('--max-calls', type=int)
        if command == 'approve':
            item.add_argument('--stage', choices=['baseline','revisions','delete'], required=True)
            item.add_argument('--note', required=True)
    item = sub.add_parser('smoke', help='Fresh one-candidate four-arm component journey; never a full batch')
    item.add_argument('--output', required=True)
    item.add_argument('--config', required=True)
    item.add_argument('--allow-paid', action='store_true')
    item.add_argument('--max-cost-usd', type=float, default=1.0)
    item.add_argument('--test-contract', choices=['legacy', 'self-contained-v1'], default='self-contained-v1',
                      help='Versioned startup prompt; legacy preserves the original generation contract')
    args = parser.parse_args()
    try:
        if args.command == 'smoke':
            from .smoke import run_smoke
            return run_smoke(args)
        globals()[args.command](args)
    except Exception as error:
        print(f'{type(error).__name__}: {error}', file=sys.stderr); return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
