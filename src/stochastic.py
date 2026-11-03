"""Three-period stochastic MPC: shared integer moves, continuous scenario stocks.
No future observed demand is used; scenarios are recursive model predictions plus
joint validation residual blocks. Only the first movement is executed.
"""
import time
import numpy as np
import pandas as pd
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import lil_matrix
from .features import features
from .optimize import edge_data,validate_inputs,validate_moves,plan

def recursive_forecast(panel,hour,models,ids,horizon=3,timezone='America/New_York'):
    hour=pd.Timestamp(hour);begin=hour-pd.Timedelta(hours=168);stop=hour+pd.Timedelta(hours=horizon)
    window=panel[panel.hour.between(begin,stop,inclusive='left') & panel.station_id.isin(ids)].copy()
    if window.groupby('station_id').size().reindex(ids).ne(168+horizon).any():raise ValueError('Incomplete recursive forecast history')
    for target in ['departures','arrivals']:
        window[target]=window[f'observed_{target}'].astype(float)
        window.loc[window.hour>=hour,target]=np.nan
    means=[]
    for step in range(horizon):
        stamp=hour+pd.Timedelta(hours=step);f=features(window,timezone)
        rows=f[f.hour==stamp].set_index('station_id').reindex(ids).reset_index()
        pred=np.stack([np.maximum(0,models[t].predict(rows)) for t in ['departures','arrivals']],axis=-1)
        means.append(pred)
        for k,sid in enumerate(ids):
            mask=(window.station_id==sid)&(window.hour==stamp)
            window.loc[mask,['departures','arrivals']]=pred[k]
    return np.stack(means)

def stochastic_plan(inventory,capacity,mean,scenarios,distance,cfg):
    start=time.perf_counter();H,n,_=mean.shape;S=len(scenarios)
    i,c,d,a=validate_inputs(inventory,capacity,mean[0,:,0],mean[0,:,1],distance,cfg)
    if scenarios.shape!=(S,H,n,2) or S<1 or (scenarios<0).any() or not np.isfinite(scenarios).all():raise ValueError('Invalid forecast scenarios')
    edges,supply,demand=edge_data(i,c,d,a,distance,cfg);m=len(edges)
    if not m or cfg['budget']==0:return np.zeros((n,n),int),dict(solver_status='optimal_no_edges',fallback=False,runtime_ms=(time.perf_counter()-start)*1000)
    offset=H*m;x=np.arange(offset).reshape(H,m)
    stock=np.arange(offset,offset+S*(H+1)*n).reshape(S,H+1,n);offset+=stock.size
    unmet=np.arange(offset,offset+S*H*n).reshape(S,H,n);offset+=unmet.size
    blocked=np.arange(offset,offset+S*H*n).reshape(S,H,n);offset+=blocked.size
    low=np.arange(offset,offset+S*n).reshape(S,n);offset+=low.size
    high=np.arange(offset,offset+S*n).reshape(S,n);offset+=high.size
    obj=np.zeros(offset);lb=np.zeros(offset);ub=np.full(offset,np.inf);integer=np.zeros(offset)
    integer[x.ravel()]=1;ub[x.ravel()]=cfg['budget']
    for h in range(H):obj[x[h]]=cfg['distance_weight']*np.array([distance[s,t] for s,t in edges])
    ub[stock.ravel()]=np.tile(c,S*(H+1));lb[stock[:,0,:].ravel()]=np.tile(i,S);ub[stock[:,0,:].ravel()]=np.tile(i,S)
    ub[unmet.ravel()]=scenarios[:,:,:,0].ravel();ub[blocked.ravel()]=scenarios[:,:,:,1].ravel()
    obj[unmet.ravel()]=cfg['shortage_weight']/S;obj[blocked.ravel()]=cfg['overflow_weight']/S
    obj[low.ravel()]=.5*cfg['shortage_weight']/S;obj[high.ravel()]=.5*cfg['overflow_weight']/S
    rows=[];lower=[];upper=[]
    def add(coeff,l=-np.inf,u=np.inf):rows.append(coeff);lower.append(l);upper.append(u)
    for h in range(H):add({int(v):1 for v in x[h]},u=cfg['budget'])
    for node in range(n):
        add({int(x[0,k]):1 for k,(s,t) in enumerate(edges) if s==node},u=supply[node])
        add({int(x[0,k]):1 for k,(s,t) in enumerate(edges) if t==node},u=demand[node])
    for scenario in range(S):
        for h in range(H):
            for node in range(n):
                post={int(stock[scenario,h,node]):1}
                dyn={int(stock[scenario,h+1,node]):1,int(stock[scenario,h,node]):-1,int(unmet[scenario,h,node]):-1,int(blocked[scenario,h,node]):1}
                for k,(s,t) in enumerate(edges):
                    delta=int(t==node)-int(s==node)
                    if delta:post[int(x[h,k])]=delta;dyn[int(x[h,k])]=-delta
                add(post,l=0,u=c[node]);net=scenarios[scenario,h,node,1]-scenarios[scenario,h,node,0];add(dyn,l=net,u=net)
        for node in range(n):
            add({int(stock[scenario,H,node]):-1,int(low[scenario,node]):-1},u=-c[node]*cfg['lower_fraction'])
            add({int(stock[scenario,H,node]):1,int(high[scenario,node]):-1},u=c[node]*cfg['upper_fraction'])
    matrix=lil_matrix((len(rows),offset))
    for r,coeff in enumerate(rows):
        for k,v in coeff.items():matrix[r,k]=v
    result=milp(obj,integrality=integer,bounds=Bounds(lb,ub),constraints=LinearConstraint(matrix.tocsr(),lower,upper),options={'time_limit':cfg['solver_seconds'],'mip_rel_gap':.02})
    moves=np.zeros((n,n),int);fallback=not result.success
    if result.success:
        for k,(s,t) in enumerate(edges):moves[s,t]=int(round(result.x[x[0,k]]))
    else:moves,_=plan('milp',i,c,d,a,distance,cfg)
    validate_moves(i,c,moves,distance,cfg,d,a)
    return moves,dict(solver_status=f'{result.status}:{result.message}',fallback=fallback,mip_gap=getattr(result,'mip_gap',None),planned_proxy_objective=float(result.fun) if result.success else None,runtime_ms=(time.perf_counter()-start)*1000)
