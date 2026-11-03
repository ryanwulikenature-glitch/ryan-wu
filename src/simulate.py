"""Explicitly hourly count-based scenario simulation, NOT historical service loss."""
import argparse
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from .common import ROOT,load_config,distances,save_json
from .optimize import plan,validate_moves
from .metrics import change,block_bootstrap

STRATEGIES=['none','greedy','milp']

def event_orders(dep,arr,seed,hour_index):
    # Per-hour immutable sample path reused for all policies; separate RNG from optimization.
    rng=np.random.default_rng(np.random.SeedSequence([seed,hour_index]))
    return [rng.permutation(np.r_[-np.ones(int(d),dtype=np.int8),np.ones(int(a),dtype=np.int8)]) for d,a in zip(dep,arr)]

def play_hour(inventory,capacity,orders):
    inv=inventory.copy();unmet=blocked=served_dep=served_arr=0
    for s,events in enumerate(orders):
        for event in events:
            if event<0:
                if inv[s]>0:inv[s]-=1;served_dep+=1
                else:unmet+=1
            else:
                if inv[s]<capacity[s]:inv[s]+=1;served_arr+=1
                else:blocked+=1
    assert inv.sum()==inventory.sum()+served_arr-served_dep
    return inv,unmet,blocked,served_dep,served_arr

def simulate(predictions,stations,cfg,out=None,forecast='selected',start=None,hours=None,initial_inventory=None,capacities=None):
    p=predictions.copy();p['station_id']=p.station_id.astype(str);p['hour']=pd.to_datetime(p.hour,utc=True)
    st=stations.copy();st['station_id']=st.station_id.astype(str);st=st.sort_values('station_id').reset_index(drop=True)
    if p.duplicated(['station_id','hour']).any():raise ValueError('Duplicate predictions')
    times=sorted(p.hour.unique());times=[t for t in times if start is None or t>=pd.Timestamp(start)]
    times=times[:hours or cfg['hours']]
    if not times:raise ValueError('No simulation hours')
    if len(times)>1 and not pd.Series(times).diff().dropna().eq(pd.Timedelta(hours=1)).all():raise ValueError('Simulation needs contiguous UTC hours; missing observations must not be silently replayed')
    n=len(st);c=np.full(n,int(cfg['capacity'])) if capacities is None else np.asarray(capacities)
    if c.shape!=(n,) or not np.isfinite(c).all() or (c<=0).any() or not np.equal(c,np.rint(c)).all():raise ValueError('Invalid capacity vector')
    c=c.astype(int);dist=distances(st)
    if not 0<=cfg['initial_fraction']<=1:raise ValueError('Initial fraction must be in [0,1]')
    if cfg.get('event_order')!='random_interleaved':raise ValueError('Only declared random_interleaved event order is supported')
    initial=np.floor(c*cfg['initial_fraction']).astype(int) if initial_inventory is None else np.asarray(initial_inventory)
    if initial.shape!=(n,) or not np.isfinite(initial).all() or (initial<0).any() or (initial>c).any() or not np.equal(initial,np.rint(initial)).all():raise ValueError('Invalid initial inventory vector')
    inventories={s:initial.astype(int).copy() for s in STRATEGIES}
    hourly=[];moves_log=[];inventory_log=[]
    for h,t in enumerate(times):
        frame=p[p.hour==t].set_index('station_id').reindex(st.station_id)
        if frame[['departures','arrivals']].isna().any().any():raise ValueError(f'Incomplete station-hour at {t}; provide verified operating calendar or choose complete period')
        dep=frame.departures.to_numpy();arr=frame.arrivals.to_numpy()
        if (dep<0).any() or (arr<0).any() or not np.equal(dep,np.rint(dep)).all() or not np.equal(arr,np.rint(arr)).all():raise ValueError('Scenario counts must be nonnegative integers')
        if forecast=='oracle':pdhat,pahat=dep,arr
        elif forecast=='selected':pdhat,pahat=frame.pred_dep.to_numpy(),frame.pred_arr.to_numpy()
        elif forecast=='dep_only':pdhat,pahat=frame.pred_dep.to_numpy(),frame.arr_seasonal_naive.to_numpy()
        else:pdhat,pahat=frame[f'dep_{forecast}'].to_numpy(),frame[f'arr_{forecast}'].to_numpy()
        orders=event_orders(dep,arr,cfg['seed'],h)
        sample_hash=hashlib.sha256(b'|'.join(e.tobytes() for e in orders)).hexdigest()
        for strategy in STRATEGIES:
            before=inventories[strategy];x,info=plan(strategy,before,c,pdhat,pahat,dist,cfg)
            post=validate_moves(before,c,x,dist,cfg,pdhat,pahat)
            end,unmet,blocked,sd,sa=play_hour(post,c,orders);inventories[strategy]=end
            moved=int(x.sum());bike_km=float((x*dist).sum())
            hourly.append(dict(timestamp=t,strategy=strategy,departure_requests=int(dep.sum()),arrival_events=int(arr.sum()),
                 unmet_departures=unmet,blocked_arrivals=blocked,served_departures=sd,served_arrivals=sa,
                 bikes_moved=moved,bike_km=bike_km,scenario_objective=cfg['shortage_weight']*unmet+cfg['overflow_weight']*blocked+cfg['distance_weight']*bike_km,
                 sample_hash=sample_hash,inventory_start=int(before.sum()),inventory_end=int(end.sum()),**info))
            for s,target in np.argwhere(x>0):moves_log.append(dict(timestamp=t,strategy=strategy,source_station=st.station_id.iloc[s],target_station=st.station_id.iloc[target],bikes_moved=int(x[s,target]),distance_km=dist[s,target],**info))
            for k,sid in enumerate(st.station_id): inventory_log.append(dict(timestamp=t,strategy=strategy,station_id=sid,inventory_before=int(before[k]),inventory_post_move=int(post[k]),inventory_end=int(end[k]),capacity=int(c[k])))
    hourly=pd.DataFrame(hourly);summary=hourly.groupby('strategy',sort=False)[['departure_requests','arrival_events','unmet_departures','blocked_arrivals','bikes_moved','bike_km','scenario_objective']].sum().reset_index()
    summary['proxy_service_rate']=1-summary.unmet_departures/summary.departure_requests.replace(0,np.nan)
    runtime=hourly.groupby('strategy').agg(mean_runtime_ms=('runtime_ms','mean'),fallback_hours=('fallback','sum'))
    summary=summary.merge(runtime,on='strategy');summary['data_kind']=cfg['data_kind'];summary['simulation_kind']='hourly count-based scenario simulation';summary['hours']=len(times)
    compare=[];uncertainty=[]
    hourly['day']=pd.to_datetime(hourly.timestamp,utc=True).dt.tz_convert(cfg['timezone']).dt.date
    for strategy in ['greedy','milp']:
        for base in ['none']+(['greedy'] if strategy=='milp' else []):
            for metric in ['unmet_departures','blocked_arrivals','bike_km','scenario_objective','proxy_service_rate']:
                v=float(summary.set_index('strategy').loc[strategy,metric]);b=float(summary.set_index('strategy').loc[base,metric]);absolute,relative=change(v,b)
                compare.append(dict(strategy=strategy,baseline=base,metric=metric,absolute_difference=absolute,relative_change=relative))
            daily=hourly.groupby(['day','strategy']).scenario_objective.sum().unstack()
            lo,hi=block_bootstrap(daily[strategy]-daily[base],cfg['seed'])
            uncertainty.append(dict(strategy=strategy,baseline=base,metric='daily_scenario_objective_difference',days=len(daily),ci_low=lo,ci_high=hi,method='paired local-day block bootstrap; scenario uncertainty only'))
    if out is not None:
        out=Path(out);out.mkdir(parents=True,exist_ok=True)
        hourly.to_csv(out/'simulation_hourly.csv',index=False);summary.to_csv(out/'simulation_summary.csv',index=False)
        pd.DataFrame(moves_log,columns=['timestamp','strategy','source_station','target_station','bikes_moved','distance_km','solver_status','fallback','runtime_ms','proxy_objective']).to_csv(out/'moves.csv',index=False)
        pd.DataFrame(inventory_log).to_csv(out/'inventory_trace.csv.gz',index=False)
        pd.DataFrame(compare).to_csv(out/'policy_comparison.csv',index=False);pd.DataFrame(uncertainty).to_csv(out/'uncertainty_summary.csv',index=False)
        save_json(out/'simulation_config.json',dict(config=cfg,forecast=forecast,start=str(times[0]),hours=len(times),station_order=st.station_id.tolist(),initial_inventory=initial.tolist(),capacities=c.tolist(),
                 boundary='arrivals exogenous; no ride-level causal interpretation',versions='see training_config.json'))
    return summary,hourly

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--predictions',type=Path,default=ROOT/'outputs/official/test_predictions.csv.gz');p.add_argument('--stations',type=Path,default=ROOT/'data/processed/stations.csv');p.add_argument('--out',type=Path,default=ROOT/'outputs/official');p.add_argument('--hours',type=int);p.add_argument('--budget',type=int);p.add_argument('--capacity',type=int);p.add_argument('--radius-km',type=float);p.add_argument('--forecast',default='selected');a=p.parse_args();cfg=load_config(a.config)
    for key in ['hours','budget','capacity','radius_km']:
        if getattr(a,key) is not None:cfg[key]=getattr(a,key)
    simulate(pd.read_csv(a.predictions,dtype={'station_id':str}),pd.read_csv(a.stations,dtype={'station_id':str}),cfg,a.out,a.forecast)
