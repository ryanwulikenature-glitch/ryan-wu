import itertools
import numpy as np
import pytest
from src.common import load_config
from src.optimize import plan,objective,validate_moves

@pytest.fixture
def case():
    cfg=load_config();cfg.update(budget=3,radius_km=3)
    return np.array([3,27,8]),np.array([30]*3),np.array([15,5,17]),np.array([2,3,3]),np.array([[0,1,2],[1,0,1],[2,1,0]],float),cfg

def test_milp_matches_exhaustive_hand_case(case):
    i,c,d,a,dist,cfg=case
    x,info=plan('milp',*case)
    choices=[]
    for to0,to2 in itertools.product(range(4),repeat=2):
        if to0+to2<=3:
            candidate=np.zeros((3,3),int);candidate[1,0]=to0;candidate[1,2]=to2
            choices.append(objective(i,c,d,a,candidate,dist,cfg))
    assert info['solver_status'].startswith('0:') and not info['fallback']
    assert objective(i,c,d,a,x,dist,cfg)==pytest.approx(min(choices))
    assert objective(i,c,d,a,x,dist,cfg)<objective(i,c,d,a,np.zeros((3,3)),dist,cfg)
    assert x.sum()==3

@pytest.mark.parametrize('strategy',['none','greedy','milp'])
def test_random_network_invariants(strategy):
    rng=np.random.default_rng(42);cfg=load_config()
    for _ in range(15):
        n=6;c=np.full(n,25);i=rng.integers(0,26,n);d=rng.uniform(0,30,n);a=rng.uniform(0,30,n)
        dist=rng.uniform(0,6,(n,n));np.fill_diagonal(dist,0)
        x,info=plan(strategy,i,c,d,a,dist,cfg);validate_moves(i,c,x,dist,cfg,d,a)
        if strategy=='milp':assert objective(i,c,d,a,x,dist,cfg)<=objective(i,c,d,a,np.zeros((n,n)),dist,cfg)+1e-6

def test_forbidden_moves_and_inputs(case):
    i,c,d,a,dist,cfg=case;x=np.zeros((3,3));x[0,1]=4
    with pytest.raises(ValueError):validate_moves(i,c,x,dist,cfg)
    with pytest.raises(ValueError):plan('milp',i,c,-d,a,dist,cfg)
    x=np.zeros((3,3));x[1,0]=.5
    with pytest.raises(ValueError):validate_moves(i,c,x,dist,cfg)

def test_solver_failure_transparent_fallback(case,monkeypatch):
    from types import SimpleNamespace
    import src.optimize as module
    monkeypatch.setattr(module,'milp',lambda *a,**kw:SimpleNamespace(success=False,status=1,message='time limit'))
    x,info=plan('milp',*case);greedy,_=plan('greedy',*case)
    assert info['fallback'] and info['solver_status']=='1:time limit'
    np.testing.assert_array_equal(x,greedy)
