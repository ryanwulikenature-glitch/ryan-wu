import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import joblib
from src.common import ROOT,load_config,distances,save_json
from src.stochastic import recursive_forecast,stochastic_plan
from src.optimize import plan,validate_moves
from src.simulate import event_orders,play_hour
out=ROOT/'outputs/stochastic';out.mkdir(parents=True,exist_ok=True)
cfg=load_config(ROOT/'configs/official_counts.json');H=3;S=4;hours=48
save_json(out/'protocol.json',dict(config=cfg,horizon=H,scenarios=S,hours=hours,lead_time='recursive one-step forecasts; no future actual lags',uncertainty='paired cross-station contiguous validation residual blocks; fixed seed',objective='expected unmet/blocked count penalty plus terminal safety half-weight and move distance; continuous future stocks, integer moves',gap=.02,edges='fixed initial surplus-to-deficit directions; robust post-move bounds across scenarios',scope='exploratory receding-horizon count scenario; not true latent demand or operational truck routing'))
st=pd.read_csv(ROOT/'data/processed/stations.csv',dtype={'station_id':str}).sort_values('station_id');ids=st.station_id.tolist();n=len(ids)
panel=pd.read_parquet(ROOT/'data/processed/panel.parquet');allp=pd.read_parquet(ROOT/'outputs/official/all_predictions.parquet')
models={t:joblib.load(ROOT/f'outputs/official/{t}_xgboost.joblib') for t in ['departures','arrivals']}
v=allp[allp.split=='validation'].sort_values(['hour','station_id']);res=np.stack([(v.departures-v.dep_xgboost).to_numpy(),(v.arrivals-v.arr_xgboost).to_numpy()],axis=-1).reshape(-1,n,2)
times=sorted(allp[allp.split=='test'].hour.unique())[:hours];c=np.full(n,25);dist=distances(st);stocks={k:np.full(n,12) for k in ['none','greedy','milp','stochastic_mpc']};rows=[];logs=[]
for h,t in enumerate(times):
    mean=recursive_forecast(panel,t,models,ids,H);rng=np.random.default_rng(cfg['seed']+h)
    starts=rng.integers(0,len(res)-H+1,S);scenarios=np.maximum(0,mean[None,:,:,:]+np.stack([res[k:k+H] for k in starts]))
    actual=allp[(allp.hour==t)&(allp.split=='test')].set_index('station_id').reindex(ids);orders=event_orders(actual.departures,actual.arrivals,cfg['seed'],h)
    for policy in stocks:
        if policy=='stochastic_mpc':x,info=stochastic_plan(stocks[policy],c,mean,scenarios,dist,cfg)
        else:x,info=plan(policy,stocks[policy],c,mean[0,:,0],mean[0,:,1],dist,cfg)
        post=validate_moves(stocks[policy],c,x,dist,cfg);end,unmet,blocked,sd,sa=play_hour(post,c,orders);stocks[policy]=end
        bike_km=float((x*dist).sum());rows.append(dict(timestamp=t,strategy=policy,requests=int(actual.departures.sum()),unmet=unmet,blocked=blocked,bikes_moved=int(x.sum()),bike_km=bike_km,scenario_objective=5*(unmet+blocked)+.1*bike_km,**info))
    logs.append(dict(hour=t,residual_block_starts=starts.tolist(),forecast_step0=mean[0].tolist()))
f=pd.DataFrame(rows);f.to_csv(out/'hourly.csv',index=False);summary=f.groupby('strategy')[['requests','unmet','blocked','bikes_moved','bike_km','scenario_objective','fallback']].sum();summary['service_proxy']=1-summary.unmet/summary.requests;summary.to_csv(out/'summary.csv');save_json(out/'scenario_trace.json',logs)
print(summary.to_csv());print('PASS: recursive horizon forecasts and MPC evaluated on common 48-hour event paths.')
