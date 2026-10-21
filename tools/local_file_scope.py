"""Evidence-derived scope hints, not a cross-agent effective-precedence resolver."""
from pathlib import Path
import re


def import_ids(index, row, content):
    """Resolve only literal standalone Claude-style imports already in the index."""
    by_path = {r['real_path']: r['id'] for r in index['files']}
    result = []
    for token in re.findall(r'^\s*@([^\s]+)\s*$', content, re.M):
        path = Path(token.replace('~/', index['home'] + '/', 1))
        if not path.is_absolute(): path = Path(row['path']).parent / path
        try: target = by_path.get(str(path.resolve()))
        except (OSError, RuntimeError): target = None
        if target and target != row['id']: result.append(target)
    return result


def adjacent_ids(index, row, content):
    ids = import_ids(index, row, content)
    for ref in index['references']:
        if ref['source_id'] == row['id']: ids.append(ref['target_id'])
        elif ref['target_id'] == row['id'] and ref['kind'] in {'generated_from', 'symlink', 'references'}: ids.append(ref['source_id'])
    return list(dict.fromkeys(ids))


def applicability(index, row, content):
    path = Path(row['path'])
    role = 'generated projection' if row.get('generated') else ('alias' if row.get('is_symlink') else 'handwritten source')
    imports = import_ids(index, row, content)
    if imports and not row.get('generated'): role = 'import wrapper'
    limitations = ['Indexed path/header/import evidence only; effective agent loading and precedence are not established.']
    scope = 'Indexed location: ' + str(path.parent)
    activation = 'Activation is not established by this inventory.'
    if path.suffix == '.mdc':
        front = re.match(r'\A---\r?\n(.*?)\r?\n---', content, re.S)
        fields = re.findall(r'^(alwaysApply|globs|description):\s*(.*)$', front[1], re.M) if front else []
        activation = 'MDC header: ' + '; '.join(k + ': ' + v for k, v in fields) if fields else 'No recognized MDC activation header supplied.'
    elif path.name in {'AGENTS.md', 'AGENTS.override.md', 'CLAUDE.md'}:
        activation = 'Instruction entry point at ' + str(path.parent) + '; session, harness and directory determine loading.'
    if row.get('generated_sources'): limitations.append('Declared generated sources: ' + ', '.join(row['generated_sources']))
    if imports: limitations.append('Literal indexed imports: ' + ', '.join(imports))
    return {'role': role, 'scope': scope, 'activation': activation, 'limitations': limitations}
