import numpy as np
import pandas as pd
import pytest
from src.features import features,NUMERIC
from src.metrics import forecast_metrics,change,block_bootstrap
from src.train import model_pipeline

def panel():
    hours=pd.date_range('2025-08-01',periods=900,freq='h',tz='UTC')
    return pd.concat([pd.DataFrame({'station_id':s,'hour':hours,'departures':np.arange(len(hours))%10,'arrivals':np.arange(len(hours))%7}) for s in ['001','002']],ignore_index=True)

def test_features_no_future_leakage():
    p=panel();a=features(p);cut=pd.Timestamp('2025-08-20',tz='UTC')
    p.loc[p.hour>=cut,['departures','arrivals']]=999999;b=features(p)
    pd.testing.assert_frame_equal(a.loc[a.hour<=cut,NUMERIC],b.loc[b.hour<=cut,NUMERIC])
    station=a[a.station_id=='002'];assert station.dep_lag1.iloc[0]!=station.dep_lag1.iloc[0]
    assert station.dep_roll24_mean.iloc[24]==np.mean(np.arange(24)%10)

def test_missing_hours_not_positional_lags():
    p=panel().drop(index=10)
    with pytest.raises(ValueError,match='continuous'):features(p)

def test_metrics_zero_and_shape():
    m=forecast_metrics([0,0],[1,0]);assert m['wape'] is None and m['mae']==.5
    assert change(3,0)==(3,None)
    assert forecast_metrics([],[])['n']==0
    assert block_bootstrap([1])[0] is None

def test_models_nonnegative_and_preprocessing_train_only():
    f=features(panel()).dropna();train=f.iloc[:300];test=f.iloc[300:310].copy();test['station_id']='UNSEEN'
    for kind in ['poisson','xgboost']:
        model=model_pipeline(kind,dict(n_estimators=5,max_depth=2,learning_rate=.1))
        model.fit(train,train.departures);pred=model.predict(test)
        assert np.isfinite(pred).all() and (pred>=0).all()
        cats=model.named_steps['transform'].named_transformers_['station'].categories_[0]
        assert 'UNSEEN' not in cats

def test_unaligned_metrics_rejected():
    with pytest.raises(ValueError,match='aligned'):forecast_metrics([1,2],[1])

def test_recorded_count_mode_end_to_end_preserves_unknown_operation(tmp_path):
    from src.make_demo import make_demo
    from src.train import train
    from src.common import sha256
    data=tmp_path/'data';out=tmp_path/'outputs'
    panel,stations,cfg=make_demo(data,n=2)
    mask=panel.hour.dt.tz_convert(cfg['timezone']).dt.hour<5
    panel.loc[mask,['departures','arrivals']]=np.nan
    panel.loc[mask,['observed_departures','observed_arrivals']]=0
    panel.loc[mask,'active_flag']=0
    panel.to_parquet(data/'panel.parquet',index=False)
    digest=sha256(data/'panel.parquet');cfg['observation_mode']='recorded_event_counts'
    predictions,metrics=train(data,out,cfg)
    assert len(predictions)==2*1465
    assert predictions.loc[predictions.hour.dt.tz_convert(cfg['timezone']).dt.hour<5,'departures'].eq(0).all()
    assert sha256(data/'panel.parquet')==digest
    assert len(metrics[(metrics.split=='test')&(metrics.stratum=='all')])==8
    assert predictions[['pred_dep','pred_arr']].ge(0).all().all()
