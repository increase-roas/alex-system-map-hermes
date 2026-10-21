"""Registered remote/native repair operations. All production mutations are called
only by the approved coordinator; discovery and reads never execute writes.
No generic API proxy, model command, credential response or blind mutation retry.
"""
import copy
import datetime
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import urllib.parse
import threading
from repair_contracts import RepairError
from repair_remote_runner import digest, redact, sensitive, get_field, set_field

VERSION = '1'
ORGO_ACCOUNT = 'ca_33sT2QgdT6_Y'
NEON_ACCOUNT = 'custom_neon_mcp_dusk-glor'
SIGNOZ_READER = 'custom_signoz_mcp_vest-chott'
SIGNOZ_EDITOR = 'custom_signoz_mcp_burnt-valmy'
COMPANY = '22eb3ea5-8bb2-4768-a97c-de624fac5699'
ORGO_HOSTS = {'javar':'d9b475e2-47b2-46d4-b8eb-102564f93283', 'openclaw':'6fbffd8c-65b1-4f2e-993e-f283532109bf'}
# Fields are native configuration paths, not generic arbitrary request fields.
PROVIDERS = {
 'paperclip_agent': {'account':'agency-mini:board', 'revision':'paperclip-updateAgentSchema-2026.1012.0',
  'fields':{'name':str,'title':(str,type(None)),'capabilities':(str,type(None)), 'adapterConfig.model':str,
            'adapterConfig.promptTemplate':str,'runtimeConfig.heartbeat.enabled':bool}},
 'neon_project': {'account':NEON_ACCOUNT, 'revision':'sha256:a906871af95dbe41286dca5065d98bfa14c6aacae969b2dfe6cc8e5b0724334d', 'fields':{'name':str,'history_retention_seconds':int}},
 'neon_branch': {'account':NEON_ACCOUNT, 'revision':'sha256:a57a64671e79eb399fb559fbb0db21b6be75bef09371ab8a06e4c6104442d880', 'fields':{'name':str,'protected':bool}},
 'hindsight_bank': {'account':'hindsight-admin:Alexander', 'revision':'hindsight-bank-config-updates-v1',
  'fields':{'retain_mission':str,'observations_mission':str,'reflect_mission':str,'disposition_skepticism':int,'disposition_literalism':int,'disposition_empathy':int,'retain_extraction_mode':str,'entity_labels':dict,'mcp_enabled_tools':list}},
 'signoz_alert': {'account':SIGNOZ_READER, 'write_account':SIGNOZ_EDITOR, 'revision':'sha256:af38b8a3c771ebacc1e064b031eab8ec27eef7b2714a003c39219b7887c737cb',
  'fields':{'alert':str,'annotations.summary':str,'annotations.description':str,'condition.thresholds':dict,'evaluation':dict}},
 'signoz_dashboard': {'account':SIGNOZ_READER, 'write_account':SIGNOZ_EDITOR, 'revision':'sha256:869847e1e58fb4ae3aa3155fbc382df386c89386d4529b19baa5c958cebc212d',
  'fields':{'name':str,'tags':list,'spec.display':dict,'spec.panels':dict,'spec.layouts':list,'spec.variables':list,'spec.duration':str,'spec.refreshInterval':str,'spec.links':list}},
}


def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()


def check(kind, inputs, evidence, status='passed'):
    return {'kind':kind,'status':status,'runner_id':'registered-native-v1','input_digest':digest(inputs),
            'output_digest':digest(evidence),'evidence':evidence,'checked_at':now(),'limitations':[]}


def receipt(ok, state, evidence, fingerprint=None, checks=None):
    result={'ok':ok,'state':state,'evidence':evidence,'checks':checks or [],'limitations':[]}
    if fingerprint: result['fingerprint']=fingerprint
    return result


def run_process(argv, payload=None, timeout=60):
    try:
        result=subprocess.run(argv,input=json.dumps(payload) if payload is not None else None,
                              capture_output=True,text=True,timeout=timeout,check=False)
        response=json.loads(result.stdout)
        if result.returncode and not (isinstance(response,dict) and response.get('ok') is False): raise RepairError('remote_transport_failed')
        return response
    except RepairError: raise
    except Exception: raise RepairError('remote_transport_uncertain') from None


def unwrap(value):
    if isinstance(value,dict) and value.get('storedInFile') and value.get('outputFilePath'):
        try: value=json.loads(Path(value['outputFilePath']).read_text())
        except Exception: raise RepairError('provider_offloaded_response_unreadable') from None
    if isinstance(value,dict) and value.get('successful') is False: raise RepairError('provider_call_failed')
    if isinstance(value,dict) and 'successful' in value: value=value.get('data',{})
    if isinstance(value,dict) and value.get('isError'): raise RepairError('provider_call_failed')
    if isinstance(value,dict) and 'content' in value:
        blocks=[b.get('text','') for b in value['content'] if b.get('type')=='text']
        if len(blocks)==1:
            try: return unwrap(json.loads(blocks[0]))
            except json.JSONDecodeError: raise RepairError('provider_response_invalid')
    return value


def composio(slug, account, payload):
    # Payload exists before execution, account is explicit on every execution.
    with tempfile.TemporaryDirectory(prefix='repair-call-') as directory:
        path=Path(directory)/'payload.json'
        path.write_text(json.dumps(payload)); path.chmod(0o600)
        return unwrap(run_process(['composio','execute',slug,'--account',account,'-d','@'+str(path)]))


class RemoteTransport:
    def __init__(self, kind, host_id=None):
        self.kind=kind; self.host_id=host_id
        if kind not in ('ssh','orgo'): raise RepairError('remote_transport_unregistered')
        if kind=='orgo' and host_id not in ORGO_HOSTS.values(): raise RepairError('remote_host_unregistered')

    def __call__(self, request):
        source=Path(__file__).with_name('repair_remote_runner.py').read_text()
        if self.kind=='ssh':
            response=run_process(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','agency-mini',
                                  'python3 -c '+shlex.quote(source)], request)
        else:
            # bash's code is solely the reviewed runner; request is JSON stdin.
            code='python3 -c '+shlex.quote(source)+' <<\'REPAIR_JSON\'\n'+json.dumps(request)+'\nREPAIR_JSON'
            response=composio('CUSTOM_ORGO_MCP_ORGO_EXECUTE_BASH',ORGO_ACCOUNT,{'id':self.host_id,'command':code,'timeout':60})
            if isinstance(response,dict) and 'output' in response: response=json.loads(response['output'])
            elif isinstance(response,dict) and 'stdout' in response: response=json.loads(response['stdout'])
        if not isinstance(response,dict) or not response.get('ok'): raise RepairError(response.get('error','remote_response_invalid') if isinstance(response,dict) else 'remote_response_invalid')
        return response['result']


class RemoteFileAdapter:
    version=VERSION
    def __init__(self, kind='ssh', host_id=None, exchange=None):
        self.adapter_id='remote_file_'+kind+('_'+host_id if host_id else '')
        self.kind=kind; self.host_id=host_id
        self.exchange=exchange or RemoteTransport(kind,host_id)

    def discover(self):
        inventory=self.exchange({'action':'inventory'})
        result=[]
        for item in inventory['files']:
            identity={'host':inventory['host'],'transport':self.kind,'host_id':self.host_id,
                      'account':ORGO_ACCOUNT if self.kind=='orgo' else 'agency-mini',
                      'tool_contract_hash':'c462b2c733fbf369e3a5e559d21331f65449b5ac2ea26e6f94ef4f50154195df' if self.kind=='orgo' else 'ssh-json-stdin-v1',
                      'root':item['root'],'relative':item['relative'],'runner_revision':digest(Path(__file__).with_name('repair_remote_runner.py').read_bytes())}
            target={'id':'remote-'+digest(identity)[:24], 'adapter_id':self.adapter_id,
                    'category':'remote_files','owner':inventory['host'],'scope':'remote','identity':identity,
                    'capabilities':['read','prepare','apply','verify','undo'],'observed_at':now(),
                    'evidence':['registered host/root inventory'],'limitations':[],
                    'content_format':'text' if item['relative'].endswith('.md') else 'json'}
            if target['content_format']=='json':
                snap=self.read(target)
                target['allowed_patch_paths']=safe_paths(snap['projection'])
            result.append(target)
        return result

    def request(self,target,action,operation=None):
        identity=target['identity']
        if identity['runner_revision'] != digest(Path(__file__).with_name('repair_remote_runner.py').read_bytes()): raise RepairError('remote_runner_changed')
        request={k:identity[k] for k in ('host','root','relative')}; request['action']=action
        if operation:
            for key in ('patch','candidate','expected_fingerprint','expected_version','expected_mode','inverse'):
                if key in operation: request[key]=operation[key]
        return self.exchange(request)

    def read(self,target):
        result=self.request(target,'read')
        return {'fingerprint':result['fingerprint'],'version':result['version'],'projection':result['projection'],
                'mode':result['mode'],'context_fingerprint':digest(target['identity'])}

    def prepare(self,target,snapshot,proposal):
        op={'action':'remote_file_patch','selector':target['identity'], 'expected_fingerprint':snapshot['fingerprint'],
            'expected_version':snapshot['version'],'expected_mode':snapshot['mode'],'context_fingerprint':snapshot['context_fingerprint'],
            'public_diff':'Update '+target['identity']['relative'],'checks':[]}
        if 'patch' in proposal:
            patch=proposal['patch']
            allowed=target.get('allowed_patch_paths',safe_paths(snapshot['projection']))
            if not patch or any(key not in allowed for key in patch): raise RepairError('remote_patch_unregistered')
            op['patch']=patch
        else: op['candidate']=proposal.get('candidate')
        op['public_diff']=json.dumps({'before':snapshot['projection'],'after_patch':op.get('patch')} if 'patch' in op else {'before':snapshot['projection'],'after':op.get('candidate')},ensure_ascii=False,sort_keys=True)
        self.request(target,'check',op)
        op['checks']=[check('syntax',op,['remote native parser accepted candidate'])]
        return op

    def prepare_bundle(self,operations,targets): return operations
    def preflight(self,target,operation): return self.request(target,'preflight',operation)
    def backup(self,target,operation,backup_dir): return self.request(target,'backup',operation)
    def apply(self,target,operation,backup): return self.request(target,'apply',operation)
    def verify(self,target,operation,result):
        current=self.read(target)
        ok=current['fingerprint']==result.get('fingerprint') and current['mode']==operation['expected_mode']
        return receipt(ok,'byte_verified' if ok else 'blocked',['remote exact readback and mode'],current['fingerprint'],[check('readback',operation,['remote hash/mode readback matched' if ok else 'remote readback mismatch'],'passed' if ok else 'failed')])
    def reconcile(self,target,operation,backup):
        current=self.read(target)
        if operation.get('recovery_phase')=='undo':
            if 'patch' in operation:
                original=all(get_field(current['projection'],k)==v for k,v in backup['inverse'].items())
                candidate=all(get_field(current['projection'],k)=={'present':True,'value':v} for k,v in operation['patch'].items())
            else:
                original=current['projection']==backup['inverse']['text'];candidate=current['projection']==operation.get('candidate')
            return {'outcome':'applied' if original else 'not_applied' if candidate else 'unknown','evidence':['read-only inverse reconciliation']}
        if current['fingerprint']==operation['expected_fingerprint']: return {'outcome':'not_applied','evidence':['original fingerprint remains']}
        good=all(get_field(current['projection'],k)=={'present':True,'value':v} for k,v in operation.get('patch',{}).items()) if 'patch' in operation else current['projection']==operation.get('candidate')
        return {'outcome':'applied' if good else 'unknown','result':{'fingerprint':current['fingerprint']},'evidence':['read-only remote reconciliation']}
    def undo(self,target,operation,backup,applied):
        try:result=self.request(target,'undo',dict(operation,inverse=backup['inverse']))
        except RepairError as error:
            if error.code=='remote_undo_conflict':return receipt(False,'blocked',['Changed field no longer matches recorded applied value; no inverse attempted.'])
            raise
        return receipt(True,'undone',['conditional changed-field inverse; unrelated fields preserved'],result['fingerprint'])


def safe_paths(value,prefix=''):
    result=[]
    if isinstance(value,dict):
        for key,item in value.items():
            path=prefix+'.'+key if prefix else key
            if sensitive(key) or item=='[REDACTED]': continue
            if isinstance(item,dict): result.extend(safe_paths(item,path))
            else: result.append(path)
    return result


class ProviderAdapter:
    version=VERSION
    def __init__(self,provider,exchange=None,registrations=None):
        self.provider=provider; self.spec=PROVIDERS[provider]; self.adapter_id='provider_'+provider
        self.exchange=exchange or NativeProviderExchange(provider)
        self.registrations=registrations

    def discover(self):
        registrations=self.registrations if self.registrations is not None else self.exchange('discover',None)
        targets=[]
        for registration in registrations:
            identity={**registration['identity'],'provider':self.provider,'schema_revision':self.spec['revision'],
                      'write_account':self.spec.get('write_account',self.spec['account'])}
            if identity.get('account') != self.spec['account']: raise RepairError('provider_account_mismatch')
            target={'id':'provider-'+digest({'provider':self.provider,'identity':identity})[:24],'adapter_id':self.adapter_id,'category':self.provider,
                    'owner':identity.get('company_id') or identity.get('project_id') or identity['object_id'],
                    'scope':'remote','identity':identity,'capabilities':['read','prepare','apply','verify','undo'],
                    'observed_at':now(),'evidence':['native LIST metadata identifies registered account and object; configuration not read'],
                    'limitations':['Discovery proves listed identity only; proposal and application require fresh native configuration reads.'],
                    'content_format':'json','allowed_patch_paths':list(self.spec['fields'])}
            targets.append(target)
        return targets

    def native_read(self,target):
        result=self.exchange('read',target)
        if result.get('identity') != target['identity']: raise RepairError('provider_identity_mismatch')
        if result.get('schema_revision') != self.spec['revision']: raise RepairError('provider_schema_changed')
        return result

    def read(self,target):
        native=self.native_read(target)
        # Only declared native fields reach the model. Raw provider objects stay in transport memory.
        projection={}
        for key in self.spec['fields']:
            item=get_field(native['config'],key)
            if item['present']: set_field(projection,key,item)
        return {'fingerprint':digest({'config':redact(native['config']),'version':native.get('version')}),
                'version':str(native.get('version','')), 'projection':redact(projection),
                'context_fingerprint':digest({'identity':target['identity'],'schema':self.spec['revision']})}

    def validate_patch(self,patch):
        if not isinstance(patch,dict) or not patch: raise RepairError('provider_patch_empty')
        for key,value in patch.items():
            if key not in self.spec['fields'] or not isinstance(value,self.spec['fields'][key]): raise RepairError('provider_patch_invalid')
            if isinstance(value,bool) and self.spec['fields'][key] is not bool: raise RepairError('provider_patch_invalid')
            if key=='name' and (not value or len(value)>256): raise RepairError('provider_patch_invalid')
            if key=='history_retention_seconds' and not 0<=value<=2592000: raise RepairError('provider_patch_invalid')
            if key.startswith('disposition_') and not 1<=value<=5: raise RepairError('provider_patch_invalid')
            if redact(value)!=value or '[REDACTED]' in json.dumps(value): raise RepairError('provider_secret_patch')

    def prepare(self,target,snapshot,proposal):
        patch=proposal.get('patch'); self.validate_patch(patch)
        inverse={key:get_field(snapshot['projection'],key) for key in patch}
        if any(not item['present'] for item in inverse.values()): raise RepairError('provider_inverse_missing')
        operation={'action':'native_config_patch','selector':target['identity'],'patch':patch,
                   'expected_fingerprint':snapshot['fingerprint'],'expected_version':snapshot['version'],
                   'context_fingerprint':snapshot['context_fingerprint'],'schema_revision':self.spec['revision'],
                   'inverse':inverse,'public_diff':json.dumps({'before':{k:get_field(snapshot['projection'],k) for k in patch},'after':patch},ensure_ascii=False,sort_keys=True),'checks':[]}
        dry=self.exchange('dry_run',target,{'patch':patch,'schema_revision':self.spec['revision']})
        if not dry.get('ok') or dry.get('schema_revision')!=self.spec['revision']: raise RepairError('provider_dry_run_failed')
        evidence=['installed native validator accepted candidate'] if self.provider=='paperclip_agent' else ['published native field contract shape accepted; no provider mutation']
        operation['checks']=[check('native_dry_run' if self.provider=='paperclip_agent' else 'syntax',patch,evidence)]
        if self.provider!='paperclip_agent':operation['checks'][0]['limitations']=['Provider has no mutation-free acceptance endpoint on this registered route; exact effect requires native GET readback after approval.']
        return operation
    def prepare_bundle(self,operations,targets): return operations
    def preflight(self,target,operation):
        current=self.read(target)
        if any(current[key]!=operation.get('expected_'+key) for key in ('fingerprint','version')): raise RepairError('provider_stale')
        if current['context_fingerprint']!=operation['context_fingerprint']: raise RepairError('provider_context_changed')
        self.validate_patch(operation['patch'])
        return {'ok':True,'evidence':['account, identity, schema and native version match']}
    def backup(self,target,operation,backup_dir):
        self.preflight(target,operation)
        backup={'inverse':operation['inverse'],'fingerprint':operation['expected_fingerprint'],'version':operation['expected_version']}
        if self.provider=='paperclip_agent' and isinstance(self.exchange,NativeProviderExchange):
            backup.update(self.exchange('backup',target))
        return backup
    def apply(self,target,operation,backup):
        self.preflight(target,operation)
        return self.exchange('write',target,{'patch':operation['patch'],'expected_version':operation['expected_version'], 'expected_fingerprint':operation['expected_fingerprint']})
    def verify(self,target,operation,result):
        current=self.read(target)
        ok=all(get_field(current['projection'],key)=={'present':True,'value':value} for key,value in operation['patch'].items())
        return receipt(ok,'effective' if ok else 'blocked',['native GET confirms requested fields'],current['fingerprint'],[check('readback',operation['patch'],['native GET changed fields matched' if ok else 'native GET changed fields mismatch'],'passed' if ok else 'failed')])
    def reconcile(self,target,operation,backup):
        current=self.read(target)
        if operation.get('recovery_phase')=='undo':
            original=all(get_field(current['projection'],key)==item for key,item in backup['inverse'].items())
            candidate=all(get_field(current['projection'],key)=={'present':True,'value':value} for key,value in operation['patch'].items())
            return {'outcome':'applied' if original else 'not_applied' if candidate else 'unknown','evidence':['read-only inverse reconciliation']}
        if all(get_field(current['projection'],key)=={'present':True,'value':value} for key,value in operation['patch'].items()):
            return {'outcome':'applied','result':{'version':current['version']},'evidence':['native GET matches changed fields; no repeated write']}
        if all(get_field(current['projection'],key)==item for key,item in backup['inverse'].items()): return {'outcome':'not_applied','evidence':['native GET matches original fields']}
        return {'outcome':'unknown','evidence':['native GET does not establish write outcome']}
    def undo(self,target,operation,backup,applied):
        current=self.read(target)
        if not all(get_field(current['projection'],key)=={'present':True,'value':value} for key,value in operation['patch'].items()):return receipt(False,'blocked',['Changed field no longer matches recorded applied value; no inverse attempted.'])
        patch={key:item['value'] for key,item in backup['inverse'].items() if item['present']}
        if self.provider=='paperclip_agent' and backup.get('revision_id') and str(applied.get('version'))==current['version']:
            self.exchange('rollback',target,{'revision_id':backup['revision_id'],'expected_version':current['version']})
        else:
            self.exchange('write',target,{'patch':patch,'expected_version':current['version'],'expected_fingerprint':current['fingerprint']})
        restored=self.read(target)
        ok=all(get_field(restored['projection'],key)==item for key,item in backup['inverse'].items())
        return receipt(ok,'undone' if ok else 'blocked',['conditional native inverse; unrelated settings preserved'],restored['fingerprint'])

# Fixed mini-local API program. The credential is acquired and used on the mini;
# only declared projections and revision IDs leave it. No URL/path/command input.
PAPERCLIP_PROGRAM = r'''
import hashlib,json,subprocess,sys,urllib.request
from pathlib import Path
r=json.load(sys.stdin)
company='22eb3ea5-8bb2-4768-a97c-de624fac5699'
base=Path.home()/'Documents/Paperclip/app/node_modules/@paperclipai/shared/dist/validators/agent.js'
schema_hash=hashlib.sha256(base.read_bytes()).hexdigest()
token=json.loads((Path.home()/'.paperclip/auth.json').read_text())['credentials']['https://paperclip.increaseroas.com']['token']
def api(method,path,body=None):
 q=urllib.request.Request('http://127.0.0.1:3100/api'+path,method=method,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(q,timeout=30) as x:return json.load(x)
def safe(v):
 if isinstance(v,dict):return {k:('[REDACTED]' if any(s in k.lower() for s in ('secret','token','password','credential','apikey','api_key','authorization')) else safe(i)) for k,i in v.items()}
 if isinstance(v,list):return [safe(i) for i in v]
 return v
try:
 action=r['action']
 if action=='discover':
  rows=api('GET','/companies/'+company+'/agents');rows=rows if isinstance(rows,list) else rows.get('agents',[])
  out={'agents':[{'id':a['id'],'companyId':a['companyId']} for a in rows],'schema_hash':schema_hash}
 else:
  aid=r['object_id']
  import uuid
  uuid.UUID(aid)
  path='/agents/'+aid
  obj=api('GET',path)
  if obj['companyId']!=company:raise ValueError('identity')
  body=r.get('body')
  if body is not None:
   def merge(old,patch):
    if isinstance(old,dict) and isinstance(patch,dict):return {**old,**{k:merge(old.get(k),v) for k,v in patch.items()}}
    return patch
   body={k:merge(obj.get(k),v) if isinstance(v,dict) else v for k,v in body.items()}
  if action=='dry_run':
   code="import{updateAgentSchema}from "+json.dumps(base.as_uri())+";let s='';for await(const c of process.stdin)s+=c;const r=updateAgentSchema.safeParse(JSON.parse(s));process.stdout.write(JSON.stringify({ok:r.success}));"
   p=subprocess.run(['node','--input-type=module','-e',code],input=json.dumps(body),capture_output=True,text=True,check=True)
   out=json.loads(p.stdout);out['schema_hash']=schema_hash
  elif action=='backup':
   revisions=api('GET',path+'/config-revisions');revisions=revisions if isinstance(revisions,list) else revisions.get('revisions',[])
   out={'revision_id':revisions[0]['id'] if revisions else None}
  elif action=='rollback':
   if obj.get('updatedAt')!=r['expected_version']:raise ValueError('stale')
   revision=r['revision_id'];uuid.UUID(revision)
   result=api('POST',path+'/config-revisions/'+revision+'/rollback')
   out={'version':result.get('updatedAt'),'schema_hash':schema_hash}
  elif action=='read':out={'config':safe(obj),'version':obj.get('updatedAt'),'schema_hash':schema_hash}
  elif action=='write':
   if obj.get('updatedAt')!=r['expected_version']:raise ValueError('stale')
   result=api('PATCH',path,body);out={'version':result.get('updatedAt'),'schema_hash':schema_hash}
  else:raise ValueError('action')
 print(json.dumps({'ok':True,'result':out}))
except Exception:print(json.dumps({'ok':False,'error':'paperclip_native_operation_failed'}));sys.exit(1)
'''


def collection(value,*names):
    value=unwrap(value)
    if isinstance(value,list): return value
    if isinstance(value,dict):
        for name in names:
            if isinstance(value.get(name),list): return value[name]
        if isinstance(value.get('data'),(dict,list)): return collection(value['data'],*names)
    raise RepairError('provider_collection_invalid')


class NativeProviderExchange:
    """Concrete registered native routes; no caller may supply an endpoint/tool."""
    def __init__(self,provider):
        self.provider=provider; self.spec=PROVIDERS[provider]
        self._hindsight_module=None;self._hindsight_key=None;self._credential_lock=threading.Lock();self._known_banks=set()

    def paperclip(self,action,object_id=None,**payload):
        response=run_process(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','agency-mini',
                              'python3 -c '+shlex.quote(PAPERCLIP_PROGRAM)],dict(payload,action=action,object_id=object_id))
        if not response.get('ok'): raise RepairError('paperclip_native_failed')
        return response['result']

    def hindsight(self,method,bank=None,body=None):
        # Existing documented helper owns admin key acquisition. It stays in memory.
        try:
            with self._credential_lock:
                if self._hindsight_module is None:
                    helper=Path.home()/'Projects/stack-config/scripts/hindsight_bank_config.py'
                    module_spec=importlib.util.spec_from_file_location('registered_hindsight_config',helper)
                    module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
                    self._hindsight_module=module;self._hindsight_key=module.admin_key()
            path='/banks' if bank is None else '/banks/'+urllib.parse.quote(bank,safe='')+'/config'
            _,value=self._hindsight_module.call(self._hindsight_key,method,path,body)
            return value
        except BaseException: raise RepairError('hindsight_native_failed') from None

    def __call__(self,action,target,payload=None):
        payload=payload or {}
        if action=='discover': return self.discover()
        identity=target['identity']; object_id=identity['object_id']
        if identity['account']!=self.spec['account']: raise RepairError('provider_account_mismatch')
        if action=='dry_run':
            ProviderAdapter(self.provider,exchange=self).validate_patch(payload['patch'])
            if self.provider=='paperclip_agent':
                body={}
                for key,value in payload['patch'].items(): set_field(body,key,{'present':True,'value':value})
                result=self.paperclip('dry_run',object_id,body=body)
                if not result.get('ok') or result['schema_hash']!=identity['schema_hash']: raise RepairError('provider_schema_changed')
            elif self.provider.startswith('signoz_'):
                raw,_=self.get_native(identity)
                candidate=copy.deepcopy(raw)
                for key,value in payload['patch'].items():set_field(candidate,key,{'present':True,'value':value})
                keys=('schemaVersion','version','alert','alertType','condition','evaluation','annotations','notificationSettings','labels','disabled','ruleType','description','source','preferredChannels','evalWindow','frequency') if self.provider=='signoz_alert' else ('schemaVersion','name','tags','spec','image')
                body={k:v for k,v in candidate.items() if k in keys}
                if redact(body)!=body:raise RepairError('provider_secret_payload_requires_native_preservation')
            return {'ok':True,'schema_revision':self.spec['revision']}
        if action in ('backup','rollback') and self.provider=='paperclip_agent':
            return self.paperclip(action,object_id,**payload)
        if action=='read':
            obj,version=self.get_native(identity)
            return {'identity':identity,'config':obj,'version':version,'schema_revision':self.spec['revision']}
        if action!='write': raise RepairError('provider_action_unregistered')
        # Fresh GET and changed-version rejection happen immediately before one write.
        obj,version=self.get_native(identity)
        fingerprint=digest({'config':redact(obj),'version':version})
        if str(version)!=str(payload['expected_version']) or fingerprint!=payload['expected_fingerprint']: raise RepairError('provider_stale')
        patch=payload['patch']; ProviderAdapter(self.provider,exchange=self).validate_patch(patch)
        if self.provider=='paperclip_agent':
            body={}
            for key,value in patch.items(): set_field(body,key,{'present':True,'value':value})
            return self.paperclip('write',object_id,body=body,expected_version=version)
        if self.provider=='hindsight_bank':
            self.hindsight('PATCH',object_id,{'updates':patch});return {'written':True}
        if self.provider.startswith('neon_'):
            kind=self.provider.split('_')[1]
            args={'project_id':identity['project_id'],kind:patch}
            if kind=='branch':args['branch_id']=object_id
            composio('CUSTOM_NEON_MCP_UPDATE_'+kind.upper(),NEON_ACCOUNT,args)
            return {'written':True}
        # SigNoz update tools are full replacement. Merge in memory only; never
        # serialize unrelated credentials into backups or model projections.
        candidate=copy.deepcopy(obj)
        for key,value in patch.items(): set_field(candidate,key,{'present':True,'value':value})
        if self.provider=='signoz_alert':
            args={'ruleId':object_id,**{k:v for k,v in candidate.items() if k in ('schemaVersion','version','alert','alertType','condition','evaluation','annotations','notificationSettings','labels','disabled','ruleType','description','source','preferredChannels','evalWindow','frequency')}}; slug='CUSTOM_SIGNOZ_MCP_SIGNOZ_UPDATE_ALERT'
        else:
            args={'id':object_id,**{k:v for k,v in candidate.items() if k in ('schemaVersion','name','tags','spec','image')}};slug='CUSTOM_SIGNOZ_MCP_SIGNOZ_UPDATE_DASHBOARD'
        if redact(args)!=args:raise RepairError('provider_secret_payload_requires_native_preservation')
        composio(slug,SIGNOZ_EDITOR,args)
        return {'written':True}

    def get_native(self,identity):
        oid=identity['object_id']
        if self.provider=='paperclip_agent':
            value=self.paperclip('read',oid)
            if value['schema_hash']!=identity['schema_hash']:raise RepairError('provider_schema_changed')
            return value['config'],value['version']
        if self.provider=='hindsight_bank':
            if not self._known_banks:
                banks=collection(self.hindsight('GET'),'banks')
                self._known_banks={b.get('bank_id') or b.get('id') or b.get('name') for b in banks}
            if oid not in self._known_banks:raise RepairError('provider_object_missing')
            value=self.hindsight('GET',oid)
            if value.get('bank_id')!=oid:raise RepairError('provider_identity_mismatch')
            config={**(value.get('config') or {}),**(value.get('overrides') or {})}
            return config,digest(redact(config))
        if self.provider.startswith('neon_'):
            kind=self.provider.split('_')[1]
            args={'project_id':identity['project_id']}
            if kind=='branch':args['branch_id']=oid
            value=composio('CUSTOM_NEON_MCP_DESCRIBE_PROJECT' if kind=='project' else 'CUSTOM_NEON_MCP_GET_BRANCH',NEON_ACCOUNT,args)
            obj=value.get(kind,value) if isinstance(value,dict) else value
            if not isinstance(obj,dict) or obj.get('id')!=oid:raise RepairError('provider_identity_mismatch')
            return obj,obj.get('updated_at') or digest(redact(obj))
        if self.provider=='signoz_alert':
            value=composio('CUSTOM_SIGNOZ_MCP_SIGNOZ_GET_ALERT',SIGNOZ_READER,{'ruleId':oid})
        else:value=composio('CUSTOM_SIGNOZ_MCP_SIGNOZ_GET_DASHBOARD',SIGNOZ_READER,{'id':oid})
        obj=value.get('data',value) if isinstance(value,dict) else value
        if not isinstance(obj,dict):raise RepairError('provider_response_invalid')
        if identity.get('native_schema_version') is not None and obj.get('schemaVersion')!=identity['native_schema_version']:raise RepairError('provider_schema_changed')
        if identity.get('native_api_version') is not None and obj.get('version')!=identity['native_api_version']:raise RepairError('provider_schema_changed')
        native_id=obj.get('id') or obj.get('uuid') or obj.get('ruleId')
        if native_id!=oid:raise RepairError('provider_identity_mismatch')
        return obj,obj.get('updatedAt') or obj.get('updated_at') or digest(redact(obj))

    def discover(self):
        rows=[];metadata={}
        if self.provider=='paperclip_agent':
            value=self.paperclip('discover');rows=value['agents'];metadata={'company_id':COMPANY,'schema_hash':value['schema_hash']}
        elif self.provider=='hindsight_bank':
            rows=collection(self.hindsight('GET'),'banks')
            self._known_banks={r.get('bank_id') or r.get('id') or r.get('name') for r in rows}
        elif self.provider=='neon_project':
            rows=collection(composio('CUSTOM_NEON_MCP_LIST_PROJECTS',NEON_ACCOUNT,{'org_id':'org-cold-paper-48054737'}),'projects')
        elif self.provider=='neon_branch':
            projects=collection(composio('CUSTOM_NEON_MCP_LIST_PROJECTS',NEON_ACCOUNT,{'org_id':'org-cold-paper-48054737'}),'projects')
            for project in projects:
                for branch in collection(composio('CUSTOM_NEON_MCP_LIST_BRANCHES',NEON_ACCOUNT,{'project_id':project['id']}),'branches'):
                    rows.append(dict(branch,project_id=project['id']))
        elif self.provider=='signoz_alert':rows=collection(composio('CUSTOM_SIGNOZ_MCP_SIGNOZ_LIST_ALERT_RULES',SIGNOZ_READER,{}),'rules','items')
        elif self.provider=='signoz_dashboard':rows=collection(composio('CUSTOM_SIGNOZ_MCP_SIGNOZ_LIST_DASHBOARDS',SIGNOZ_READER,{}),'dashboards','items')
        result=[]
        for row in rows:
            oid=row.get('id') or row.get('bank_id') or row.get('uuid') or row.get('ruleId')
            if not isinstance(oid,str):raise RepairError('provider_identity_missing')
            identity={'account':self.spec['account'],'object_id':oid,**metadata}
            if row.get('schemaVersion') is not None:identity['native_schema_version']=row['schemaVersion']
            if isinstance(row.get('version'),str):identity['native_api_version']=row['version']
            if self.provider=='neon_project':identity['project_id']=oid
            elif self.provider=='neon_branch':identity['project_id']=row['project_id']
            result.append({'object_id':oid,'identity':identity})
        return result


def register_adapters(registry):
    for adapter in [RemoteFileAdapter('ssh'),*[RemoteFileAdapter('orgo',host_id) for host_id in ORGO_HOSTS.values()],
                    *[ProviderAdapter(provider) for provider in PROVIDERS]]:
        registry.register(adapter)
