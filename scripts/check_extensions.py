"""Independent reconciliation of completed historical and extended experiments."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from src.common import ROOT,sha256,save_json
from src.geography import membership
from src.history_calibrated import history_grid
out=ROOT/'outputs';hist=ROOT/'data/historical';record=json.loads((out/'history_evidence/completion_evidence.json').read_text())
manifest=pd.read_csv(hist/'manifest.csv');assert len(manifest)==12
for row in manifest.itertuples():assert sha256(hist/'raw'/row.filename)==row.sha256
f=pd.read_parquet(hist/'processed/station_status_points.parquet');assert len(f)==record['historical_observations'] and not f.duplicated(['station_id','timestamp']).any()
assert f.timestamp.dt.year.eq(2025).all() and f.station_id.nunique()==30
assert not (f.valid_counts & ((f.bikes+f.free)>f.capacity)).any()
cap=pd.read_csv(hist/'processed/official_capacity_points.csv',dtype={'station_id':str});assert len(cap)==120 and cap.station_id.nunique()==30
assert pd.to_datetime(cap.observed_at,utc=True).dt.year.eq(2025).all()
raw=pd.read_parquet(ROOT/'data/processed/panel.parquet');enriched=pd.read_parquet(hist/'processed/panel_with_evidence.parquet')
assert int((enriched.active_flag==0).sum())==record['previous_unknown_remaining']
assert ((raw.active_flag==0)&(enriched.active_flag==1)).sum()==record['previous_unknown_recovered']==2
assert enriched.observed_departures.equals(raw.observed_departures) and enriched.observed_arrivals.equals(raw.observed_arrivals)
x=pd.read_csv(out/'history_evidence/unknown_hour_summary.csv');assert x.station_hours.sum()==19634
cal=pd.read_csv(out/'history_calibrated/simulation_hourly.csv');assert len(cal)==260*3
assert cal.groupby('timestamp').sample_hash.nunique().eq(1).all() and cal.groupby('timestamp').inventory_start.nunique().eq(1).all()
assert (cal.inventory_end==cal.inventory_start+cal.served_arrivals-cal.served_departures).all()
grid=pd.read_parquet(out/'history_calibrated/asof_evidence.parquet');eligible=grid[grid.eligible]
assert (eligible.timestamp<=eligible.hour).all() and (eligible.reported_at<=eligible.hour).all()
assert (eligible.hour-eligible.timestamp).le(pd.Timedelta(minutes=15)).all() and eligible.usable_capacity.le(eligible.capacity).all()
assert grid.groupby('hour').eligible.all().sum()==260
w=pd.read_csv(out/'weather/simulation_hourly.csv');b=pd.read_csv(out/'official/simulation_hourly.csv');assert w.sample_hash.tolist()==b.sample_hash.tolist()
we=pd.read_parquet(ROOT/'data/weather/forecast_features.parquet');assert we.forecast_reference_offset_hours.ge(24).all() and not we.isna().any().any()
d=pd.read_csv(out/'duration_sensitivity/forecast_metrics.csv');assert sorted(d.cutoff_minutes.unique())==[30,60,90,120,180,360]
base=pd.read_csv(out/'official/forecast_metrics.csv');base=base[(base.split=='test')&(base.stratum=='all')&(base.model=='xgboost')].set_index('target')
assert np.allclose(d[d.cutoff_minutes==180].set_index('target').loc[base.index,'mae'],base.mae)
s=pd.read_csv(out/'stochastic/hourly.csv');assert len(s)==48*4 and s.strategy.nunique()==4 and not s.fallback.any()
assert s.groupby('timestamp').requests.nunique().eq(1).all() and s.bikes_moved.le(12).all()
r=pd.read_csv(out/'routing/routing_hours.csv');assert len(r)==96 and r.served_jobs.le(r.total_jobs).all()
settings=json.loads((out/'routing/protocol.json').read_text())['resources'];routes=json.loads((out/'routing/routes.json').read_text())
for hour in routes:
 jobs=[]
 for truck in hour['routes']:
  assert truck['max_load']<=settings['truck_capacity'] and truck['driver_minutes']<=settings['shift_minutes']+1e-6
  jobs.extend(job['job'] for job in truck['jobs'])
 assert len(jobs)==len(set(jobs))
network=pd.read_parquet(ROOT/'data/network60/panel.parquet');assert len(network)==525600 and network.station_id.nunique()==60
st=pd.read_csv(ROOT/'data/network60/stations.csv',dtype={'station_id':str});assert membership(st,'data/geography/manhattan_official_26c.geojson').all()
h=pd.read_csv(out/'network60/simulation_hourly.csv');assert len(h)==336*3 and h.groupby('timestamp').sample_hash.nunique().eq(1).all()
assert (h.inventory_end==h.inventory_start+h.served_arrivals-h.served_departures).all()
save_json(ROOT/'reports/validation/extensions_reconciled.json',dict(historical_files_sha256='passed',historical_identity_time_and_bounds='passed',unsupported_hours_preserved='passed',historical_common_state_hours=260,weather_lead_and_common_paths='passed',duration_baseline_exact_match='passed',mpc_four_policy_common_requests='passed',routing_constraints_and_failures='passed',network60_polygons_and_accounting='passed'))
print('PASS: historical file hashes, IDs, years, as-of freshness, unknown masks, 260 common-state hours, weather paths, six cutoffs, MPC, routing and 60-site accounting independently reconciled.')
