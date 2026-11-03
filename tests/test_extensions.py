import itertools,json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from src.common import load_config
from src.history_evidence import crosswalk
from src.history_calibrated import history_grid
from src.stochastic import recursive_forecast,stochastic_plan
from src.optimize import validate_moves
from src.routing import route_transfers
from src.geography import membership

def test_historical_join_uses_past_fresh_states_and_microsecond_times():
    t=pd.Timestamp('2025-11-01T10:00Z');ts=pd.DatetimeIndex([t-pd.Timedelta(minutes=2),t+pd.Timedelta(minutes=1)]).as_unit('us')
    f=pd.DataFrame({'station_id':['A','A'],'timestamp':ts,'reported_at':ts,'bikes':[10,0],'free':[20,30],'capacity':[35,35],'fresh':[True,True],'valid_counts':[True,True],'renting':[1,1],'returning':[1,1]})
    g=history_grid(f,[t,t+pd.Timedelta(hours=1)],['A'])
    assert g.bikes.iloc[0]==10 and g.usable_capacity.iloc[0]==30 and g.eligible.iloc[0]
    assert not g.eligible.iloc[1]

def test_current_snapshot_cannot_become_historical(tmp_path):
    folder=tmp_path/'wayback';folder.mkdir()
    (folder/'station_information_20250101000000.json').write_text(json.dumps({'last_updated':int(pd.Timestamp('2026-01-01',tz='UTC').timestamp()),'data':{'stations':[]}}))
    st=pd.DataFrame({'station_id':['001'],'latitude':[40.75],'longitude':[-73.99]})
    with pytest.raises(ValueError,match='Not a 2025'):crosswalk(st,tmp_path)

def test_recursive_multihour_forecast_cannot_see_future_actuals():
    from types import SimpleNamespace
    ts=pd.date_range('2025-10-20',periods=172,tz='UTC',freq='h');t=ts[168]
    f=pd.DataFrame({'station_id':'A','hour':ts,'observed_departures':5,'observed_arrivals':3})
    class Model:
        def __init__(self,col,inc):self.col=col;self.inc=inc
        def predict(self,rows):return rows[self.col].to_numpy()+self.inc
    models={'departures':Model('dep_lag1',1),'arrivals':Model('arr_lag1',2)}
    p=recursive_forecast(f,t,models,['A']);f.loc[f.hour>=t,['observed_departures','observed_arrivals']]=1000000
    np.testing.assert_array_equal(p,recursive_forecast(f,t,models,['A']))
    np.testing.assert_array_equal(p[:,0,0],[6,7,8]);np.testing.assert_array_equal(p[:,0,1],[5,7,9])

def test_stochastic_single_scenario_matches_enumerated_inventory_dynamics():
    i=np.array([3,27,8]);c=np.array([30]*3);d=np.array([15,5,17]);a=np.array([2,3,3]);dist=np.array([[0,1,2],[1,0,1],[2,1,0]],float)
    cfg=load_config();cfg['budget']=3;mean=np.stack([d,a],axis=-1)[None,:,:]
    x,info=stochastic_plan(i,c,mean,mean[None,:,:,:],dist,cfg)
    values=[]
    for b0,b2 in itertools.product(range(4),repeat=2):
        if b0+b2>3:continue
        m=np.zeros((3,3),int);m[1,0]=b0;m[1,2]=b2;post=i+m.sum(axis=0)-m.sum(axis=1);raw=post+a-d;end=np.clip(raw,0,c)
        cost=5*(np.maximum(0,-raw).sum()+np.maximum(0,raw-c).sum())+2.5*(np.maximum(0,.3*c-end).sum()+np.maximum(0,end-.7*c).sum())+.1*(m*dist).sum();values.append(cost)
    assert not info['fallback'];assert info['planned_proxy_objective']==pytest.approx(min(values))
    validate_moves(i,c,x,dist,cfg,d,a)

def test_routes_split_jobs_and_preserve_capacity_and_shift():
    moves=np.zeros((3,3),int);moves[0,1]=7;dist=np.ones((3,3))-np.eye(3)
    routes,info=route_transfers(moves,dist,truck_capacity=6)
    assert info['served_jobs']==2 and info['total_truck_km']==pytest.approx(4)
    assert sum(j['bikes'] for r in routes for j in r['jobs'])==7
    assert all(r['max_load']<=6 and r['driver_minutes']<=60 for r in routes)

def test_infeasible_routes_not_presented_as_served():
    moves=np.array([[0,1],[0,0]]);dist=np.array([[0,1],[1,0]])
    routes,info=route_transfers(moves,dist,shift_minutes=0)
    assert not routes and info['served_jobs']==0 and info['status'].startswith('2:')

def test_polygon_holes_and_outside_points(tmp_path):
    path=tmp_path/'area.json';path.write_text(json.dumps({'type':'Feature','properties':{'boroname':'Manhattan'},'geometry':{'type':'Polygon','coordinates':[[[0,0],[10,0],[10,10],[0,10],[0,0]],[[4,4],[6,4],[6,6],[4,6],[4,4]]]}}))
    st=pd.DataFrame({'longitude':[1,5,11],'latitude':[1,5,11]})
    assert membership(st,path).tolist()==[True,False,False]

def test_impossible_counts_are_not_accepted_as_historical_initial_state():
    t=pd.Timestamp('2025-11-01T10:00Z')
    f=pd.DataFrame({'station_id':['A'],'timestamp':[t-pd.Timedelta(minutes=1)],'reported_at':[t-pd.Timedelta(minutes=1)],'bikes':[20],'free':[20],'capacity':[30],'fresh':[True],'valid_counts':[True],'renting':[1],'returning':[1]})
    assert not history_grid(f,[t],['A']).eligible.iloc[0]

def test_weather_lead_must_precede_prediction(tmp_path):
    from src.make_demo import make_demo
    from src.train import train
    data=tmp_path/'data';panel,_,cfg=make_demo(data,n=2)
    w=pd.DataFrame({'hour':panel.hour.drop_duplicates(),'forecast_reference_offset_hours':0,'temperature_2m_previous_day1':0,'precipitation_previous_day1':0,'wind_speed_10m_previous_day1':0})
    path=tmp_path/'weather.parquet';w.to_parquet(path,index=False);cfg['weather_file']=str(path)
    with pytest.raises(ValueError,match='horizon'):train(data,tmp_path/'out',cfg)
