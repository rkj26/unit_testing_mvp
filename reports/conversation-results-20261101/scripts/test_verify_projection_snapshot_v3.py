import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from verify_projection_snapshot_v3 import verify


class PublicSnapshotContract(unittest.TestCase):
    def fixture(self, root, rows):
        run = root/'data/runs/demo'
        run.mkdir(parents=True, exist_ok=True)
        raw = b''.join((json.dumps(row)+'\n').encode() for row in rows)
        config = b'{"run_name":"demo"}\n'
        (run/'records.jsonl').write_bytes(raw)
        (run/'config.json').write_bytes(config)
        manifest = {'schema_version': 3, 'resumable': False, 'runs': {'demo': {
            'published_records_sha256': hashlib.sha256(raw).hexdigest(),
            'published_config_sha256': hashlib.sha256(config).hexdigest(),
            'rows': len(rows), 'distinct_candidates': len(rows),
            'source_row_sha256_in_order': ['a'*64]*len(rows)}}}
        (root/'provenance.json').write_text(json.dumps(manifest))
        return run

    def test_valid_scalars(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.fixture(root, [{'run_name': 'demo', 'candidate_id': 'one', 'failed': True, 'blame': 'infra', 'n_pairs_run': None}])
            self.assertEqual(verify(root), {'demo': 1})

    def test_checksum_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = self.fixture(root, [{'run_name': 'demo', 'candidate_id': 'one', 'failed': False, 'blame': None}])
            (run/'records.jsonl').write_bytes(b'{}\n')
            with self.assertRaises(ValueError): verify(root)

    def test_private_field_and_duplicate_identity_rejected(self):
        for payload in ({'calls': []}, {'reason': 'private raw reply'}, {'avg_score': {'raw': 'private'}}):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                self.fixture(root, [{'run_name': 'demo', 'candidate_id': 'one', 'failed': False, 'blame': None, **payload}])
                with self.assertRaises(ValueError): verify(root)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = {'run_name': 'demo', 'candidate_id': 'one', 'failed': False, 'blame': None}
            self.fixture(root, [row, row])
            with self.assertRaises(ValueError): verify(root)


if __name__ == '__main__': unittest.main()
