"""Run paired-ride replay against the actual cleaned official partitions."""
import sys
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
from src.common import ROOT,load_config,save_json
from src.event_replay import replay
out=ROOT/'outputs/official';data=ROOT/'data/processed'
p=pd.read_csv(out/'test_predictions.csv.gz',dtype={'station_id':str});p['hour']=pd.to_datetime(p.hour,utc=True)
st=pd.read_csv(data/'stations.csv',dtype={'station_id':str});cfg=load_config(ROOT/'configs/official_counts.json')
# Full test replay, same horizon and starting docked stocks as the count scenario.
cfg['hours']=p.hour.nunique();start=p.hour.min();stop=p.hour.max()+pd.Timedelta(hours=1)
paths=json.loads((data/'clean_partitions.json').read_text());dataset=ds.dataset(paths,format='parquet')
condition=((ds.field('start')<pa.scalar(stop)) & (ds.field('end')>=pa.scalar(start)) &
           (ds.field('start_station_id').isin(st.station_id.tolist()) | ds.field('end_station_id').isin(st.station_id.tolist())))
rides=dataset.to_table(filter=condition,columns=['ride_id','start','end','start_station_id','end_station_id']).to_pandas()
print(f'Replaying {len(rides):,} cleaned recorded rides; {cfg["hours"]} test hours',flush=True)
r,ledger=replay(rides,p,st,cfg,out/'paired_events')
assert (r.accounted_fleet==r.initial_fleet+r.boundary_incoming-r.boundary_outgoing).all()
summary=r.groupby('strategy')[['unmet_departures','blocked_arrivals','served_departures','bikes_moved','bike_km']].sum().reset_index()
summary['departure_requests']=summary.unmet_departures+summary.served_departures
summary['proxy_service_rate']=1-summary.unmet_departures/summary.departure_requests.replace(0,float('nan'))
summary['simulation_kind']='paired recorded-ride counterfactual scenario';summary['hours']=cfg['hours']
summary.to_csv(out/'paired_events/event_replay_summary.csv',index=False)
save_json(out/'paired_events/config.json',dict(config=cfg,rides=len(rides),causal_return_suppression=True,
    full_fleet_accounting='passed',blocked_return_rule='held off dock through horizon; no retry',
    boundary='external arrivals exogenous; initially underway rides included in initial scenario fleet',
    interpretation='counterfactual sample-path scenario, not observed 2025 losses'))
print(summary.to_csv(index=False));print('PASS: full fleet conservation at every paired event, all policies.')
