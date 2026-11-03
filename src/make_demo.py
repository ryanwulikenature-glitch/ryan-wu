"""Synthetic full-year interface validation; never official-data evidence."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from .common import ROOT,load_config,save_json

def make_demo(out=ROOT/'data/demo',n=30,seed=2025):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(seed)
    cfg=load_config();cfg.update(data_kind='synthetic',n_stations=n,seed=seed)
    hours=pd.date_range('2025-01-01','2026-01-01',freq='h',inclusive='left',tz=cfg['timezone']).tz_convert('UTC')
    stations=pd.DataFrame({'station_id':[f'DEMO{i:03d}' for i in range(n)],'station_name':[f'Synthetic station {i}' for i in range(n)],
        'latitude':40.74+np.arange(n)//6*.005,'longitude':-74.0+np.arange(n)%6*.006,
        'capacity':cfg['capacity'],'capacity_source':'assumed','selection_reason':'synthetic_fixture_not_real_selection'})
    frames=[];local=hours.tz_convert(cfg['timezone']);hour=local.hour.to_numpy();weekday=(local.dayofweek.to_numpy()<5)
    seasonal=1+.3*np.sin(2*np.pi*(local.dayofyear.to_numpy()-80)/365)
    for k,sid in enumerate(stations.station_id):
        base=1.8+(k%7)*.5
        am=np.exp(-((hour-8)/2)**2);pm=np.exp(-((hour-17)/2.5)**2)
        commute=1 if k%2==0 else -1
        dep_rate=(base+weekday*(5*am+4*pm)+2*np.exp(-((hour-13)/4)**2))*seasonal
        arr_rate=(base+weekday*((5-2*commute)*am+(4+2*commute)*pm)+2*np.exp(-((hour-13)/4)**2))*seasonal
        dep=rng.poisson(dep_rate);arr=rng.poisson(arr_rate)
        frames.append(pd.DataFrame({'station_id':sid,'hour':hours,'departures':dep,'arrivals':arr,'observed_departures':dep,
                                     'observed_arrivals':arr,'netflow':arr-dep,'active_flag':1,'activity_source':'synthetic_known_operating'}))
    panel=pd.concat(frames,ignore_index=True);panel.to_parquet(out/'panel.parquet',index=False);stations.to_csv(out/'stations.csv',index=False)
    save_json(out/'config.json',cfg)
    summary=dict(data_kind='synthetic',months=list(range(1,13)),complete_year=True,stations=n,panel_rows=len(panel),unknown_hours=0,
                 source='seeded independent Poisson counts; no real rides',count_conservation='synthetic_counts_only')
    save_json(out/'data_quality_summary.json',summary);pd.DataFrame([summary]).to_csv(out/'data_quality_summary.csv',index=False)
    return panel,stations,cfg

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'data/demo');p.add_argument('--n-stations',type=int,default=30);a=p.parse_args();make_demo(a.out,a.n_stations)
