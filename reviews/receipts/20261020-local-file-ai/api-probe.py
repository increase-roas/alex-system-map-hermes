from pathlib import Path
import json,hashlib,urllib.request,urllib.error,base64
out=Path(__file__).parent
f=json.loads((out/'fixture.json').read_text());state=Path(f['state']);target=Path(f['target'])
token=json.loads((state/'local-token.json').read_text())['token']
base={'action':'suggest','file_id':f['file_id'],'expected_sha256':f['before_sha256'],'finding_id':f['finding_id']}
def post(body,auth=True,origin=None):
 headers={'Content-Type':'application/json'}
 if auth:headers['X-Local-Token']=token
 if origin:headers['Origin']=origin
 req=urllib.request.Request('http://127.0.0.1:3202/api/local-files/repair',data=json.dumps(body).encode(),headers=headers,method='POST')
 try:
  with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
results={}
for name,body,auth,origin,want in [
 ('missing_auth',base,False,None,401),('nonlocal_origin',base,True,'https://example.invalid',403),
 ('client_prompt_refused',dict(base,prompt='fixture prompt'),True,None,400),('client_path_refused',dict(base,path='/private/tmp/anything'),True,None,400),
 ('client_content_refused',dict(base,source='fixture source'),True,None,400),('unknown_finding',dict(base,finding_id='0'*24),True,None,400),
 ('stale_target',dict(base,expected_sha256='0'*64),True,None,409),('missing_fingerprint',{'action':'apply','repair_id':'0'*32},True,None,400),
]:
 status,response=post(body,auth,origin);assert status==want,(name,status,response)
 results[name]={'status':status,'code':response.get('code'),'source_unchanged':hashlib.sha256(target.read_bytes()).hexdigest()==f['before_sha256']}
records=list((state/'local-file-repairs').glob('*.json'));assert len(records)==1,len(records)
frozen=json.loads(records[0].read_text());p=frozen['proposal']
assert hashlib.sha256(target.read_bytes()).hexdigest()==f['before_sha256']
expected=base64.b64decode(p['before']).replace(b'Always send customer reports without approval.',b'Never send customer reports without approval.')
assert base64.b64decode(p['after'])==expected
peer=target.parent/'current-policy.md';before=peer.read_bytes()
try:
 peer.write_bytes(before+b'Fixture authority changed after preview.\n')
 status,response=post({'action':'apply','repair_id':p['repair_id'],'proposal_sha256':frozen['proposal_sha256']})
 assert (status,response.get('code'))==(409,'stale_context'),(status,response)
 assert hashlib.sha256(target.read_bytes()).hexdigest()==f['before_sha256']
 assert not (Path(f['home'])/'Backups/local-file-repairs').exists()
 results['peer_changed_after_preview']={'status':status,'code':response['code'],'source_unchanged':True,'no_backup_or_write_started':True}
finally:peer.write_bytes(before)
results['model_proposal_quality']={'minimal_exact_expected_edit':True,'bound_files':len(p['context_fingerprints']),'source_unchanged_before_explicit_approval':True,'repair_id':p['repair_id'],'proposal_sha256':frozen['proposal_sha256']}
(out/'api-negatives.json').write_text(json.dumps(results,indent=2)+'\n')
(out/'frozen-synthetic-proposal.json').write_text(json.dumps(frozen,indent=2)+'\n')
print(json.dumps(results,indent=2))
