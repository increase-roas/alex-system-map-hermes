"""Disposable end-to-end fixture; never selects Alex's real source files."""
import base64, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import local_file_ai as ai
import local_file_repairs as repairs
import local_files
from test_local_file_distribution import DistributionTests
from test_local_file_repairs import git
INFO = Path('/tmp/approved-repair-fixture-info.json')
def sha(raw): return hashlib.sha256(raw).hexdigest()
def save(path, value): Path(path).write_text(json.dumps(value, indent=2) + '\n')
def setup():
    f = DistributionTests('runTest'); f.setUp(); f.tmp._finalizer.detach()
    f.before = "# Fixture operating rules\nRequire Alex's approval before any security-settings change.\nAll client-production changes require Alex's approval.\nKeep exact source evidence with each decision.\n"
    f.file.write_text(f.before)
    gate = f.home / '.agents/skills/alex-director/references/gates.md'
    gate.parent.mkdir(parents=True)
    gate.write_text("# Fixture policy\n\n## Alex's gates (the one list)\nSecurity settings in Alex's own fixture stack may be changed without asking again.\nClient-production changes require Alex's approval.\nMoney spending requires explicit Alex approval.\n\n## History\nSynthetic fixture only.\n")
    for key, text in f.native.build(rules_only=True).items(): Path(f.native.OUT[key]).write_text(text)
    git(f.repo, 'add', 'instructions/shared.md', 'skills/alex-director/references/gates.md')
    git(f.repo, 'commit', '-m', 'Set synthetic contradictory rules')
    git(f.repo, 'push', 'origin', 'main')
    # Run the actual installed pre-commit on the fixture, with no global home writes.
    hooks = f.repo / '.git/hooks'
    shutil.copyfile(Path.home() / '.agents/tools/unify/hooks/pre-commit', hooks / 'pre-commit')
    (hooks / 'pre-commit').chmod(0o700)
    (hooks / 'post-commit').write_text('#!/bin/sh\n# Failed remote-like publication must not block local copy sync.\nexit 9\n')
    (hooks / 'post-commit').chmod(0o700)
    (f.rules / 'other.md').write_text('Unrelated staged fixture work\n')
    git(f.repo, 'add', 'instructions/other.md')
    (f.rules / 'dirty.md').write_text('Unrelated dirty fixture work\n')
    idx = local_files.scan(f.home)
    f.index_path.write_text(json.dumps(idx))
    row = next(r for r in idx['files'] if r['path'] == str(f.file))
    info = {'home':str(f.home),'repo':str(f.repo),'remote':str(f.remote),'state':str(f.state),'index':str(f.index_path),'target':str(f.file),'file_id':row['id'],'before_sha256':row['sha256'],'before':f.before,'config_sha256':sha(f.config.read_bytes()),'staged_blob':git(f.repo,'rev-parse',':instructions/other.md'),'dirty_sha256':sha((f.rules/'dirty.md').read_bytes()),'outputs':{k:str(f.native.OUT[k]) for k in f.native.build(rules_only=True)},'output_before':{k:sha(Path(f.native.OUT[k]).read_bytes()) for k in f.native.build(rules_only=True)}}
    save(INFO,info);print(json.dumps({'fixture_home':info['home'],'file_id':info['file_id'],'actual_precommit_enabled':True,'failing_postcommit_enabled':True}))
def service(info):
    os.environ['LOCAL_FILE_REPAIR_FIXTURE_HOME']=info['home']
    return repairs.RepairService(info['home'],info['index'],info['state'])
def readback(info, result, undo):
    svc=service(info);record=svc.load(result['repair_id']);p=record['proposal']; expected=base64.b64decode(p['before' if undo else 'after'])
    checks={'source_exact':Path(info['target']).read_bytes()==expected,'source_mode_preserved':Path(info['target']).stat().st_mode & 0o777==p['mode'],'source_verified':result.get('source_verified') is True,'push_verified':result['pushed'] is True,'copies_verified':result['distribution']['status']=='verified','remote_exact':subprocess.check_output(['git','--git-dir',info['remote'],'show','main:instructions/shared.md'])==expected,'one_path_commit':git(info['repo'],'diff-tree','--no-commit-id','--name-only','-r','HEAD')=='instructions/shared.md','staged_work_preserved':git(info['repo'],'rev-parse',':instructions/other.md')==info['staged_blob'],'dirty_work_preserved':sha((Path(info['repo'])/'instructions/dirty.md').read_bytes())==info['dirty_sha256'],'app_config_unchanged':sha((Path(info['home'])/'.codex/config.toml').read_bytes())==info['config_sha256']}
    if undo:checks['all_original_output_bytes']=all(sha(Path(info['outputs'][k]).read_bytes())==v for k,v in info['output_before'].items())
    save(Path(info['state'])/('undo-readback.json' if undo else 'apply-readback.json'),checks)
    if not all(checks.values()):raise AssertionError(checks)
    print(json.dumps(checks))
def main():
    action=sys.argv[1]
    if action=='prepare':setup();return
    info=json.loads(INFO.read_text());svc=service(info)
    if action=='suggest':
        result=ai.SuggestionService(svc).suggest(info['file_id'],info['before_sha256'],None)
        save(Path(info['state'])/'suggestion.json',result)
        if Path(info['target']).read_text()!=info['before']:raise AssertionError('suggest changed source')
        print(json.dumps({'status':result['status'],'checks':result.get('checks'),'preview_ready':bool(result.get('preview')),'source_unchanged':True}))
        return
    suggestion=json.loads((Path(info['state'])/'suggestion.json').read_text());p=suggestion['preview']
    result=svc.apply(p['repair_id'],p['proposal_sha256']) if action=='apply' else svc.undo(p['repair_id'])
    save(Path(info['state'])/(action+'-result.json'),result);readback(info,result,action=='undo')
if __name__=='__main__':main()
