"""Predeclared exploratory sensitivity/ablation, no test-based model tuning."""
from pathlib import Path
import json
import pandas as pd
from .common import save_json, versions
from .simulate import simulate

def scenarios(cfg):
    result=[('base',{},'selected',None)]
    for key,values in {'capacity':[15,35],'budget':[6,24],'radius_km':[2,5],
                       'initial_fraction':[.3,.7],'seed':[7,42],
                       'shortage_weight':[2,10],'overflow_weight':[2,10]}.items():
        result.extend((f'{key}_{v}',{key:v},'selected',None) for v in values)
    result.extend([(f'forecast_{m}',{},m,None) for m in ['seasonal_naive','dep_only','xgboost','oracle']])
    result.extend([('december',{},'selected','2025-12-01T05:00:00Z'),
                   ('weekday',{},'selected','2025-11-03T05:00:00Z')])
    return result

def run_experiments(predictions,stations,cfg,out,hours=48):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);plan=scenarios(cfg)
    save_json(out/'predeclared_scenarios.json',[dict(name=n,overrides=o,forecast=f,start=s,hours=hours) for n,o,f,s in plan])
    records=[]
    for name,overrides,forecast,start in plan:
        scenario=cfg|overrides;path=out/name
        try:
            summary,_=simulate(predictions,stations,scenario,path,forecast,start,hours)
            for row in summary.to_dict('records'):
                records.append(dict(experiment=name,forecast=forecast,oracle_non_deployable=forecast=='oracle',status='completed',
                                    parameters=json.dumps(scenario,sort_keys=True),result_path=str(path),**row))
        except ValueError as error:
            records.append(dict(experiment=name,forecast=forecast,status='failed',error=str(error),parameters=json.dumps(scenario,sort_keys=True),result_path=str(path)))
        pd.DataFrame(records).to_csv(out/'experiments.csv',index=False)
    frame=pd.DataFrame(records)
    if 'scenario_objective' in frame:frame.pivot_table(index='experiment',columns='strategy',values='scenario_objective').to_csv(out/'robustness_pivot.csv')
    save_json(out/'experiment_protocol.json',dict(classification='exploratory sensitivity on held-out test period; not a fresh untouched evaluation',
               hours=hours,versions=versions(),weather_ablation='not run: no forecast-vintage weather source; no target-hour observations substituted'))
    return frame
