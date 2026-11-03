"""Real raw-data cutoff sensitivity; fixed forecasting parameters, all scenarios kept."""
import zipfile,json
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from .common import ROOT,load_config,save_json
from .prepare import REQUIRED,clean_chunk
from .features import features,TARGETS
from .train import model_pipeline
from .metrics import forecast_metrics
from .simulate import simulate

THRESHOLDS=[30,60,90,120,180,360]

def run():
    out=ROOT/'outputs/duration_sensitivity';out.mkdir(parents=True,exist_ok=True)
    cfg=load_config(ROOT/'configs/official_counts.json')|{'max_duration_minutes':360}
    save_json(out/'protocol.json',dict(thresholds_minutes=THRESHOLDS,selection='same original 30 stations, fixed original XGBoost parameters; no test tuning',simulation_hours=48,scope='cutoff changes the retained-record estimand, not a controlled change to optimizer quality'))
    st=pd.read_csv(ROOT/'data/processed/stations.csv',dtype={'station_id':str});ids=set(st.station_id)
    cache=ROOT/'data/duration';cache.mkdir(exist_ok=True);parts=[];seen=set();audit=[]
    for path in sorted((ROOT/'data/raw').glob('2025*.zip')):
        n=0
        with zipfile.ZipFile(path) as z:
            for name in sorted(z.namelist()):
                if not name.endswith('.csv') or name.startswith('__MACOSX'):continue
                with z.open(name) as source:
                    for chunk in pd.read_csv(source,usecols=REQUIRED,dtype={'ride_id':'string','start_station_id':'string','end_station_id':'string'},chunksize=200000):
                        selected=chunk.start_station_id.isin(ids)|chunk.end_station_id.isin(ids)
                        f,a=clean_chunk(chunk.loc[selected],cfg)
                        keep=[]
                        for rid in f.ride_id:
                            keep.append(rid not in seen);seen.add(rid)
                        f=f.loc[keep]
                        if f.empty:continue
                        f['minutes']=(f.end-f.start).dt.total_seconds()/60
                        f=f[['ride_id','start_station_id','end_station_id','start','end','minutes']]
                        f.to_parquet(cache/f'part_{len(parts):04d}.parquet',index=False);parts.append(f);n+=len(f)
        audit.append(dict(file=path.name,retained_selected_up_to_360=n));print(path.name,n,'selected rides',flush=True)
    rides=pd.concat(parts,ignore_index=True);pd.DataFrame(audit).to_csv(out/'source_audit.csv',index=False)
    original=pd.read_parquet(ROOT/'data/processed/panel.parquet').sort_values(['station_id','hour']).reset_index(drop=True)
    scores=[];policies=[]
    for cutoff in THRESHOLDS:
        rr=rides[rides.minutes<=cutoff];panel=original.copy()
        for target,idcol,time in [('departures','start_station_id','start'),('arrivals','end_station_id','end')]:
            count=rr.assign(hour=rr[time].dt.floor('h')).groupby([idcol,'hour']).size();count.index.names=['station_id','hour']
            values=count.reindex(pd.MultiIndex.from_frame(panel[['station_id','hour']]),fill_value=0).to_numpy()
            if cutoff==180 and not np.array_equal(values,panel[f'observed_{target}'].to_numpy()):raise ValueError('180-minute recomputation does not match original raw endpoint counts')
            panel[target]=values
        f=features(panel,cfg['timezone']);f=f[f.dep_lag168.notna()&f.arr_lag168.notna()].copy()
        test=f.split=='test';prediction=f.loc[test,['station_id','hour','departures','arrivals']].copy()
        for target,prefix in zip(TARGETS,['dep','arr']):
            saved=joblib.load(ROOT/f'outputs/official/{target}_xgboost.joblib').named_steps['model'].get_params()
            params={k:saved[k] for k in ['n_estimators','max_depth','learning_rate','min_child_weight']}
            model=model_pipeline('xgboost',params);model.fit(f.loc[~test],f.loc[~test,target]);pred=np.maximum(0,model.predict(f.loc[test]))
            prediction[f'pred_{prefix}']=pred
            scores.append(dict(cutoff_minutes=cutoff,target=target,retained_selected_rides=len(rr),test_count=int(f.loc[test,target].sum()),**forecast_metrics(f.loc[test,target],pred)))
        summary,_=simulate(prediction,st,cfg,out/f'{cutoff}_minutes',hours=48)
        summary['cutoff_minutes']=cutoff;policies.append(summary)
        prediction.to_csv(out/f'predictions_{cutoff}.csv.gz',index=False)
        pd.DataFrame(scores).to_csv(out/'forecast_metrics.csv',index=False);pd.concat(policies).to_csv(out/'simulation_summary.csv',index=False)
    print('PASS: six full raw-data duration cutoffs; 180-minute raw endpoint recomputation matches original, fixed-parameter forecasting and paired policy scenarios complete.')

if __name__=='__main__':run()
