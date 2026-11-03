"""Verify generated outputs and reproducibility independently of their presentation."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
root=Path(__file__).resolve().parents[1];out=root/'outputs/demo'
p=pd.read_csv(out/'test_predictions.csv.gz');assert len(p)==43950
assert not p.duplicated(['station_id','hour']).any()
assert (p[['pred_dep','pred_arr']]>=0).all().all()
h=pd.read_csv(out/'simulation_hourly.csv');s=pd.read_csv(out/'simulation_summary.csv')
assert len(h)==336*3 and h.groupby('timestamp').sample_hash.nunique().eq(1).all()
assert (h.inventory_end==h.inventory_start+h.served_arrivals-h.served_departures).all()
assert s.data_kind.eq('synthetic').all() and s.fallback_hours.eq(0).all()
for row in s.itertuples():
    actual=h[h.strategy==row.strategy]
    for metric in ['departure_requests','unmet_departures','blocked_arrivals','bikes_moved','bike_km','scenario_objective']:
        assert np.isclose(actual[metric].sum(),getattr(row,metric))
e=pd.read_csv(out/'experiments/experiments.csv');assert e.status.eq('completed').all()
assert e.experiment.nunique()==21 and len(e)==63
assert len(list((out/'figures').glob('*.png')))>=12
# Hash deterministic numeric outputs, excluding measured runtime.
stable=h.drop(columns=['runtime_ms','solver_status']).to_csv(index=False,float_format='%.10g').encode()
fingerprint=hashlib.sha256(stable).hexdigest();path=root/'reports/validation/simulation_fingerprint.json'
if path.exists():assert json.loads(path.read_text())['sha256']==fingerprint,'Re-run changed deterministic simulation output'
else:path.write_text(json.dumps({'sha256':fingerprint,'excludes':['runtime_ms','solver_status']},indent=2))
print(f'PASS: {len(p)} test station-hours; 3 x 336 simulated hours; 21 x 3 sensitivity runs; accounting, alignment, generated report inputs and repeatability fingerprint verified.')
print('Synthetic outputs only; official dataset not validated.')
