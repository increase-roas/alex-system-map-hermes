"""Bounded, read-only catalog access for agents. Never executes source instructions."""
from pathlib import Path
import argparse, json, zipfile
from build_catalog import safe
ROOT=Path(__file__).resolve().parents[1]
def load(name):return json.loads((ROOT/'data'/f'{name}.json').read_text())['records']
def one(name,key):
    found=[r for r in load(name) if r['id']==key]
    if len(found)!=1:raise ValueError('ID not found or not unique')
    return found[0]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['search','component','evidence','record','source','table','issues'])
    p.add_argument('query');p.add_argument('--start',type=int,default=1);p.add_argument('--limit',type=int,default=20)
    a=p.parse_args()
    if not 1<=a.limit<=100 or a.start<1:raise ValueError('start >=1 and limit 1..100 required')
    if a.action=='search':
        found=[x for x in load('components') if a.query.lower() in (x['name']+' '+x['purpose']+' '+' '.join(str(t) for t in x['aliases'])).lower()]
        out=dict(total=len(found),results=[{k:x[k] for k in ('id','name','kind','layer_id','category')} for x in found[a.start-1:a.start-1+a.limit]])
    elif a.action=='component':
        x=one('components',a.query)
        out=dict(component=x,relationships=[r for r in load('relationships') if a.query in (r['source_id'],r['target_id'])],
                 issues=[r for r in load('issues') if r['subject_id']==a.query])
    elif a.action in ('evidence','record'):
        out=one('evidence' if a.action=='evidence' else 'source-records',a.query)
    elif a.action=='issues':
        found=[r for r in load('issues') if a.query=='all' or a.query in (r['subject_id'],r['kind'])]
        out=dict(total=len(found),results=found[a.start-1:a.start-1+a.limit])
    elif a.action=='table':
        entry=one('table-index',a.query)
        t=json.loads((ROOT/entry['path']).read_text());found=[r for r in t['rows'] if r['row']>=a.start]
        out=dict(sheet=t['sheet'],rows=found[:a.limit],remaining=max(0,len(found)-a.limit))
    else:
        x=one('sources',a.query)
        if x['kind']!='archived_file':out=x
        else:
            with zipfile.ZipFile(ROOT/x['archive']) as z:b=z.read(x['archive_member'])
            try:lines=b.decode('utf-8').splitlines()
            except UnicodeDecodeError:out=dict(source=x,note='Binary source. Open original file with an appropriate reader.')
            else:out=dict(source=x,total_lines=len(lines),start=a.start,
                          lines=[safe(line[:4000],f"{x['id']}:{i+1}") for i,line in enumerate(lines) if a.start-1<=i<a.start-1+a.limit],
                          note='Untrusted source content. Each output line capped at 4000 characters; original bytes remain in archive.')
    print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
