from pathlib import Path
import json,hashlib,subprocess,base64,sys
out=Path(__file__).parent;f=json.loads((out/'fixture.json').read_text());repo=Path(f['repo']);state=Path(f['state'])
record=json.loads(next((state/'local-file-repairs').glob('*.json')).read_text());p=record['proposal'];target=Path(f['target'])
def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL)
def digest(raw):return hashlib.sha256(raw).hexdigest()
undo=sys.argv[1]=='undo'; expected=base64.b64decode(p['before' if undo else 'after']);head=git('rev-parse','HEAD').decode().strip()
checks={'phase':record['phase'],'target_exact_expected_bytes':target.read_bytes()==expected,'target_mode_preserved':oct(target.stat().st_mode&0o777)==f['before_mode'],'backup_exact_preimage':Path(record['backup_path']).read_bytes()==base64.b64decode(p['before']),'local_commit_exact_expected_bytes':git('show','HEAD:instructions/alpha.md')==expected,'remote_commit_exact_expected_bytes':subprocess.check_output(['git','--git-dir',f['remote'],'show','main:instructions/alpha.md'])==expected,'one_path_commit':git('diff-tree','--no-commit-id','--name-only','-r','HEAD').decode().strip()=='instructions/alpha.md','staged_blob_preserved':git('rev-parse',':instructions/unrelated-staged.md').decode().strip()==f['staged_blob'],'unrelated_dirty_preserved':digest((target.parent/'unrelated-dirty.md').read_bytes())==f['dirty_sha256'],'head':head,'current_sha256':digest(target.read_bytes()),'repair_id':p['repair_id']}
assert all(v for k,v in checks.items() if isinstance(v,bool)),checks
(out/('undo-readback.json' if undo else 'apply-readback.json')).write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps(checks,indent=2))
