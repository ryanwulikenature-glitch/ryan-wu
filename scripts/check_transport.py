"""Reconcile saved road routes, actual cargo events and service/fleet outputs."""
import json,sys,math
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from src.common import ROOT,save_json,sha256
o=ROOT/'outputs/transport_service'
p=json.loads((o/'protocol.json').read_text());cfg=p['config'];routes=json.loads((o/'routes.json').read_text())
h=pd.read_csv(o/'hourly.csv');closing=pd.read_csv(o/'closing.csv');s=pd.read_csv(o/'summary.csv').set_index('strategy')
e=pd.read_csv(o/'truck_events.csv');e['timestamp']=pd.to_datetime(e.timestamp,utc=True)
a=pd.read_csv(o/'initial_state.csv',dtype={'station_id':str});anchor=pd.Timestamp(p['start_utc'])
roads=json.loads((ROOT/'data/road_network/osrm_table.json').read_text());travel=np.asarray(roads['durations']);km=np.asarray(roads['distances'])/1000
assert sha256(ROOT/'data/road_network/osrm_table.json')==p['road_matrix_sha256']
assert a.eligible.all() and (pd.to_datetime(a.timestamp,utc=True)<=anchor).all() and (pd.to_datetime(a.reported_at,utc=True)<=anchor).all()
assert ((anchor-pd.to_datetime(a.reported_at,utc=True))<=pd.Timedelta(minutes=15)).all()
assert (a.bikes+a.free==a.usable_capacity).all() and (a.usable_capacity<=a.capacity).all()
assert len(h)==p['hours']*4 and h.groupby('timestamp').departure_requests.nunique().eq(1).all()
for frame in [h,closing]:assert (frame.accounted_fleet==frame.initial_fleet+frame.boundary_incoming-frame.boundary_outgoing).all()
assert h.picked_bikes.le(cfg['budget']).all() and h.planned_bikes.le(cfg['budget']).all()
counts=['departure_requests','served_departures','unmet_departures','blocked_arrivals','picked_bikes','delivered_bikes','truck_km','bike_km','driver_seconds']
assert np.allclose(pd.concat([h,closing]).groupby('strategy')[counts].sum().loc[s.index],s[counts])
assert np.allclose(s.served_departures+s.unmet_departures,s.departure_requests)
keys=['timestamp','strategy','truck','job','event'];expected_events=[];work={};totals={};routecount=0
for hour in routes:
 stamp=pd.Timestamp(hour['timestamp']);strategy=hour['strategy'];assigned=0
 for route in hour['routes']:
  routecount+=1;k=route['truck'];assert 0<=k<cfg['trucks'];assert route['end_load']==0
  load=route['initial_load'];maxload=load;visits=route['visits'];legs=route['legs'];assert len(legs)==len(visits)+1
  assert legs[0]['source']==0 and legs[-1]['target']==0 and legs[0]['depart_seconds']==0
  for j,leg in enumerate(legs):
   assert math.isclose(leg['km'],km[leg['source'],leg['target']])
   assert leg['arrival_seconds']==leg['depart_seconds']+math.ceil(travel[leg['source'],leg['target']])
   if j<len(visits):
    v=visits[j];assert leg['target']==v['station'] and leg['arrival_seconds']==v['arrival_seconds']
    assert v['service_seconds']==math.ceil(v['quantity']*cfg['service_seconds_per_bike'])
    assert legs[j+1]['source']==v['station'] and legs[j+1]['depart_seconds']==v['arrival_seconds']+v['service_seconds']
    if v['kind']=='pickup':load+=v['quantity'];assigned+=1;at=stamp+pd.Timedelta(seconds=v['arrival_seconds']);event='pickup'
    else:load-=v['quantity'];at=stamp+pd.Timedelta(seconds=v['arrival_seconds']+v['service_seconds']);event='delivery_after_unload'
    assert 0<=load<=cfg['truck_capacity'];maxload=max(maxload,load)
    expected_events.append((at,strategy,k,v['job_id'],event))
  assert load==0 and maxload==route['max_planned_load'] and route['driver_seconds']==legs[-1]['arrival_seconds']<=3600
  shift=int(stamp.timestamp()//cfg['driver_shift_seconds']);key=(strategy,k,shift);work[key]=work.get(key,0)+route['driver_seconds'];assert work[key]<=cfg['driver_shift_seconds']
  totals.setdefault(strategy,[0.,0.]);totals[strategy][0]+=sum(x['km'] for x in legs);totals[strategy][1]+=route['driver_seconds']
 assert assigned==hour['status']['assigned'] and assigned+hour['status']['unassigned']==hour['status']['requested']
actual=e[e.event.isin(['pickup','delivery_after_unload'])]
assert Counter(expected_events)==Counter(actual[keys].itertuples(index=False,name=None))
assert actual.stock_after.between(0,actual.capacity).all() and actual.actual.between(0,actual.requested).all()
for (strategy,truck),events in e.groupby(['strategy','truck'],sort=False):
 cargo=0;jobs={}
 for row in events.sort_values('timestamp',kind='stable').itertuples():
  if row.event=='pickup':cargo+=int(row.actual);jobs[row.job]=jobs.get(row.job,0)+int(row.actual)
  elif row.event=='delivery_after_unload':
   assert jobs.get(row.job,0)>=row.actual;jobs[row.job]-=int(row.actual);cargo-=int(row.actual)
  assert cargo==row.cargo_after and 0<=cargo<=cfg['truck_capacity']
 assert cargo==sum(jobs.values())
for strategy,(dist,seconds) in totals.items():
 log=e[(e.strategy==strategy)&(e.event=='road_departure')]
 assert math.isclose(dist,s.loc[strategy,'truck_km']) and math.isclose(seconds,s.loc[strategy,'driver_seconds'])
 assert math.isclose(log.km.sum(),dist) and math.isclose((log.km*log.cargo_after).sum(),s.loc[strategy,'bike_km'])
 for event,col in [('pickup','picked_bikes'),('delivery_after_unload','delivered_bikes')]:assert e[(e.strategy==strategy)&(e.event==event)].actual.sum()==s.loc[strategy,col]
rides=pd.read_parquet(o/'input_rides.parquet');assert len(rides)==p['paired_rides'] and rides.ride_id.is_unique
assert sha256(o/'input_rides.parquet')==p['input_rides_sha256']
prediction=pd.read_csv(o/'input_predictions.csv.gz',dtype={'station_id':str});base=pd.read_csv(ROOT/'outputs/official/test_predictions.csv.gz',dtype={'station_id':str})
base=base[(pd.to_datetime(base.hour,utc=True)>=anchor)&(pd.to_datetime(base.hour,utc=True)<pd.Timestamp(p['stop_utc']))]
pd.testing.assert_frame_equal(prediction.reset_index(drop=True),base.reset_index(drop=True))
save_json(ROOT/'reports/validation/transport_reconciled.json',dict(routes=routecount,paired_rides=len(rides),hours=p['hours'],stations=p['stations'],road_time_distance_service_and_depot='passed',planned_and_actual_truck_capacity='passed',pickup_before_delivery_and_actual_quantities='passed',hourly_budget_and_driver_shifts='passed',same_requests_baseline_forecasts_and_historical_anchor='passed',fleet_balance_including_enroute_cargo='passed',truck_km_and_load_weighted_bike_km='passed',all_negative_results_retained=True))
print(f'PASS: {routecount} directed road routes; actual cargo/arrival/unloading times, truck/driver/budget bounds, common requests, historic anchor, fleet and transport ledgers reconciled.')
