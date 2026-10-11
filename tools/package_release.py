"""Package final local foundation with integrity manifest and portable skill links."""
from pathlib import Path
import hashlib,json,os,zipfile,mmap,io
R=Path(__file__).resolve().parents[1]
def digest(b):return hashlib.sha256(b).hexdigest()
def read(p):
    if not p.stat().st_size:return b''
    with p.open('rb') as f:
        with mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as m:return m[:]
def selected():
    for p in sorted(R.rglob('*')):
        if '__pycache__' in p.parts or p.name in ('.DS_Store','release-manifest.json'):continue
        if p.is_symlink() or p.is_file():yield p
def main():
    entries=[]
    for p in selected():
        link=p.is_symlink();data=os.readlink(p).encode() if link else read(p)
        entries.append(dict(path=str(p.relative_to(R)),kind='symlink' if link else 'file',bytes=len(data),sha256=digest(data)))
    manifest=dict(version='1.0.0',snapshot_date='2026-10-09',scope='Verified local foundation; Cursor application pending',files=entries)
    mp=R/'release-manifest.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
    target=R.parent/'Alex_System_Foundation_v1.zip';tmp=target.with_suffix('.zip.tmp')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in [*selected(),mp]:
            rel=R.name+'/'+str(p.relative_to(R));zi=zipfile.ZipInfo(rel,(2026,10,9,23,0,0));zi.create_system=3
            zi.compress_type=zipfile.ZIP_DEFLATED
            if p.is_symlink():zi.external_attr=0o120777<<16;data=os.readlink(p).encode()
            else:zi.external_attr=0o100644<<16;data=read(p)
            z.writestr(zi,data)
    os.replace(tmp,target)
    with zipfile.ZipFile(io.BytesIO(read(target))) as z:
        for e in entries:assert digest(z.read(R.name+'/'+e['path']))==e['sha256'],e['path']
        assert z.testzip() is None
        links=sum((i.external_attr>>16)&0o170000==0o120000 for i in z.infolist())
        assert links==9,links
    receipt=dict(version='1.0.0',archive=target.name,sha256=digest(read(target)),bytes=target.stat().st_size,
        manifest_sha256=digest(read(mp)),files=len(entries),native_skill_links=links,zip_integrity='PASS',
        source_originals_unchanged=True,drive_status='local-only; Drive not updated',application_status='Pending Cursor implementation and runtime acceptance')
    (R.parent/'Alex_System_Foundation_Release.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
