"""Fixed-model forecast audit conditional on past-only station-state evidence.
Evidence at the hour boundary does not verify operation throughout that hour.
"""
import numpy as np
import pandas as pd
from .metrics import forecast_metrics,block_bootstrap

MODELS=['last_hour','seasonal_naive','poisson','xgboost']
STRATA=['all_recorded_counts','start_state_supported','start_state_unsupported']

def evaluate_evidence_strata(predictions,grid,timezone='America/New_York',seed=2025):
    p=predictions.copy();g=grid.copy();keys=['station_id','hour']
    for f in [p,g]:
        f['station_id']=f.station_id.astype(str);f['hour']=pd.to_datetime(f.hour,utc=True)
        if f.duplicated(keys).any():raise ValueError('Duplicate station-hour keys')
    if g.eligible.isna().any():raise ValueError('Missing evidence criterion')
    for col in ['timestamp','reported_at']:
        g[col]=pd.to_datetime(g[col],utc=True)
        if (g.eligible & (g[col].isna() | (g[col]>g.hour))).any():raise ValueError('Future/missing eligible source state')
    joined=p.merge(g[keys+['eligible']],on=keys,how='left',validate='one_to_one',indicator=True)
    if joined._merge.ne('both').any() or len(p)!=len(g):raise ValueError('Evidence grid must cover exact forecast keys')
    joined['local_day']=joined.hour.dt.tz_convert(timezone).dt.date
    masks=[np.ones(len(joined),bool),joined.eligible.to_numpy(bool),~joined.eligible.to_numpy(bool)]
    metrics=[];comparisons=[]
    for stratum,mask in zip(STRATA,masks):
        frame=joined.loc[mask]
        for target,prefix in [('departures','dep'),('arrivals','arr')]:
            for model in MODELS:
                metrics.append(dict(stratum=stratum,target=target,model=model,**forecast_metrics(frame[target],frame[f'{prefix}_{model}'])))
            for baseline in ['last_hour','seasonal_naive']:
                delta=np.abs(frame[target]-frame[f'{prefix}_xgboost'])-np.abs(frame[target]-frame[f'{prefix}_{baseline}'])
                daily=pd.DataFrame({'day':frame.local_day,'difference':delta}).groupby('day').difference.mean()
                lo,hi=block_bootstrap(daily.to_numpy(),seed)
                comparisons.append(dict(stratum=stratum,target=target,model='xgboost',baseline=baseline,n=len(frame),local_days=len(daily),mean_daily_mae_difference=float(daily.mean()) if len(daily) else None,ci_low=lo,ci_high=hi))
    return pd.DataFrame(metrics),pd.DataFrame(comparisons)
