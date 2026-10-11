"""Validate portable foundation against original workbook and archive, not build claims."""
from pathlib import Path
from collections import Counter
import json, hashlib, zipfile, sys, re
import openpyxl
from build_catalog import SECRET, ASSIGN
ROOT=Path(__file__).resolve().parents[1]
def load(name):return json.loads((ROOT/'data'/f'{name}.json').read_text())['records']
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    checks=[]
    def check(name,okay,detail=None):checks.append(dict(name=name,passed=bool(okay),detail=detail))
    collections={n:load(n) for n in ['components','relationships','sources','evidence','issues','source-records','table-index','layers']}
    for n,rows in collections.items():check(n+' IDs unique',len({x['id'] for x in rows})==len(rows),len(rows))
    ids={n:{x['id'] for x in rows} for n,rows in collections.items()};cc=collections['components'];ee=collections['evidence'];rr=collections['relationships']
    for n in ['components','relationships','issues','source-records']:
        check(n+' evidence references resolve',all(set(x.get('evidence_ids',[]))<=ids['evidence'] for x in collections[n]))
    check('all evidence sources resolve',all(x['source_id'] in ids['sources'] for x in ee))
    check('all component source records resolve',all(set(c['source_record_ids'])<=ids['source-records'] for c in cc))
    check('relationship endpoints resolve',all(x['source_id'] in ids['components'] and x['target_id'] in ids['components'] for x in rr))
    check('issue subjects resolve',all(x['subject_id'] in ids['components']|ids['table-index'] for x in collections['issues']))
    enums={'category':{'documented_current','historical','planned','unresolved'},'evidence_level':{'reported','configured','tested','unverified'},'observed_condition':{'working','failing','blocked','unknown'}}
    for field,values in enums.items():check(field+' enum valid',all(x[field] in values for x in cc+rr))
    check('no unobserved live-health promotion',all(x['observed_condition']=='unknown' and x['observed_at'] is None for x in cc+rr))
    check('all layers resolve',all(x['layer_id'] in ids['layers'] for x in cc))
    v=json.loads((ROOT/'views/overview.json').read_text())
    presentation_ids={x['component_id'] for x in v['memberships']}
    check('one presentation per component and all parents visible',len(presentation_ids)==len(v['memberships']) and presentation_ids==ids['components'] and all(not x['parent_id'] or x['parent_id'] in presentation_ids for x in v['memberships']))
    check('presentation membership separate and valid',v['membership_is_runtime_relationship'] is False and all(x['component_id'] in ids['components'] and (not x['parent_id'] or x['parent_id'] in ids['components']) for x in v['memberships']))
    m=json.loads((ROOT/'inputs/coverage-audit-manifest.json').read_text());cov=load('coverage')
    check('all 198 original map entries retain exact names and boundaries',all(any(c['name']==x['name'] and c['boundary']==x['boundary'] and c['purpose']==x['purpose'] for c in cc) for x in m['components']))
    check('coverage exact counts',dict(Counter(x['record_type'] for x in cov))==m['coverage_counts'],dict(Counter(x['record_type'] for x in cov)))
    check('coverage every record exactly once',Counter(x['record_id'] for x in cov)==Counter(x['id'] for x in collections['source-records']))
    w=openpyxl.load_workbook(ROOT/'inputs/Alex_Master_Build_and_Connectors.xlsx',read_only=False)
    check('coverage exact workbook identity',all(w['MAP COVERAGE'].cell(x['coverage_row'],1).value==x['record_type'] and next(r for r in collections['source-records'] if r['id']==x['record_id'])['label']==w['MAP COVERAGE'].cell(x['coverage_row'],2).value for x in cov))
    check('source row references in bounds',all(e.get('sheet') is None or (e['sheet'] in w.sheetnames and 1<=e['row']<=w[e['sheet']].max_row) for e in ee))
    check('relationship table exact accounting',len(rr)==w['S04-20 Relationships'].max_row-1 and {e['row'] for r in rr for e in ee if e['id'] in r['evidence_ids']}==set(range(2,w['S04-20 Relationships'].max_row+1)))
    with zipfile.ZipFile(ROOT/'inputs/Alex_Master_Source_Files.zip') as z:
        src=[s for s in collections['sources'] if s['kind']=='archived_file']
        check('all 1009 archived source bytes match',len(src)==1009 and all(hashlib.sha256(z.read(s['archive_member'])).hexdigest()==s['sha256'] for s in src))
    check('original workbook unchanged',digest(ROOT/'inputs/Alex_Master_Build_and_Connectors.xlsx')==m['xlsx_sha256'])
    check('original source ZIP unchanged',digest(ROOT/'inputs/Alex_Master_Source_Files.zip')==m['source_zip_sha256'])
    check('all 192 source tables exported',len(collections['table-index'])==len(w.sheetnames)==192 and {t['sheet'] for t in collections['table-index']}==set(w.sheetnames))
    check('component pages complete',all((ROOT/'components'/f"{x['id']}.md").exists() for x in cc))
    # The generated export must contain no recognized secret values. Originals are pinned, not reclassified.
    found=[]
    for folder in ['data','components','views','docs','examples','workflows']:
        for p in (ROOT/folder).rglob('*'):
            if p.suffix not in ('.json','.md','.txt'):continue
            text=p.read_text()
            if SECRET.search(text) or ASSIGN.search(text):found.append(str(p.relative_to(ROOT)))
    check('generated text credential-pattern scan',not found,found)
    x=openpyxl.load_workbook(ROOT/'views/Alex_System_Foundation.xlsx')
    check('generated XLSX has full catalog and coverage',x['TOP DOWN MAP'].max_row==len(cc)+1 and x['COVERAGE'].max_row==len(cov)+1)
    check('generated XLSX no formula/error cells',not any(c.data_type in ('f','e') for s in x for row in s for c in row))
    check('negative omitted-record test',Counter(a['record_type'] for a in cov[1:])!=Counter(a['record_type'] for a in cov))
    check('negative dangling-edge test','nonexistent-component' not in ids['components'])
    report=dict(status='PASS' if all(c['passed'] for c in checks) else 'FAIL',checks=checks,
       limitations=['Source reconciliation, not live system audit.','Pattern scan cannot prove absence of every possible opaque secret. No credential fields were fetched.','Cursor UI and authenticated application acceptance remain pending.'])
    (ROOT/'reports/catalog-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=sum(c['passed'] for c in checks),total=len(checks),failed=[c for c in checks if not c['passed']]),indent=2))
    return report['status']!='PASS'
if __name__=='__main__':sys.exit(main())
