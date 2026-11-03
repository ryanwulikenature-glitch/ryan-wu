import argparse
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import PoissonRegressor
from xgboost import XGBRegressor
from .common import ROOT, load_config, save_json, versions
from .features import features, NUMERIC, TARGETS
from .metrics import forecast_metrics

def model_pipeline(kind,params=None,numeric_columns=None):
    numeric=Pipeline([('impute',SimpleImputer(strategy='median',keep_empty_features=True)),('scale',StandardScaler())])
    transform=ColumnTransformer([('numeric',numeric,numeric_columns or NUMERIC),('station',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['station_id'])])
    estimator=PoissonRegressor(alpha=.1,max_iter=500,tol=1e-5) if kind=='poisson' else XGBRegressor(objective='count:poisson',n_jobs=2,random_state=2025,tree_method='hist',**params)
    return Pipeline([('transform',transform),('model',estimator)])

def train(data,out,cfg):
    data,out=Path(data),Path(out); out.mkdir(parents=True,exist_ok=True)
    panel=pd.read_parquet(data/'panel.parquet')
    if cfg.get('observation_mode')=='recorded_event_counts':
        # Explicit alternate estimand: counts in cleaned archives, not latent demand
        # or verified operating-hour demand. Keep the audited panel unchanged.
        panel=panel.copy()
        for target in TARGETS:panel[target]=panel[f'observed_{target}']
    f=features(panel,cfg['timezone']);numeric_columns=NUMERIC.copy()
    if cfg.get('weather_file'):
        weather_path=Path(cfg['weather_file']);weather_path=weather_path if weather_path.is_absolute() else ROOT/weather_path
        weather=pd.read_parquet(weather_path)
        cols=['temperature_2m_previous_day1','precipitation_previous_day1','wind_speed_10m_previous_day1']
        if weather.hour.duplicated().any() or not weather.forecast_reference_offset_hours.ge(24).all():raise ValueError('Invalid weather forecast horizon/alignment')
        f=f.merge(weather[['hour']+cols],on='hour',how='left',validate='many_to_one')
        if f[cols].isna().any().any():raise ValueError('Incomplete archived forecast coverage')
        numeric_columns+=cols
    f.to_parquet(data/('features_weather.parquet' if cfg.get('weather_file') else 'features.parquet'),index=False)
    # Identical valid rows for every model; no target imputation; missing history is train-fit imputed.
    eligible=f[TARGETS+['dep_lag168','arr_lag168']].notna().all(axis=1)
    f=f.loc[eligible].copy()
    if any((f.split==split).sum()==0 for split in ['train','validation','test']): raise ValueError('All chronological splits need eligible observations')
    train_mask=f.split=='train'; val_mask=f.split=='validation'; test_mask=f.split=='test'
    records=[]; tuning=[]; predictions=f[['station_id','hour','departures','arrivals','split']].copy()
    chosen={}
    candidates=[dict(n_estimators=80,max_depth=3,learning_rate=.08,min_child_weight=5),dict(n_estimators=120,max_depth=5,learning_rate=.06,min_child_weight=10)]
    for target,prefix in zip(TARGETS,['dep','arr']):
        prediction_map={'last_hour':f[f'{prefix}_lag1'].fillna(0).to_numpy(), 'seasonal_naive':f[f'{prefix}_lag168'].to_numpy()}
        for kind in ['poisson','xgboost']:
            best=None; best_score=np.inf
            target_candidates=[cfg['fixed_xgboost_params'][target]] if cfg.get('fixed_xgboost_params') else candidates
            for params in ([None] if kind=='poisson' else target_candidates):
                model=model_pipeline(kind,params,numeric_columns); model.fit(f.loc[train_mask],f.loc[train_mask,target])
                score=forecast_metrics(f.loc[val_mask,target],model.predict(f.loc[val_mask]))['mae']
                tuning.append(dict(target=target,model=kind,params=params,validation_mae=score))
                if score<best_score: best=model; best_score=score; selected=params
            # Train/validation predictions stay from train-only model. Refit fixed hyperparameters for test.
            p=np.maximum(0,best.predict(f)); refit=model_pipeline(kind,selected,numeric_columns)
            refit.fit(f.loc[~test_mask],f.loc[~test_mask,target]); p[test_mask.to_numpy()]=np.maximum(0,refit.predict(f.loc[test_mask]))
            prediction_map[kind]=p; joblib.dump(refit,out/f'{target}_{kind}.joblib')
        target_scores={}
        for name,p in prediction_map.items():
            if not np.isfinite(p).all() or (p<0).any(): raise ValueError('Invalid predictions')
            predictions[f'{prefix}_{name}']=p
            for split in ['train','validation','test']:
                mask=f.split==split; m=forecast_metrics(f.loc[mask,target],p[mask])
                records.append(dict(model=name,target=target,split=split,stratum='all',**m))
                if split=='validation': target_scores[name]=m['mae']
        chosen[target]=min(target_scores,key=target_scores.get)
        predictions[f'pred_{prefix}']=prediction_map[chosen[target]]
    test=predictions.loc[test_mask].copy()
    if test.duplicated(['station_id','hour']).any(): raise ValueError('Prediction key duplicated')
    test.to_csv(out/'test_predictions.csv.gz',index=False)
    predictions.to_parquet(out/'all_predictions.parquet',index=False)
    testlocal=test.hour.dt.tz_convert(cfg['timezone'])
    station_volume=f.loc[train_mask].groupby('station_id').departures.sum()
    high=set(station_volume[station_volume>=station_volume.median()].index)
    strata={'weekday':testlocal.dt.dayofweek<5,'weekend':testlocal.dt.dayofweek>=5,
            'peak':testlocal.dt.hour.isin([7,8,9,16,17,18]),'november':testlocal.dt.month==11,'december':testlocal.dt.month==12,
            'high_volume':test.station_id.isin(high),'low_volume':~test.station_id.isin(high)}
    for target,prefix in zip(TARGETS,['dep','arr']):
        for name in ['last_hour','seasonal_naive','poisson','xgboost']:
            for stratum,mask in strata.items(): records.append(dict(model=name,target=target,split='test',stratum=stratum,**forecast_metrics(test.loc[mask,target],test.loc[mask,f'{prefix}_{name}'])))
    metrics=pd.DataFrame(records); metrics.to_csv(out/'forecast_metrics.csv',index=False)
    metrics[metrics.model.isin(['last_hour','seasonal_naive','poisson'])].to_csv(out/'forecast_baseline_metrics.csv',index=False)
    save_json(out/'forecast_metrics.json',json.loads(metrics.to_json(orient='records')))
    save_json(out/'training_config.json',dict(config=cfg,selected_models=chosen,tuning=tuning,versions=versions(),
                protocol='rolling one-step; train-only preprocessing and tuning; train+validation refit for test',
                train_metrics='in-sample diagnostic',eligible_rows=len(f),excluded_rows=len(panel)-len(f),features=numeric_columns+['station_id']))
    return test,metrics

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--data',type=Path,default=ROOT/'data/processed');p.add_argument('--out',type=Path,default=ROOT/'outputs/official');a=p.parse_args();train(a.data,a.out,load_config(a.config))
