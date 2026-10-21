"""Fixed checks on candidate bytes. Never runs a hook or executable candidate."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def load_json(raw):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate native JSON key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('nonfinite native JSON value')
    return json.loads(raw, object_pairs_hook=object_pairs, parse_constant=constant)


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def check(kind, status, runner, value, evidence, limitations=None):
    return {'kind': kind, 'status': status, 'runner_id': runner, 'input_digest': digest(value),
            'output_digest': digest([status, evidence]), 'evidence': evidence,
            'checked_at': datetime.now(timezone.utc).isoformat(), 'limitations': limitations or []}


def syntax_check(candidate, language):
    """AST/compile, shell -n and node --check are parsing only, in a private root."""
    language = language.lstrip('.').lower()
    if language == 'py':
        try:
            tree = ast.parse(candidate, filename='<candidate>')
            compile(tree, '<candidate>', 'exec')
            return check('syntax', 'passed', 'python.ast+compile.v1', candidate, ['AST parsed and compiled without execution.'])
        except (SyntaxError, ValueError, TypeError):
            return check('syntax', 'failed', 'python.ast+compile.v1', candidate, ['Candidate Python syntax is invalid.'])
    runner = {'sh': ['sh', '-n'], 'bash': ['bash', '-n'], 'zsh': ['zsh', '-n'],
              'js': ['node', '--check'], 'cjs': ['node', '--check'], 'mjs': ['node', '--check']}.get(language)
    if not runner:
        return check('syntax', 'unavailable', 'fixed.syntax.v1', candidate, [], ['No fixed parser is registered for this language.'])
    binary = shutil.which(runner[0])
    if not binary:
        return check('syntax', 'unavailable', '.'.join(runner), candidate, [], ['Required native parser is not installed.'])
    with tempfile.TemporaryDirectory(prefix='repair-syntax-') as root:
        path = Path(root) / ('candidate.' + language)
        path.write_text(candidate)
        try:
            result = subprocess.run([binary, *runner[1:], str(path)], cwd=root, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
                                    env={'PATH': '/usr/bin:/bin:/opt/homebrew/bin', 'HOME': root})
            status = 'passed' if result.returncode == 0 else 'failed'
        except (OSError, subprocess.TimeoutExpired):
            status = 'unavailable'
    return check('syntax', status, '.'.join(runner) + '.v1', candidate, ['Native parser checked disposable candidate bytes; candidate was not executed.'])


def skill_checks(candidate, folder, home):
    folder, home = Path(folder), Path(home)
    match = re.match(r'\A---\r?\n(.*?)\r?\n---\r?\n(.+)\Z', candidate, re.S)
    fields = {}
    if match:
        fields = dict(re.findall(r'^([a-z-]+):\s*([^\n]+)$', match[1], re.M))
        fields = {k: v.strip().strip('\"\'') for k, v in fields.items()}
    structural = bool(match and fields.get('name') == folder.name and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', fields.get('name', ''))
                      and 0 < len(fields.get('name', '')) <= 64 and 0 < len(fields.get('description', '')) <= 1024)
    references = set(re.findall(r'\]\(((?:references|scripts|assets)/[^)#\s]+)', candidate))
    references.update(re.findall(r'`((?:references|scripts|assets)/[^`\s]+)`', candidate))
    for value in references:
        path = folder / value
        if not path.is_file() or folder.resolve() not in path.resolve().parents:
            structural = False
    links = []
    lifecycle = True
    for runtime in ('.claude', '.cursor'):
        link = home / runtime / 'skills' / folder.name
        if link.exists() or link.is_symlink():
            valid = link.is_symlink() and link.resolve() == folder.resolve()
            lifecycle = lifecycle and valid
            links.append(f'{runtime}: canonical link ' + ('preserved' if valid else 'conflict'))
    return [check('structural', 'passed' if structural else 'failed', 'agent-skills-format.v1', candidate,
                  ['Frontmatter name/description and local references checked.']),
            check('lifecycle', 'passed' if lifecycle else 'failed', 'shared-skill-one-home.v1', [candidate, links], links,
                  ['Runtime discovery and automatic model selection require separate observed evidence.'])]


def json_check(value, category, runtime):
    try:
        json.dumps(value, allow_nan=False)
        ok = isinstance(value, dict)
    except (ValueError, TypeError):
        ok = False
    if not ok:
        return check('native', 'failed', runtime + '.json-settings-contract.2026-10-21', value, ['Native configuration must be a JSON object.'])
    for key in ('model', 'outputStyle', 'language', 'effortLevel'):
        if key in value:
            ok = ok and isinstance(value[key], str) and bool(value[key].strip())
    for key in ('alwaysThinkingEnabled', 'spinnerTipsEnabled'):
        if key in value:
            ok = ok and type(value[key]) is bool
    if category == 'hook' or 'hooks' in value:
        hooks = value.get('hooks', {})
        ok = ok and isinstance(hooks, dict)
        if runtime == 'cursor':
            ok = ok and value.get('version') == 1
        if isinstance(hooks, dict):
            for event, rows in hooks.items():
                ok = ok and isinstance(event, str) and isinstance(rows, list)
                if isinstance(rows, list):
                    ok = ok and all(isinstance(row, dict) for row in rows)
                    if runtime == 'cursor':
                        for row in rows:
                            if isinstance(row, dict):
                                kind = row.get('type', 'command')
                                ok = ok and kind in ('command', 'prompt') and isinstance(row.get(kind), str) and bool(row.get(kind))
                    if runtime == 'claude':
                        for row in rows:
                            if isinstance(row, dict):
                                handlers = row.get('hooks')
                                ok = ok and isinstance(handlers, list)
                                for handler in handlers if isinstance(handlers, list) else []:
                                    if not isinstance(handler, dict):
                                        ok = False
                                        continue
                                    kind = handler.get('type')
                                    field = 'url' if kind == 'http' else 'prompt' if kind in ('prompt', 'agent') else 'command'
                                    ok = ok and kind in ('command', 'prompt', 'agent', 'http') and isinstance(handler.get(field), str) and bool(handler.get(field))
                                    if 'timeout' in handler:
                                        ok = ok and type(handler['timeout']) in (int, float) and handler['timeout'] > 0
    return check('native', 'passed' if ok else 'failed', runtime + '.json-settings-contract.2026-10-21', value,
                 ['Strict native JSON and supported configuration shape parsed; no CLI startup or hook execution.'],
                 ['File parsing proves configured values; active precedence, trust and runtime reload remain unobserved.'])


def run_checks(candidate, category='executable', path=None, home=None, runtime='local'):
    if category in ('hook', 'cli_config', 'app_settings'):
        return [json_check(candidate, category, runtime)]
    if category == 'skill':
        return skill_checks(candidate, Path(path).parent, home)
    if category == 'executable':
        return [syntax_check(candidate, Path(path).suffix)]
    return [check('structural', 'passed' if candidate.strip() else 'failed', 'canonical-text.v1', candidate, ['Canonical UTF-8 text checked.'])]


def check_candidate(*args, **kwargs):
    return run_checks(*args, **kwargs)
