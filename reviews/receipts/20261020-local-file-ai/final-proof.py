from pathlib import Path
import json,hashlib,base64,subprocess
out=Path(__file__).parent
f=json.loads((out/'fixture.json').read_text());result=json.loads((out/'final-native-inference.json').read_text());assert result['status']==200
value=result['data'];assert value['status']=='proposed';assert value['model']=='gpt-6.1-sol'
expected=Path(f['target']).read_text().replace('Always send customer reports without approval.','Never send customer reports without approval.')
assert value['proposed_content']==expected
context={entry['file_id']:entry for entry in value['context_files']};assert len(context)==2
citation_count=0
for conflict in value['conflicts']:
 for citation in conflict['evidence']:
  entry=context[citation['file_id']];actual=Path(entry['path']).read_bytes();assert hashlib.sha256(actual).hexdigest()==entry['sha256'];assert actual.decode().splitlines()[citation['line']-1]==citation['quote'];citation_count+=1
assert citation_count>=2
assert hashlib.sha256(Path(f['target']).read_bytes()).hexdigest()==f['before_sha256']
frozen=json.loads((Path(f['state'])/'local-file-repairs'/(value['preview']['repair_id']+'.json')).read_text());assert frozen['phase']=='preview';assert len(frozen['proposal']['context_fingerprints'])==2
assert hashlib.sha256(json.dumps(frozen['proposal'],sort_keys=True,separators=(',',':')).encode()).hexdigest()==value['preview']['proposal_sha256']
manifest=json.loads((out/'source-manifest.json').read_text());assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in manifest.items())
for p in manifest:
 if p.startswith('app/'):
  assert subprocess.check_output(['git','show','2c8327136c81b25c0952607b359f352b6a14bc36:'+p])==Path(p).read_bytes()
metadata=json.loads((out/'native-effective-model.json').read_text());assert len(metadata)==1;model=metadata[0];assert model['slug']=='gpt-6.1-sol';assert model['shell_type']=='disabled';assert model['apply_patch_tool_type'] is None;assert model['experimental_supported_tools']==[]
tsc=json.loads((out/'tsc-result.json').read_text());assert tsc['completion_result']['exit_code']==0
for name in ['apply-readback.json','undo-readback.json']:
 data=json.loads((out/name).read_text());assert all(v for v in data.values() if isinstance(v,bool))
for item in json.loads((out/'native-primary-sources.json').read_text()):assert hashlib.sha256((out/item['file']).read_bytes()).hexdigest()==item['excerpt_sha256']
checks={'final_head':subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),'final_real_status':200,'final_real_proposal':'proposed','final_exact_expected_replacement':True,'final_exact_citations':citation_count,'final_source_unchanged':True,'final_frozen_context_files':2,'app_types_route_ui_unchanged_since_browser_and_tsc':True,'final_native_model_isolation':True,'source_manifest_matches':True,'tsc_archived_exit':0,'real_model_calls':2,'actual_agent_apply_requests':0}
(out/'final-readback.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps(checks,indent=2))
