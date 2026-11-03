"""Fetch a dated directed OSRM driving proxy; preserve existing study matrix."""
import argparse,json,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import requests
from src.common import ROOT,save_json,sha256
p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true',help='Replace retained proxy; rerun transport study if refreshed');a=p.parse_args()
dest=ROOT/'data/road_network';dest.mkdir(parents=True,exist_ok=True)
if (dest/'osrm_table.json').exists() and not a.refresh:
    print('Retaining existing dated study matrix:',sha256(dest/'osrm_table.json'));raise SystemExit(0)
st=pd.read_csv(ROOT/'data/processed/stations.csv',dtype={'station_id':str}).sort_values('station_id')
coords=';'.join(f'{r.longitude:.8f},{r.latitude:.8f}' for r in st.itertuples())
r=requests.get('https://router.project-osrm.org/table/v1/driving/'+coords,params={'annotations':'distance,duration'},timeout=90);r.raise_for_status();d=r.json()
if d.get('code')!='Ok' or any(x is None for row in d['durations'] for x in row):raise ValueError('Incomplete OSRM network')
save_json(dest/'osrm_table.json',d)
save_json(dest/'source.json',dict(url=r.url,retrieved_utc=datetime.now(timezone.utc).isoformat(),engine='OSRM public driving profile',station_order=st.station_id.tolist(),scope='current OSM road-network driving proxy, not verified 2025 traffic or truck-specific height/weight routing',license='OpenStreetMap contributors; ODbL underlying road database; OSRM project routing service',max_snap_m=max(x['distance'] for x in d['sources']),data_version=d.get('data_version')))
print('Road matrix:',len(d['durations']),'points; max snap',max(x['distance'] for x in d['sources']))
