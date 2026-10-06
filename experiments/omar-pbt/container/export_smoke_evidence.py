"""Export only the bounded smoke's audit artifacts, never its project copy or credentials.

No model calls, Docker calls, or metrics recomputation. Refuses overwrites and obvious secrets.
The raw model replies/test source are deliberately retained for independent inspection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    source, destination = args.source.resolve(), args.destination.resolve()
    if destination.exists():
        raise ValueError('destination exists; never replace published evidence')
    names = ['smoke-results.json', 'attempts.jsonl', 'usage.jsonl', 'study.json',
             'manifest.json', 'component-source-bundle.json', 'runner-dependencies.txt',
             'candidate-dependencies.txt']
    names += [f'components/{arm}{suffix}.json'
              for arm in ('baseline', 'no-feedback', 'feedback', 'delete-only')
              for suffix in ('', '-config')]
    report = json.loads((source / 'smoke-results.json').read_text(encoding='utf-8'))
    if report['attempts'] != 4 or not report['completed']:
        raise ValueError('this release exporter requires a completed four-call smoke')
    hashes = {}
    for name in names:
        raw = (source / name).read_bytes()
        if re.search(rb'(?:sk-(?:or-v1-)?[A-Za-z0-9_-]{24,}|Bearer\s+[A-Za-z0-9._-]{24,})', raw):
            raise ValueError(f'possible secret in {name}; manual review required')
        hashes[name] = hashlib.sha256(raw).hexdigest()
    destination.mkdir(parents=True)
    for name in names:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    (destination / 'SHA256.json').write_text(json.dumps(hashes, indent=2, sort_keys=True)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'exported_files': len(names), 'provider_calls': 0}))


if __name__ == '__main__':
    main()
