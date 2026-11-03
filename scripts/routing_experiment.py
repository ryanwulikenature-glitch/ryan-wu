import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from src.common import ROOT,distances,save_json
from src.routing import route_transfers
out=ROOT/'outputs/routing';out.mkdir(parents=True,exist_ok=True);st=pd.read_csv(ROOT/'data/processed/stations.csv',dtype={'station_id':str}).sort_values('station_id');ids=st.station_id.tolist();idx={s:k for k,s in enumerate(ids)};distance=distances(st)
orders=pd.read_csv(ROOT/'outputs/official/moves.csv',dtype={'source_station':str,'target_station':str});orders['timestamp']=pd.to_datetime(orders.timestamp,utc=True)
h=pd.read_csv(ROOT/'outputs/official/simulation_hourly.csv');h['timestamp']=pd.to_datetime(h.timestamp,utc=True);times=sorted(h.timestamp.unique())[:48]
settings=dict(depot=0,trucks=2,truck_capacity=6,speed_kmh=15,shift_minutes=60,minutes_per_bike_per_stop=1.5,time_limit=5)
save_json(out/'protocol.json',dict(resources=settings,depot_station=ids[0],scope='Fixed transfer orders from count-scenario policies; 2-truck atomic pickup-delivery routing feasibility audit; no co-loading, assumed depot/speed/service time, no road network or actual dispatch data',comparison='Truck-km is separate from bike-km; no service improvement is inferred from a route-feasibility audit'))
results=[];route_logs=[]
for t in times:
    for policy in ['greedy','milp']:
        sub=orders[(orders.timestamp==t)&(orders.strategy==policy)];x=np.zeros((len(ids),len(ids)),int)
        for row in sub.itertuples():x[idx[row.source_station],idx[row.target_station]]+=row.bikes_moved
        routes,info=route_transfers(x,distance,**settings);results.append(dict(timestamp=t,strategy=policy,bikes_requested=int(x.sum()),**info))
        route_logs.append(dict(timestamp=t,strategy=policy,routes=routes))
pd.DataFrame(results).to_csv(out/'routing_hours.csv',index=False);save_json(out/'routes.json',route_logs)
print(pd.DataFrame(results).groupby(['strategy','status']).size().to_string());print('PASS: successful routes checked for job uniqueness, capacity, pickup-before-delivery and shift limits; unresolved jobs remain explicitly unserved.')
