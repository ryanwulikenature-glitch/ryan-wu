import numpy as np
import pandas as pd
import pytest
from src.common import load_config
from src.simulate import simulate,play_hour,event_orders
from src.event_replay import replay

def inputs():
    hours=pd.date_range('2025-11-01 04:00',periods=48,tz='UTC',freq='h');stations=pd.DataFrame({'station_id':['A','B'],'latitude':[40.75,40.751],'longitude':[-73.99,-73.991]})
    p=pd.DataFrame([dict(station_id=s,hour=h,departures=8 if s=='A' else 2,arrivals=2 if s=='A' else 8,
                        pred_dep=8 if s=='A' else 2,pred_arr=2 if s=='A' else 8,dep_seasonal_naive=5,arr_seasonal_naive=5) for h in hours for s in ['A','B']])
    return p,stations

def test_count_simulation_fairness_reproducibility_and_accounting(tmp_path):
    p,s=inputs();cfg=load_config();cfg['hours']=48
    summary,h=simulate(p,s,cfg,tmp_path)
    assert h.groupby('timestamp').sample_hash.nunique().eq(1).all()
    assert (h.inventory_end==h.inventory_start+h.served_arrivals-h.served_departures).all()
    assert h[h.strategy=='none'].bikes_moved.sum()==0
    summary2,h2=simulate(p,s,cfg)
    stable=[c for c in h.columns if c!='runtime_ms'];pd.testing.assert_frame_equal(h[stable],h2[stable])
    trace=pd.read_csv(tmp_path/'inventory_trace.csv.gz');assert trace.inventory_end.between(0,25).all()
    assert len(summary)==3

def test_missing_hour_or_station_rejected():
    p,s=inputs();p=p.iloc[1:]
    with pytest.raises(ValueError,match='Incomplete'):simulate(p,s,load_config())

def test_event_order_common_and_balance():
    a=event_orders([5,10],[3,4],2025,1);b=event_orders([5,10],[3,4],2025,1)
    for x,y in zip(a,b):np.testing.assert_array_equal(x,y)
    inv,unmet,blocked,sd,sa=play_hour(np.array([0,2]),np.array([2,2]),[np.array([-1,1,-1]),np.array([1,-1])])
    assert unmet==1 and blocked==1 and inv.sum()==2+sa-sd

def test_paired_rejected_departure_cancels_return_and_external_balance(tmp_path):
    p,s=inputs();cfg=load_config();cfg.update(initial_fraction=0,budget=0,hours=1)
    start=p.hour.min()
    rides=pd.DataFrame([dict(ride_id='refused',start=start+pd.Timedelta(minutes=1),end=start+pd.Timedelta(minutes=10),start_station_id='A',end_station_id='B'),
                        dict(ride_id='external',start=start+pd.Timedelta(minutes=2),end=start+pd.Timedelta(minutes=11),start_station_id='OUT',end_station_id='A')])
    r,ledger=replay(rides,p,s,cfg,tmp_path)
    assert r.unmet_departures.eq(1).all() and r.docked.eq(1).all()
    assert (ledger.event=='suppressed_return').sum()==3
    assert (r.accounted_fleet==r.initial_fleet+r.boundary_incoming-r.boundary_outgoing).all()

def test_paired_held_return_and_initial_transit():
    p,s=inputs();cfg=load_config();cfg.update(initial_fraction=1,budget=0,hours=1)
    t=p.hour.min();rides=pd.DataFrame([dict(ride_id='underway',start=t-pd.Timedelta(minutes=5),end=t+pd.Timedelta(minutes=5),start_station_id='OUT',end_station_id='A')])
    r,_=replay(rides,p,s,cfg);assert r.blocked_arrivals.eq(1).all() and r.held_off_dock.eq(1).all()
    assert (r.accounted_fleet==r.initial_fleet).all()

def test_initial_outbound_transit_conservation():
    p,s=inputs();cfg=load_config();cfg.update(budget=0,hours=1)
    t=p.hour.min();rides=pd.DataFrame([dict(ride_id='outbound',start=t-pd.Timedelta(minutes=5),end=t+pd.Timedelta(minutes=5),start_station_id='A',end_station_id='OUT')])
    r,_=replay(rides,p,s,cfg)
    assert r.boundary_outgoing.eq(1).all()
    assert (r.accounted_fleet==r.initial_fleet-1).all()
