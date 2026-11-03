"""Measured-anchor, paired-ride experiment with delayed co-loaded road trucks."""
import argparse,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
from src.common import ROOT,load_config,save_json,sha256
from src.transport_sim import simulate_transport

cli=argparse.ArgumentParser();cli.add_argument('--reuse-rides',action='store_true',help='Use hash-verified retained 48h ride slice from delivery instead of full clean partitions');args=cli.parse_args()
out=ROOT/'outputs/transport_service';out.mkdir(parents=True,exist_ok=True)
st=pd.read_csv(ROOT/'data/processed/stations.csv',dtype={'station_id':str}).sort_values('station_id')
source=json.loads((ROOT/'data/road_network/source.json').read_text())
if st.station_id.tolist()!=source['station_order']:raise ValueError('Road matrix station alignment differs')
roads=json.loads((ROOT/'data/road_network/osrm_table.json').read_text())
travel=np.asarray(roads['durations'],float);km=np.asarray(roads['distances'],float)/1000
grid=pd.read_parquet(ROOT/'outputs/history_calibrated/asof_evidence.parquet')
eligible=grid.groupby('hour').eligible.all();start=eligible[eligible].index.min()
if pd.isna(start):raise ValueError('No measured common initial state')
anchor=grid[grid.hour==start].set_index('station_id').reindex(st.station_id).reset_index()
assert anchor.eligible.all() and (anchor.timestamp<=start).all() and (anchor.reported_at<=start).all()
anchor.to_csv(out/'initial_state.csv',index=False)
hours=48;stop=start+pd.Timedelta(hours=hours)
p=pd.read_csv(ROOT/'outputs/official/test_predictions.csv.gz',dtype={'station_id':str});p['hour']=pd.to_datetime(p.hour,utc=True)
p=p[(p.hour>=start)&(p.hour<stop)];p.to_csv(out/'input_predictions.csv.gz',index=False)
# Resolve old absolute manifests against the current checkout for portability.
if args.reuse_rides:
    previous=json.loads((out/'protocol.json').read_text())
    assert pd.Timestamp(previous['start_utc'])==start and pd.Timestamp(previous['stop_utc'])==stop
    assert previous['input_rides_sha256']==sha256(out/'input_rides.parquet')
    rides=pd.read_parquet(out/'input_rides.parquet')
else:
    paths=json.loads((ROOT/'data/processed/clean_partitions.json').read_text())
    paths=[str(ROOT/'data/interim'/Path(path).name) for path in paths]
    dataset=ds.dataset(paths,format='parquet');ids=st.station_id.tolist()
    condition=((ds.field('start')<pa.scalar(stop))&(ds.field('end')>=pa.scalar(start))&
               (ds.field('start_station_id').isin(ids)|ds.field('end_station_id').isin(ids)))
    rides=dataset.to_table(filter=condition,columns=['ride_id','start','end','start_station_id','end_station_id']).to_pandas()
    rides.to_parquet(out/'input_rides.parquet',index=False)
cfg=load_config(ROOT/'configs/official_counts.json')|dict(trucks=2,truck_capacity=6,service_seconds_per_bike=90,driver_shift_seconds=28800,routing_search_ms=200)
print(f'{start} to {stop}: {len(rides):,} paired recorded rides, {hours} hours, {len(st)} stations',flush=True)
tick=time.monotonic()
h,events,routes,closing=simulate_transport(rides,p,st,cfg,travel,km,anchor.bikes,anchor.usable_capacity,hours=hours)
h.to_csv(out/'hourly.csv',index=False);pd.DataFrame(events).to_csv(out/'truck_events.csv',index=False);closing.to_csv(out/'closing.csv',index=False);save_json(out/'routes.json',routes)
metrics=['departure_requests','served_departures','unmet_departures','served_returns','blocked_arrivals','suppressed_returns','picked_bikes','delivered_bikes','failed_pickup_bikes','blocked_transfer_attempts','planned_bikes','unassigned_bikes','truck_km','bike_km','driver_seconds','flow_solver_fallbacks','route_solver_failures','dispatch_busy_skips','instant_bikes']
summary=pd.concat([h,closing]).groupby('strategy')[metrics].sum().reset_index()
summary['proxy_service_rate']=1-summary.unmet_departures/summary.departure_requests
summary['driver_hours']=summary.driver_seconds/3600
summary['proxy_cost']=cfg['shortage_weight']*summary.unmet_departures+cfg['overflow_weight']*summary.blocked_arrivals+cfg['distance_weight']*summary.bike_km
summary['resource_class']=summary.strategy.map(lambda x:'instantaneous resource relaxation' if x=='instant_milp_relaxation' else 'equal road-fleet scenario' if x.startswith('road_') else 'no intervention')
summary.to_csv(out/'summary.csv',index=False)
save_json(out/'protocol.json',dict(config=cfg,start_utc=start,stop_utc=stop,hours=hours,stations=len(st),paired_rides=len(rides),elapsed_seconds=time.monotonic()-tick,
 initial_state='First common test hour meeting predeclared fresh/valid/enabled <=15 min historical criterion; no selection by outcome',
 capacity='Observed bikes+free usable capacity at anchor; frozen for 48 h, not evidence of historical capacity/operating-state continuity',
 depot='Virtual depot colocated with first station in sorted ID order; not an observed operator depot',
 roads=source,road_matrix_sha256=sha256(ROOT/'data/road_network/osrm_table.json'),input_rides_sha256=sha256(out/'input_rides.parquet'),
 policy='Same fixed baseline forecasts and paired recorded-ride requests. MILP/greedy flow target -> optional unit-bike OR-Tools co-loaded pickup-delivery routing. New pickup budget 12/h; 2 x 6-bike trucks; directed driving time + 90 s/bike at pickup and delivery; return to depot within hour; <=8 active driver hours per fixed UTC eight-hour shift.',
 transport='No teleport: pickup at loading start subject to contemporaneous stock; delivery only after arrival+unloading subject to docks. Failed pickup not delivered; blocked transfer remains aboard assigned truck with mandatory retry. All en-route cargo counted. Empty deadhead truck km and load-weighted bike km both counted.',
 customer='Rejected recorded departures suppress paired returns; external arrivals exogenous; initially underway rides in initial fleet; blocked customer returns held off dock without retry.',
 event_order='At equal times: depot ready, customer returns, finished truck unloading, truck pickups, road departures, customer departures, dispatch. Hour boundaries use [start,end). Closing truck events reported separately.',
 interpretation='48 h counterfactual stress scenario; completed recorded trips are not total latent demand. Current OSM/OSRM driving proxy is not 2025 traffic or truck-specific routing. Heuristic routes certify checked feasibility, not global routing optimality. Instantaneous MILP reference has relaxed transport resources, not a fair equal-fleet competitor.',
 measured_history='No later inventory resets or future station-status inputs; missing 2025 operating states remain unknown; this scenario does not infer actual operator losses.'
))
print(summary.to_csv(index=False));print('PASS: event-level dock/truck bounds and complete fleet accounting',flush=True)
