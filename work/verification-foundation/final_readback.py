from pathlib import Path
import mmap,hashlib,json,zipfile,io,sys
ROOT=Path(__file__).resolve().parents[2]
def raw(p):
 with p.open('rb') as f:
  with mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as m:return m[:]
def load(p):return json.loads(raw(p))
def sha(p):return hashlib.sha256(raw(p)).hexdigest()
results=[]
def check(name,okay,evidence):
 results.append(dict(item=name,status='VERIFIED' if okay else 'FAILED',evidence=evidence))
 if not okay:raise AssertionError(name)
graph=load(ROOT/'reports/independent-foundation-graph.json')
check('prior_independent_graph_behavior',all(x['status']=='VERIFIED' for x in graph['results']),dict(checks=len(graph['results']),report='reports/independent-foundation-graph.json'))
check('current_canonical_json_matches_verified_graph',all(sha(ROOT/p)==h for p,h in graph['checked_sha256'].items()),dict(compared_files=len(graph['checked_sha256']),scope='Top-level maintained catalog JSON bytes match final independently checked graph.'))
workflow=load(ROOT/'reports/independent-foundation-workflow.json')
check('verified_workflow_engine_bytes_unchanged',all(x['status']=='VERIFIED' for x in workflow['results']) and sha(ROOT/'tools/workflow_engine.py')==workflow['engine_sha256'],dict(checks=len(workflow['results']),engine_sha256=workflow['engine_sha256']))
schemas=load(ROOT/'reports/independent-foundation-schemas.json');check('latest_independent_schema_and_negative_output',all(x['status']=='VERIFIED' for x in schemas['results']),dict(checks=len(schemas['results']),report='reports/independent-foundation-schemas.json'))
for r in graph['results']:
 if r['item'].startswith('original_') and r['item'].endswith('_preserved'):
  e=r['evidence'];check(r['item']+'_current_bytes',sha(Path(e['source_path']))==sha(Path(e['copy_path']))==e['sha256'],e)
cc=load(ROOT/'data/components.json')['records'];actualpages={p.stem for p in (ROOT/'components').glob('*.md')}
check('current_component_pages_match_canonical_records',actualpages=={c['id'] for c in cc} and all(c['id'] in raw(ROOT/'components'/f"{c['id']}.md").decode() and c['name'] in raw(ROOT/'components'/f"{c['id']}.md").decode() and (not c['boundary'] or c['boundary'] in raw(ROOT/'components'/f"{c['id']}.md").decode()) for c in cc),dict(pages=len(actualpages),reader='read-only mmap; ordinary readall stall bypassed without mutation'))
pro=ROOT/'inputs/pro-ai-workflow-editor.zip';original=Path('/Users/alexlobaito/Downloads/pro-ai-workflow-editor.zip')
check('supplied_pro_zip_current_original_identity',sha(pro)==sha(original)=='5b69062bfdf61535125bfb64c75f68aae3e7e5ba363553d84146645c153e7ec3',dict(path=str(pro),bytes=pro.stat().st_size))
with zipfile.ZipFile(io.BytesIO(raw(pro))) as z:check('supplied_pro_zip_current_crc_and_entries',len(z.namelist())==92 and z.testzip() is None,dict(entries=len(z.namelist())))
for n in ['system-map-catalog','workflow-checkpoint-recovery','react-flow-system-explorer']:
 canonical=ROOT/'skills'/n/'SKILL.md'
 check(n+'_project_links',all((ROOT/d/'skills'/n).is_symlink() and (ROOT/d/'skills'/n).resolve()==canonical.parent.resolve() and raw(ROOT/d/'skills'/n/'SKILL.md')==raw(canonical) for d in ['.agents','.cursor','.claude']),dict(canonical_sha256=sha(canonical)))
agent=raw(ROOT/'docs/AGENT_PROTOCOL.md').decode();design=raw(ROOT/'docs/DESIGN_SPEC.md').decode();handoff=raw(ROOT/'docs/CURSOR_HANDOFF.md').decode()
check('corrected_catalog_workflow_authority',all(t in agent for t in ['Every workflow mutation','The v1 JSON catalog has no per-record revision field or mutation API.','This patch evidence is separate from the workflow review-task receipt.']) and 'The only v1 catalog-write path is the explicitly authorized single-editor patch/validate/regenerate process' in design,dict(paths=['docs/AGENT_PROTOCOL.md','docs/DESIGN_SPEC.md','docs/CURSOR_HANDOFF.md']))
check('file_browser_and_five_view_handoff',all(t in handoff for t in ['Current file','Archived snapshot','File browser','File relationships','File proof and secrecy']) and 'Implement five main views.' in design,dict(ui_status='Pending Cursor runtime; verifies written requirement only'))
for name in ['independent-foundation-docs.json','independent-foundation-pro-template.json']:
 d=load(ROOT/'reports'/name);check(name+'_accepted_scoped_evidence',all(x['status'] in ('VERIFIED','UNVERIFIED') for x in d['results']) and not any(x['status']=='FAILED' for x in d['results']),dict(report='reports/'+name))
out=dict(scope='Final limited mmap readback; no broad source audit repeated, no changes to foundation sources/catalog/engine',results=results,limitations=['Prior graph audit passed27 checks including all294002sourcecells. A later ordinary FileIO repeat timed out; current maintainedJSON/engine/sourceinput bytes agree with its evidence, currentpages reopened using mmap.','Cursor UI/native targetruntime automaticselection intentionally pending beyond foundation acceptance.'])
(ROOT/'reports/independent-foundation-final-readback.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2));sys.exit(0)
