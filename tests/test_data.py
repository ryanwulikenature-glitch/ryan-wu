import zipfile
import pandas as pd
import numpy as np
import pytest
from src.common import load_config
from src.prepare import clean_chunk,csv_chunks,local_to_utc,select_stations,build_panel,prepare

def raw_rides():
    return pd.DataFrame({'ride_id':['r1','r2','r3','r4'],'started_at':['2025-01-01 10:00','2025-01-01 10:00','bad','2025-01-01 10:00'],
        'ended_at':['2025-01-01 10:15','2025-01-01 09:00','2025-01-01 10:15','2025-01-01 10:15'],
        'start_station_id':['001','001','001',None],'end_station_id':['OUT','OUT','OUT','OUT'],
        'start_lat':[40.75]*4,'start_lng':[-73.99]*4,'end_lat':[40.7]*4,'end_lng':[-74.01]*4})

def events():
    rows=[]
    for month in range(1,13):
        h=pd.Timestamp(f'2025-{month:02d}-01 15:00',tz='UTC')
        for sid,count in [('001',10),('TEST_ONLY',10000 if month>8 else 0)]:
            if count:
                rows.extend([dict(station_id=sid,hour=h,direction=d,count=count,latitude=40.75,longitude=-73.99,station_name=sid) for d in ['departures','arrivals']])
    return pd.DataFrame(rows)

def test_cleaning_exclusive_reason_audit():
    f,a=clean_chunk(raw_rides(),load_config());assert list(f.ride_id)==['r1'];assert f.start_station_id.iloc[0]=='001'
    assert a['invalid_duration']==1 and a['invalid_time_or_dst']==1 and a['missing_id']==1
    assert a['raw_rows']==a['clean_before_dedup']+a['invalid_duration']+a['invalid_time_or_dst']+a['missing_id']+a['invalid_coordinate']

def test_dst_policy_and_utc_hours():
    x=local_to_utc(pd.Series(['2025-03-09 02:30','2025-11-02 01:30','2025-03-09 03:30']),'America/New_York')
    assert x.isna().tolist()==[True,True,False]
    hours=pd.date_range('2025-01-01','2026-01-01',tz='America/New_York',freq='h',inclusive='left')
    assert len(hours)==8760
    assert sum(hours.date==pd.Timestamp('2025-03-09').date())==23
    assert sum(hours.date==pd.Timestamp('2025-11-02').date())==25

def test_zip_multimember_and_string_ids(tmp_path):
    csv=raw_rides().iloc[:1].to_csv(index=False);p=tmp_path/'multi.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr('a.csv',csv);z.writestr('folder/b.csv',csv);z.writestr('__MACOSX/a.csv',csv)
    chunks=list(csv_chunks(p));assert len(chunks)==2
    assert chunks[0][1].start_station_id.iloc[0]=='001'

def test_train_only_station_selection():
    cfg=load_config();cfg.update(n_stations=1,min_training_events=1)
    st=select_stations(events(),cfg);assert list(st.station_id)==['001']
    changed=events();changed.loc[changed.hour.dt.month>8,'count']=1000000
    pd.testing.assert_frame_equal(st,select_stations(changed,cfg))

def test_panel_conservation_cross_boundary_and_unknown():
    cfg=load_config();cfg.update(n_stations=1,min_training_events=1)
    e=events();st=select_stations(e,cfg);p=build_panel(e,st,cfg)
    assert len(p)==8760
    assert p.observed_departures.sum()==120 and p.observed_arrivals.sum()==120
    assert p.departures.isna().sum()==8748
    assert (p.loc[p.active_flag==1,'departures']==10).all()
    cal=pd.DataFrame({'station_id':['001'],'hour':[p.hour.iloc[0]],'active_flag':[1]})
    pp=build_panel(e,st,cfg,cal);assert pp.departures.iloc[0]==0

def test_duplicate_inputs_not_double_counted(tmp_path):
    raw=tmp_path/'raw';raw.mkdir();cfg=load_config();cfg.update(n_stations=1,min_active_months=1,min_training_events=1)
    df=raw_rides().iloc[:1];df.to_csv(raw/'a.csv',index=False)
    with zipfile.ZipFile(raw/'b.zip','w') as z:z.writestr('a.csv',df.to_csv(index=False));z.writestr('b.csv',df.to_csv(index=False))
    p,st=prepare(raw,tmp_path/'processed',cfg,allow_incomplete=True)
    assert p.observed_departures.sum()==1
    audit=pd.read_csv(tmp_path/'interim/monthly_audit.csv');assert audit.duplicate_across_members.sum()==2

def test_incomplete_year_rejected(tmp_path):
    raw=tmp_path/'raw';raw.mkdir();raw_rides().to_csv(raw/'a.csv',index=False)
    with pytest.raises(ValueError,match='coverage incomplete'):prepare(raw,tmp_path/'processed',load_config())

def test_invalid_operating_evidence_rejected():
    cfg=load_config();cfg.update(n_stations=1,min_training_events=1)
    e=events();st=select_stations(e,cfg)
    with pytest.raises(ValueError,match='0 or 1'):
        build_panel(e,st,cfg,pd.DataFrame({'station_id':['001'],'hour':['2025-01-01T00:00:00Z'],'active_flag':[2]}))
    with pytest.raises(ValueError,match='timezone'):
        build_panel(e,st,cfg,pd.DataFrame({'station_id':['001'],'hour':['2025-01-01'],'active_flag':[1]}))
    with pytest.raises(ValueError,match='closed hours'):
        build_panel(e,st,cfg,pd.DataFrame({'station_id':['001'],'hour':['2025-01-01T15:00:00Z'],'active_flag':[0]}))

def test_coordinate_and_duration_threshold_sensitivity():
    f=raw_rides().iloc[:1].copy();cfg=load_config();cfg['max_duration_minutes']=10
    clean,a=clean_chunk(f,cfg);assert len(clean)==0 and a['invalid_duration']==1
    cfg['max_duration_minutes']=180;f.loc[0,'start_lat']=0
    clean,a=clean_chunk(f,cfg);assert len(clean)==0 and a['invalid_coordinate']==1
