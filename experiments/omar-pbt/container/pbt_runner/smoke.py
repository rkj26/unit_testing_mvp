"""Connected four-call component journey using frozen protocol score methods.

Not a full 52-candidate Run: the original SecondRevision.prepare population gate is
not exercised here. Fresh baseline/diagnostics are bound to one reviewed candidate.
Full-study prepare/linkage remains covered by the separate workflow regression.
"""
from __future__ import annotations
import json
import math
import os
import re
from pathlib import Path
import time

from . import backend as b
from . import test_contract

MODEL = 'openai-api/azureai/gpt-5.6-terra'
CANDIDATE = 'BCB121_honest'
ARMS = ('baseline', 'no-feedback', 'feedback', 'delete-only')
MAX_OUTPUT = 8192
MAX_REQUEST_BYTES = 32000
# Twice published Azure Standard Global Terra rates. This is conservative token
# accounting, not a promise about a customer's Azure invoice or non-inference fees.
INPUT_RATE = 4.0
OUTPUT_RATE = 24.0


def usage_cost(usage):
    if not isinstance(usage, dict):
        return None
    input_n, output_n = usage.get('input_tokens'), usage.get('output_tokens')
    if any(type(n) is not int or n < 0 for n in (input_n, output_n)):
        return None
    extras = [usage.get(k, 0) or 0 for k in ('input_tokens_cache_read', 'input_tokens_cache_write')]
    if any(type(n) is not int or n < 0 for n in extras):
        return None
    return ((input_n + sum(extras)) * INPUT_RATE + output_n * OUTPUT_RATE) / 1e6


class Guard:
    """Reserve before sending; at most one request per arm, no retries/resume."""
    def __init__(self, output, cap):
        from .__main__ import append
        self.output, self.cap, self.append = Path(output), cap, append
        self.count, self.charged, self.arm, self.seen = 0, 0.0, None, set()

    def call(self, original, model, prompt, kind, schema=None):
        runtime = model.runtime
        if (runtime.name != MODEL or runtime.max_tokens != MAX_OUTPUT or
                runtime.http_retries != 0 or runtime.reasoning_effort.value != 'low'):
            raise ValueError('smoke model/token/retry settings changed')
        if self.arm not in ARMS or self.arm in self.seen or self.count >= 4:
            raise ValueError('four-call/per-arm ceiling reached')
        shape = schema.model_dump(mode='json') if schema is not None else {}
        nbytes = len(prompt.encode()) + len(json.dumps(shape, ensure_ascii=False).encode()) + 2048
        if nbytes > MAX_REQUEST_BYTES:
            raise ValueError('request exceeds conservative byte ceiling; no call sent')
        reserve = (nbytes * INPUT_RATE + MAX_OUTPUT * OUTPUT_RATE) / 1e6
        if self.charged + reserve > self.cap:
            raise ValueError('next-call reserve exceeds cost limit; no call sent')
        self.append(self.output / 'attempts.jsonl', {'arm': self.arm, 'attempt': self.count + 1,
            'reserved_at': time.time(), 'model': MODEL, 'prompt_sha256': b.byte_hash(prompt.encode()),
            'request_byte_bound': nbytes, 'output_token_cap': MAX_OUTPUT, 'http_retries': 0,
            'reserve_usd_at_buffered_rates': reserve})
        self.count += 1; self.seen.add(self.arm); self.charged += reserve
        # A transport failure remains reserved and ends this command, never replayed.
        response = original(model, prompt, kind, schema)
        actual = usage_cost(response.usage)
        charged = reserve if actual is None else max(0.0, actual)
        self.charged += charged - reserve
        self.append(self.output / 'usage.jsonl', {'arm': self.arm, 'usage': response.usage,
            'response_model': response.response_model, 'response_id': response.response_id,
            'charged_usd_at_buffered_rates': charged, 'usage_missing': actual is None})
        if actual is not None and actual > reserve:
            raise ValueError('provider usage exceeded reserved bound; stop and review')
        if not re.fullmatch(r'gpt-5\.6-terra(?:-\d{4}-\d{2}-\d{2})?', response.response_model or ''):
            raise ValueError('provider reported a different or missing response model; stop and review')
        return response


def measured(score):
    counts = score.get('n_pairs_by_outcome')
    return (not score.get('failed', False) and isinstance(counts, dict)
            and score.get('n_pairs_expected', 0) > 0
            and score.get('n_pairs_run') == score['n_pairs_expected']
            and counts.get('prop_error') == 0 and counts.get('candidate_crash') == 0)


def verify_exact_subset(original, selected, extractor):
    """Compare text and order, not original line offsets (which shift after deletion)."""
    source = extractor(original)
    retained = extractor(selected)
    if (not retained or any(name not in source for name in retained)
            or list(retained) != [name for name in source if name in retained]
            or any(source[name][2] != item[2] for name, item in retained.items())):
        raise ValueError('delete-only result is not an exact-text subset')
    return True


def run_smoke(args):
    from . import __main__ as cli
    contract = getattr(args, 'test_contract', test_contract.VERSION)
    if contract not in ('legacy', test_contract.VERSION):
        raise ValueError('unknown test contract')
    config = cli.read_json(args.config); cli.validate_config(config)
    if config['model'] != MODEL:
        raise ValueError('this priced four-call smoke requires gpt-5.6-terra; no model fallback')
    if not math.isfinite(args.max_cost_usd) or not 0 < args.max_cost_usd <= 1:
        raise ValueError('smoke cost ceiling must be positive and at most USD 1')
    if not args.allow_paid:
        raise ValueError('smoke requires explicit --allow-paid; no calls started')
    if not all(os.environ.get(k) for k in ('AZUREAI_API_KEY', 'AZUREAI_BASE_URL')):
        raise ValueError('set AZUREAI_API_KEY and AZUREAI_BASE_URL at runtime')
    if not os.environ['AZUREAI_BASE_URL'].rstrip('/').endswith('/openai/v1'):
        raise ValueError('AZUREAI_BASE_URL must end /openai/v1, not /responses')
    cli.init(args)  # Requires a new empty output; validates all original input hashes.
    output, project, config = cli.study(args.output)
    lock = output / 'smoke.lock'
    with lock.open('x') as f: f.write('exclusive four-call smoke; never delete to retry\n')
    report = {'scope': 'single-candidate component smoke, not a population experiment',
        'candidate_id': CANDIDATE, 'model': MODEL, 'stages': [], 'completed': False,
        'test_contract': contract,
        'test_contract_sha256': b.byte_hash(test_contract.INSTRUCTIONS.encode()) if contract != 'legacy' else None,
        'full_second_revision_prepare_exercised': False,
        'pricing_reference': 'https://azure.microsoft.com/en-us/blog/gpt-5-6-now-available-in-microsoft-foundry/',
        'buffered_usd_per_million': {'input': INPUT_RATE, 'output': OUTPUT_RATE},
        'max_cost_usd_at_buffered_rates': args.max_cost_usd}
    guard = Guard(output, args.max_cost_usd)
    with cli.project_context(project), test_contract.install(contract):
        from pipeline import model as model_mod, sandbox
        from pipeline.protocols import UnitTesting, SecondRevision, unit_testing
        from pipeline.protocols.test_repair import feedback_summary
        model_mod.INSPECT_HTTP_RETRIES = 0; unit_testing.INSPECT_HTTP_RETRIES = 0
        b.install_sandbox()
        original_call, original_sandbox = model_mod.complete_sync, sandbox.run_raw
        executions = []
        def captured(*a, **kw):
            result = original_sandbox(*a, **kw); executions.append(result); return result
        sandbox.run_raw = captured
        model_mod.complete_sync = lambda *a, **kw: guard.call(original_call, *a, **kw)
        try:
            data, spaces = b.validate_inputs()
            task, candidate = next((t,c) for t,c in data.candidates() if c.candidate_id == CANDIDATE)
            report['preflight'] = cli.preflight(config)
            report['image'] = config['docker_image']
            params = b.common(config)
            base = UnitTesting(run_name=config['prefix']+'-component-baseline', code_visible=True, **params)
            base.prepare(data)

            def execute(arm, protocol):
                guard.arm = arm; start = len(executions)
                cli.write_new(output / 'components' / (arm+'-config.json'), protocol.config() | {'test_contract': contract})
                score = protocol.score(task, candidate)
                issues = test_contract.unresolved_names(score.get('tests_src')) if contract != 'legacy' else []
                entry = {'arm': arm, 'score': score, 'execution': executions[start:],
                         'source_contract_errors': issues, 'measured': measured(score) and not issues}
                cli.write_new(output / 'components' / (arm+'.json'), entry)
                report['stages'].append(entry)
                print(json.dumps({'arm': arm, 'measured': entry['measured'], 'calls': len(score.get('calls',[]))}), flush=True)
                return score

            initial = execute('baseline', base)
            if not report['stages'][0]['measured']:
                details = '; '.join(report['stages'][0]['source_contract_errors'])
                if not details:
                    details = str(initial.get('n_pairs_by_outcome') or initial.get('reason') or 'no complete grid')
                raise ValueError('baseline unusable; dependent calls blocked: ' + details)
            source, error = unit_testing.suite_source(initial['calls'][0]['raw'])
            if error or source != initial['tests_src']:
                raise ValueError('baseline raw-response/suite mismatch')
            raw_result = report['stages'][0]['execution'][-1]
            diagnostic = feedback_summary(raw_result, None, source, spaces[CANDIDATE])
            provenance = {'source_record_sha256': b.object_hash(initial), 'inputs_sha256': b.object_hash(spaces[CANDIDATE]),
                          'code_sha256': b.byte_hash(candidate.code.encode()), 'suite_sha256': b.byte_hash(source.encode())}
            bundle_path = output / 'component-source-bundle.json'
            bundle = {'scope': 'one-candidate component linkage, not full-study bundle', 'candidate_id': CANDIDATE,
                'dataset_sha256': b.file_hash(b.DATA), 'provenance': provenance, 'baseline': initial,
                'inputs': spaces[CANDIDATE], 'execution': raw_result, 'diagnostic': diagnostic}
            cli.write_new(bundle_path, bundle); bundle_hash = b.file_hash(bundle_path)
            report['component_source_bundle_sha256'] = bundle_hash
            def validate_source():
                if b.file_hash(bundle_path) != bundle_hash or b.object_hash(cli.read_json(bundle_path)) != b.object_hash(bundle):
                    raise ValueError('component source bundle changed')

            for arm, visible in (('no-feedback', False), ('feedback', True)):
                validate_source()
                revision = SecondRevision(run_name=config['prefix']+'-component-'+arm,
                    baseline_run=base.run_name, source_bundle=str(bundle_path), source_bundle_sha256=bundle_hash,
                    feedback_visible=visible, max_candidates=52, code_visible=False, **params)
                # Preserve the full dataset contract; bind only this component rather than
                # fabricate records for the other 51 candidates to satisfy prepare().
                revision.trigger_space = base.trigger_space
                revision.revision_context = {CANDIDATE: {'eligible': True, 'source': source,
                    'diagnostic': diagnostic, 'provenance': provenance, 'stratum': 'complete_source'}}
                execute(arm, revision)
            validate_source()
            DeleteOnly, helpers = b.delete_definitions()
            tests = helpers['exact_tests'](source)
            if len(tests) != 10: raise ValueError('deletion requires exactly ten source tests')
            visible = {k:diagnostic[k] for k in ('complete','n_records','n_expected') if k in diagnostic}
            visible['tests'] = None if diagnostic['tests'] is None else [
                {'test': row['test'], 'counts':row.get('counts'),
                 'events':[{k:e[k] for k in ('prop','i','outcome')} for e in row['events']]} for row in diagnostic['tests']]
            delete = DeleteOnly(run_name=config['prefix']+'-component-delete-only', code_visible=False,
                source_context={CANDIDATE:{'eligible':True, 'source':source, 'source_sha256':provenance['suite_sha256'],
                    'tests':sorted(tests), 'space':spaces[CANDIDATE], 'diagnostic':visible}}, **params)
            selected = execute('delete-only', delete)
            if selected.get('tests_src'):
                report['delete_exact_subset_verified'] = verify_exact_subset(source, selected['tests_src'], helpers['exact_tests'])
            report['completed'] = guard.count == 4 and len(report['stages']) == 4 and all(x['measured'] for x in report['stages'])
        except Exception as error:
            # Raw provider exceptions can contain request/credential material. Their type is
            # enough for the public report; provider responses remain in successful records.
            report['error_type'] = type(error).__name__
            report['error'] = str(error) if isinstance(error, ValueError) else 'Provider/infrastructure failure; no automatic retry'
        finally:
            model_mod.complete_sync = original_call; sandbox.run_raw = original_sandbox
            report['attempts'] = guard.count; report['accounted_usd_at_buffered_rates'] = guard.charged
            cli.write_new(output / 'smoke-results.json', report)
    print(json.dumps({k:report.get(k) for k in ('completed','attempts','accounted_usd_at_buffered_rates','error_type','error')}))
    return 0 if report['completed'] else 1
