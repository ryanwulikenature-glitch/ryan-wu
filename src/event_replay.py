"""Optional paired ride replay: rejected departures suppress their own returns.
External-origin arrivals are exogenous boundary inflows; blocked returns stay held
off dock through the horizon. Trips already underway at start are initialized as
in transit. This is a counterfactual sample-path scenario, not actual lost demand.
"""
import argparse
import heapq
from pathlib import Path
import numpy as np
import pandas as pd
from .common import ROOT,load_config,distances
from .optimize import plan,validate_moves
from .simulate import STRATEGIES

def replay(rides,predictions,stations,cfg,out=None,hours=None):
    rides=rides.copy();p=predictions.copy();p['hour']=pd.to_datetime(p.hour,utc=True)
    stations=stations.sort_values('station_id').reset_index(drop=True);ids=stations.station_id.astype(str).tolist();index={s:k for k,s in enumerate(ids)}
    rides['start']=pd.to_datetime(rides.start,utc=True);rides['end']=pd.to_datetime(rides.end,utc=True)
    if rides.ride_id.duplicated().any():raise ValueError('Duplicate ride IDs in paired replay')
    if (rides.end<=rides.start).any():raise ValueError('Invalid paired event times')
    times=sorted(p.hour.unique())[:hours or cfg['hours']]
    if not times:raise ValueError('No replay period')
    start=times[0];stop=times[-1]+pd.Timedelta(hours=1)
    if len(times)>1 and not pd.Series(times).diff().dropna().eq(pd.Timedelta(hours=1)).all():raise ValueError('Replay period must be contiguous')
    r=rides[(rides.start<stop)&(rides.end>=start)].copy()
    events=[];initial_transit=set()
    for row in r.itertuples():
        s=index.get(str(row.start_station_id));t=index.get(str(row.end_station_id))
        if s is None and t is None:continue
        rid=str(row.ride_id)
        if row.start<start:
            # Known observed ride underway at scenario initialization.
            initial_transit.add(rid)
        elif s is not None:events.append((row.start,1,rid,s,t))
        if row.end<stop:
            # Incoming external trips enter the modeled fleet at arrival time.
            events.append((row.end,0,rid,s,t))
    events.sort(key=lambda e:(e[0],e[1],e[2])) # Return before departure on equal timestamp.
    c=np.full(len(ids),int(cfg['capacity']));dist=distances(stations);rows=[];ledger=[]
    for strategy in STRATEGIES:
        inv=np.floor(c*cfg['initial_fraction']).astype(int);transit=set(initial_transit);held=set();rejected=set()
        initial=int(inv.sum())+len(transit);incoming=outgoing=0;cursor=0
        for hour in times:
            f=p[p.hour==hour].assign(station_id=lambda d:d.station_id.astype(str)).set_index('station_id').reindex(ids)
            if f[['pred_dep','pred_arr']].isna().any().any():raise ValueError('Incomplete forecasts')
            x,info=plan(strategy,inv,c,f.pred_dep.to_numpy(),f.pred_arr.to_numpy(),dist,cfg);inv=validate_moves(inv,c,x,dist,cfg)
            unmet=blocked=served=0
            while cursor<len(events) and events[cursor][0]<hour+pd.Timedelta(hours=1):
                stamp,kind,rid,s,t=events[cursor];cursor+=1
                if kind==1:
                    if inv[s]>0:inv[s]-=1;transit.add(rid);served+=1
                    else:unmet+=1;rejected.add(rid)
                else:
                    if rid in rejected:
                        ledger.append(dict(strategy=strategy,ride_id=rid,event='suppressed_return',timestamp=stamp));continue
                    if rid not in transit:
                        if s is not None:raise ValueError(f'Unmatched selected-origin return {rid}')
                        incoming+=1;transit.add(rid)
                    transit.remove(rid)
                    if t is None:outgoing+=1
                    elif inv[t]<c[t]:inv[t]+=1
                    else:held.add(rid);blocked+=1
                assert inv.sum()+len(transit)+len(held)==initial+incoming-outgoing
            rows.append(dict(timestamp=hour,strategy=strategy,unmet_departures=unmet,blocked_arrivals=blocked,served_departures=served,
                docked=int(inv.sum()),in_transit=len(transit),held_off_dock=len(held),boundary_incoming=incoming,boundary_outgoing=outgoing,
                initial_fleet=initial,accounted_fleet=int(inv.sum())+len(transit)+len(held),bikes_moved=int(x.sum()),bike_km=float((x*dist).sum()),**info))
    result=pd.DataFrame(rows)
    if out:
        out=Path(out);out.mkdir(parents=True,exist_ok=True);result.to_csv(out/'event_replay_hourly.csv',index=False)
        pd.DataFrame(ledger,columns=['strategy','ride_id','event','timestamp']).to_csv(out/'event_replay_ledger.csv',index=False)
    return result,pd.DataFrame(ledger)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--rides',type=Path,required=True);p.add_argument('--predictions',type=Path,required=True);p.add_argument('--stations',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--config');a=p.parse_args()
    replay(pd.read_parquet(a.rides),pd.read_csv(a.predictions,dtype={'station_id':str}),pd.read_csv(a.stations,dtype={'station_id':str}),load_config(a.config),a.out)
