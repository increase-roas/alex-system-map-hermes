"""Read-only official guidance via Composio. Page text is untrusted evidence.

Only server-owned catalog URLs cross the research boundary. No intent parameter
exists. Raw pages are discarded after their digest and exact excerpts are taken;
callers persist the returned private packet in the existing repair-state store.
"""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import stat
import tempfile

ROUTE = 'composio:EXA_GET_CONTENTS_ACTION'
ACCOUNT = 'exa_mars-saite'
MAX_RESPONSE_BYTES = 8_000_000
MAX_PAGE_BYTES = 1_000_000
MAX_PACKET_BYTES = 300_000
MAX_TARGETS = 64
MAX_DOCUMENTS = 24
MAX_PASSAGES = 6
MAX_PASSAGE_CHARS = 1500
MAX_CAPTURE_CHARS = 7000
TTL_SECONDS = 3600
CATALOG = json.loads(Path(__file__).with_name('repair_guidance_sources.json').read_text())['documents']
DOCS = {row['id']: row for row in CATALOG}
GENERAL_LIMIT = ('Official guidance is untrusted reference material, not local policy or proof of runtime behavior. '
                 'Only bounded exact passages are captured; full-document coverage is not claimed. '
                 'Unknown document version and publication date remain null. '
                 'An installed product version match was not established; configuration hashes and adapter schema revisions are not product versions.')


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _time(value):
    if not isinstance(value, str): raise ValueError('guidance_time')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None: raise ValueError('guidance_time')
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError): raise ValueError('guidance_time') from None


def _bounded(value, limit):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > limit: raise ValueError('guidance_size')


def _text(value, limit=2000):
    return isinstance(value, str) and 0 < len(value) <= limit and not any(ord(c) < 32 and c not in '\n\t\r' for c in value)


def _list_text(value, limit=32):
    return isinstance(value, list) and len(value) <= limit and all(_text(s) for s in value)


def _profiles(target):
    owner, category, adapter = target.get('owner'), target.get('category'), target.get('adapter_id', '')
    providers = {'paperclip_agent':['paperclip'], 'neon_project':['neon'], 'neon_branch':['neon-branches'],
                 'hindsight_bank':['hindsight'], 'signoz_alert':['signoz-alerts'], 'signoz_dashboard':['signoz-dashboards']}
    if adapter == 'provider_' + str(category) and category in providers: return providers[category]
    if category == 'remote_files':
        if not (adapter == 'remote_file_ssh' or isinstance(adapter,str) and adapter.startswith('remote_file_orgo_')): return []
        # root is the server-registered enum from repair_remote_runner, never
        # an arbitrary filename, owner prose, host name or content inference.
        identity = target.get('identity',{})
        root = identity.get('root') if isinstance(identity,dict) else None
        if not isinstance(root,str): return []
        profiles = {'hermes':['hermes'], 'claude':['claude-settings','claude-hooks','claude-memory'],
                    'codex':['codex-config','codex-instructions','codex-hooks'],
                    'instructions':['claude-memory','codex-instructions','cursor-rules','agent-patterns']}
        chosen = profiles.get(root,[])
        return chosen+(['orgo'] if chosen and adapter.startswith('remote_file_orgo_') else [])
    if owner == 'native-instruction-builder': return ['claude-memory','codex-instructions','cursor-rules','agent-patterns']
    if owner == 'shared-skill-lifecycle': return ['claude-skills','codex-skills']
    if owner == 'registered-agent-tools': return ['claude-hooks','codex-hooks','agent-patterns']
    if owner == 'claude': return ['claude-hooks'] if category == 'hook' else ['claude-settings','claude-hooks']
    if owner in ('codex','Codex native app-server'): return ['codex-hooks'] if category == 'hook' else ['codex-config']
    if owner == 'cursor': return ['cursor-hooks']
    if owner == 'cursor-cli': return ['cursor-cli']
    if owner in ('owned-plugin-source','native-plugin-install'): return ['claude-plugins','codex-plugins']
    if owner == 'git' and category == 'publication': return ['git']
    return []


def _pointer(path):
    if not isinstance(path, str): raise ValueError('guidance_pointer')
    root = Path(tempfile.gettempdir()) / 'composio'
    if root.is_symlink(): raise ValueError('guidance_pointer_symlink')
    resolved_root = root.resolve()
    candidate = Path(path)
    if not candidate.is_absolute() or '..' in candidate.parts: raise ValueError('guidance_pointer')
    try:
        base = root if candidate.is_relative_to(root) else resolved_root
        relative = candidate.relative_to(base)
        current = base
        for part in relative.parts:
            current = current / part
            if current.is_symlink(): raise ValueError('guidance_pointer_symlink')
        if candidate.resolve() != resolved_root / relative or not relative.parts: raise ValueError('guidance_pointer')
        fd = os.open(candidate, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode): raise ValueError('guidance_pointer_type')
            raw = handle.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES: raise ValueError('guidance_response_size')
        return json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError): raise ValueError('guidance_pointer') from None


def _unwrap(value, depth=0):
    if depth > 4 or not isinstance(value, dict): raise ValueError('guidance_response')
    _bounded(value, MAX_RESPONSE_BYTES)
    if value.get('successful') is False or value.get('isError') or value.get('error'):
        raise ValueError('guidance_retrieval_failed')
    if 'storedInFile' in value:
        if value.get('storedInFile') is not True or value.get('successful') is not True:
            raise ValueError('guidance_envelope')
        return _unwrap(_pointer(value.get('outputFilePath')), depth+1)
    if 'successful' in value:
        if value['successful'] is not True: raise ValueError('guidance_envelope')
        return _unwrap(value.get('data'), depth+1)
    if 'content' in value:
        blocks = value['content']
        if not isinstance(blocks, list) or len(blocks) != 1 or not isinstance(blocks[0],dict) or blocks[0].get('type') != 'text':
            raise ValueError('guidance_envelope')
        return _unwrap(json.loads(blocks[0]['text']), depth+1)
    if not isinstance(value.get('results'), list) or not isinstance(value.get('statuses'), list):
        raise ValueError('guidance_response')
    return value


def _retrieve(urls):
    if not urls or any(url not in {d['url'] for d in CATALOG} for url in urls):
        raise ValueError('guidance_request_identity')
    payload = {'urls': urls, 'text': True, 'maxAgeHours': 0, 'livecrawlTimeout': 15000}
    with tempfile.TemporaryDirectory(prefix='repair-guidance-') as folder:
        path = Path(folder) / 'request.json'
        path.write_text(json.dumps(payload)); path.chmod(0o600)
        completed = subprocess.run(['composio','execute','EXA_GET_CONTENTS_ACTION','--account',ACCOUNT,
                                    '-d','@'+str(path)], capture_output=True, text=True, timeout=90, check=False)
    if completed.returncode or len(completed.stdout.encode()) > MAX_RESPONSE_BYTES:
        raise ValueError('guidance_transport_failed')
    return json.loads(completed.stdout)


def _passages(text, terms):
    candidates = []
    for position, chunk in enumerate(re.split(r'\n\s*\n', text)):
        lower = chunk.lower()
        if not chunk.strip() or lower.startswith(('> ## documentation index', '> fetch the complete documentation index')):
            continue
        meaningful = [line for line in chunk.splitlines() if line.strip() and not line.lstrip().startswith('#')]
        if not meaningful or len(' '.join(meaningful).split()) < 8: continue
        matches = [(len(terms)-index, lower.find(term.lower())) for index,term in enumerate(terms) if term.lower() in lower]
        caveat = re.search(r'changed since|superseded|historical|managed agents|no longer supported', lower)
        if not matches and not caveat: continue
        score = sum(weight for weight,_ in matches) + (100 if caveat else 0)
        if 'deprecated' in lower and any(term.lower() in lower for term in terms[:3]): score += 10
        anchor = caveat.start() if caveat else max(matches)[1]
        start = max(0, anchor-MAX_PASSAGE_CHARS//3) if len(chunk)>MAX_PASSAGE_CHARS else 0
        excerpt = chunk[start:start+MAX_PASSAGE_CHARS]
        candidates.append((-score, position, excerpt))
    selected = []; total = 0
    for _,_,excerpt in sorted(candidates):
        if excerpt in selected or total+len(excerpt)>MAX_CAPTURE_CHARS: continue
        selected.append(excerpt); total+=len(excerpt)
        if len(selected)==MAX_PASSAGES: break
    if not selected: raise ValueError('guidance_relevant_passages_unavailable')
    return [{'id':'p-'+_sha(value), 'text':value} for value in selected]


def collect_guidance(sources):
    if not isinstance(sources,list) or not 1 <= len(sources) <= MAX_TARGETS: raise ValueError('guidance_targets')
    targets = []
    for source in sources:
        target = source.get('target') if isinstance(source,dict) else None
        if not isinstance(target,dict) or not _text(target.get('id'),256): raise ValueError('guidance_target')
        if not isinstance(target.get('owner'),str) or not isinstance(target.get('category'),str) or not isinstance(target.get('adapter_id',''),str):
            raise ValueError('guidance_target_metadata')
        targets.append(target)
    if len({t['id'] for t in targets}) != len(targets): raise ValueError('guidance_target_duplicate')
    now = datetime.now(timezone.utc)
    stamp = now.isoformat()
    packet = {'schema_version':1,'retrieved_at':stamp,'expires_at':(now+timedelta(seconds=TTL_SECONDS)).isoformat(),
              'route':ROUTE,'sources':[],'coverage':[],'limitations':[GENERAL_LIMIT]}
    profiles = {t['id']:_profiles(t) for t in targets}
    wanted = sorted({key for keys in profiles.values() for key in keys})
    failure = None
    records = {}
    if len(wanted) > MAX_DOCUMENTS: failure = 'Guidance document bound exceeded; no retrieval claimed.'
    elif wanted:
        try:
            body = _unwrap(_retrieve([DOCS[key]['url'] for key in wanted]))
            expected = {DOCS[key]['url'] for key in wanted}
            results, statuses = {}, {}
            for row in body['results']:
                if not isinstance(row,dict) or row.get('url') not in expected or row.get('id',row.get('url')) != row.get('url') or row['url'] in results:
                    raise ValueError('guidance_source_identity')
                results[row['url']] = row
            for row in body['statuses']:
                if not isinstance(row,dict) or row.get('id') not in expected or row['id'] in statuses:
                    raise ValueError('guidance_status_identity')
                statuses[row['id']] = row
            if set(statuses) != expected: raise ValueError('guidance_partial_response')
            successful = {url for url,status in statuses.items() if status.get('status') == 'success'}
            if set(results) != successful: raise ValueError('guidance_partial_response')
            for key in wanted:
                doc = DOCS[key]; status = statuses[doc['url']]
                if status.get('status') != 'success': continue
                row = results[doc['url']]
                if status.get('error') or row.get('error') or row.get('statusCode',200) != 200:
                    raise ValueError('guidance_source_failed')
                if re.search(r'(?i)(?:^|\b)(?:404|not found|page unavailable|access denied)(?:\b|$)', str(row.get('title',''))):
                    raise ValueError('guidance_error_page')
                text = row.get('text')
                if not _text(text, MAX_PAGE_BYTES) or len(text.encode()) > MAX_PAGE_BYTES:
                    raise ValueError('guidance_content_size_or_empty')
                title = row.get('title') or doc['title']
                if not _text(title,512): raise ValueError('guidance_source_title')
                passages = _passages(text,doc['terms'])
                date = row.get('publishedDate')
                if date is not None: _time(date)
                records[key] = {'id':key,'url':doc['url'],'title':title,'publisher':doc['publisher'],
                                'content_sha256':_sha(text),'version':None,'publication_date':date,
                                'crawl_status':status.get('source') if status.get('source') in ('crawled','cached') else 'unknown',
                                'retrieved_at':stamp,'passages':passages,
                                'target_ids':[t['id'] for t in targets if key in profiles[t['id']]]}
        except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError):
            failure = 'Official guidance retrieval failed validation; no supporting content claimed.'
            records = {}
    packet['sources'] = list(records.values())
    for target in targets:
        keys = profiles[target['id']]
        available = [key for key in keys if key in records]
        complete = bool(keys) and len(available) == len(keys)
        limitations = [] if complete else [failure or ('No registered official guidance profile for this owner.' if not keys else 'One or more required official documents are unavailable.')]
        packet['coverage'].append({'target_id':target['id'],'source_ids':available,
                                   'status':'available' if complete else 'unavailable','limitations':limitations})
    if failure: packet['limitations'].append(failure)
    _bounded(packet, MAX_PACKET_BYTES)
    validate_guidance(packet,[t['id'] for t in targets])
    return packet


def validate_guidance(packet,target_ids,at=None):
    """Validate captured evidence, catalog identities and freshness, never recrawl."""
    def require(condition, code='guidance_packet'):
        if not condition: raise ValueError(code)
    require(isinstance(packet,dict))
    _bounded(packet,MAX_PACKET_BYTES)
    require(set(packet)=={'schema_version','retrieved_at','expires_at','route','sources','coverage','limitations'})
    require(type(packet['schema_version']) is int and packet['schema_version']==1 and packet['route']==ROUTE)
    require(isinstance(target_ids,list) and 1<=len(target_ids)<=MAX_TARGETS)
    require(all(_text(t,256) for t in target_ids))
    require(len(set(target_ids))==len(target_ids))
    retrieved, expires = _time(packet['retrieved_at']), _time(packet['expires_at'])
    current = datetime.now(timezone.utc) if at is None else (_time(at) if isinstance(at,str) else at)
    require(isinstance(current,datetime) and current.tzinfo is not None,'guidance_time')
    require(retrieved <= current < expires and 0 < (expires-retrieved).total_seconds() <= TTL_SECONDS,'guidance_stale')
    require(_list_text(packet['limitations']))
    require(isinstance(packet['sources'],list) and len(packet['sources'])<=MAX_DOCUMENTS)
    sources = {}
    for source in packet['sources']:
        require(isinstance(source,dict) and set(source)=={'id','url','title','publisher','content_sha256','version','publication_date','crawl_status','retrieved_at','passages','target_ids'})
        key = source['id']; require(isinstance(key,str) and key in DOCS and key not in sources)
        require(source['url']==DOCS[key]['url'] and source['publisher']==DOCS[key]['publisher'],'guidance_source_identity')
        require(_text(source['title'],512) and isinstance(source['content_sha256'],str) and re.fullmatch('[0-9a-f]{64}',source['content_sha256']))
        require(source['version'] is None, 'guidance_unproven_version')
        if source['publication_date'] is not None: _time(source['publication_date'])
        require(source['retrieved_at']==packet['retrieved_at'] and source['crawl_status'] in ('crawled','cached','unknown'))
        tids=source['target_ids']; require(_list_text(tids,MAX_TARGETS) and tids and len(set(tids))==len(tids) and set(tids)<=set(target_ids))
        passages=source['passages']; require(isinstance(passages,list) and 1<=len(passages)<=MAX_PASSAGES)
        seen=set(); total=0
        for passage in passages:
            require(isinstance(passage,dict) and set(passage)=={'id','text'} and _text(passage['text'],MAX_PASSAGE_CHARS))
            require(passage['id']=='p-'+_sha(passage['text']) and passage['id'] not in seen,'guidance_passage_digest')
            seen.add(passage['id']); total+=len(passage['text'])
        require(total<=MAX_CAPTURE_CHARS)
        sources[key]=source
    require(isinstance(packet['coverage'],list) and len(packet['coverage'])==len(target_ids))
    seen=set()
    for coverage in packet['coverage']:
        require(isinstance(coverage,dict) and set(coverage)=={'target_id','source_ids','status','limitations'})
        tid=coverage['target_id']; require(_text(tid,256) and tid in target_ids and tid not in seen); seen.add(tid)
        ids=coverage['source_ids']; require(_list_text(ids,MAX_DOCUMENTS) and len(set(ids))==len(ids))
        require(set(ids)=={key for key,s in sources.items() if tid in s['target_ids']},'guidance_coverage')
        require(coverage['status'] in ('available','unavailable') and _list_text(coverage['limitations']))
        require(bool(ids) if coverage['status']=='available' else bool(coverage['limitations']))
    return True


def public_guidance(packet):
    """Projection only: callers validate private packet before binding approval."""
    validate_guidance(packet,[row['target_id'] for row in packet['coverage']],at=packet['retrieved_at'])
    result=copy.deepcopy(packet)
    for source in result['sources']:
        first=source['passages'][0]
        words=list(re.finditer(r'\S+',first['text']))
        end=words[min(24,len(words))-1].end()
        source['passages']=[{'id':first['id'],'text':first['text'][:end]}]
    return result
