from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
checks=['file:START_HERE.md non-empty','file:docs/CURSOR_HANDOFF.md non-empty','file:docs/DATA_CONTRACT.md non-empty','file:docs/WORKFLOW_CONTRACT.md non-empty','file:tools/workflow_engine.py non-empty']
for name in ['components','relationships','evidence','sources','source-records','coverage','issues','table-index','layers']:checks.append('json:data/'+name+'.json')
for name in ['system-map-catalog','workflow-checkpoint-recovery','react-flow-system-explorer']:
 checks.extend(['file:skills/'+name+'/SKILL.md non-empty','absent:skills/'+name+'/SKILL.md::/Users/'])
 checks.append('cmd:/Users/alexlobaito/.local/pipx/.cache/f1f7d7da70349d4/bin/python /Users/alexlobaito/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/'+name)
checks.extend(['file:inputs/pro-ai-workflow-editor.zip non-empty','file:docs/PRO_TEMPLATE_INTAKE.md non-empty','contains:docs/CURSOR_HANDOFF.md::Archived snapshot','contains:docs/AGENT_PROTOCOL.md::This patch evidence is separate from the workflow review-task receipt.','contains:docs/DESIGN_SPEC.md::The only v1 catalog-write path is the explicitly authorized single-editor patch/validate/regenerate process','cmd:python3 work/verification-foundation/final_readback.py'])
r=subprocess.run([sys.executable,'/Users/alexlobaito/.agents/skills/verify-before-done/scripts/check_acceptance.py',*checks],cwd=ROOT,capture_output=True,text=True)
(ROOT/'reports/independent-foundation-optional-repeat.md').write_text(r.stdout)
print(r.stdout);sys.exit(r.returncode)
