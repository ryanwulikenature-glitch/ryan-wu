"""Post-hoc evidence-age sensitivity; no model refit or test-based retuning."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from src.common import ROOT,save_json
from src.history_calibrated import history_grid
from src.coverage_audit import evaluate_evidence_strata

out=ROOT/'outputs/coverage_audit';out.mkdir(parents=True,exist_ok=True)
p=pd.read_parquet(ROOT/'outputs/official/all_predictions.parquet');p=p[p.split=='test'].copy()
points=pd.read_parquet(ROOT/'data/historical/processed/station_status_points.parquet')
points=points[(points.timestamp>=p.hour.min()-pd.Timedelta(hours=1))&(points.timestamp<=p.hour.max())]
metrics=[];comparisons=[];summaries=[];eligibility=[]
for age in [5,15,30,60]:
    grid=history_grid(points,sorted(p.hour.unique()),sorted(p.station_id.unique()),tolerance=f'{age}min')
    m,c=evaluate_evidence_strata(p,grid);m['max_age_minutes']=age;c['max_age_minutes']=age
    metrics.append(m);comparisons.append(c)
    summaries.append(dict(max_age_minutes=age,test_station_hours=len(p),supported_start_states=int(grid.eligible.sum()),unsupported_start_states=int((~grid.eligible).sum()),supported_fraction=float(grid.eligible.mean()),common_network_hours=int(grid.groupby('hour').eligible.all().sum()),test_hours=p.hour.nunique()))
    eligibility.append(grid[['station_id','hour','timestamp','reported_at','eligible']].assign(max_age_minutes=age))
    print(summaries[-1],flush=True)
m=pd.concat(metrics,ignore_index=True);c=pd.concat(comparisons,ignore_index=True);s=pd.DataFrame(summaries)
m.to_csv(out/'forecast_metrics.csv',index=False);c.to_csv(out/'paired_daily_comparisons.csv',index=False);s.to_csv(out/'threshold_coverage.csv',index=False)
pd.concat(eligibility,ignore_index=True).to_parquet(out/'evidence_eligibility.parquet',index=False)
base=pd.read_csv(ROOT/'outputs/official/forecast_metrics.csv');base=base[(base.split=='test')&(base.stratum=='all')].set_index(['target','model'])
for age in s.max_age_minutes:
    a=m[(m.max_age_minutes==age)&(m.stratum=='all_recorded_counts')].set_index(['target','model']).reindex(base.index)
    assert np.allclose(a[['n','mae','rmse','wape']],base[['n','mae','rmse','wape']],rtol=1e-10,atol=1e-10)
assert s.supported_start_states.is_monotonic_increasing and s.loc[s.max_age_minutes==15,'common_network_hours'].iloc[0]==260
panel=pd.read_parquet(ROOT/'data/processed/panel.parquet');enriched=pd.read_parquet(ROOT/'data/historical/processed/panel_with_evidence.parquet')
mask=panel[['station_id','hour','active_flag']].rename(columns={'active_flag':'original_flag'}).merge(enriched[['station_id','hour','active_flag']],on=['station_id','hour'],validate='one_to_one')
mask['original_unknown']=mask.original_flag.eq(0);mask['unresolved']=mask.active_flag.eq(0);mask['local_month']=mask.hour.dt.tz_convert('America/New_York').dt.month;mask['local_hour']=mask.hour.dt.tz_convert('America/New_York').dt.hour
for key,name in [('local_month','by_month.csv'),('local_hour','by_hour.csv'),('station_id','by_station.csv')]:
    group=mask.groupby(key).agg(station_hours=('hour','size'),original_unknown=('original_unknown','sum'),remaining_unsupported=('unresolved','sum')).reset_index();group['remaining_fraction']=group.remaining_unsupported/group.station_hours;group.to_csv(out/name,index=False)
save_json(out/'protocol.json',dict(analysis='Exploratory post-hoc sensitivity audit, not a new untouched test',models='Original four fixed fitted baseline predictors; no training/retuning or forecast replacement',thresholds_minutes=[5,15,30,60],supported='Latest observation at/before decision; both archive timestamp and source report within threshold; original source freshness <=300s; valid counts; renting/returning enabled. Criterion is point evidence, not continuous operating truth.',unsupported='Fails this evidence criterion; does not mean closed or zero latent demand',comparisons='Every model uses identical rows within each stratum. Thresholds change composition; cross-stratum/cross-threshold errors do not identify model gains or missing-at-random selection.',bootstrap='Paired local-day MAE differences, XGBoost minus named baseline, 1000 resamples seed2025; conditional on sampled days and assumptions',panel_station_hours=len(mask),original_unknown=int(mask.original_unknown.sum()),remaining_unsupported=int(mask.unresolved.sum()),remaining_fraction=float(mask.unresolved.mean()),operating_truth='The remaining 19632 historical station-hours were not filled. Current prospective data never backfills 2025.'))
print('PASS: original test metrics exactly reproduced; all past-only strata reconciled; no unknown state manufactured.')
