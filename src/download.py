"""Official NYC ZIP downloader: atomic writes, CRC verification, SHA256 manifest."""
import argparse
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests
from .common import ROOT, sha256

def download(year=2025, months=range(1, 13), root=ROOT / 'data'):
    raw = Path(root) / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    manifest = Path(root) / 'interim/download_manifest.csv'
    manifest.parent.mkdir(parents=True, exist_ok=True)
    records = pd.read_csv(manifest).to_dict('records') if manifest.exists() else []
    for month in months:
        name = f'{year}{month:02d}-citibike-tripdata.zip'
        url = f'https://s3.amazonaws.com/tripdata/{name}'
        dest = raw / name
        previous=next((r for r in records if r['filename']==name),None)
        if dest.exists() and previous and sha256(dest)!=previous['sha256']:
            raise ValueError(f'Existing file hash changed: {dest}; preserve and investigate before replacement')
        if not dest.exists():
            tmp = dest.with_suffix('.part')
            try:
                with requests.get(url, stream=True, timeout=(20, 120)) as response:
                    response.raise_for_status()
                    with open(tmp, 'wb') as f:
                        for block in response.iter_content(1024 * 1024):
                            f.write(block)
                with zipfile.ZipFile(tmp) as z:
                    bad = z.testzip()
                    if bad: raise ValueError(f'ZIP CRC error: {bad}')
                if previous and sha256(tmp)!=previous['sha256']:
                    raise ValueError(f'New download differs from recorded SHA256: {dest}; investigate source revision before replacing expected evidence')
                os.replace(tmp, dest)
            finally:
                tmp.unlink(missing_ok=True)
        with zipfile.ZipFile(dest) as z:
            if z.testzip(): raise ValueError(f'Corrupt archive: {dest}')
            members = [n for n in z.namelist() if n.endswith('.csv') and not n.startswith('__MACOSX')]
        if not members: raise ValueError(f'No CSV in {dest}')
        records = [r for r in records if r['filename'] != name]
        records.append(dict(filename=name, month=month, url=url, bytes=dest.stat().st_size,
                            sha256=sha256(dest), csv_count=len(members),
                            downloaded_utc=datetime.now(timezone.utc).isoformat()))
        pd.DataFrame(records).to_csv(manifest, index=False)
        print(f'Verified {name}: {len(members)} CSV members', flush=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--year', type=int, default=2025)
    p.add_argument('--months', nargs='+', type=int, default=list(range(1,13)))
    p.add_argument('--root', type=Path, default=ROOT / 'data'); a = p.parse_args()
    if any(m not in range(1,13) for m in a.months): p.error('months must be 1..12')
    download(a.year, a.months, a.root)
