"""Org Map claim-to-source check (read-only). Every node that is not "unknown" must cite at least one source that
exists (a ~/ or repo-relative file, or an http(s) link). Every line must carry evidence, and when that evidence is a
file path, the file must exist. Exit 1 lists each gap. Reads app/.data/org-map.json only; makes no network call."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
MAP = ROOT / 'app' / '.data' / 'org-map.json'


def resolves(ref: str) -> bool:
    ref = ref.strip()
    if ref.startswith(('http://', 'https://')):
        return True
    if ', ' in ref:  # a list of files: every one must exist
        return all(resolves(r) for r in ref.split(', '))
    path = re.split(r' (?:line|lines|rule|section) | \(', ref)[0].strip()
    if path.startswith('~/'):
        return (HOME / path[2:]).exists()
    if path.startswith('/'):
        return Path(path).exists()
    return (ROOT / path).exists()


def looks_like_path(text: str) -> bool:
    return bool(re.match(r'^(~/|/|[\w.-]+/)', text.strip()))


def main(argv: list[str]) -> int:
    only = argv[1] if len(argv) > 1 else ''  # optional id prefix filter, e.g. "obs:" or "traces:"
    data = json.loads(MAP.read_text())
    gaps = []
    for n in data['nodes']:
        if only and not n['id'].startswith(only) and not any(e['source'] == n['id'] or e['target'] == n['id'] for e in data['edges'] if e['id'].startswith(only)):
            continue
        if n['status'] == 'unknown':
            continue
        srcs = n.get('sources') or []
        if not srcs:
            gaps.append(f"node {n['id']}: no source")
        for s in srcs:
            if not resolves(s):
                gaps.append(f"node {n['id']}: source does not exist: {s}")
    for e in data['edges']:
        if only and not e['id'].startswith(only) and only not in (e['source'], e['target']) and not e['target'].startswith(only):
            continue
        ev = (e.get('evidence') or '').strip()
        if not ev:
            gaps.append(f"line {e['id']}: no evidence")
        elif looks_like_path(ev) and not resolves(ev):
            gaps.append(f"line {e['id']}: evidence file does not exist: {ev}")
    scope = f" (scope: {only})" if only else ''
    print(json.dumps({'map_built_at': data.get('built_at'), 'scope': only or 'whole map', 'nodes': len(data['nodes']),
                      'lines': len(data['edges']), 'gaps': gaps}, indent=1))
    print(('FAIL' if gaps else 'PASS') + f': {len(gaps)} gap(s){scope}')
    return 1 if gaps else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
