from pathlib import Path
import json,urllib.request,urllib.error,hashlib,subprocess,os
OUT=Path(__file__).parent
F=json.loads((OUT/'fixture.json').read_text()); HOME=Path(F['home']); BASE='http://127.0.0.1:3203'; records=[]
def request(path,body=None,headers=None,raw=None):
    h=dict(headers or {}); data=raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if data is not None:h.setdefault('Content-Type','application/json')
    try:
        r=urllib.request.urlopen(urllib.request.Request(BASE+path,data=data,headers=h),timeout=60);code=r.status;val=json.load(r)
    except urllib.error.HTTPError as e:
        code=e.code
        try:val=json.load(e)
        except Exception:val={}
    return code,val
_,health=request('/api/health'); TOKEN=health['token']; AUTH={'X-Local-Token':TOKEN}
def call(name,body=None,path='/api/local-files/repair',headers=None,expected=None,raw=None):
    code,val=request(path,body,AUTH if headers is None else headers,raw)
    rec={'check':name,'status':code,'state':val.get('state'),'error':val.get('error'),'editable':val.get('editable')};records.append(rec)
    if expected is not None:assert code in expected,(name,code,val)
    return val
_,idx=request('/api/local-files',{},AUTH); IDS={r['path']:r['id'] for r in idx['files']}
TARGET=Path(F['target']); ID=IDS[str(TARGET)]; BEFORE=TARGET.read_bytes(); NEW='Require explicit approval before customer messages.\nAlways keep source evidence readable.\n'
def preview(new=NEW,sha=None):return call('preview_valid',{'action':'preview','file_id':ID,'expected_sha256':sha or hashlib.sha256(TARGET.read_bytes()).hexdigest(),'new_content':new},expected={200})
def git(args,cwd=None):
    r=subprocess.run(['git',*args],cwd=cwd or F['repo'],capture_output=True,text=True);assert r.returncode==0,(args,r.stderr);return r.stdout.strip()
def unchanged():assert TARGET.read_bytes()==BEFORE
if __name__=='__main__':
    for suffix in ['generated.md','alias.md','sensitive-rule.md','unsupported.sh']:
        val=call('source_refusal_'+suffix,path='/api/local-files/repair?id='+IDS[str(TARGET.parent/suffix)],expected={200});assert val['editable'] is False
    val=call('generated_codex_owner',path='/api/local-files/repair?id='+IDS[str(HOME/'.codex/AGENTS.md')],expected={200});assert val['editable'] is False and ID in val['source_file_ids']
    skill=HOME/'.agents/skills/managed/SKILL.md'; val=call('source_refusal_managed',path='/api/local-files/repair?id='+IDS[str(skill)],expected={200});assert val['editable'] is False
    call('no_token',{'action':'preview'},headers={},expected={401});call('wrong_token',{'action':'preview'},headers={'X-Local-Token':'fixture-bad'},expected={401});call('remote_host',path='/api/local-files/repair?id='+ID,headers={'Host':'example.com'},expected={403});call('cross_site',path='/api/local-files/repair?id='+ID,headers={'Origin':'https://example.com','Sec-Fetch-Site':'cross-site'},expected={403})
    call('malformed',raw=b'{',expected={400});call('arbitrary_path',{'action':'preview','path':'/etc/passwd'},expected={400});call('oversized_body',raw=b'x'*196609,expected={400,413});call('new_secret',{'action':'preview','file_id':ID,'expected_sha256':F['before_sha256'],'new_content':'api_key=fixture-secret'},expected={400,409});call('stale_hash',{'action':'preview','file_id':ID,'expected_sha256':'0'*64,'new_content':NEW},expected={409});unchanged()
    p=preview();call('wrong_proposal_fingerprint',{'action':'apply','repair_id':p['repair_id'],'proposal_sha256':'0'*64},expected={409,400});unchanged()
    TARGET.write_text('Concurrent fixture edit.\n');call('stale_apply',{'action':'apply','repair_id':p['repair_id'],'proposal_sha256':p['proposal_sha256']},expected={409});assert TARGET.read_text()=='Concurrent fixture edit.\n';TARGET.write_bytes(BEFORE)
    p=preview(); TARGET.unlink(); TARGET.symlink_to(TARGET.parent/'beta.md');call('link_swap_after_preview',{'action':'apply','repair_id':p['repair_id'],'proposal_sha256':p['proposal_sha256']},expected={409,400});assert TARGET.is_symlink();TARGET.unlink();TARGET.write_bytes(BEFORE);os.chmod(TARGET,int(F['before_mode'],8))
    p=preview();head=git(['rev-parse','HEAD']);tree=git(['rev-parse','HEAD^{tree}']);other=git(['-c','user.name=Repair acceptance fixture','-c','user.email=fixture@example.invalid','--git-dir',F['origin'],'commit-tree',tree,'-p',head,'-m','Fixture remote divergence']);git(['--git-dir',F['origin'],'update-ref','refs/heads/main',other]);call('remote_ref_diverged',{'action':'apply','repair_id':p['repair_id'],'proposal_sha256':p['proposal_sha256']},expected={409,400});unchanged();git(['--git-dir',F['origin'],'update-ref','refs/heads/main',head])
    assert git(['status','--porcelain'])==F['baseline_status'];assert git(['rev-parse',':instructions/unrelated-staged.md'])==F['staged_blob'];assert hashlib.sha256((TARGET.parent/'unrelated-dirty.md').read_bytes()).hexdigest()==F['dirty_sha256']
    (OUT/'api-negatives.json').write_text(json.dumps({'checks':records,'source_unchanged':True,'unrelated_work_preserved':True},indent=2)+'\n');print(json.dumps({'checks':len(records),'source_unchanged':True,'unrelated_work_preserved':True}))
