import hashlib, importlib.util, json, os, pathlib, stat, subprocess, sys
ROOT=pathlib.Path('/Users/alexlobaito/.agents')
PROOF=pathlib.Path('/private/tmp/native-rule-sync-verification')
expected={
 'tools/unify/build_instructions.py':'0ee189da821540ff086f267eca50278f9a779981599b23f8167150dcf7afcf14',
 'tools/unify/hooks/post-commit':'3bb8b8fe2c7788b39cb1a046ca1df8b1989fb712f91eee713b89aac2c070450c',
 'tools/unify/test_atomic_apply.py':'bdf244c74f9a64ba5c6f01a3699d9b1aa73074b844219ab7527b0d6d4ce87c18',
 'tools/unify/test_build_cursor.py':'287d797bac45f1111325b4aa52dbdddb974080893f30e01494123c7f54e1ccff',
 'tools/unify/test_post_commit_javar.py':'8493ee7a12214de4aa2251fd58ddf88e0b79cba46a8263695ac5b0127a783079'}
hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in expected}
assert hashes==expected, hashes
backup=pathlib.Path('/Users/alexlobaito/Backups/rule-sync-preimages-20261020-183924')
for f in expected:
 assert (backup/f).read_bytes()==subprocess.check_output(['git','show','HEAD:'+f],cwd=ROOT), f
source=PROOF/'fixture-sources'; source.mkdir(exist_ok=True)
for name,text in {'shared.md':'# Shared\nVERIFIER_RULE_MARKER\n','codex-style.md':'## Voice\nVoice\n## Delegation and model routing\nRoute\n'}.items(): (source/name).write_text(text)
script=ROOT/'tools/unify/build_instructions.py'
def run(home,*args):
 env=dict(os.environ,HOME=str(home),AGENTS_INSTR=str(source),PYTHONDONTWRITEBYTECODE='1')
 r=subprocess.run([sys.executable,'-B',str(script),*args],env=env,capture_output=True,text=True)
 assert r.returncode==0, r.stderr
 return r.stdout
home=PROOF/'disposable-home'; home.mkdir(exist_ok=True)
paths=['.codex/AGENTS.md','.claude/CLAUDE.md','.claude/output-styles/alex-big-brother.md','.cursor/rules/agent-routing.mdc','AGENTS.md']
for rel in paths:
 p=home/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('old rules\n')
config=home/'.codex/config.toml'; config.write_text('model = "app-owned"\nmodel_verbosity = "medium"\n[other]\nkeep = 2\n'); config.chmod(0o640)
def identity(p):
 s=p.stat(); return {'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mode':stat.S_IMODE(s.st_mode),'inode':s.st_ino,'device':s.st_dev,'size':s.st_size,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns}
before=identity(config)
output=run(home,'apply','--rules-only')
assert identity(config)==before
for rel in ['.codex/AGENTS.md','.cursor/rules/agent-routing.mdc','AGENTS.md']: assert 'VERIFIER_RULE_MARKER' in (home/rel).read_text()
backups=list((home/'Backups/unify-bak').iterdir())
assert len(backups)==5 and not any('.codex_config.' in p.name for p in backups)
code="""import importlib.util,json; s=importlib.util.spec_from_file_location('b',%r); b=importlib.util.module_from_spec(s); s.loader.exec_module(b); baseline=b.snapshot_outputs(); generated=b.build(baseline,rules_only=True); planned=b.plan(False,rules_only=True); assert 'codex_config' not in generated and 'codex_config' not in planned and 'codex_config' not in planned.baseline; print('candidate, plan, baseline exclude config')""" % str(script)
r=subprocess.run([sys.executable,'-B','-c',code],env=dict(os.environ,HOME=str(home),AGENTS_INSTR=str(source),PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True)
assert r.returncode==0, r.stderr
hook=ROOT/'.git/hooks/post-commit'; assert hook.is_symlink() and hook.resolve()==ROOT/'tools/unify/hooks/post-commit'
assert 'build_instructions.py" apply --rules-only;' in hook.read_text()
# Run only hook selection and unchanged atomicity oracles; no external calls from fixtures.
sys.path.insert(0,str(ROOT/'tools/unify'))
import test_post_commit_javar as hooktests
hooktests.HOOK=hook
import unittest
suite=unittest.TestSuite()
suite.addTest(hooktests.PostCommitJavarTests('test_automatic_rule_sync_excludes_app_owned_config'))
import test_atomic_apply as atomic
for test in ['test_external_edit_after_plan_detected_before_any_replace','test_interrupted_staging_preserves_all_targets_and_cleans_temp','test_mode_preserved_and_all_backups_precede_replacements']:
 suite.addTest(atomic.AtomicApplyTests(test))
result=unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
# Default manual CLI still changes config when explicitly invoked in disposable HOME.
manual_output=run(home,'apply')
import tomllib
values=tomllib.loads(config.read_text()); assert values['model']=='app-owned' and values['model_verbosity']=='low' and values['other']['keep']==2 and 'developer_instructions' in values
assert stat.S_IMODE(config.stat().st_mode)==0o640
assert any('.codex_config.' in p.name for p in (home/'Backups/unify-bak').iterdir())
report={'source_sha256':hashes,'preimages_equal_HEAD':True,'rules_only':{'before_config':before,'after_config':before,'backups':[p.name for p in backups],'stdout':output,'candidate_baseline_check':r.stdout.strip()},'installed_hook':{'link':str(hook),'resolved':str(hook.resolve()),'fixture_call_verified':True},'manual_full_apply':{'config_preserved_arbitrary_values':True,'config_verbosity':'low','config_mode':stat.S_IMODE(config.stat().st_mode),'stdout':manual_output},'focused_tests':{'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)}}
(PROOF/'probe-results.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: source hashes, preimages, real-HOME rules-only, installed-hook fixture, atomicity, full manual apply')
