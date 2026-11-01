"""Verify public scalar projections, without model/candidate execution or private sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

NATIVE = frozenset({'run_name', 'protocol', 'split', 'task_id', 'candidate_id',
    'label', 'is_attack', 'failed', 'blame', 'solution_chars', 'pairs_total',
    'pairs_passed', 'pairs_crashed', 'pair_agreement', 'solves', 'attempts_agree',
    'dropped', 'n_parsed', 'n_requested', 'avg_score', 'triggers_run',
    'n_pairs_run', 'n_pairs_expected'})
NATIVE = NATIVE | frozenset({'n_fired', 'raw_n_parsed', 'plan_chars', 'eligibility_exclusion', 'exclusion_kind'})
DERIVED = frozenset({'derived_scores_count', 'derived_fired_count',
    'derived_catches_count', 'derived_critiqued_out_count',
    'derived_n_pairs_by_outcome_is_null', 'derived_n_pairs_pass',
    'derived_n_pairs_catch', 'derived_n_pairs_candidate_crash', 'derived_n_pairs_prop_error'})

DERIVED = DERIVED | frozenset({'derived_plan_names_count', 'derived_eligibility_dropped_count', 'derived_tests_not_shown_count', 'derived_provider_filter_exclusion_recorded', 'derived_qualification_result_is_null', 'derived_qualification_bare_run_ok', 'derived_qualification_complete', 'derived_qualification_domain_excluded', 'derived_qualification_exclusion_count', 'derived_qualification_fixture_unmeasured', 'derived_qualification_n_expected', 'derived_qualification_n_records', 'derived_qualification_ok', 'derived_qualification_runtime_unmeasured'})


def verify(root: Path) -> dict:
    manifest = json.loads((root/'provenance.json').read_bytes())
    if manifest['schema_version'] != 3 or manifest['resumable'] is not False:
        raise ValueError('Wrong snapshot contract')
    result = {}
    for name, expected in manifest['runs'].items():
        run = root/'data/runs'/name
        raw = (run/'records.jsonl').read_bytes()
        config = (run/'config.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected['published_records_sha256']:
            raise ValueError('Records checksum mismatch')
        if hashlib.sha256(config).hexdigest() != expected['published_config_sha256']:
            raise ValueError('Config checksum mismatch')
        if raw and not raw.endswith(b'\n'):
            raise ValueError('Torn final record')
        rows = [json.loads(line) for line in raw.splitlines()]
        if len(rows) != expected['rows'] or len({r['candidate_id'] for r in rows}) != expected['distinct_candidates']:
            raise ValueError('Row/identity count mismatch')
        if len(rows) != len({r['candidate_id'] for r in rows}):
            raise ValueError('Duplicate identities')
        if len(expected['source_row_sha256_in_order']) != len(rows) or any(
            not re.fullmatch('[a-f0-9]{64}', value) for value in expected['source_row_sha256_in_order']):
            raise ValueError('Invalid private-source row hash list')
        for row in rows:
            if set(row) - NATIVE - DERIVED or any(type(value) in (list, dict) for value in row.values()):
                raise ValueError('Non-allowlisted or nested private payload')
            if row['run_name'] != name or type(row['failed']) is not bool or row['blame'] not in (None, 'model', 'infra'):
                raise ValueError('Bad identity/failure fields')
        result[name] = len(rows)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, nargs='?', default=Path(__file__).resolve().parents[1])
    print(json.dumps(verify(parser.parse_args().root), indent=2))
