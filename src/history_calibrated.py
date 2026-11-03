"""One-hour policy comparisons starting from fresh, measured historical stocks.
Hours reset to the common measured state: these are independent one-step
counterfactual assessments, not a continuous two-month fleet replay.
"""
import pandas as pd
import numpy as np
from .common import ROOT,load_config,save_json
from .history_sources import HISTORY
from .simulate import simulate
from .metrics import block_bootstrap

def history_grid(points,hours,ids,tolerance='15min'):
    points=points.copy();points['timestamp']=pd.to_datetime(points.timestamp,utc=True).astype('datetime64[ns, UTC]')
    grid=pd.MultiIndex.from_product([ids,hours],names=['station_id','hour']).to_frame(index=False)
    grid['hour']=pd.to_datetime(grid.hour,utc=True).astype('datetime64[ns, UTC]')
    if points.duplicated(['station_id','timestamp']).any():raise ValueError('Duplicate historical keys')
    joined=pd.merge_asof(grid.sort_values('hour'),points.sort_values('timestamp'),left_on='hour',right_on='timestamp',by='station_id',direction='backward',tolerance=pd.Timedelta(tolerance))
    joined['usable_capacity']=joined.bikes+joined.free
    joined['eligible']=joined.fresh.eq(True)&joined.valid_counts.eq(True)&(joined.renting==1)&(joined.returning==1)&joined.usable_capacity.gt(0)&joined.usable_capacity.le(joined.capacity)&joined.bikes.ge(0)&joined.free.ge(0)&joined.reported_at.le(joined.hour)&((joined.hour-joined.reported_at)<=pd.Timedelta(tolerance))
    return joined

def run():
    out=ROOT/'outputs/history_calibrated';out.mkdir(parents=True,exist_ok=True)
    st=pd.read_csv(ROOT/'data/processed/stations.csv',dtype={'station_id':str}).sort_values('station_id')
    p=pd.read_csv(ROOT/'outputs/official/test_predictions.csv.gz',dtype={'station_id':str});p['hour']=pd.to_datetime(p.hour,utc=True)
    f=pd.read_parquet(HISTORY/'processed/station_status_points.parquet')
    grid=history_grid(f,sorted(p.hour.unique()),st.station_id.tolist());grid.to_parquet(out/'asof_evidence.parquet',index=False)
    eligible=grid.groupby('hour').eligible.all();times=eligible[eligible].index
    if not len(times):raise ValueError('No common complete fresh historical initial states')
    cfg=load_config(ROOT/'configs/official_counts.json');hourly=[]
    for t in times:
        g=grid[grid.hour==t].set_index('station_id').reindex(st.station_id)
        localcfg=cfg|{'hours':1,'seed':cfg['seed']+int(t.timestamp()//3600)}
        _,h=simulate(p,st,localcfg,hours=1,start=t,initial_inventory=g.bikes.to_numpy(),capacities=g.usable_capacity.to_numpy())
        hourly.append(h)
    h=pd.concat(hourly,ignore_index=True);h.to_csv(out/'simulation_hourly.csv',index=False)
    cols=['departure_requests','arrival_events','unmet_departures','blocked_arrivals','bikes_moved','bike_km','scenario_objective']
    summary=h.groupby('strategy')[cols].sum().reset_index();summary['proxy_service_rate']=1-summary.unmet_departures/summary.departure_requests.replace(0,np.nan)
    summary['hours']=len(times);summary.to_csv(out/'simulation_summary.csv',index=False)
    h['day']=pd.to_datetime(h.timestamp,utc=True).dt.tz_convert(cfg['timezone']).dt.date
    daily=h.groupby(['day','strategy']).scenario_objective.sum().unstack();ci=[]
    for strategy,base in [('greedy','none'),('milp','none'),('milp','greedy')]:
        lo,hi=block_bootstrap(daily[strategy]-daily[base],cfg['seed']);ci.append(dict(strategy=strategy,baseline=base,ci_low=lo,ci_high=hi))
    pd.DataFrame(ci).to_csv(out/'uncertainty.csv',index=False)
    save_json(out/'protocol.json',dict(config=cfg,eligible_test_hours=len(times),total_test_hours=p.hour.nunique(),stations=len(st),max_age_minutes=15,
        initial_state='Most recent historical observation at or before hour; both row and source report at most 15 min old',
        capacity='Measured usable capacity = bikes+free at anchor; physical slots retained in evidence, disabled capacity excluded',
        assessment='Independent one-hour scenarios reset to measured state; same state across policies, no continuous causal claim',
        selection='All common fresh enabled hours, fixed criterion, not chosen by policy outcomes; event-sampling/daytime bias remains',
        unavailable='No heartbeat between count changes: operational flags cannot be assumed constant over archive gaps'))
    print(summary.to_csv(index=False));print('Measured common-state hours:',len(times))

if __name__=='__main__':run()
