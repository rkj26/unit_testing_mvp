"""Zero-API diagnostic: isolate the effect of missing imports; never replace research scores."""
import argparse
import ast
from collections import Counter
import json
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--record', required=True)
parser.add_argument('--image', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
output = Path(args.output)
if output.exists():
    raise ValueError('diagnostic output exists; preserve evidence')
record = json.loads(Path(args.record).read_text())
source = record['score']['tests_src']
os.chdir('/opt/archive/snapshot')
sys.path.insert(0, os.getcwd())
from pbt_runner import backend as b
from pbt_runner.test_contract import unresolved_names
from pipeline import sandbox
from pipeline.protocols.unit_testing import suite_source

assert suite_source(record['score']['calls'][0]['raw'])[0] == source
b.install_sandbox()
data, spaces = b.validate_inputs()
task, candidate = next((t,c) for t,c in data.candidates() if c.candidate_id == 'BCB121_honest')
tree = ast.parse(source)
affected = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and unresolved_names(ast.unparse(node)):
        issues = unresolved_names(ast.unparse(node))
        if issues != [f'{node.name}: unresolved names: pd']:
            raise ValueError('fixture contains an issue other than missing pd')
        node.body.insert(0, ast.Import(names=[ast.alias(name='pandas', asname='pd')]))
        affected.append(node.name)
diagnostic_source = ast.unparse(ast.fix_missing_locations(tree))
assert affected and not unresolved_names(diagnostic_source)
results = {}
for label, text in [('original', source), ('diagnostic_import_only', diagnostic_source)]:
    result = sandbox.run_raw(task, candidate.code, text, spaces[candidate.candidate_id],
        timeout_s=120, isolation=sandbox.Isolation.DOCKER, docker_image=args.image)
    if not result['ok'] or not result['complete']:
        raise ValueError(f'{label} infrastructure failure')
    results[label] = {'outcomes': dict(Counter(r['outcome'] for r in result['records'])), 'execution': result}
report = {'scope': 'counterfactual diagnostic only, not repaired experiment results', 'provider_calls': 0,
    'candidate_id': candidate.candidate_id, 'image': args.image, 'affected_tests': affected,
    'original_source_sha256': b.byte_hash(source.encode()),
    'diagnostic_source_sha256': b.byte_hash(diagnostic_source.encode()), 'results': results}
output.parent.mkdir(parents=True, exist_ok=True)
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps({k:v['outcomes'] for k,v in results.items()}))
assert results['original']['outcomes'] == {'prop_error':55, 'pass':35}
assert results['diagnostic_import_only']['outcomes'] == {'pass':90}
