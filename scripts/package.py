"""Export reviewable source, executed notebook, synthetic inputs and all results."""
import hashlib
import json
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT.parent/'deliverables';DEST.mkdir(exist_ok=True)
paths=[]
for folder in ['src','tests','configs','scripts','services','.github','application','models','reports','notebooks','data/demo','data/processed','data/gbfs','data/historical/processed','data/historical/wayback','data/geography','data/weather','data/road_network','data/network60','outputs/demo','outputs/event_demo','outputs/official','outputs/history_evidence','outputs/history_calibrated','outputs/weather','outputs/duration_sensitivity','outputs/stochastic','outputs/routing','outputs/transport_service','outputs/network60','outputs/coverage_audit','outputs/external_202601']:
    paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
paths.extend(ROOT/n for n in ['README.md','README_EN.md','PROJECT_OVERVIEW.md','CONTRIBUTIONS.md','README_ZH.md','DATA_DICTIONARY.md','requirements.txt','requirements-lock.txt','pyproject.toml','.gitignore','.gitattributes'])
paths.extend(p for p in (ROOT/'data/interim').glob('*.csv') if p.is_file())
paths.extend(p for p in (ROOT/'data/historical').glob('*') if p.is_file() and p.name!='directory.json')
archive=DEST/'CitiBike_project.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(set(paths)):z.write(p,arcname=Path('citibike_project')/p.relative_to(ROOT))
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}
    z.writestr('citibike_project/MANIFEST_SHA256.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name,digest in manifest.items():assert hashlib.sha256(z.read('citibike_project/'+name)).hexdigest()==digest
checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
(DEST/'CitiBike_project.sha256').write_text(checksum+'  CitiBike_project.zip\n')
print(f'PASS: {len(manifest)} files, ZIP CRC + per-file SHA256 verified; {archive.stat().st_size/1e6:.2f} MB')
print(archive)
