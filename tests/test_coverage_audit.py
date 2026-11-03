import pandas as pd
import pytest
from src.coverage_audit import evaluate_evidence_strata

def inputs():
    times=pd.date_range('2025-11-01T04:00Z',periods=2,freq='h')
    p=pd.DataFrame(dict(station_id=['A','A'],hour=times,departures=[10,2],arrivals=[8,2]))
    for prefix in ['dep','arr']:
        for model in ['last_hour','seasonal_naive','poisson','xgboost']:
            p[f'{prefix}_{model}']=[9,1] if model=='xgboost' else [0,0]
    g=pd.DataFrame(dict(station_id=['A','A'],hour=times,timestamp=times-pd.Timedelta(minutes=2),reported_at=times-pd.Timedelta(minutes=3),eligible=[True,False]))
    return p,g

def test_supported_and_unsupported_partition_exact_same_forecast_rows():
    p,g=inputs();m,c=evaluate_evidence_strata(p,g)
    x=m[(m.target=='departures')&(m.model=='xgboost')].set_index('stratum')
    assert x.loc['all_recorded_counts','n']==2
    assert x.loc['start_state_supported','n']==x.loc['start_state_unsupported','n']==1
    assert x.loc['all_recorded_counts','mae']==1
    assert m[(m.target=='departures')&(m.model=='last_hour')].set_index('stratum').loc['all_recorded_counts','mae']==6
    assert c.ci_low.isna().all() # only one local day: no pretend bootstrap interval

def test_eligible_future_state_cannot_be_used_for_conditioning():
    p,g=inputs();g.loc[0,'timestamp']=g.loc[0,'hour']+pd.Timedelta(seconds=1)
    with pytest.raises(ValueError,match='Future'):evaluate_evidence_strata(p,g)

def test_missing_or_duplicate_forecast_evidence_cannot_silently_change_sample():
    p,g=inputs()
    with pytest.raises(ValueError,match='exact forecast keys'):evaluate_evidence_strata(p,g.iloc[:1])
    with pytest.raises(ValueError,match='Duplicate'):evaluate_evidence_strata(pd.concat([p,p.iloc[:1]]),g)
