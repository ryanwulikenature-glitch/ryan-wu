import numpy as np
import pandas as pd
from src.common import load_config
from src.pickup_delivery import plan_routes
from src.transport_sim import simulate_transport

def test_co_loading_routing_respects_capacity_and_precedence():
    d=np.array([[0,100,200],[100,0,100],[200,100,0]],float);jobs=[dict(job_id=f'j{k}',source=0,target=2,quantity=1) for k in range(3)]
    routes,info=plan_routes(jobs,[[]],d,d/1000,capacity=3,service_seconds_per_bike=10,search_ms=100)
    assert info['assigned']==3 and len(routes)==1
    r=routes[0];assert r['max_planned_load']==3 and r['driver_seconds']<=3600
    for job in jobs:
        v=[x for x in r['visits'] if x['job_id']==job['job_id']];assert [x['kind'] for x in v]==['pickup','delivery']
        assert v[1]['arrival_seconds']>=v[0]['arrival_seconds']+v[0]['service_seconds']

def test_existing_cargo_assigned_to_its_real_truck():
    d=np.array([[0,100],[100,0]],float);held=[[dict(job_id='carried',target=1,quantity=2)],[]]
    routes,info=plan_routes([],held,d,d/1000,capacity=2,service_seconds_per_bike=10)
    assert len(routes)==1 and routes[0]['truck']==0 and routes[0]['max_planned_load']==2

def test_infeasible_new_orders_are_dropped_not_executed():
    d=np.array([[0,10000],[10000,0]],float)
    routes,info=plan_routes([dict(job_id='far',source=0,target=1,quantity=1)],[[]],d,d/1000,max_seconds=60,search_ms=100)
    assert info['assigned']==0 and info['unassigned']==1 and not routes

def test_pickup_races_and_transport_delay_affect_service_and_fleet_balance():
    start=pd.Timestamp('2025-11-01T04:00Z');st=pd.DataFrame({'station_id':['A','B'],'latitude':[40.75,40.751],'longitude':[-73.99,-73.991]})
    p=pd.DataFrame([{'station_id':sid,'hour':start+pd.Timedelta(hours=h),'pred_dep':0 if sid=='A' else 8,'pred_arr':0} for h in range(2) for sid in ['A','B']])
    # A customer wants the only bike before a ten-minute road delivery can arrive at B.
    rides=pd.DataFrame([dict(ride_id='early',start=start+pd.Timedelta(minutes=1),end=start+pd.Timedelta(minutes=6),start_station_id='B',end_station_id='A'),dict(ride_id='later',start=start+pd.Timedelta(minutes=20),end=start+pd.Timedelta(minutes=25),start_station_id='A',end_station_id='B')])
    cfg=load_config();cfg.update(budget=1,trucks=1,truck_capacity=1,service_seconds_per_bike=30,routing_search_ms=100)
    travel=np.array([[0,600],[600,0]],float);km=np.array([[0,1],[1,0]],float)
    h,logs,routes,closing=simulate_transport(rides,p,st,cfg,travel,km,[2,0],[2,2],hours=2)
    first=h[h.timestamp==start].set_index('strategy')
    assert first.loc['instant_milp_relaxation','unmet_departures']==0
    assert first.loc['road_milp','unmet_departures']==1
    assert first.loc['road_milp','truck_km']>0
    assert (h.accounted_fleet==h.initial_fleet+h.boundary_incoming-h.boundary_outgoing).all()
    assert (closing.accounted_fleet==closing.initial_fleet+closing.boundary_incoming-closing.boundary_outgoing).all()
    delivered=[x for x in logs if x['strategy']=='road_milp' and x['event']=='delivery_after_unload' and x['actual']]
    assert delivered and min(x['timestamp'] for x in delivered)>=start+pd.Timedelta(seconds=660)
    for policy in h.strategy.unique():assert h[h.strategy==policy].departure_requests.sum()==2

def test_customers_can_consume_stock_before_truck_pickup():
    start=pd.Timestamp('2025-11-01T04:00Z');st=pd.DataFrame({'station_id':['A','B','C']})
    p=pd.DataFrame([dict(station_id=sid,hour=start+pd.Timedelta(hours=h),pred_dep=8 if sid=='C' else 0,pred_arr=2 if sid=='A' else 0) for h in range(2) for sid in st.station_id])
    rides=pd.DataFrame([dict(ride_id=f'r{k}',start=start+pd.Timedelta(minutes=k),end=start+pd.Timedelta(minutes=k+5),start_station_id='B',end_station_id='external') for k in [1,2]])
    cfg=load_config()|dict(budget=1,trucks=1,truck_capacity=1,service_seconds_per_bike=30,routing_search_ms=100)
    travel=np.full((3,3),600.);np.fill_diagonal(travel,0);km=np.where(travel>0,1.,0.)
    h,events,_,closing=simulate_transport(rides,p,st,cfg,travel,km,[0,2,0],[2,2,2],hours=2)
    road=h[h.strategy=='road_milp'];assert road.failed_pickup_bikes.sum()==1 and road.delivered_bikes.sum()==0
    assert any(x['event']=='pickup' and x['requested']==1 and x['actual']==0 for x in events if x['strategy']=='road_milp')
    assert (closing.accounted_fleet==closing.initial_fleet+closing.boundary_incoming-closing.boundary_outgoing).all()

def test_blocked_truck_cargo_stays_aboard_and_is_delivered_on_retry():
    start=pd.Timestamp('2025-11-01T04:00Z');st=pd.DataFrame({'station_id':['A','B']})
    p=pd.DataFrame([dict(station_id=sid,hour=start+pd.Timedelta(hours=h),pred_dep=5 if sid=='B' else 0,pred_arr=0) for h in range(2) for sid in st.station_id])
    rides=pd.DataFrame([dict(ride_id='external',start=start+pd.Timedelta(minutes=1),end=start+pd.Timedelta(minutes=5),start_station_id='external',end_station_id='B'),dict(ride_id='opens_dock',start=start+pd.Timedelta(minutes=70),end=start+pd.Timedelta(minutes=75),start_station_id='B',end_station_id='A')])
    cfg=load_config()|dict(budget=1,trucks=1,truck_capacity=1,service_seconds_per_bike=30,routing_search_ms=100)
    travel=np.array([[0,600],[600,0]],float);km=np.array([[0,1],[1,0]],float)
    h,events,_,closing=simulate_transport(rides,p,st,cfg,travel,km,[2,0],[2,1],hours=2)
    road=h[h.strategy=='road_milp'].reset_index(drop=True)
    assert road.loc[0,'truck_stock_end']==1 and road.loc[0,'blocked_transfer_attempts']==1
    assert road.loc[1,'truck_stock_start']==1 and road.loc[1,'delivered_bikes']==1
    assert closing.set_index('strategy').loc['road_milp','truck_stock']==0
    deliveries=[x for x in events if x['strategy']=='road_milp' and x['event']=='delivery_after_unload']
    assert [x['actual'] for x in deliveries]==[0,1] and deliveries[0]['job']==deliveries[1]['job']
