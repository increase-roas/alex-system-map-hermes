from pathlib import Path
import json,copy,sys
from jsonschema import Draft202012Validator
ROOT=Path(__file__).resolve().parents[2];results=[]
for p in sorted((ROOT/'schemas').glob('*.schema.json')):
 schema=json.loads(p.read_text());Draft202012Validator.check_schema(schema);v=Draft202012Validator(schema)
 if p.name=='workflow-request.schema.json':file=ROOT/'examples/workflow-create-request.json'
 else:file=ROOT/'data'/p.name.replace('.schema.json','.json')
 data=json.loads(file.read_text());errors=list(v.iter_errors(data))
 results.append(dict(item=p.name,status='VERIFIED' if not errors else 'FAILED',schema=str(p.relative_to(ROOT)),file=str(file.relative_to(ROOT)),errors=[str(e.message) for e in errors[:5]]))
 if 'records' in data and data['records']:
  bad=copy.deepcopy(data);bad['records'][0]['id']=123
  results.append(dict(item=p.name+'_negative_numeric_id',status='VERIFIED' if list(v.iter_errors(bad)) else 'FAILED',evidence='Mutated in memory only; invalid numeric ID must reject.'))
  bad=copy.deepcopy(data);bad['records'][0]['unexpected_extra']='x'
  results.append(dict(item=p.name+'_negative_unknown_field',status='VERIFIED' if list(v.iter_errors(bad)) else 'FAILED',evidence='Mutated in memory only; extra record field must reject.'))
 else:
  bad=copy.deepcopy(data);bad['expected_revision']=True
  results.append(dict(item=p.name+'_negative_boolean_revision',status='VERIFIED' if list(v.iter_errors(bad)) else 'FAILED',evidence='Mutated in memory only; Boolean revision must reject.'))
out={'scope':'Fresh independent JSON Schema 2020-12 validation plus in-memory negative mutations; no artifact mutations','results':results}
(ROOT/'reports/independent-foundation-schemas.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2));sys.exit(1 if any(x['status']=='FAILED' for x in results) else 0)
