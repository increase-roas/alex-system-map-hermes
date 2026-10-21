import copy
import json
import os
import shlex
import subprocess
import sys
from unittest.mock import patch
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest

from repair_contracts import RepairError
from repair_remote_runner import run_request
from repair_remote_adapters import RemoteFileAdapter, RemoteTransport, ProviderAdapter, PROVIDERS, ORGO_HOSTS, NativeProviderExchange, PAPERCLIP_PROGRAM


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / 'settings.json'
        self.path.write_text(json.dumps({'model': 'old', 'apiKey': 'PRIVATE', 'other': 1}))
        self.roots = {'fixture': str(self.root)}
        self.base = {'root': 'fixture', 'relative': 'settings.json', 'host': 'fixture'}

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, action, **kw):
        return run_request(dict(self.base, action=action, **kw), self.roots, 'fixture')

    def test_json_lifecycle_secret_free_inverse_preserves_unrelated(self):
        before = self.request('read')
        self.assertNotIn('PRIVATE', json.dumps(before))
        op = {'patch': {'model': 'new'}, 'expected_fingerprint': before['fingerprint'], 'expected_mode': before['mode']}
        backup = self.request('backup', **op)
        self.assertNotIn('PRIVATE', json.dumps(backup))
        result = self.request('apply', **op)
        self.assertEqual(result['projection']['model'], 'new')
        current = json.loads(self.path.read_text())
        current['other'] = 2
        self.path.write_text(json.dumps(current))
        undo = self.request('undo', patch=op['patch'], inverse=backup['inverse'])
        self.assertEqual(undo['projection']['model'], 'old')
        self.assertEqual(json.loads(self.path.read_text())['other'], 2)
        self.assertEqual(json.loads(self.path.read_text())['apiKey'], 'PRIVATE')

    def test_parse_interleaving_rejects_unrelated_edit_for_apply_and_undo(self):
        import repair_remote_runner as runner
        original_parse = runner.parse
        for action in ('apply', 'undo'):
            with self.subTest(action=action):
                self.path.write_text('{"model":"old","other":1}')
                before = self.request('read')
                op = {'patch': {'model': 'new'}, 'expected_fingerprint': before['fingerprint'], 'expected_mode': before['mode']}
                backup = self.request('backup', **op)
                if action == 'undo': self.request('apply', **op)
                calls = []
                def interleave(path, data):
                    calls.append(1)
                    if len(calls) == 2:
                        state = json.loads(path.read_text()); state['other'] = 2
                        path.write_text(json.dumps(state))
                    return original_parse(path, data)
                with patch.object(runner, 'parse', side_effect=interleave):
                    with self.assertRaises(RepairError) as caught:
                        self.request(action, **dict(op, inverse=backup['inverse']))
                self.assertEqual(caught.exception.code, 'remote_stale')
                self.assertEqual(json.loads(self.path.read_text())['other'], 2)
                self.assertEqual(json.loads(self.path.read_text())['model'], 'new' if action == 'undo' else 'old')

    def test_final_source_anchor_rejects_same_bytes_new_inode_and_mode_change(self):
        import repair_remote_runner as runner
        original_parse = runner.parse
        for change in ('inode', 'mode'):
            with self.subTest(change=change):
                self.path.write_text('{"model":"old","other":1}'); self.path.chmod(0o640)
                before = self.request('read'); calls = []
                def interleave(path, data):
                    calls.append(1)
                    if len(calls) == 2:
                        if change == 'mode': path.chmod(0o600)
                        else:
                            replacement = path.with_suffix('.replacement')
                            replacement.write_bytes(path.read_bytes()); replacement.chmod(0o640)
                            os.replace(replacement, path)
                    return original_parse(path, data)
                with patch.object(runner, 'parse', side_effect=interleave):
                    with self.assertRaises(RepairError) as caught:
                        self.request('apply', patch={'model':'new'}, expected_fingerprint=before['fingerprint'], expected_mode=before['mode'])
                self.assertEqual(caught.exception.code,'remote_stale')
                self.assertEqual(json.loads(self.path.read_text())['model'],'old')

    def test_cas_mode_host_escape_and_symlink(self):
        before = self.request('read')
        for req in [dict(self.base, host='wrong', action='read'), dict(self.base, relative='../x', action='read')]:
            with self.assertRaises(RepairError): run_request(req, self.roots, 'fixture')
        self.path.chmod(0o600)
        with self.assertRaises(RepairError): self.request('apply', patch={'model':'new'}, expected_fingerprint=before['fingerprint'], expected_mode=before['mode'])
        self.path.unlink()
        self.path.symlink_to('/tmp')
        with self.assertRaises(RepairError): self.request('read')

    def test_undo_refuses_changed_field(self):
        before = self.request('read')
        op = {'patch':{'model':'new'}, 'expected_fingerprint':before['fingerprint'], 'expected_mode':before['mode']}
        backup = self.request('backup', **op)
        self.request('apply', **op)
        self.path.write_text('{"model":"someone else"}')
        with self.assertRaises(RepairError): self.request('undo', patch=op['patch'], inverse=backup['inverse'])


class TransportTests(unittest.TestCase):
    def test_ssh_and_orgo_reviewed_stdin_runner_lifecycle(self):
        for kind in ('ssh','orgo'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                home=Path(tmp); (home/'.claude').mkdir()
                file=home/'.claude/settings.json';file.write_text('{"model":"old","apiKey":"PRIVATE","other":1}')
                env=dict(os.environ,HOME=tmp)
                def execute_source(command,payload):
                    words=shlex.split(command)
                    result=subprocess.run([sys.executable,'-c',words[2]],input=json.dumps(payload),capture_output=True,text=True,env=env)
                    return json.loads(result.stdout)
                def ssh(argv,payload=None,timeout=60):
                    self.assertEqual(argv[-2],'agency-mini')
                    return execute_source(argv[-1],payload)
                def orgo(slug,account,payload):
                    self.assertEqual(account,'ca_33sT2QgdT6_Y')
                    self.assertEqual(payload['id'],next(iter(ORGO_HOSTS.values())))
                    command,stdin=payload['command'].split(" <<'REPAIR_JSON'\n",1)
                    result=execute_source(command,json.loads(stdin.rsplit('\nREPAIR_JSON',1)[0]))
                    return {'output':json.dumps(result),'exit_code':0}
                with patch('repair_remote_adapters.run_process',side_effect=ssh),patch('repair_remote_adapters.composio',side_effect=orgo):
                    adapter=RemoteFileAdapter(kind,next(iter(ORGO_HOSTS.values())) if kind=='orgo' else None)
                    target=adapter.discover()[0]; snap=adapter.read(target)
                    op=adapter.prepare(target,snap,{'patch':{'model':'new'}})
                    backup=adapter.backup(target,op,tmp)
                    result=adapter.apply(target,op,backup)
                    verified=adapter.verify(target,op,result);self.assertTrue(verified['ok']);self.assertTrue(verified['checks']);self.assertEqual(verified['checks'][0]['status'],'passed')
                    self.assertNotIn('PRIVATE',json.dumps([snap,backup,op]))
                    self.assertEqual(adapter.reconcile(target,op,backup)['outcome'],'applied')
                    current=json.loads(file.read_text());current['other']=2;file.write_text(json.dumps(current))
                    self.assertTrue(adapter.undo(target,op,backup,result)['ok'])
                    self.assertEqual(adapter.reconcile(target,dict(op,recovery_phase='undo'),backup)['outcome'],'applied')
                    self.assertEqual(json.loads(file.read_text())['other'],2)

    def test_lost_remote_write_response_reconciles_without_reapplying(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'settings.json').write_text('{"model":"old"}');writes=[]
            def transport(request):
                result=run_request(request,{'fixture':tmp},'fixture')
                if request['action']=='apply':writes.append(1);raise RepairError('remote_transport_uncertain')
                return result
            adapter=RemoteFileAdapter(exchange=transport)
            target={'identity':{'root':'fixture','relative':'settings.json','host':'fixture','runner_revision':__import__('hashlib').sha256(Path(__file__).with_name('repair_remote_runner.py').read_bytes()).hexdigest()},'allowed_patch_paths':['model']}
            op=adapter.prepare(target,adapter.read(target),{'patch':{'model':'new'}});backup=adapter.backup(target,op,tmp)
            with self.assertRaises(RepairError):adapter.apply(target,op,backup)
            self.assertEqual(adapter.reconcile(target,op,backup)['outcome'],'applied');self.assertEqual(len(writes),1)


class NativePaperclipTests(unittest.TestCase):
    def test_token_stays_remote_native_validate_patch_readback_and_revision_rollback(self):
        aid='e72281f5-234f-495c-9013-8f02a92633f8'
        rid='11111111-1111-4111-8111-111111111111'
        state={'id':aid,'companyId':'22eb3ea5-8bb2-4768-a97c-de624fac5699','name':'old','updatedAt':'v1','adapterConfig':{'apiKey':'PRIVATE'}}
        routes=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_GET(self):
                self.assert_auth();routes.append(('GET',self.path))
                body=[{'id':aid,'companyId':state['companyId']}] if self.path.endswith('/agents') else [{'id':rid}] if self.path.endswith('/config-revisions') else state
                self.send_response(200);self.end_headers();self.wfile.write(json.dumps(body).encode())
            def assert_auth(self):
                if self.headers.get('Authorization')!='Bearer PRIVATE':raise AssertionError('remote auth')
            def do_PATCH(self):
                self.assert_auth();routes.append(('PATCH',self.path))
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if body!={'name':'new'}:raise AssertionError('field-scoped patch')
                state.update(body);state['updatedAt']='v2'
                self.send_response(200);self.end_headers();self.wfile.write(json.dumps(state).encode())
            def do_POST(self):
                self.assert_auth();routes.append(('POST',self.path));state['name']='old';state['updatedAt']='v3'
                self.send_response(200);self.end_headers();self.wfile.write(json.dumps(state).encode())
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                home=Path(tmp);auth=home/'.paperclip';auth.mkdir()
                (auth/'auth.json').write_text(json.dumps({'credentials':{'https://paperclip.increaseroas.com':{'token':'PRIVATE'}}}))
                module=home/'Documents/Paperclip/app/node_modules/@paperclipai/shared/dist/validators';module.mkdir(parents=True)
                (module/'package.json').write_text('{"type":"module"}')
                (module/'agent.js').write_text('export const updateAgentSchema={safeParse:x=>({success: typeof x.name === "string" && Object.keys(x).length===1})};')
                source=PAPERCLIP_PROGRAM.replace('http://127.0.0.1:3100',f'http://127.0.0.1:{server.server_port}')
                def ssh(argv,payload=None,timeout=60):
                    result=subprocess.run([sys.executable,'-c',source],input=json.dumps(payload),env=dict(os.environ,HOME=tmp),capture_output=True,text=True)
                    self.assertNotIn('PRIVATE',result.stdout)
                    return json.loads(result.stdout)
                with patch('repair_remote_adapters.run_process',side_effect=ssh):
                    adapter=ProviderAdapter('paperclip_agent');target=adapter.discover()[0]
                    snap=adapter.read(target);op=adapter.prepare(target,snap,{'patch':{'name':'new'}})
                    backup=adapter.backup(target,op,tmp);applied=adapter.apply(target,op,backup)
                    self.assertTrue(adapter.verify(target,op,applied)['ok'])
                    self.assertTrue(adapter.undo(target,op,backup,applied)['ok'])
                    self.assertIn(('POST','/api/agents/'+aid+'/config-revisions/'+rid+'/rollback'),routes)
                    self.assertEqual(state['adapterConfig']['apiKey'],'PRIVATE')
        finally:server.shutdown();server.server_close();thread.join()


class NativeProviderWireTests(unittest.TestCase):
    def test_fixed_neon_hindsight_signoz_wire_payloads_and_inverse(self):
        for provider in ('neon_project','neon_branch','hindsight_bank','signoz_alert','signoz_dashboard'):
            with self.subTest(provider=provider):
                spec=PROVIDERS[provider];field=next(iter(spec['fields']));writes=[]
                state={'id':'fixture',field:'old','unrelated':'keep','updated_at':'v1'}
                if provider == 'signoz_alert':
                    field = 'annotations.summary'
                    state.update({'alert':'old','condition':{'thresholds':{'critical':7},'query':'preserve query'},
                                  'annotations':{'summary':'old','description':'preserve description','runbook':'preserve URL'},
                                  'evaluation':{'interval':'1m'},'labels':{'team':'ops'}})
                elif provider == 'signoz_dashboard':
                    field = 'spec.duration'
                    state.update({'name':'old','tags':['keep'], 'spec':{'duration':'old','panels':{'a':{'query':'keep'}},
                                  'display':{'title':'keep'},'variables':[{'name':'service'}], 'customSibling':{'keep':True}}})
                original = copy.deepcopy(state)
                identity={'object_id':'fixture','account':spec['account'],'project_id':'project'}
                native=NativeProviderExchange(provider)
                def cli(slug,account,payload):
                    if 'GET_' in slug or 'DESCRIBE_PROJECT' in slug:return copy.deepcopy(state)
                    self.assertEqual(account,spec.get('write_account',spec['account']))
                    writes.append(copy.deepcopy(payload))
                    if provider.startswith('neon_'):
                        kind=provider.split('_')[1];self.assertEqual(payload['project_id'],'project');body=payload[kind]
                        if kind=='branch':self.assertEqual(payload['branch_id'],'fixture')
                    else:
                        self.assertEqual(payload.get('ruleId') or payload.get('id'),'fixture');body=payload
                    if provider.startswith('signoz_'):
                        # Native UPDATE replaces the complete writable object.
                        replacement = {k:v for k,v in body.items() if k not in ('ruleId','id')}
                        state.clear();state.update({'id':'fixture', **replacement})
                    else: state.update(body)
                    state['updated_at']='v'+str(len(writes)+1);return {'ok':True}
                def bank(method,bank_id=None,body=None):
                    if bank_id is None:return {'banks':[{'bank_id':'fixture'}]}
                    if method=='GET':return {'bank_id':'fixture','config':dict(state),'overrides':{}}
                    self.assertEqual(body,{'updates':{field:body['updates'][field]}});writes.append(copy.deepcopy(body));state.update(body['updates']);return {}
                with patch('repair_remote_adapters.composio',side_effect=cli),patch.object(native,'hindsight',side_effect=bank),tempfile.TemporaryDirectory() as tmp:
                    adapter=ProviderAdapter(provider,exchange=native,registrations=[{'object_id':'fixture','identity':identity}])
                    target=adapter.discover()[0];op=adapter.prepare(target,adapter.read(target),{'patch':{field:'new'}})
                    backup=adapter.backup(target,op,tmp);applied=adapter.apply(target,op,backup)
                    self.assertTrue(adapter.verify(target,op,applied)['ok'])
                    if provider.startswith('signoz_'):
                        sibling = 'annotations' if provider == 'signoz_alert' else 'spec'
                        for key, value in original[sibling].items():
                            if key != field.split('.')[-1]: self.assertEqual(state[sibling][key], value)
                        preserved = ('condition','evaluation','labels') if provider == 'signoz_alert' else ('name','tags')
                        for key in preserved: self.assertEqual(state[key], original[key])
                        state[sibling]['externalSibling'] = 'changed'
                    else: state['unrelated']='changed'
                    self.assertTrue(adapter.undo(target,op,backup,applied)['ok'])
                    from repair_remote_runner import get_field
                    self.assertEqual(get_field(state, field)['value'],'old')
                    if provider.startswith('signoz_'):
                        self.assertEqual(state[sibling]['externalSibling'], 'changed')
                        for key, value in original[sibling].items(): self.assertEqual(state[sibling][key], value)
                        for key in preserved: self.assertEqual(state[key], original[key])
                    else: self.assertEqual(state['unrelated'],'changed')
                    self.assertEqual(len(writes),2)

    def test_native_same_object_writers_serialize_and_second_baseline_is_stale(self):
        spec = PROVIDERS['neon_project']
        state = {'id':'fixture', 'name':'old', 'updated_at':'v1'}
        entered_write = threading.Event(); release_write = threading.Event(); second_started = threading.Event()
        calls = []; outcomes = []
        identity = {'object_id':'fixture','project_id':'fixture','account':spec['account']}
        def transport(slug, account, payload):
            self.assertEqual(account, spec['account'])
            if 'DESCRIBE' in slug:
                calls.append('get'); return copy.deepcopy(state)
            calls.append('write'); entered_write.set()
            self.assertTrue(release_write.wait(3))
            self.assertEqual(set(payload), {'project_id','project'})
            state.update(payload['project']);state['updated_at']='v2';return {}
        first = NativeProviderExchange('neon_project'); second = NativeProviderExchange('neon_project')
        from repair_remote_runner import digest
        payload = {'patch':{'name':'new'}, 'expected_version':'v1', 'expected_fingerprint':digest({'config':state,'version':'v1'})}
        def write(native, started=None):
            if started: started.set()
            try: outcomes.append(native('write', {'identity':identity}, payload))
            except RepairError as error: outcomes.append(error.code)
        with patch('repair_remote_adapters.composio', side_effect=transport):
            a=threading.Thread(target=write,args=(first,)); b=threading.Thread(target=write,args=(second,second_started))
            a.start();self.assertTrue(entered_write.wait(3));b.start();self.assertTrue(second_started.wait(3))
            # First native write holds the OS lock while its API response is pending.
            self.assertEqual(calls, ['get','write'])
            release_write.set();a.join(3);b.join(3)
        self.assertFalse(a.is_alive() or b.is_alive())
        self.assertEqual(calls, ['get','write','get'])
        self.assertIn('provider_stale', outcomes)
        self.assertEqual(state['name'], 'new')

    def test_external_edit_after_final_get_is_honestly_nonconditional(self):
        spec = PROVIDERS['neon_project']; state = {'id':'fixture','name':'old','updated_at':'v1','other':'keep'}
        writes=[]
        def transport(slug, account, payload):
            if 'DESCRIBE' in slug: return copy.deepcopy(state)
            # Independent client writes after final GET. Native Neon mutation
            # contains no version predicate and therefore can overwrite it.
            state['name']='external edit';state['updated_at']='external-version'
            writes.append(copy.deepcopy(payload));state.update(payload['project']);state['updated_at']='v2';return {}
        native=NativeProviderExchange('neon_project')
        adapter=ProviderAdapter('neon_project',exchange=native,registrations=[{'identity':{'object_id':'fixture','project_id':'fixture','account':spec['account']}}])
        with patch('repair_remote_adapters.composio',side_effect=transport):
            target=adapter.discover()[0];op=adapter.prepare(target,adapter.read(target),{'patch':{'name':'new'}})
            backup=adapter.backup(target,op,'unused');applied=adapter.apply(target,op,backup)
            verified=adapter.verify(target,op,applied)
        self.assertEqual(writes,[{'project_id':'fixture','project':{'name':'new'}}])
        self.assertEqual(state['name'],'new');self.assertEqual(state['other'],'keep')
        self.assertTrue(verified['ok'])
        for item in (target,op,applied,verified):
            self.assertIn('no server-side version condition', ' '.join(item['limitations']))


class ProviderTests(unittest.TestCase):
    def test_every_provider_lifecycle_and_uncertain_reconcile(self):
        for provider, spec in PROVIDERS.items():
            with self.subTest(provider=provider):
                field = next(iter(spec['fields']))
                state = {field:'old', 'apiKey':'PRIVATE', 'unrelated':'keep'}
                writes = []
                def exchange(action, target, payload=None):
                    if action == 'read': return {'identity':target['identity'], 'config':copy.deepcopy(state), 'version':'v1', 'schema_revision':spec['revision']}
                    if action == 'write':
                        writes.append(copy.deepcopy(payload)); state.update(payload['patch']); return {'version':'v2'}
                    if action == 'dry_run': return {'ok':True, 'schema_revision':spec['revision']}
                    raise AssertionError(action)
                adapter = ProviderAdapter(provider, exchange=exchange, registrations=[{'object_id':'fixture', 'identity':{'object_id':'fixture','account':spec['account']}}])
                target = adapter.discover()[0]
                snap = adapter.read(target)
                self.assertNotIn('PRIVATE', json.dumps(snap))
                op = adapter.prepare(target, snap, {'patch':{field:'new'}})
                self.assertTrue(adapter.preflight(target,op)['ok'])
                with tempfile.TemporaryDirectory() as tmp:
                    backup = adapter.backup(target,op,tmp)
                    self.assertNotIn('PRIVATE',json.dumps(backup))
                    result = adapter.apply(target,op,backup)
                    verified=adapter.verify(target,op,result);self.assertTrue(verified['ok']);self.assertTrue(verified['checks']);self.assertEqual(verified['checks'][0]['status'],'passed')
                    self.assertEqual(adapter.reconcile(target,op,backup)['outcome'],'applied')
                    self.assertEqual(len(writes),1)
                    state['unrelated']='changed'
                    self.assertTrue(adapter.undo(target,op,backup,result)['ok'])
                    self.assertEqual(state[field],'old')
                    self.assertEqual(state['unrelated'],'changed')
                    self.assertEqual(state['apiKey'],'PRIVATE')
                    self.assertEqual(adapter.reconcile(target,dict(op,recovery_phase='undo'),backup)['outcome'],'applied')

    def test_uncertain_write_reconciles_without_repeating_and_undo_conflicts(self):
        spec=PROVIDERS['neon_project'];state={'name':'old'};writes=[]
        def exchange(action,target,payload=None):
            if action=='read':return {'identity':target['identity'],'config':dict(state),'version':str(len(writes)),'schema_revision':spec['revision']}
            if action=='dry_run':return {'ok':True,'schema_revision':spec['revision']}
            if action=='write':
                writes.append(payload);state.update(payload['patch']);raise RepairError('remote_transport_uncertain')
        adapter=ProviderAdapter('neon_project',exchange=exchange,registrations=[{'object_id':'fixture','identity':{'object_id':'fixture','account':spec['account']}}])
        target=adapter.discover()[0];op=adapter.prepare(target,adapter.read(target),{'patch':{'name':'new'}})
        backup=adapter.backup(target,op,'unused')
        with self.assertRaises(RepairError):adapter.apply(target,op,backup)
        self.assertEqual(adapter.reconcile(target,op,backup)['outcome'],'applied')
        self.assertEqual(len(writes),1)
        state['name']='other owner update'
        self.assertEqual(adapter.undo(target,op,backup,{})['state'],'blocked')
        self.assertEqual(len(writes),1)

    def test_embedded_credentials_redacted_before_model_and_public_diff(self):
        spec=PROVIDERS['paperclip_agent']
        state={'name':'old','adapterConfig':{'promptTemplate':'Authorization: Bearer abcdefghijklmnopqrstuvwxyz'}}
        def exchange(action,target,payload=None):return {'identity':target['identity'],'config':state,'version':'v1','schema_revision':spec['revision']}
        adapter=ProviderAdapter('paperclip_agent',exchange=exchange,registrations=[{'object_id':'fixture','identity':{'object_id':'fixture','account':spec['account']}}])
        target=adapter.discover()[0];snapshot=adapter.read(target)
        self.assertNotIn('abcdefghijklmnopqrstuvwxyz',json.dumps(snapshot));self.assertIn('[REDACTED]',json.dumps(snapshot))

    def test_discovery_lists_identity_without_fetching_config_and_selected_preflight_reads_fresh(self):
        spec=PROVIDERS['neon_project'];calls=[];state={'name':'old'}
        rows=[{'object_id':str(i),'identity':{'object_id':str(i),'account':spec['account']}} for i in range(30)]
        def exchange(action,target,payload=None):
            calls.append(action)
            if action=='discover':return rows
            if action=='read':return {'identity':target['identity'],'config':dict(state),'version':'v1','schema_revision':spec['revision']}
            if action=='dry_run':return {'ok':True,'schema_revision':spec['revision']}
            raise AssertionError(action)
        adapter=ProviderAdapter('neon_project',exchange=exchange)
        targets=adapter.discover();self.assertEqual(len(targets),30);self.assertEqual(calls,['discover'])
        selected=targets[0];snapshot=adapter.read(selected)
        operation=adapter.prepare(selected,snapshot,{'patch':{'name':'new'}})
        self.assertEqual(calls.count('read'),1)
        self.assertTrue(adapter.preflight(selected,operation)['ok']);self.assertEqual(calls.count('read'),2)
        state['name']='updated after preview'
        with self.assertRaises(RepairError):adapter.preflight(selected,operation)
        self.assertEqual(calls.count('read'),3)

    def test_native_read_rejects_mismatched_identity_with_valid_schema(self):
        spec=PROVIDERS['neon_project']
        registration={'object_id':'fixture','identity':{'object_id':'fixture','account':spec['account']}}
        def exchange(action,target,payload=None):
            return {'identity':dict(target['identity'],object_id='different-object'),
                    'config':{'name':'old'},'version':'v1','schema_revision':spec['revision']}
        adapter=ProviderAdapter('neon_project',exchange=exchange,registrations=[registration])
        target=adapter.discover()[0]
        with self.assertRaises(RepairError) as caught:adapter.read(target)
        self.assertEqual(caught.exception.code,'provider_identity_mismatch')

    def test_allowed_typed_field_rejects_embedded_credential_value(self):
        spec=PROVIDERS['paperclip_agent']
        registration={'object_id':'fixture','identity':{'object_id':'fixture','account':spec['account']}}
        def exchange(action,target,payload=None):
            return {'identity':target['identity'],'config':{'adapterConfig':{'promptTemplate':'existing instructions'}},
                    'version':'v1','schema_revision':spec['revision']}
        adapter=ProviderAdapter('paperclip_agent',exchange=exchange,registrations=[registration])
        target=adapter.discover()[0];snapshot=adapter.read(target)
        with self.assertRaises(RepairError) as caught:
            adapter.prepare(target,snapshot,{'patch':{'adapterConfig.promptTemplate':'Authorization: Bearer syntheticcredentialvalue12345'}})
        self.assertEqual(caught.exception.code,'provider_secret_patch')

    def test_stale_schema_identity_and_secret_patch_rejected(self):
        spec=PROVIDERS['neon_project']
        state={'name':'old'}
        def exchange(action,target,payload=None): return {'identity':target['identity'], 'config':state,'version':'v1','schema_revision':'wrong'}
        adapter=ProviderAdapter('neon_project',exchange=exchange,registrations=[{'object_id':'fixture','identity':{'object_id':'fixture','account':spec['account']}}])
        target=adapter.discover()[0]
        with self.assertRaises(RepairError): adapter.read(target)


if __name__ == '__main__': unittest.main()
