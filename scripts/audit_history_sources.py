import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.common import ROOT
os.chdir(ROOT)
import requests,json
from pathlib import Path
root=Path('data/external');root.mkdir(parents=True,exist_ok=True)
for label,until in [('start','2025-01-01T00:00:00Z'),('end','2025-12-31T23:59:59Z')]:
 u='https://api.github.com/repos/citybikes/analytics/commits';r=requests.get(u,params={'path':'collect.py','until':until,'per_page':1},timeout=30);r.raise_for_status();d=r.json()
 if d:
  sha=d[0]['sha'];code=requests.get(f'https://raw.githubusercontent.com/citybikes/analytics/{sha}/collect.py',timeout=30);code.raise_for_status();(root/f'collector_{label}_2025.py.txt').write_text(code.text)
  (root/f'collector_{label}_2025_source.json').write_text(json.dumps({'commit':sha,'commit_time':d[0]['commit']['committer']['date'],'url':code.url,'scope':'source revision at 2025 period boundary; deployment continuity cannot be independently proven'},indent=2))
  print(label,sha,'counts-only dedup present:', "val=(station['bikes'],station['free'])" in ''.join(code.text.split()).replace(chr(34),chr(39)))
u='https://data.cityofnewyork.us/resource/5uei-swth.json';r=requests.get(u,params={'$select':'min(inpectiondate) as first,max(inpectiondate) as last,count(*) as rows'},timeout=40);print('inspection coverage',r.status_code,r.text[:1000]);(root/'inspection_coverage.json').write_text(r.text)
for feed in ['station_information','station_status']:
 u='https://web.archive.org/cdx/search/cdx';r=requests.get(u,params={'url':f'gbfs.citibikenyc.com/gbfs/en/{feed}.json','output':'json','filter':'statuscode:200','from':'2025','to':'2025','fl':'timestamp,digest,length','limit':10000},timeout=60);print(feed,'all captures',r.status_code,len(r.json())-1 if r.status_code==200 else 'unavailable');(root/f'all_cdx_{feed}.json').write_text(r.text)
