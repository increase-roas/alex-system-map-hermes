#!/usr/bin/env python3
"""Bounded, read-only local instruction evidence. Findings are candidates, never authority."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

EXCLUDED_DIRS = {'.git', 'node_modules', 'vendor', 'dist', 'build', '.next', '__pycache__', 'logs', 'sessions', 'transcripts', 'runtime', 'credentials', 'secrets', 'backups', 'cache', '.cache', 'memories'}
EXTENSIONS = {'.md', '.mdc', '.txt', '.json', '.toml', '.yaml', '.yml', '.py', '.sh', '.js', '.ts'}
SENSITIVE = re.compile(r'(?i)(secret|password|passwd|credential|token|api.?key|authorization|private.?key|client.?secret|access.?key|connection.?string|database.?url|dsn|cookie|command|script|headers?|env|args|arguments)')
EXCLUSIONS = ['Credential/auth/env files and stores', 'Logs, sessions, transcripts, databases, runtime and memory archives', 'Dependency, build, cache, backup and .git trees', 'Unselected roots and symlinks escaping selected roots', 'Unsupported file types; bounded depth, bytes and file count']


def now():
    return datetime.now(timezone.utc).isoformat()


def ident(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def within(path, roots):
    return any(path == r or r in path.parents for r in roots)


def selected_roots(home):
    entries = [('.agents/instructions', 'Shared instructions'), ('.agents/skills', 'Shared skills'), ('.agents/tools/cards', 'Tool cards'), ('.agents/tools/guards', 'Guards'), ('.agents/tools/unify', 'Instruction distribution'), ('.agents/AGENTS.md', 'Shared root rules'), ('.codex/AGENTS.md', 'Codex rules'), ('.codex/config.toml', 'Codex configuration'), ('.codex/hooks', 'Codex hooks'), ('.codex/skills', 'Codex skills'), ('.claude/CLAUDE.md', 'Claude rules'), ('.claude/settings.json', 'Claude settings'), ('.claude/settings.local.json', 'Claude local settings'), ('.claude/rules', 'Claude rules directory'), ('.claude/skills', 'Claude skills'), ('.claude/hooks', 'Claude hooks'), ('.cursor/rules', 'Cursor rules'), ('.cursor/skills', 'Cursor skills'), ('.cursor/hooks', 'Cursor hooks'), ('AGENTS.md', 'Home rules'), ('AGENT-CONTEXT.md', 'Stack context'), ('Alex-Director/AGENTS.md', 'Director rules'), ('Alex-Director/rules', 'Director rules directory'), ('Documents/Codex/handoffs', 'Selected handoffs')]
    return [(home / p, label) for p, label in entries]



def screen_assignment_containers(text):
    """Mask sensitive YAML/TOML values, including multiline argument arrays."""
    edits = []
    for match in re.finditer(r'(?m)^\s*["\']?([\w.-]+)["\']?\s*[:=][ \t]*', text):
        if not SENSITIVE.search(match.group(1)):
            continue
        start = match.end()
        if start >= len(text) or text[start] in '\r\n':
            continue  # YAML block containers are masked by indentation below.
        end = text.find('\n', start)
        if end < 0:
            end = len(text)
        if text[start] in '[{':
            stack = []
            quote = None
            escaped = False
            position = start
            while position < len(text):
                char = text[position]
                if quote:
                    if escaped:
                        escaped = False
                    elif char == '\\':
                        escaped = True
                    elif text.startswith(quote, position):
                        position += len(quote) - 1
                        quote = None
                elif char in '\"\'':
                    quote = char * 3 if text.startswith(char * 3, position) else char
                    position += len(quote) - 1
                elif char in '[{':
                    stack.append(char)
                elif char in ']}':
                    if stack:
                        stack.pop()
                    if not stack:
                        end = position + 1
                        break
                position += 1
            else:
                end = len(text)  # Malformed sensitive container: fail closed.
        edits.append((start, end))
    edits = [(a, b) for a, b in edits if not any(c < a and b <= d for c, d in edits)]
    for start, end in sorted(edits, reverse=True):
        text = text[:start] + '[REDACTED]' + '\n' * text[start:end].count('\n') + text[end:]
    return text


def screen(text):
    original = text
    text = screen_assignment_containers(text)
    # Keep source line numbers stable, including multiline PEM material.
    def hide(match):
        return '[REDACTED]' + '\n' * match.group(0).count('\n')
    text = re.sub(r'-----BEGIN [^-]*(?:PRIVATE KEY|CERTIFICATE)-----.*?(?:-----END [^-]+-----|\Z)', hide, text, flags=re.S)
    # Decode JSON values at sensitive keys (including containers), replacing values
    # without reformatting the surrounding source or shifting evidence line numbers.
    edits = []
    for m in re.finditer(r'"([^"\\]+)"\s*:\s*', text):
        if SENSITIVE.search(m.group(1)):
            try:
                _, length = json.JSONDecoder().raw_decode(text[m.end():])
                end = m.end() + length
                edits.append((m.end(), end))
            except (ValueError, json.JSONDecodeError):
                pass
    edits = [(a, b) for a, b in edits if not any(c < a and b <= d for c, d in edits)]
    for start, end in sorted(edits, reverse=True):
        text = text[:start] + '"[REDACTED]"' + '\n' * text[start:end].count('\n') + text[end:]
    text = re.sub(r'(?im)^(\s*[\w.-]*(?:command|script|headers?|env)[\w.-]*\s*[:=]\s*).+$', r'\1[REDACTED]', text)
    text = re.sub(r'(?im)^(.*?\b(?:export\s+)?[\w.-]*(?:secret|password|passwd|token|api[_-]?key|authorization|credential|private[_-]?key|database[_-]?url|dsn|cookie)[\w.-]*\s*[:=]\s*).+$', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)(\b(?:token|secret|password|api[_-]?key|authorization)\s*[:=]\s*)(?:"[^"\n]*"|\x27[^\x27\n]*\x27|[^\s,;]+)', r'\1[REDACTED]', text)
    text = re.sub(r'(?im)^.*(?:\bcurl\b|\bwget\b|\bAuthorization\s*:|\bBearer\s+).+$', '[REDACTED command or authorization]', text)
    text = re.sub(r'\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{10,}|gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|xox[baprs]-[A-Za-z0-9-]+|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b', '[REDACTED credential]', text)
    text = re.sub(r'(?i)(https?://)[^\s/@:]+:[^\s/@]+@', r'\1[REDACTED]@', text)
    lines = text.splitlines(keepends=True)
    sensitive_section = False
    yaml_indent = None
    for i, line in enumerate(lines):
        section = re.match(r'\s*\[([^\]]+)\]', line)
        if section:
            sensitive_section = bool(SENSITIVE.search(section.group(1)))
        elif sensitive_section and line.strip() and not line.lstrip().startswith('#'):
            lines[i] = '[REDACTED section value]' + ('\n' if line.endswith('\n') else '')
        yaml_key = re.match(r'^(\s*)([\w.-]+):\s*$', line.rstrip('\n'))
        indent = len(line) - len(line.lstrip())
        if yaml_indent is not None and line.strip():
            if indent > yaml_indent or (indent == yaml_indent and line.lstrip().startswith('- ')):
                lines[i] = ' ' * indent + '[REDACTED section value]' + ('\n' if line.endswith('\n') else '')
            else:
                yaml_indent = None
        if yaml_key and SENSITIVE.search(yaml_key.group(2)):
            yaml_indent = len(yaml_key.group(1))
    text = ''.join(lines)
    return text, text != original


def read_source(path, allowed, max_bytes):
    resolved = path.resolve(strict=True)
    if excluded(resolved) or any(parent.name in EXCLUDED_DIRS for parent in resolved.parents):
        raise PermissionError('excluded source target')
    if not within(resolved, allowed):
        raise PermissionError('outside selected roots')
    # Walk every resolved directory with no-follow descriptors; a concurrent
    # ancestor rename/link swap cannot redirect the read outside selected roots.
    parent_fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in resolved.parts[1:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = next_fd
        fd = os.open(resolved.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise PermissionError('not a regular file')
        if before.st_size > max_bytes:
            raise OverflowError('size limit')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(max_bytes)
        after = os.fstat(fd)
        current = resolved.stat()
        if (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino):
            raise RuntimeError('source replaced during read')
        if len(raw) > max_bytes or len(raw) != after.st_size:
            raise OverflowError('size limit')
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino) or path.resolve(strict=True) != resolved:
            raise RuntimeError('source changed during read')
        return raw, after, resolved
    finally:
        os.close(fd)


def excluded(path):
    name = path.name.lower()
    return name.startswith('.env') or bool(re.search(r'(^|[._-])(auth|credentials?|secrets?|tokens?)([._-]|$)', name)) or path.suffix.lower() not in EXTENSIONS


def kind(path):
    lower = str(path).lower()
    if path.name == 'SKILL.md' or '/skills/' in lower:
        return 'skill'
    if '/hooks/' in lower or '/guards/' in lower:
        return 'hook'
    if 'handoff' in lower:
        return 'handoff'
    if path.suffix in {'.json', '.toml', '.yaml', '.yml'}:
        return 'config'
    if path.suffix in {'.py', '.sh', '.ts', '.js'}:
        return 'script'
    return 'rule' if any(x in lower for x in ('agents.md', 'claude.md', '/rules/', '/instructions/')) else 'document'


def scan(home=None, roots=None, max_files=6000, max_depth=12, max_bytes=262144):
    home = Path(home or Path.home()).absolute()
    roots = [(Path(p).absolute(), label) for p, label in (roots if roots is not None else selected_roots(home))]
    allowed = [p.resolve() for p, _ in roots]
    coverage = {'roots': [], 'exclusions': EXCLUSIONS + ['24 MiB aggregate source-read budget; 48000 traversal entries'], 'limits': {'max_files': max_files, 'max_depth': max_depth, 'max_bytes': max_bytes}, 'truncated': False, 'skipped': [], 'errors': []}
    idx = {'schema_version': 1, 'scanned_at': now(), 'home': str(home), 'files': [], 'duplicates': [], 'findings': [], 'references': [], 'coverage': coverage}
    skips, sources, seen_paths = Counter(), {}, set()
    total_bytes, entries_seen = 0, 0
    aggregate_limit, entry_limit = 24 * 1024 * 1024, 48000
    root_rows = {}
    root_entries = Counter()
    root_entry_limit = entry_limit
    def partial(root, reason):
        root_rows[str(root)]['state'] = 'partial'
        coverage['truncated'] = True
        skips[reason] += 1

    def candidates(p, root, depth, ancestors, deferred):
        """Yield one directory's files; queue descendants for breadth-first reads."""
        nonlocal entries_seen
        if depth > max_depth:
            partial(root, 'depth limit')
            return
        try:
            real = p.resolve()
            if not within(real, allowed):
                skips['outside selected roots'] += 1
                return
            if p.name in EXCLUDED_DIRS or any(q.name in EXCLUDED_DIRS for q in real.parents):
                skips['excluded directory'] += 1
                return
            if real in ancestors:
                skips['directory cycle'] += 1
                return
            children = []
            with os.scandir(p) as stream:
                for entry in stream:
                    if entries_seen >= entry_limit or root_entries[str(root)] >= root_entry_limit:
                        partial(root, 'traversal entry limit')
                        break
                    entries_seen += 1
                    root_entries[str(root)] += 1
                    children.append(Path(entry.path))
            priorities = {'AGENTS.md', 'CLAUDE.md', 'config.toml', 'settings.json', 'settings.local.json'}
            for child in sorted(children, key=lambda c: (c.name not in priorities, c.name)):
                if child.is_dir():
                    deferred.append((child, depth + 1, ancestors | {real}))
                elif depth + 1 > max_depth:
                    partial(root, 'depth limit')
                else:
                    yield child
        except (OSError, RuntimeError) as exc:
            partial(root, 'directory read failure')
            coverage['errors'].append(f'{p}: {type(exc).__name__}')

    def read_candidate(p, root):
        nonlocal total_bytes
        try:
            real = p.resolve()
        except (OSError, RuntimeError):
            partial(root, 'unresolvable link')
            return
        if not within(real, allowed):
            skips['outside selected roots'] += 1
            return
        if excluded(p) or excluded(real) or any(q.name in EXCLUDED_DIRS for q in real.parents):
            skips['excluded file'] += 1
            return
        if str(p) in seen_paths:
            return
        if len(idx['files']) >= max_files:
            partial(root, 'file limit')
            return
        remaining = aggregate_limit - total_bytes
        if remaining <= 0:
            partial(root, 'aggregate source byte limit (24 MiB)')
            return
        seen_paths.add(str(p))
        row = {'id': ident(str(p)), 'path': str(p), 'real_path': str(real), 'root': str(root), 'relative_path': str(p.relative_to(root)) if p != root else p.name, 'kind': kind(p), 'state': 'readable', 'bytes': None, 'mtime': None, 'sha256': None, 'line_count': None, 'is_symlink': p.is_symlink() or any(x.is_symlink() for x in p.parents if x != home), 'link_target': None, 'generated': False, 'generated_sources': []}
        if row['is_symlink']:
            row['link_target'] = str(real)
        try:
            st = p.stat()
            row.update(bytes=st.st_size, mtime=datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat())
            if st.st_size > remaining and st.st_size <= max_bytes:
                partial(root, 'aggregate source byte limit (24 MiB)')
                return
            if st.st_size > max_bytes:
                raise OverflowError('size limit')
            # Reserve before reading, including reads that later fail/change. Limit
            # this descriptor read to the reserved size, preventing a growing or
            # failing source from consuming unaccounted aggregate bytes.
            read_limit = min(max_bytes, remaining, st.st_size)
            total_bytes += read_limit
            raw, st, real = read_source(p, allowed, read_limit)
            text = raw.decode('utf-8', errors='replace')
            screened, _ = screen(text)
            row.update(sha256=hashlib.sha256(raw).hexdigest(), line_count=len(text.splitlines()))
            header = screened[:6000]
            row['generated'] = bool(re.search(r'(?i)\bgenerated\b|auto.generated|do not edit', header))
            if row['generated']:
                matches = re.findall(r'(?im)^\s*(?:Sources?|Generated from):\s*(.+)', header)
                row['generated_sources'] = [v.strip(' `') for m in matches for v in m.split(',') if v.strip()]
            sources[row['id']] = screened
        except FileNotFoundError:
            row['state'] = 'missing'
        except OverflowError:
            row['state'] = 'too_large'
        except RuntimeError:
            row['state'] = 'changed_during_scan'
        except OSError:
            row['state'] = 'unreadable'
        if row['state'] != 'readable':
            partial(root, 'source ' + row['state'])
        idx['files'].append(row)
        root_rows[str(root)]['files'] += 1

    singletons, directories = [], []
    for p, label in roots:
        missing = not p.exists() and not p.is_symlink()
        row = {'path': str(p), 'label': label, 'state': 'missing' if missing else 'scanned', 'files': 0}
        coverage['roots'].append(row)
        root_rows[str(p)] = row
        if missing:
            coverage['truncated'] = True
        elif p.is_dir():
            directories.append((p, []))
        else:
            singletons.append(p)
    root_entry_limit = max(1, entry_limit // max(1, len(directories)))
    # Critical explicitly selected rule/config files are independent of tree sizes.
    for p in singletons:
        read_candidate(p, p)

    def interleave(streams):
        active = list(streams)
        while active:
            remaining = []
            for root, stream in active:
                try:
                    read_candidate(next(stream), root)
                    remaining.append((root, stream))
                except StopIteration:
                    pass
            active = remaining

    # All roots receive shallow evidence before any root consumes deep skill trees.
    interleave([(root, candidates(root, root, 0, set(), queue)) for root, queue in directories])
    def descendants(root, queue):
        position = 0
        while position < len(queue):
            p, depth, ancestors = queue[position]
            position += 1
            yield from candidates(p, root, depth, ancestors, queue)
    interleave([(root, descendants(root, queue)) for root, queue in directories])
    coverage['skipped'] = [{'reason': k, 'count': v} for k, v in sorted(skips.items())]
    analyze(idx, sources)
    return idx


def analyze(idx, sources):
    real_groups, hash_groups = defaultdict(list), defaultdict(list)
    for row in idx['files']:
        if row['state'] == 'readable':
            real_groups[row['real_path']].append(row)
            hash_groups[row['sha256']].append(row)
    for mode, groups in [('same_file', real_groups), ('identical_copy', hash_groups)]:
        for key, rows in sorted(groups.items()):
            if len(rows) < 2 or (mode == 'identical_copy' and len({r['real_path'] for r in rows}) < 2):
                continue
            idx['duplicates'].append({'id': ident(mode + key), 'kind': mode, 'file_ids': [r['id'] for r in rows], 'reason': ('Paths resolve to the same file.' if mode == 'same_file' else 'Different resolved files have identical raw SHA-256 bytes.') + (' Contains generated distribution; duplication alone is not a defect.' if any(r['generated'] for r in rows) else '')})
    by_real = {r['real_path']: r['id'] for r in idx['files'] if r['real_path']}
    repeated, declarations = defaultdict(list), defaultdict(list)
    for row in idx['files']:
        text = sources.get(row['id'], '')
        if row['is_symlink'] and row['real_path'] in by_real and by_real[row['real_path']] != row['id']:
            idx['references'].append({'source_id': row['id'], 'target_id': by_real[row['real_path']], 'kind': 'symlink', 'line': None})
        for ref in row['generated_sources']:
            candidates = [Path(row['path']).parent / ref, Path(row['root']) / ref, Path(row['root']).parent / ref]
            for target in candidates:
                target_id = by_real.get(str(target.resolve()))
                if target_id and target_id != row['id']:
                    idx['references'].append({'source_id': row['id'], 'target_id': target_id, 'kind': 'generated_from', 'line': None})
                    break
        for line_no, line in enumerate(text.splitlines(), 1):
            for token in re.findall(r'`([^`\n]+)`|\]\(([^)\n]+)\)', line):
                ref = token[0] or token[1]
                if ref.startswith(('https:', 'http:', 'app:', '#')) or len(ref) > 500:
                    continue
                ref = ref.removeprefix('file://').split('#')[0]
                target = Path(ref.replace('~/', idx['home'] + '/', 1))
                if not target.is_absolute():
                    target = Path(row['path']).parent / target
                try:
                    target_id = by_real.get(str(target.resolve()))
                except (OSError, RuntimeError):
                    target_id = None
                if target_id and target_id != row['id']:
                    idx['references'].append({'source_id': row['id'], 'target_id': target_id, 'kind': 'references', 'line': line_no})
            clean = line.strip().lstrip('-* ').strip()
            if len(clean) < 20 or len(clean) > 800 or '[REDACTED' in clean:
                continue
            ev = {'file_id': row['id'], 'line': line_no, 'text': line[:900]}
            if re.search(r'(?i)\b(always|never|must|only|required|do not)\b', clean):
                repeated[clean].append(ev)
            # Exclude visibly quoted/historical lines. Generated files remain evidence,
            # but candidates explicitly state distribution/context may explain differences.
            if line.lstrip().startswith(('>', '"', "'")) or re.search(r'(?i)\b(historical|retired|previously|used to|deprecated)\b', clean):
                continue
            m = re.search(r'(?i)\b(always|never)\s+((?:send|use|allow|execute|delete|contact|spend)\b.+?)[.!]?$', clean)
            if m:
                declarations[('explicit opposite directive', re.sub(r'\s+', ' ', m.group(2).lower()).rstrip('.!'))].append((m.group(1).lower(), ev))
            # This unanchored expression can backtrack at every position in
            # ordinary prose. Its required literal is a semantics-preserving gate.
            m = re.search(r'(?i)(?:use\s+)?(.{1,90}?)\s+(?:as\s+)?the (?:only|one) memory layer', clean) if 'memory layer' in clean.lower() else None
            if m:
                value = re.sub(r'(?i)^.*\buse\s+', '', m.group(1)).lower().strip()
                declarations[('exclusive memory declarations', 'memory layer')].append((value, ev))
            m = re.search(r'(?i)\bonly use\s+([\w .-]{2,60}?)\s+for\s+([\w .-]{3,60})[.!]?$', clean)
            if m:
                declarations[('exclusive route declarations', m.group(2).lower().rstrip('.'))].append((m.group(1).lower(), ev))
    for text, evidence in sorted(repeated.items()):
        unique = list({(e['file_id'], e['line']): e for e in evidence}.values())
        if len({e['file_id'] for e in unique}) > 1:
            idx['findings'].append({'id': ident('repeat' + text), 'kind': 'repeated_rule', 'topic': 'Exact repeated instruction', 'reason': 'Exact screened line appears in multiple paths; aliases/generated distribution may explain it.', 'confidence': 'exact', 'evidence': unique[:20]})
    for (topic, subject), values in sorted(declarations.items()):
        if len({v for v, _ in values}) < 2 or len({e['file_id'] for _, e in values}) < 2:
            continue
        idx['findings'].append({'id': ident(topic + subject), 'kind': 'conflict_candidate', 'topic': topic + ': ' + subject, 'reason': 'Explicit declarations differ. Candidate only: scope, dates, quotations or generated distribution may explain this; no semantic completeness or authority is inferred.', 'confidence': 'candidate', 'evidence': [e for _, e in values][:20]})
    if len(idx['findings']) > 1500 or len(idx['references']) > 12000:
        idx['coverage']['truncated'] = True
        idx['coverage']['skipped'].append({'reason': 'finding/reference output limit', 'count': max(0, len(idx['findings']) - 1500) + max(0, len(idx['references']) - 12000)})
    idx['findings'] = idx['findings'][:1500]
    idx['references'] = idx['references'][:12000]


def content(idx, file_id):
    row = next((r for r in idx['files'] if r['id'] == file_id), None)
    if row is None:
        raise KeyError('Unknown indexed file ID')
    result = {'file_id': file_id, 'path': row['path'], 'scanned_sha256': row['sha256'], 'current_sha256': None, 'changed_since_scan': False, 'read_at': now(), 'content': '', 'redacted': False, 'truncated': False}
    allowed = [Path(r['path']).resolve() for r in idx['coverage']['roots']]
    try:
        if str(Path(row['path']).resolve(strict=True)) != row['real_path']:
            raise PermissionError('indexed source target changed')
        raw, _, _ = read_source(Path(row['path']), allowed, idx['coverage']['limits']['max_bytes'])
        result['current_sha256'] = hashlib.sha256(raw).hexdigest()
        result['changed_since_scan'] = result['current_sha256'] != row['sha256']
        result['content'], result['redacted'] = screen(raw.decode('utf-8', errors='replace'))
    except (OSError, RuntimeError, OverflowError) as exc:
        result['error'] = f'Unable to read source ({type(exc).__name__})'
        result['truncated'] = True
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['scan', 'content'])
    parser.add_argument('--index', required=True)
    parser.add_argument('--id')
    args = parser.parse_args()
    target = Path(args.index)
    if args.command == 'scan':
        idx = scan()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(idx), encoding='utf-8')
        os.chmod(temporary, 0o600)
        temporary.replace(target)
        print(json.dumps(idx))
    else:
        idx = json.loads(target.read_text())
        try:
            print(json.dumps(content(idx, args.id)))
        except KeyError:
            print(json.dumps({'error': 'Unknown indexed file ID'}))
            sys.exit(2)


if __name__ == '__main__':
    main()
