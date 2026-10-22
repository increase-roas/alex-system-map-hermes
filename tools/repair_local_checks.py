"""Parsing and source projection checks. Copied execution lives in repair_hook_checks."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import io
import tokenize

from local_files import screen


# Unlike the generic prose viewer, Python ownership distinguishes a key/name
# from its value. Reading an environment variable or passing a variable through
# a credential-shaped field does not embed a credential in source bytes.
_CREDENTIAL_SHAPE = re.compile(r'-----BEGIN [^-]*(?:PRIVATE KEY|CERTIFICATE)-----|\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{10,}|gh[pousr]_[A-Za-z0-9_]{10,}|github_pat_[A-Za-z0-9_]{10,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b|https?://[^\s/@:]+:[^\s/@]+@')
_SENSITIVE_BINDING = re.compile(r'(?:^|_)(?:api_key|access_key|access_token|refresh_token|auth_token|client_secret|secret_key|password|passwd|credential|credentials|token|tokens|secret|private_key|cookie|authorization|dsn|database_url|connection_string)$')
_INLINE_CREDENTIAL = re.compile(r'(?i)\b(?:[\w-]*[_-])?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password|passwd|authorization|client[_-]?secret)\s*[:=]\s*["\']?([A-Za-z0-9_./+~=-]{3,})|\bBearer\s+([A-Za-z0-9_./+~=-]{3,})|--(?:api[-_]key|token|password|secret)\s+["\']?([A-Za-z0-9_./+~=-]{3,})|[?&](?:key|token|password|secret|api[_-]?key)=([^\s&#"\']+)')
REGEX_CALLS = frozenset(('compile', 'findall', 'finditer', 'match', 'fullmatch', 'search', 'split', 'sub', 'subn', 'escape'))
REGEX_FLAGS = frozenset(('A', 'ASCII', 'I', 'IGNORECASE', 'L', 'LOCALE', 'M', 'MULTILINE', 'S', 'DOTALL', 'U', 'UNICODE', 'X', 'VERBOSE', 'NOFLAG', 'DEBUG'))


def _sensitive_binding(name):
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name).lower().replace('-', '_')
    return bool(_SENSITIVE_BINDING.search(name))


def _literal_strings(node):
    """Collect only stored literal values, never evaluate an expression/call."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return [node.value]
        if isinstance(node.value, bytes):
            return [node.value.decode('utf-8', errors='replace')]
    if isinstance(node, ast.BinOp):
        left, right = _literal_strings(node.left), _literal_strings(node.right)
        # Literal concatenation is structural, never eval/literal_eval.
        return left + right + ([left[0] + right[0]] if isinstance(node.op, ast.Add) and len(left) == len(right) == 1 else [])
    if isinstance(node, ast.JoinedStr):
        return [value for child in node.values for value in _literal_strings(child)]
    if isinstance(node, ast.FormattedValue):
        return _literal_strings(node.value)
    if isinstance(node, ast.Call):
        name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else None
        # Lookup keys are selectors; only fallback bytes are stored values.
        args = node.args[1:] if name in ('getenv', 'get') else node.args
        return [value for child in args + [kw.value for kw in node.keywords if kw.arg not in ('key',)] for value in _literal_strings(child)]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):

        return [value for child in node.elts for value in _literal_strings(child)]
    return []


def _binding_names(node):
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [node.attr]
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
        return [node.slice.value]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [name for child in node.elts for name in _binding_names(child)]
    return []


def _private_literal(value):
    return bool(_CREDENTIAL_SHAPE.search(value) or _INLINE_CREDENTIAL.search(value))


def python_source_projection(source):
    """Return exact safe Python, or withhold source containing private literals.

    This is a pure AST inspection. It never imports, evaluates or executes the
    candidate. Invalid Python remains unsupported and uses existing screening.
    """
    try:
        tree = ast.parse(source, filename='<owner-source>')
    except (SyntaxError, ValueError, TypeError):
        return screen(source)[0], True
    private = False
    regex_modules = {alias.asname or alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                     for alias in node.names if alias.name == 're'}
    rebound = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))}
    rebound.update(node.arg for node in ast.walk(tree) if isinstance(node, ast.arg))
    rebound.update(node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            rebound.update(alias.asname or alias.name.split('.')[0] for alias in node.names
                           if not (isinstance(node, ast.Import) and alias.name == 're'))
    # Module attributes are shared across aliases. Any mutation or escaping
    # module reference invalidates the parser-pattern exemption for all aliases.
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    mutable = any(isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                  and node.value.id in regex_modules
                  and not (isinstance(node.ctx, ast.Load) and (node.attr in REGEX_FLAGS or node.attr in REGEX_CALLS
                           and isinstance(parents.get(node), ast.Call) and parents[node].func is node))
                  or isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in regex_modules
                  and not (isinstance(parents.get(node), ast.Attribute) and parents[node].value is node)
                  for node in ast.walk(tree))
    dynamic = any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id in ('exec', 'eval', 'globals', 'locals', 'vars', '__import__') for node in ast.walk(tree))
    if mutable or dynamic:
        regex_modules.clear()
    regex_modules -= rebound
    def stored_literals(value):
        if (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                and isinstance(value.func.value, ast.Name) and value.func.value.id in regex_modules
                and value.func.attr in ('compile', 'findall', 'finditer', 'match', 'fullmatch', 'search', 'split', 'sub', 'subn')):
            return [text for child in value.args[1:] + [kw.value for kw in value.keywords if kw.arg != 'pattern']
                    for text in stored_literals(child)]
        if isinstance(value, ast.BinOp):
            return stored_literals(value.left) + stored_literals(value.right)
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            return [text for child in value.elts for text in stored_literals(child)]
        return _literal_strings(value)
    def bound(names, value):
        # Lexical token patterns are parser syntax, not stored credentials.
        # Every literal is still independently screened for credential material.
        return any(_sensitive_binding(name) for name in names) and any(text.strip() and text.strip().lower() not in ('bearer', 'basic') for text in stored_literals(value))
    def assignment(target, value):
        if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)) and len(target.elts) == len(value.elts):
            return any(assignment(left, right) for left, right in zip(target.elts, value.elts))
        return bound(_binding_names(target), value)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Constant, ast.BinOp, ast.JoinedStr)):
            private = private or any(_private_literal(value) for value in _literal_strings(node))
        elif isinstance(node, ast.Assign):
            private = private or any(assignment(target, node.value) for target in node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
            private = private or assignment(node.target, node.value)
        elif isinstance(node, ast.Dict):
            private = private or any(isinstance(key, ast.Constant) and isinstance(key.value, str) and bound([key.value], value) for key, value in zip(node.keys, node.values))
        elif isinstance(node, ast.keyword) and node.arg:
            private = private or bound([node.arg], node.value)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            args = node.args
            names = args.posonlyargs + args.args
            private = private or any(bound([arg.arg], value) for arg, value in zip(names[len(names) - len(args.defaults):], args.defaults))
            private = private or any(value is not None and bound([arg.arg], value) for arg, value in zip(args.kwonlyargs, args.kw_defaults))
    # Comments are outside the AST; explicit credential material there is still
    # source material and must never be copied to a model, plan or full backup.
    try:
        private = private or any(token.type == tokenize.COMMENT and _private_literal(token.string) for token in tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return screen(source)[0], True
    if private:
        return '[REDACTED Python source containing a private literal]\n', True
    return source, False


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
              'go': ['gofmt', '-e'], 'js': ['node', '--check'], 'cjs': ['node', '--check'], 'mjs': ['node', '--check']}.get(language)
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
    return [check('syntax', 'passed' if structural else 'failed', 'agent-skills-format.v1', candidate,
                  ['Frontmatter name/description and local references checked.']),
            check('owner_lifecycle', 'passed' if lifecycle else 'failed', 'shared-skill-one-home.v1', [candidate, links], links,
                  ['Runtime discovery and automatic model selection require separate observed evidence.'])]


def json_check(value, category, runtime):
    try:
        json.dumps(value, allow_nan=False)
        ok = isinstance(value, dict)
    except (ValueError, TypeError):
        ok = False
    if not ok:
        return check('syntax', 'failed', runtime + '.json-settings-contract.2026-10-21', value, ['Native configuration must be a JSON object.'])
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
    return check('syntax', 'passed' if ok else 'failed', runtime + '.json-settings-contract.2026-10-21', value,
                 ['Strict native JSON and supported configuration shape parsed; no CLI startup or hook execution.'],
                 ['File parsing proves configured values; active precedence, trust and runtime reload remain unobserved.'])


def run_checks(candidate, category='executable', path=None, home=None, runtime='local'):
    if category in ('hook', 'cli_config', 'app_settings'):
        return [json_check(candidate, category, runtime)]
    if category == 'skill':
        return skill_checks(candidate, Path(path).parent, home)
    if category == 'executable':
        return [syntax_check(candidate, Path(path).suffix)]
    return [check('syntax', 'passed' if candidate.strip() else 'failed', 'canonical-text.v1', candidate, ['Canonical UTF-8 text checked.'])]


def check_candidate(*args, **kwargs):
    return run_checks(*args, **kwargs)
