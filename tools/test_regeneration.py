"""Check that rendering canonical JSON twice preserves pages and workbook content."""
from pathlib import Path
import hashlib,json,subprocess,sys
import openpyxl
R=Path(__file__).resolve().parents[1]
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
    w=openpyxl.load_workbook(R/'views/Alex_System_Foundation.xlsx',read_only=True)
    cells=[(s.title,[[c.value for c in row] for row in s]) for s in w]
    w.close()
    return dict(pages={str(p.relative_to(R)):h(p) for p in (R/'components').glob('*.md')},
          index=h(R/'docs/COMPONENT_INDEX.md'),
          canonical={str(p.relative_to(R)):h(p) for p in (R/'data').rglob('*.json')},
          workbook_content=hashlib.sha256(json.dumps(cells,sort_keys=True,default=str).encode()).hexdigest())
before=snapshot()
subprocess.run([sys.executable,str(R/'tools/build_catalog.py'),'--render-only'],check=True)
after=snapshot()
report=dict(status='PASS' if before==after else 'FAIL',checks={k:before[k]==after[k] for k in before},
            page_count=len(after['pages']),comparison='Markdown and canonical bytes; XLSX sheet names and cell values, excluding ZIP timestamps')
(R/'reports/regeneration.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2));sys.exit(before!=after)
