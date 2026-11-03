import argparse
from pathlib import Path
from .common import ROOT,load_config
from .make_demo import make_demo
from .prepare import prepare
from .train import train
from .simulate import simulate
from .experiments import run_experiments
from .report import create_reports

def run(demo=False,hours=336,experiment_hours=48,calendar=None,config=None,prepared=False):
    if demo:
        data=ROOT/'data/demo';_,stations,cfg=make_demo(data)
        out=ROOT/'outputs/demo'
    else:
        cfg=load_config(config);data=ROOT/'data/processed';out=ROOT/'outputs/official'
        if prepared:
            import pandas as pd
            stations=pd.read_csv(data/'stations.csv',dtype={'station_id':str})
        else:_,stations=prepare(ROOT/'data/raw',data,cfg,calendar)
    cfg['hours']=hours
    predictions,_=train(data,out,cfg)
    simulate(predictions,stations,cfg,out)
    run_experiments(predictions,stations,cfg,out/'experiments',experiment_hours)
    print(create_reports(data,out))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--demo',action='store_true');p.add_argument('--hours',type=int,default=336);p.add_argument('--experiment-hours',type=int,default=48);p.add_argument('--calendar');p.add_argument('--config');p.add_argument('--prepared',action='store_true');a=p.parse_args();run(a.demo,a.hours,a.experiment_hours,a.calendar,a.config,a.prepared)
