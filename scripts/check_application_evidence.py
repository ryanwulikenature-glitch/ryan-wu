"""Independent reconciliation of evidence strata and the frozen 2026 holdout."""
import json,re,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import joblib,numpy as np,pandas as pd
from src.common import ROOT,save_json,sha256
from src.features import features
from src.metrics import forecast_metrics

out=ROOT/'outputs/coverage_audit';m=pd.read_csv(out/'forecast_metrics.csv');g=pd.read_parquet(out/'evidence_eligibility.parquet');summary=pd.read_csv(out/'threshold_coverage.csv')
assert summary.supported_start_states.is_monotonic_increasing
for age,frame in g.groupby('max_age_minutes'):
    assert len(frame)==43950 and not frame.duplicated(['station_id','hour']).any()
    e=frame[frame.eligible]
    for col in ['timestamp','reported_at']:assert (e[col]<=e.hour).all() and ((e.hour-e[col])<=pd.Timedelta(minutes=int(age))).all()
    for _,scores in m[m.max_age_minutes==age].groupby(['model','target']):
        a=scores.set_index('stratum');parts=a.loc[['start_state_supported','start_state_unsupported']]
        assert parts.n.sum()==a.loc['all_recorded_counts','n']==43950
        assert np.isclose((parts.mae*parts.n).sum()/parts.n.sum(),a.loc['all_recorded_counts','mae'])
for file in ['by_month.csv','by_hour.csv','by_station.csv']:
    f=pd.read_csv(out/file);assert f.station_hours.sum()==262800 and f.remaining_unsupported.sum()==19632

ext=ROOT/'outputs/external_202601';protocol=json.loads((ROOT/'configs/external_202601.json').read_text());v=json.loads((ext/'validation.json').read_text());pred=pd.read_parquet(ext/'predictions.parquet');panel=pd.read_parquet(ext/'panel.parquet');metrics=pd.read_csv(ext/'forecast_metrics.csv')
assert v['protocol']==protocol and v['model_hashes_unchanged'] and not v['models_refitted']
assert pd.Timestamp(v['source']['retrieved_utc'])>pd.Timestamp(protocol['frozen_utc'])
for name,digest in protocol['model_sha256'].items():assert sha256(ROOT/name)==digest
assert sha256(ROOT/'data/holdout/raw/202601-citibike-tripdata.zip')==v['source']['sha256']
assert len(pred)==len(panel)==22320 and pred.station_id.nunique()==30 and pred.hour.nunique()==744 and not pred.duplicated(['station_id','hour']).any()
assert panel.departures.sum()==v['departure_records'] and panel.arrivals.sum()==v['arrival_records']
start=pd.Timestamp(protocol['period_start']);old=pd.read_parquet(ROOT/'data/processed/panel.parquet');old=old[(old.hour>=start-pd.Timedelta(hours=168))&(old.hour<start)].copy()
for target in ['departures','arrivals']:old[target]=old['observed_'+target]
f=features(pd.concat([old[panel.columns],panel],ignore_index=True));f=f[f.hour>=start].reset_index(drop=True);pred=pred.sort_values(['station_id','hour']).reset_index(drop=True)
for target,prefix in [('departures','dep'),('arrivals','arr')]:
    assert np.array_equal(f[target],pred[target])
    assert np.array_equal(f[prefix+'_lag1'],pred[prefix+'_last_hour']) and np.array_equal(f[prefix+'_lag168'],pred[prefix+'_seasonal_naive'])
    for kind in ['poisson','xgboost']:assert np.allclose(np.maximum(0,joblib.load(ROOT/f'outputs/official/{target}_{kind}.joblib').predict(f)),pred[prefix+'_'+kind])
    for kind in ['last_hour','seasonal_naive','poisson','xgboost']:
        actual=forecast_metrics(pred[target],pred[prefix+'_'+kind]);row=metrics[(metrics.target==target)&(metrics.model==kind)&(metrics.stratum=='all')].iloc[0]
        assert all(np.isclose(actual[key],row[key]) for key in ['n','mae','rmse','wape'])
root=ROOT/'application';claims=pd.read_csv(root/'CLAIMS_AND_EVIDENCE.csv')
for evidence in claims.evidence:
    if not evidence.startswith('https://'):assert (ROOT/evidence).is_file()
for filename,expected in [('application/RESEARCH_BRIEF.pdf',2),('reports/technical_report.pdf',10)]:
    info=subprocess.check_output(['pdfinfo',str(ROOT/filename)],text=True);assert int(re.search(r'^Pages:\s+(\d+)',info,re.M).group(1))==expected
save_json(ROOT/'reports/validation/application_reconciled.json',dict(coverage_past_only_and_partition_accounting='passed',unknown_mask_total=19632,external_protocol_freeze_and_unchanged_models='passed',external_same_rows_baselines_and_all_metrics='passed',external_model_predictions_independently_recomputed='passed',external_station_hours=22320,claim_evidence_files='passed',research_brief_pages=2,technical_report_pages=10,directions=['financial engineering','data science','operations research'],personal_role='AI-assisted; editable claims must match actual contribution',not_claimed=['real operator gains','financial returns','peer-reviewed publication','complete historical state truth','long-term uptime']))
print('PASS: evidence partitions, frozen 2026 models/predictions/metrics, claim sources, two-page brief and ten-page report reconciled.')
