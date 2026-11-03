import numpy as np

def forecast_metrics(y,p):
    y,p=np.asarray(y,float),np.asarray(p,float)
    if y.shape!=p.shape or y.ndim!=1: raise ValueError('Metrics require aligned one-dimensional arrays')
    if len(y)==0: return {'n':0,'mae':None,'rmse':None,'wape':None}
    if not np.isfinite(y).all() or not np.isfinite(p).all(): raise ValueError('Non-finite metric input')
    error=y-p
    return {'n':len(y),'mae':float(np.abs(error).mean()),'rmse':float(np.sqrt((error**2).mean())),
            'wape':float(np.abs(error).sum()/y.sum()) if y.sum()>0 else None}

def change(value, baseline):
    return value-baseline, (value-baseline)/baseline if baseline else None

def block_bootstrap(differences,seed=2025,repetitions=1000):
    x=np.asarray(differences,float)
    if len(x)<2: return (None,None)
    rng=np.random.default_rng(seed)
    means=np.mean(rng.choice(x,(repetitions,len(x)),replace=True),axis=1)
    return tuple(float(v) for v in np.quantile(means,[.025,.975]))
