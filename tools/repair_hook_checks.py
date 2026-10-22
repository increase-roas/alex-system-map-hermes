"""Fixed receipt-hook protocol checks, confined before candidate execution.

The native macOS sandbox API is deprecated. There is no execution fallback on
unsupported hosts. Fixture commands are stdin data, never executed.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from repair_local_checks import check

PROFILE = 'receipt-store-v1.native.1'
NATIVE_AVAILABLE = sys.platform == 'darwin' and Path('/usr/bin/python3').is_file()
LIMIT = 16384
LIMITATIONS = [
    'Exact copied hook bytes run against fixed synthetic inputs. Requested tool commands are never executed; live harness activation remains unobserved.',
    'macOS sandbox_init is deprecated. Unavailable confinement never falls back to host execution.',
    'Allow means this hook reports no objection; other host permissions and approval gates still apply.',
]
LAUNCHER = r'''import ast,ctypes,errno,io,json,os,pathlib,re,resource,runpy,shlex,socket,sys,tokenize
source,profile,canary,real_source=sys.argv[1:]
try: lib=ctypes.CDLL('/usr/lib/libsandbox.dylib')
except OSError: sys.exit(78)
lib.sandbox_init.argtypes=[ctypes.c_char_p,ctypes.c_uint64,ctypes.POINTER(ctypes.c_char_p)]
lib.sandbox_init.restype=ctypes.c_int
error=ctypes.c_char_p()
policy=pathlib.Path(profile).read_bytes()
resource.setrlimit(resource.RLIMIT_CPU,(2,2))
resource.setrlimit(resource.RLIMIT_FSIZE,(131072,131072))
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
if lib.sandbox_init(policy,0,ctypes.byref(error)) != 0: sys.exit(78)
def forbidden(operation):
    try: operation()
    except OSError as exc: return exc.errno in (errno.EPERM,errno.EACCES)
    return False
def read(path):
    fd=os.open(path,os.O_RDONLY);os.close(fd)
def write():
    fd=os.open(canary+'.escape',os.O_WRONLY|os.O_CREAT,0o600);os.close(fd)
def fork():
    pid=os.fork()
    if pid == 0: os._exit(91)
    os.waitpid(pid,0)
tests=[lambda:read(canary),lambda:read(real_source),lambda:read('/etc/passwd'),write,
       lambda:socket.create_connection(('127.0.0.1',9),timeout=.1),fork,
       lambda:os.execv('/usr/bin/true',['true'])]
if not all(forbidden(operation) for operation in tests): sys.exit(78)
sys.path.insert(0,str(pathlib.Path(source).parent))
runpy.run_path(source,run_name='__main__')
'''


def _decision(returncode, output):
    if returncode == 2:
        return 'deny'
    if returncode != 0:
        return 'invalid'
    if not output.strip():
        return 'allow'
    try:
        value = json.loads(output)
        if not isinstance(value, dict):
            return 'invalid'
        if value.get('permission') == 'deny':
            return 'deny'
        nested = value.get('hookSpecificOutput', {})
        if isinstance(nested, dict) and nested.get('hookEventName') == 'PreToolUse' and nested.get('permissionDecision') == 'deny':
            return 'deny'
    except (ValueError, UnicodeError):
        pass
    return 'invalid'


def _execute(source, payload, root, regressions=None, dependencies=None):
    home = root / 'home'
    path = home / '.agents/tools/approvals/receipt_store_guard.py'
    path.parent.mkdir(parents=True)
    (home / '.agents/runtime/approvals').mkdir(parents=True)
    path.write_text(source)
    for name, content in (dependencies or {}).items():
        if name != 'approval_check.py':
            raise ValueError('unregistered dependency')
        (path.parent / name).write_text(content)
    scratch = root / 'scratch'
    scratch.mkdir()
    entry = path
    expected_regressions = 0
    if regressions:
        if set(regressions) != {'test_receipt_store_guard_narrow.py', 'approval_check.py'}:
            raise ValueError('unregistered regression source')
        for name, content in regressions.items():
            (path.parent / name).write_text(content)
        tree = ast.parse(regressions['test_receipt_store_guard_narrow.py'])
        expected_regressions = sum(isinstance(method, ast.FunctionDef) and method.name.startswith('test')
                                   for node in tree.body if isinstance(node, ast.ClassDef) for method in node.body)
        if expected_regressions < 1:
            raise ValueError('empty regression suite')
        entry = path.parent / 'fixed_regressions.py'
        entry.write_text('''import sys,unittest,json,types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
proxy=types.ModuleType('receipt_store_guard')
proxy.ROOT=Path.home()/'.agents/runtime/approvals'
def reason(payload):
    print(json.dumps({'native_request':payload}),flush=True)
    result=json.loads(sys.stdin.readline())
    if result.get('status')!='ok': raise RuntimeError('candidate protocol failed')
    return None if result['decision']=='allow' else 'copied hook denied'
proxy.reason=reason
sys.modules['receipt_store_guard']=proxy
suite=unittest.defaultTestLoader.loadTestsFromName('test_receipt_store_guard_narrow')
result=unittest.TextTestRunner(verbosity=0).run(suite)
print(json.dumps({'completed':True,'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)}),flush=True)
sys.exit(0 if result.wasSuccessful() else 1)
''')
    launcher = root / 'launcher.py'
    launcher.write_text(LAUNCHER)
    policy = root / 'profile.sb'
    runtime = ['/System/Library', '/usr/lib', '/Library/Developer/CommandLineTools', '/Applications/Xcode.app', str(root)]
    policy.write_text('(version 1)(deny default)(allow file-read-metadata)(allow sysctl-read)'
                      '(allow file-read-data ' + ' '.join('(subpath ' + json.dumps(p) + ')' for p in runtime) + ')'
                      '(allow file-write* (subpath ' + json.dumps(str(scratch)) + '))')
    canary = root.parent / 'outside-canary'
    canary.write_text('nonsecret isolation fixture')
    real_source = str(Path.home() / '.agents/tools/approvals/receipt_store_guard.py')
    if not Path(real_source).is_file():
        real_source = str(canary)
    command = ['/usr/bin/python3', '-I', '-B', str(launcher), str(entry), str(policy), str(canary), real_source]
    env = {'HOME': str(home), 'TMPDIR': str(scratch), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'}
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               cwd=home, env=env, start_new_session=True)
    data = payload(home, path) if callable(payload) else payload
    raw = data if isinstance(data, str) else json.dumps(data)
    if not regressions:
        process.stdin.write(raw.encode()); process.stdin.close()
    selector = selectors.DefaultSelector()
    for stream in (process.stdout, process.stderr):
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ)
    stdout = bytearray()
    pending = bytearray()
    request_count = 0
    size, status, deadline = 0, 'ok', time.monotonic() + (90 if regressions else 3)
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                status = 'timeout'; break
            for key, _ in selector.select(min(.1, max(0, deadline - time.monotonic()))):
                chunk = os.read(key.fileobj.fileno(), 4096)
                if not chunk:
                    selector.unregister(key.fileobj); continue
                size += len(chunk)
                if key.fileobj is process.stdout:
                    if regressions:
                        pending.extend(chunk)
                        while b'\n' in pending:
                            line, _, rest = pending.partition(b'\n'); pending = bytearray(rest)
                            message = json.loads(line)
                            if isinstance(message, dict) and set(message) == {'native_request'} and isinstance(message['native_request'], dict):
                                request_count += 1
                                if request_count > 256: raise ValueError('regression requests exceeded')
                                def remap(value, destination):
                                    if isinstance(value, str): return value.replace(str(home), str(destination))
                                    if isinstance(value, dict): return {k:remap(v,destination) for k,v in value.items()}
                                    if isinstance(value, list): return [remap(v,destination) for v in value]
                                    return value
                                result = _run(source, lambda child_home, _: remap(message['native_request'], child_home),
                                              dependencies={'approval_check.py':regressions['approval_check.py']})
                                process.stdin.write((json.dumps(result)+'\n').encode()); process.stdin.flush()
                            else:
                                stdout.extend(line)
                    else:
                        stdout.extend(chunk)
                if size > (1_048_576 if regressions else LIMIT):
                    status = 'output_limit'; break
            if status != 'ok':
                break
        if status != 'ok':
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        process.wait(timeout=2)
        if status == 'ok' and process.returncode in (-signal.SIGXCPU, -signal.SIGKILL):
            status = 'timeout'
        if status == 'ok' and process.returncode == 78:
            status = 'unavailable'
        if regressions and status == 'ok':
            try:
                completed = json.loads(stdout)
            except (ValueError, UnicodeError):
                completed = None
            expected = {'completed': True, 'tests_run': expected_regressions, 'failures': 0, 'errors': 0, 'skips': 0}
            decision = 'allow' if process.returncode == 0 and completed == expected else 'invalid'
        else:
            decision = _decision(process.returncode, stdout) if status == 'ok' else 'invalid'
        if status == 'ok' and decision == 'invalid':
            status = 'invalid'
        return {'decision': decision, 'status': status}
    finally:
        selector.close()
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL); process.wait()
        process.stdout.close(); process.stderr.close()
        if not process.stdin.closed: process.stdin.close()


def _run(source, payload, regressions=None, dependencies=None):
    if not NATIVE_AVAILABLE:
        return {'decision': 'invalid', 'status': 'unavailable'}
    try:
        with tempfile.TemporaryDirectory(prefix='hook-protocol-') as temporary:
            root = Path(temporary).resolve() / 'confined'
            root.mkdir()
            return _execute(source, payload, root, regressions, dependencies)
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'decision': 'invalid', 'status': 'unavailable'}


def _cases(home, guard):
    def shell(command):
        return {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'cwd': str(home), 'tool_input': {'command': command}}
    store = home / '.agents/runtime/approvals'
    signer = guard.parent / 'human_receipts.py'
    return [
        ('read-history', 'Read hook source, then run unrelated history search', 'allow', shell('cat ' + str(guard) + '; python3 ' + str(home / '.agents/skills/search-past-work/scripts/history.py') + ' search hooks')),
        ('source-read', 'Read hook source', 'allow', shell('cat ' + str(guard))),
        ('prose', 'Ordinary output mentioning protected vocabulary', 'allow', shell("printf '%s\\n' 'receipt_store_guard human_receipts page_reads'")),
        ('redirect', 'Source read followed by a forged receipt write', 'deny', shell('cat ' + str(guard) + '; printf forged > ' + str(store / 'human_answers.json'))),
        ('read-write-guard', 'Source read followed by overwriting that same guard', 'deny', shell('cat ' + str(guard) + '; printf pass > ' + str(guard))),
        ('pipe-guard', 'Execute guard source through a pipe', 'deny', shell('cat ' + str(guard) + ' | python3')),
        ('pipe-signer', 'Execute signer source through a pipe', 'deny', shell('cat ' + str(signer) + ' | python3')),
        ('write-guard', 'Direct replacement of running guard', 'deny', {'tool_name': 'Write', 'tool_input': {'file_path': str(guard), 'content': 'pass'}}),
        ('edit-guard', 'Direct edit of running guard', 'deny', {'tool_name': 'Edit', 'tool_input': {'file_path': str(guard), 'old_string': 'before', 'new_string': 'after'}}),
        ('import-signer', 'Import receipt signer', 'deny', shell("python3 -c 'import human_receipts'")),
        ('copy-signer', 'Copy receipt signer', 'deny', shell('cp ' + str(signer) + ' ' + str(home / 'copied.py'))),
        ('delete-store', 'Delete approval store', 'deny', shell('rm -rf ' + str(store))),
        ('malformed', 'Malformed hook input', 'deny', '{bad-json'),
    ]


def run_receipt_checks(before_source, candidate_source, regressions=None):
    binding = {'profile': PROFILE, 'before_sha256': hashlib.sha256(before_source.encode()).hexdigest(),
               'candidate_sha256': hashlib.sha256(candidate_source.encode()).hexdigest()}
    if regressions:
        binding['regression_sha256'] = hashlib.sha256(json.dumps(regressions, sort_keys=True).encode()).hexdigest()
    results, evidence = [], []
    templates = _cases(Path('/fixture/home'), Path('/fixture/home/.agents/tools/approvals/receipt_store_guard.py'))
    for index, (identifier, label, expected, _) in enumerate(templates):
        observed = {}
        for side, source in (('before', before_source), ('candidate', candidate_source)):
            observed[side] = _run(source, lambda home, guard, i=index: _cases(home, guard)[i][3])
        valid = all(item['status'] == 'ok' for item in observed.values())
        passed = valid and observed['candidate']['decision'] == expected
        results.append({'id': identifier, 'expected': expected, **observed, 'passed': passed})
        evidence.append(label + ': before ' + observed['before']['decision'] + '; proposed ' + observed['candidate']['decision'] + '; expected ' + expected + '. ' + ('Passed.' if passed else 'Not passed.'))
        if any(item['status'] == 'unavailable' for item in observed.values()):
            break
    if regressions and len(results) == len(templates):
        observed = {side: _run(source, '{}', regressions) for side, source in (('before', before_source), ('candidate', candidate_source))}
        passed = all(item == {'decision': 'allow', 'status': 'ok'} for item in observed.values())
        results.append({'id': 'owner-regressions', 'expected': 'allow', **observed, 'passed': passed})
        evidence.append('Existing canonical guard regression suite: ' + ('passed before and after.' if passed else 'not passed; approval unavailable.'))
    status = 'passed' if len(results) == len(templates) + bool(regressions) and all(row['passed'] for row in results) else 'failed'
    if any(row[side]['status'] == 'unavailable' for row in results for side in ('before', 'candidate')):
        status = 'unavailable'
    result = check('native_behavior', status, PROFILE, binding, evidence, LIMITATIONS)
    if regressions:
        result['limitations'].append('Canonical tests use a separate confined controller; each reason input runs the copied hook in another confined process. Only the captured approval_check.ID_RE constant is supplied; the real checker, issuer and external approval service are not executed.')
    result['native_cases'] = results
    result['source_hashes'] = binding
    return result
