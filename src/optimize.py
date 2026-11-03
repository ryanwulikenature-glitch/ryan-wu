"""Directed surplus-to-deficit MILP, with explicit status and transparent fallback."""
import time
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import lil_matrix

def validate_inputs(inventory,capacity,dep,arr,distance,cfg):
    i,c,d,a=map(lambda x:np.asarray(x,float),[inventory,capacity,dep,arr])
    if not (i.shape==c.shape==d.shape==a.shape) or i.ndim!=1: raise ValueError('Vector alignment required')
    if not all(np.isfinite(x).all() for x in [i,c,d,a,distance]): raise ValueError('Non-finite optimization inputs')
    if (c<=0).any() or (i<0).any() or (i>c).any() or (d<0).any() or (a<0).any(): raise ValueError('Invalid inventory/capacity/forecast')
    if not np.equal(i,np.rint(i)).all() or not np.equal(c,np.rint(c)).all(): raise ValueError('Inventory and capacity must be integers')
    if np.shape(distance)!=(len(i),len(i)) or (np.asarray(distance)<0).any(): raise ValueError('Invalid distances')
    if cfg['budget']<0 or int(cfg['budget'])!=cfg['budget'] or cfg['radius_km']<0: raise ValueError('Invalid transport constraints')
    if not 0<=cfg['lower_fraction']<=cfg['upper_fraction']<=1: raise ValueError('Invalid safety interval')
    if any(cfg[k]<0 for k in ['shortage_weight','overflow_weight','distance_weight']): raise ValueError('Negative weight')
    return i,c,d,a

def edge_data(i,c,dep,arr,dist,cfg):
    end=i+arr-dep; middle=c*(cfg['lower_fraction']+cfg['upper_fraction'])/2
    supply=np.minimum(i,np.maximum(0,np.floor(end-middle))).astype(int)
    demand=np.minimum(c-i,np.maximum(0,np.ceil(middle-end))).astype(int)
    edges=[(s,t) for s in np.flatnonzero(supply) for t in np.flatnonzero(demand) if s!=t and dist[s,t]<=cfg['radius_km']]
    return edges,supply,demand

def objective(inventory,capacity,dep,arr,moves,distance,cfg):
    end=np.asarray(inventory)+moves.sum(axis=0)-moves.sum(axis=1)+np.asarray(arr)-np.asarray(dep)
    return float(cfg['shortage_weight']*np.maximum(0,np.asarray(capacity)*cfg['lower_fraction']-end).sum()+
                 cfg['overflow_weight']*np.maximum(0,end-np.asarray(capacity)*cfg['upper_fraction']).sum()+
                 cfg['distance_weight']*(moves*distance).sum())

def validate_moves(inventory,capacity,moves,distance,cfg,dep=None,arr=None):
    x=np.asarray(moves)
    if x.shape!=(len(inventory),len(inventory)) or not np.isfinite(x).all(): raise ValueError('Invalid move matrix')
    if (x<0).any() or not np.allclose(x,np.rint(x)) or np.trace(x)!=0: raise ValueError('Moves must be nonnegative integer off-diagonal')
    if x.sum()>cfg['budget'] or ((x>0)&(distance>cfg['radius_km'])).any(): raise ValueError('Budget or radius violation')
    post=np.asarray(inventory)+x.sum(axis=0)-x.sum(axis=1)
    if (post<0).any() or (post>capacity).any() or (x.sum(axis=1)>inventory).any(): raise ValueError('Inventory/capacity violation')
    if ((x.sum(axis=0)>0)&(x.sum(axis=1)>0)).any(): raise ValueError('Transshipment forbidden')
    if dep is not None:
        edges,supply,demand=edge_data(np.asarray(inventory),np.asarray(capacity),dep,arr,distance,cfg)
        allowed=np.zeros_like(x,bool)
        for s,t in edges: allowed[s,t]=True
        if ((x>0)&~allowed).any() or (x.sum(axis=1)>supply).any() or (x.sum(axis=0)>demand).any(): raise ValueError('Supply/demand restriction violated')
    return post.astype(int)

def plan(strategy,inventory,capacity,dep,arr,distance,cfg):
    start=time.perf_counter(); i,c,d,a=validate_inputs(inventory,capacity,dep,arr,distance,cfg)
    n=len(i); moves=np.zeros((n,n),dtype=int); status='not_applicable'; fallback=False
    edges,supply,demand=edge_data(i,c,d,a,distance,cfg)
    if strategy not in ['none','greedy','milp']: raise ValueError(f'Unknown strategy {strategy}')
    if strategy=='greedy':
        remaining=int(cfg['budget']); sleft=supply.copy(); tleft=demand.copy()
        for s,t in sorted(edges,key=lambda e:(distance[e],e)):
            amount=min(sleft[s],tleft[t],remaining); moves[s,t]=amount
            sleft[s]-=amount; tleft[t]-=amount; remaining-=amount
    elif strategy=='milp':
        m=len(edges)
        if not m or not cfg['budget']: status='optimal_no_edges'
        else:
            # Variables x[m], lower slacks[n], upper slacks[n].
            coeff=np.r_[[cfg['distance_weight']*distance[s,t] for s,t in edges],np.full(n,cfg['shortage_weight']),np.full(n,cfg['overflow_weight'])]
            matrix=lil_matrix((4*n+1,m+2*n)); lower=np.full(4*n+1,-np.inf); upper=np.full(4*n+1,np.inf)
            end=i+a-d
            for k,(s,t) in enumerate(edges):
                matrix[s,k]=1; matrix[t,k]=-1 # out-in; lower slack inequality
                matrix[n+s,k]=-1;matrix[n+t,k]=1
                matrix[2*n+s,k]=1;matrix[3*n+t,k]=1;matrix[4*n,k]=1
            for k in range(n):
                matrix[k,m+k]=-1;upper[k]=end[k]-c[k]*cfg['lower_fraction']
                matrix[n+k,m+n+k]=-1;upper[n+k]=c[k]*cfg['upper_fraction']-end[k]
                upper[2*n+k]=supply[k];upper[3*n+k]=demand[k]
            upper[4*n]=cfg['budget']
            result=milp(coeff,integrality=np.r_[np.ones(m),np.zeros(2*n)],bounds=Bounds(np.zeros(m+2*n),np.full(m+2*n,np.inf)),
                        constraints=LinearConstraint(matrix.tocsr(),lower,upper),options={'time_limit':cfg['solver_seconds'],'mip_rel_gap':0.0})
            status=f'{result.status}:{result.message}'
            if result.success:
                for k,(s,t) in enumerate(edges): moves[s,t]=int(round(result.x[k]))
            else:
                moves,info=plan('greedy',i,c,d,a,distance,cfg);fallback=True
    validate_moves(i,c,moves,distance,cfg,d,a)
    return moves,{'solver_status':status,'fallback':fallback,'runtime_ms':(time.perf_counter()-start)*1000,
                  'proxy_objective':objective(i,c,d,a,moves,distance,cfg)}
