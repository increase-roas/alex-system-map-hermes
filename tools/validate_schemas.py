from pathlib import Path
import json, sys
from jsonschema import Draft202012Validator
R=Path(__file__).resolve().parents[1]
errors=[];checked=[]
for p in sorted((R/'schemas').glob('*.schema.json')):
    name=p.name.replace('.schema.json',''); data=R/'data'/f'{name}.json'
    if not data.exists():continue
    schema=json.loads(p.read_text());Draft202012Validator.check_schema(schema)
    validator=Draft202012Validator(schema);d=json.loads(data.read_text());checked.append(name)
    for e in validator.iter_errors(d):errors.append({'collection':name,'path':list(e.path),'message':e.message})
# Negative proof: unknown evidence status must not silently reach UI consumers.
d=json.loads((R/'data/components.json').read_text());d['records'][0]['evidence_level']='live_because_agent_says_so'
negative=bool(list(Draft202012Validator(json.loads((R/'schemas/components.schema.json').read_text())).iter_errors(d)))
report={'status':'PASS' if not errors and negative else 'FAIL','collections':checked,'errors':errors,'negative_status_rejected':negative}
(R/'reports/schema-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2));sys.exit(report['status']!='PASS')
