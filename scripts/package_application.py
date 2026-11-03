"""Small review/application bundle; full datasets remain in the separate project ZIP."""
import hashlib,json,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];dest=ROOT.parent/'deliverables';dest.mkdir(exist_ok=True)
paths=[]
for folder in ['application','models/frozen_2025','src','reports/results/application','reports/results/external_202601']:
    paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
paths.extend(ROOT/p for p in ['PROJECT_OVERVIEW.md','CONTRIBUTIONS.md','README_ZH.md','README_EN.md','requirements-lock.txt','reports/technical_report.pdf','reports/optimization_formulation.md','reports/results/forecast_metrics.csv','reports/results/extensions/DATABASE_NOTICE.md','reports/results/operations/summary.csv','reports/validation/pytest.txt','reports/validation/pytest.xml','reports/validation/github_research_runs.json','reports/validation/monitoring_audit.json','reports/validation/application_reconciled.json','configs/external_202601.json'])
paths.extend(ROOT/p for p in ['scripts/external_202601.py','configs/official_counts.json','requirements.txt'])
paths.append(ROOT/'README.md')
paths.extend(ROOT/p for p in ['reports/validation/external_portable.json','reports/validation/external_202601.log'])
manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}
archive=dest/'CitiBike_application_materials.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for path in sorted(set(paths)):z.write(path,arcname=Path('CitiBike_application_materials')/path.relative_to(ROOT))
    z.writestr('CitiBike_application_materials/MANIFEST_SHA256.json',json.dumps(manifest,indent=2))
    z.writestr('CitiBike_application_materials/SOURCE_REFERENCE.json',json.dumps(dict(repository='https://github.com/ryanwulikenature-glitch/ryan-wu',commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),scope='Application drafts plus research evidence; large full-project delivery is separate'),indent=2))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for path,digest in manifest.items():assert hashlib.sha256(z.read('CitiBike_application_materials/'+path)).hexdigest()==digest
(dest/'CitiBike_application_materials.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
print(f'PASS: {len(manifest)} files; CRC and every SHA256 verified; {archive.stat().st_size/1e6:.2f} MB; {archive}')
