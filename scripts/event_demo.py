"""Small paired-event synthetic demonstration; separate from count experiments."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from src.common import ROOT,load_config
from src.event_replay import replay
rng=np.random.default_rng(2025);start=pd.Timestamp('2025-11-01 04:00',tz='UTC')
stations=pd.DataFrame({'station_id':['EVENT_A','EVENT_B','EVENT_C'],'latitude':[40.75,40.751,40.752],'longitude':[-73.99,-73.991,-73.992]})
ids=stations.station_id.tolist();rides=[]
for k in range(300):
    t=start+pd.Timedelta(minutes=int(rng.integers(-30,480)))
    rides.append(dict(ride_id=f'synthetic_ride_{k}',start=t,end=t+pd.Timedelta(minutes=int(rng.integers(1,70))),
                      start_station_id=rng.choice(ids+['OUT']),end_station_id=rng.choice(ids+['OUT'])))
rides=pd.DataFrame(rides);pred=pd.DataFrame([dict(station_id=s,hour=h,pred_dep=8,pred_arr=7) for h in pd.date_range(start,periods=8,freq='h') for s in ids])
cfg=load_config();cfg.update(data_kind='synthetic',hours=8,capacity=8,budget=3)
out=ROOT/'outputs/event_demo';out.mkdir(parents=True,exist_ok=True)
rides.to_parquet(out/'synthetic_paired_rides.parquet',index=False)
r,ledger=replay(rides,pred,stations,cfg,out)
assert (r.accounted_fleet==r.initial_fleet+r.boundary_incoming-r.boundary_outgoing).all()
print('PASS: 300 synthetic paired rides, 3 policies x 8 hours, causal suppression and boundary fleet conservation.')
print(r.groupby('strategy')[['unmet_departures','blocked_arrivals','bikes_moved']].sum().to_csv())
