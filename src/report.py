import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from .common import ROOT

NOTICE='SYNTHETIC VALIDATION ONLY — NO HISTORICAL SERVICE CLAIM' 

def table(frame):return frame.to_csv(index=False)

def create_reports(data,out):
    data,out=Path(data),Path(out);fig=out/'figures';fig.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((data/'config.json').read_text());kind=cfg['data_kind'];notice=NOTICE if kind=='synthetic' else 'Observed completed rides; simulated service outcomes under assumptions'
    panel=pd.read_parquet(data/'panel.parquet');stations=pd.read_csv(data/'stations.csv',dtype={'station_id':str});p=pd.read_csv(out/'test_predictions.csv.gz',parse_dates=['hour'],dtype={'station_id':str});metrics=pd.read_csv(out/'forecast_metrics.csv');summary=pd.read_csv(out/'simulation_summary.csv')
    daily=panel.groupby('hour')[['departures','arrivals']].sum(min_count=1).resample('D').sum(min_count=1)
    def save(name):plt.suptitle(notice,fontsize=8);plt.tight_layout();plt.savefig(fig/name,dpi=130);plt.close()
    daily.plot(figsize=(10,4));plt.ylabel('Completed/synthetic counts per day');save('eda_daily.png')
    hourly=panel.groupby('hour')[['departures','arrivals']].sum(min_count=1);hourly.iloc[:168].plot(figsize=(10,4));save('eda_hourly.png')
    local=panel.hour.dt.tz_convert(cfg['timezone']);z=panel.assign(local_hour=local.dt.hour,weekday=local.dt.dayofweek)
    heat=z.pivot_table(index='weekday',columns='local_hour',values='departures',aggfunc='mean')
    plt.figure(figsize=(10,4));plt.imshow(heat,aspect='auto');plt.colorbar(label='Mean departures');plt.xlabel('Local hour');plt.ylabel('Day of week (Mon=0)');save('eda_heatmap.png')
    net=panel.groupby('station_id').netflow.mean();pos=stations.set_index('station_id').reindex(net.index)
    assert pos[['latitude','longitude']].notna().all().all(), 'Station coordinate alignment failed'
    panel.groupby('station_id').netflow.agg(['mean','std','min','median','max']).to_csv(out/'station_netflow_distribution.csv')
    panel.groupby('station_id').netflow.quantile([.05,.25,.75,.95]).unstack().to_csv(out/'station_netflow_quantiles.csv')
    plt.figure(figsize=(7,5));plt.scatter(pos.longitude,pos.latitude,c=net,cmap='coolwarm');plt.colorbar(label='Mean netflow');plt.xlabel('Longitude');plt.ylabel('Latitude');save('eda_map.png')
    panel.groupby('station_id').netflow.mean().plot.bar(figsize=(10,4));plt.ylabel('Mean netflow per hour');save('eda_netflow.png')
    panel.groupby('station_id').departures.agg(['mean','std']).plot.bar(figsize=(10,4));save('eda_heterogeneity.png')
    anomaly=daily.assign(total=daily.sum(axis=1)).sort_values('total',ascending=False).head(10);anomaly.to_csv(out/'anomalous_dates.csv')
    m=metrics[(metrics.split=='test')&(metrics.stratum=='all')];m.pivot(index='model',columns='target',values='mae').plot.bar(figsize=(9,4));save('forecast_errors.png')
    sample=p[p.station_id==p.station_id.iloc[0]].head(168);sample.set_index('hour')[['departures','pred_dep']].plot(figsize=(10,4));save('forecast_trace.png')
    plt.figure(figsize=(7,4));plt.hist(p.departures-p.pred_dep,bins=40);plt.xlabel('Departure residual');save('forecast_residuals.png')
    summary.set_index('strategy')[['unmet_departures','blocked_arrivals']].plot.bar(figsize=(8,4));save('policy_service.png')
    summary.set_index('strategy')[['bikes_moved','bike_km']].plot.bar(figsize=(8,4));save('policy_cost.png')
    expath=out/'experiments/experiments.csv'
    if expath.exists():
        experiments=pd.read_csv(expath);valid=experiments[experiments.status=='completed']
        valid.pivot_table(index='experiment',columns='strategy',values='scenario_objective').plot.bar(figsize=(13,5));save('robustness.png')
        failures=experiments.loc[experiments.status!='completed'].to_dict('records')
    else:failures=['Experiments not run']
    traincfg=json.loads((out/'training_config.json').read_text());quality=json.loads((data/'data_quality_summary.json').read_text())
    eda=f'''# EDA findings ({kind})\n\n{notice}\n\nThe figures use saved panel values. Largest daily totals:\n\n```csv\n{anomaly.to_csv()}\n```\n\nStation netflow range: {net.min():.3f} to {net.max():.3f} counts/hour. Persistent positive and negative netflow motivates moving bikes between complementary stations. Hour/weekday heatmap shows when that imbalance occurs.\n\nFor synthetic data, commute peaks and seasonal variation were imposed by the generator; they are not discoveries about NYC. For official data, peaks alone cannot establish weather effects or closures. The top dates are diagnostic candidates, not proven anomalies. Coordinates use an approximate Manhattan rectangle, not official borough membership.\n'''
    (out/'eda_findings.md').write_text(eda)
    text=f'''# NYC Citi Bike — reproducible technical report\n\n## 1. Problem Definition\n\n{notice}\n\nCompare next-hour departure/arrival forecasts and three rebalancing strategies for {len(stations)} stations. Data kind: **{kind}**. No historic empty/full inventory observations are available.\n\n## 2. Data\n\n```json\n{json.dumps(quality,indent=2)}\n```\n\nUTC hourly index with America/New_York calendar features; unresolved local DST folds/gaps are excluded during raw ingestion. Official zero counts require operation evidence; unverified hours remain missing. Training-only activity/geography/drift selection applies to raw data; demo stations are generated fixtures.\n\n## 3. Forecasting\n\nJan–Aug training, Sep–Oct validation, Nov–Dec test. Lag 1/24/168 and shifted 24/168 rolling statistics, station one-hot, calendar and US federal holidays. Last-hour, seasonal-naive, regularized Poisson GLM and XGBoost count:poisson; separate targets. All transforms fit on training, hyperparameters use validation; final models refit train+validation. Rolling test features can use previously observed test hours. No weather features because forecast-vintage inputs are absent. Train metrics are in-sample diagnostics.\n\nSelected on validation: {json.dumps(traincfg['selected_models'])}. Test metrics:\n\n```csv\n{table(m)}\n```\n\n## 4. Optimization\n\nSee `reports/optimization_formulation.md`. Integer supply-to-deficit moves, inventory/capacity, budget and radius constraints; HiGHS via SciPy. Objective is forecast-end safety-band slack plus bike-km, not realized service or money. Every solver status and fallback is logged.\n\n## 5. Simulation\n\n**Hourly count-based scenario simulation**: instant moves followed by seeded random interleaving of exogenous arrivals and departures at each station. Same event sample hash, initial inventory and restrictions for all policies. This count model does not suppress arrivals after rejected departures and does not claim fleet conservation; station inventory balance is checked. Optional paired-event replay is implemented separately and must not be mixed with these count results.\n\n## 6. Results\n\n```csv\n{table(summary)}\n```\n\nAbsolute and relative policy differences are in policy_comparison.csv; percentages with zero baseline are undefined. Objective weights are preference units, bike-km is not truck route length. These outputs do not prove a complex model or MILP improves reality.\n\n## 7. Robustness\n\nPredeclared one-factor scenarios vary capacity, budget, radius, initial inventory, weights, seeds and dates. Ablations replace predictors with seasonal naive, departures-only, fixed XGBoost, and a non-deployable future-count oracle. The oracle is an information benchmark, not a mathematical service upper bound: the optimization objective is only a proxy. Test-period sensitivities are exploratory. Paired daily block bootstrap reports scenario-objective differences; it quantifies within-scenario variability only. Weather ablation is unavailable, not a passing result. Failures: {json.dumps(failures,ensure_ascii=False)}.\n\n## 8. Limitations\n\nCompleted rides are a censored sample of potential demand. Capacities, starting inventories, instantaneous transport and costs are assumed. Current GBFS cannot reconstruct 2025 capacities. Random hourly ordering differs from actual ride causality; optional event replay still has external-boundary assumptions and blocked returns remain held off dock. Approximate rectangle selection can include non-Manhattan locations. Unresolved DST times are excluded, not assigned arbitrary folds. No causal operational or financial improvement is established.\n\n## 9. Conclusion and completion status\n\n{'Synthetic end-to-end execution verifies software interfaces and scenario accounting only. Official 2025 data download is blocked by network policy; real-data EDA, forecasts and policy conclusions remain unrun.' if kind=='synthetic' else 'The saved outputs provide observed-rides forecasting and assumption-dependent scenario results. Read the metrics and uncertainty tables before drawing any performance conclusion.'}\n\nAll numeric results above were read from generated files. See tests output for executed checks and README for reproduction. Optional routing, stochastic optimization, network expansion and prospective inventory collection are documented extensions, not claimed as executed.\n'''
    if cfg.get('observation_mode')=='recorded_event_counts':
        text += '\n## Explicit recorded-event estimand\n\nThe audited panel preserves unknown operating hours as missing. For this experiment only, training and simulation use observed_departures/observed_arrivals: counts in the retained completed-ride archive, including zero recorded events. This is an explicit alternate observation model; it does not reclassify station operation as verified or imply zero latent demand. Both lag features and labels use the same recorded-event definition. Quality-audited EDA remains conditional on eventful hours for per-station means; daily archive totals retain all observed counts. The strict operating-hour workflow remains available separately.\n'
    paired=out/'paired_events/event_replay_summary.csv'
    if paired.exists():
        text += '\n## Executed paired-event upgrade\n\nThe full same test horizon was also replayed by cleaned ride_id, including external boundaries and initial in-transit rides. Rejected departures suppress the corresponding arrival. Full fleet accounting is asserted at each processed event. Blocked returns remain held off dock through the horizon; the alternative scenario is not historical observed loss.\n\n```csv\n'+pd.read_csv(paired).to_csv(index=False)+'```\n'
    (out/'final_report.md').write_text(text)
    return out/'final_report.md'
