import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.common import ROOT
os.chdir(ROOT)
import requests,json
from pathlib import Path
import pandas as pd
url='https://previous-runs-api.open-meteo.com/v1/forecast'
params=dict(latitude=40.75,longitude=-73.99,start_date='2025-01-01',end_date='2026-01-01',hourly='temperature_2m_previous_day1,precipitation_previous_day1,wind_speed_10m_previous_day1',models='gfs_seamless',timezone='UTC')
r=requests.get(url,params=params,timeout=120);r.raise_for_status();d=r.json()
root=Path('data/weather');root.mkdir(exist_ok=True)
(root/'gfs_previous_day1.json').write_text(json.dumps(d))
f=pd.DataFrame(d['hourly']);f['hour']=pd.to_datetime(f.pop('time'),utc=True)
f['forecast_reference_offset_hours']=24
f.to_parquet(root/'forecast_features.parquet',index=False)
(root/'source.json').write_text(json.dumps({'url':r.url,'docs':'https://open-meteo.com/en/docs/previous-runs-api','provider_statement':'_previous_day1 is the value predicted 24 hours before valid time','validity':'UTC target hour; do not substitute target-hour analysis/reanalysis','model':'gfs_seamless','lead_hours':24,'rows':len(f),'missing':f.isna().sum().to_dict()},indent=2))
print('Archived 24-hour-lead forecast rows:',len(f));print(f.isna().sum())
