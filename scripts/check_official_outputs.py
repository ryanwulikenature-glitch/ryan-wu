import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
from src.common import ROOT,save_json
out=ROOT/'outputs/official';data=ROOT/'data/processed'
quality=json.loads((data/'data_quality_summary.json').read_text());assert quality['months']==list(range(1,13))
manifest=pd.read_csv(data.parent/'interim/download_manifest.csv');assert len(manifest)==12
assert len(set(manifest.month))==12 and manifest.sha256.str.len().eq(64).all()
panel=pd.read_parquet(data/'panel.parquet');assert len(panel)==262800
paths=json.loads((data/'clean_partitions.json').read_text());rides=ds.dataset(paths,format='parquet')
assert rides.count_rows()==quality['retained_rides']
ids=pd.read_csv(data/'stations.csv',dtype={'station_id':str}).station_id.tolist()
begin=pa.scalar(pd.Timestamp('2025-01-01',tz='America/New_York').tz_convert('UTC'))
end=pa.scalar(pd.Timestamp('2026-01-01',tz='America/New_York').tz_convert('UTC'))
for target,station,time in [('departures','start_station_id','start'),('arrivals','end_station_id','end')]:
 condition=ds.field(station).isin(ids)&(ds.field(time)>=begin)&(ds.field(time)<end)
 assert rides.count_rows(filter=condition)==int(panel[f'observed_{target}'].sum()),'Raw cleaned endpoint conservation failed'
p=pd.read_csv(out/'test_predictions.csv.gz');assert len(p)==43950 and not p.duplicated(['station_id','hour']).any()
assert np.isfinite(p[['pred_dep','pred_arr']]).all().all() and (p[['pred_dep','pred_arr']]>=0).all().all()
h=pd.read_csv(out/'simulation_hourly.csv');assert len(h)==1465*3 and h.groupby('timestamp').sample_hash.nunique().eq(1).all()
assert (h.inventory_end==h.inventory_start+h.served_arrivals-h.served_departures).all()
trace=pd.read_csv(out/'inventory_trace.csv.gz');assert trace.inventory_end.between(0,25).all() and trace.inventory_post_move.between(0,25).all()
e=pd.read_csv(out/'experiments/experiments.csv');assert e.status.eq('completed').all() and e.experiment.nunique()==21
for metric in ['unmet_departures','blocked_arrivals','bikes_moved','bike_km','scenario_objective']:
 s=pd.read_csv(out/'simulation_summary.csv').set_index('strategy')[metric]
 assert np.allclose(h.groupby('strategy')[metric].sum().reindex(s.index),s)
r=pd.read_csv(out/'paired_events/event_replay_hourly.csv');assert len(r)==1465*3
assert (r.accounted_fleet==r.initial_fleet+r.boundary_incoming-r.boundary_outgoing).all()
save_json(ROOT/'reports/validation/official_run_evidence.json',dict(raw_months=12,raw_rows=quality['raw_rows'],
 retained_rides=quality['retained_rides'],stations=30,panel_rows=len(panel),unknown_operating_hours=quality['unknown_hours'],
 test_station_hours=len(p),test_hours=1465,policies=3,sensitivity_scenarios=21,sensitivity_hours=48,
 count_scenario_station_balance='passed',paired_event_fleet_conservation='passed',
 observation_mode='recorded event counts; unknown station operation not reclassified as active',
 solver_fallback_hours=int(h.fallback.sum())))
print('PASS: 12 official months, 30 stations, 43,950 test station-hours; full 1,465-hour count and paired-event scenarios, 21 sensitivity scenarios, inventory bounds, accounting, shared sample paths and saved-summary reconciliation.')
