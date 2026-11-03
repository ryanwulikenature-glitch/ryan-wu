import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from src.common import ROOT,load_config,save_json
from src.simulate import simulate
from src.metrics import block_bootstrap
out=ROOT/'outputs/weather';cfg=load_config(ROOT/'configs/weather.json');cfg['hours']=1465
p=pd.read_csv(out/'test_predictions.csv.gz',dtype={'station_id':str});base=pd.read_csv(ROOT/'outputs/official/test_predictions.csv.gz',dtype={'station_id':str})
st=pd.read_csv(ROOT/'data/processed/stations.csv',dtype={'station_id':str});summary,h=simulate(p,st,cfg,out,forecast='xgboost',hours=1465)
prior=pd.read_csv(ROOT/'outputs/official/simulation_hourly.csv');assert h.sample_hash.tolist()==prior.sample_hash.tolist()
compare=base.merge(p,on=['station_id','hour'],suffixes=('_base','_weather'),validate='one_to_one');days=pd.to_datetime(compare.hour,utc=True).dt.tz_convert(cfg['timezone']).dt.date
rows=[]
for target,prefix in [('departures','dep'),('arrivals','arr')]:
 assert compare[f'{target}_base'].equals(compare[f'{target}_weather'])
 err=(compare[f'{target}_weather']-compare[f'{prefix}_xgboost_weather']).abs()-(compare[f'{target}_base']-compare[f'{prefix}_xgboost_base']).abs()
 daily=err.groupby(days).mean();lo,hi=block_bootstrap(daily,cfg['seed']);rows.append(dict(target=target,mean_daily_MAE_difference=float(daily.mean()),ci_low=lo,ci_high=hi,comparison='with 24-hour-lead GFS forecast minus no-weather; fixed XGBoost parameters'))
pd.DataFrame(rows).to_csv(out/'weather_ablation_uncertainty.csv',index=False)
save_json(out/'weather_protocol.json',dict(config=cfg,baseline='outputs/official',matched_targets_and_paths='passed',source='Open-Meteo Previous Runs, gfs_seamless, previous_day1 (24 hours before valid time)',interpretation='post-hoc exploratory weather ablation on already evaluated test; no new untouched test claim',units={'temperature':'C','precipitation':'mm','wind_speed':'km/h'},limitations='Provider archived forecast lead-time statement used; not target-hour actual or reanalysis; one NYC grid cell, not station microclimates'))
print(summary.to_csv(index=False));print(pd.DataFrame(rows).to_csv(index=False));print('PASS: weather ablation uses identical target samples and common simulation random paths.')
