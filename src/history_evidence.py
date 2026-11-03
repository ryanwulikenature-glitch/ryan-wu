"""Historical point evidence with exact GBFS short_name/UID crosswalk.
CityBikes suppresses unchanged bike/free pairs, including flag-only changes:
never turn missing change records into verified operation or perfect uptime.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from .common import ROOT,save_json,distances
from .history_sources import HISTORY,ATTRIBUTION

def crosswalk(stations,root=HISTORY):
    wanted=set(stations.station_id.astype(str));rows=[]
    for path in sorted((root/'wayback').glob('station_information_2025*.json')):
        body=json.loads(path.read_text());stamp=pd.Timestamp(body['last_updated'],unit='s',tz='UTC')
        if stamp.year!=2025:raise ValueError('Not a 2025 feed payload')
        for point in body['data']['stations']:
            sid=str(point.get('short_name'))
            if sid in wanted:
                ref=stations.set_index('station_id').loc[sid]
                coords=pd.DataFrame([dict(latitude=ref.latitude,longitude=ref.longitude),dict(latitude=point['lat'],longitude=point['lon'])])
                distance=distances(coords)[0,1]
                if distance>.2:raise ValueError(f'Historical coordinate mismatch: {sid}')
                rows.append(dict(station_id=sid,gbfs_uid=str(point['station_id']),observed_at=stamp,
                                 capacity=int(point['capacity']),distance_km=distance,source=path.name))
    f=pd.DataFrame(rows)
    if set(f.station_id)!=wanted:raise ValueError('Incomplete official historical crosswalk')
    if f.groupby('gbfs_uid').station_id.nunique().max()>1:raise ValueError('Ambiguous UID identity')
    return f

def extract_history():
    out=HISTORY/'processed';out.mkdir(exist_ok=True)
    st=pd.read_csv(ROOT/'data/processed/stations.csv',dtype={'station_id':str});mapping=crosswalk(st)
    mapping.to_csv(out/'official_capacity_points.csv',index=False)
    lookup=mapping[['station_id','gbfs_uid']].drop_duplicates().set_index('gbfs_uid').station_id.to_dict();parts=[];coverage=[]
    for path in sorted((HISTORY/'raw').glob('2025*-citi-bike-nyc-stats.parquet')):
        frame=pd.read_parquet(path,filters=[('nuid','in',list(lookup))])
        frame['station_id']=frame.nuid.map(lookup);frame['timestamp']=pd.to_datetime(frame.timestamp,utc=True)
        extras=frame.extra.map(json.loads)
        for name,key in [('capacity','slots'),('renting','renting'),('returning','returning'),('last_reported','last_updated')]:frame[name]=extras.map(lambda x:x.get(key))
        frame['reported_at']=pd.to_datetime(frame.last_reported,unit='s',utc=True,errors='coerce')
        frame['report_age_seconds']=(frame.timestamp-frame.reported_at).dt.total_seconds()
        frame['fresh']=frame.report_age_seconds.between(0,300)
        valid=(frame.bikes>=0)&(frame.free>=0)&(frame.capacity>0)&(frame.bikes+frame.free<=frame.capacity)
        frame['valid_counts']=valid
        coverage.append(dict(month=path.name[:6],selected_rows=len(frame),stations=frame.station_id.nunique(),fresh_rows=int(frame.fresh.sum()),invalid_counts=int((~valid).sum()),min_timestamp=frame.timestamp.min(),max_timestamp=frame.timestamp.max()))
        keep=['station_id','nuid','id','timestamp','reported_at','bikes','free','capacity','renting','returning','fresh','valid_counts','latitude','longitude']
        parts.append(frame[keep]);print(path.name,len(frame),'selected observations',flush=True)
    f=pd.concat(parts,ignore_index=True).sort_values(['station_id','timestamp']).drop_duplicates(['station_id','timestamp'],keep='last')
    f.to_parquet(out/'station_status_points.parquet',index=False)
    pd.DataFrame(coverage).to_csv(out/'monthly_coverage.csv',index=False)
    # Record summaries are event-sampled, NOT time-weighted historical stockout rates.
    summary=f.groupby('station_id').agg(observations=('bikes','size'),first=('timestamp','min'),last=('timestamp','max'),capacity_min=('capacity','min'),capacity_max=('capacity','max'),renting_disabled_points=('renting',lambda x:int((x==0).sum())),returning_disabled_points=('returning',lambda x:int((x==0).sum())),zero_bike_points=('bikes',lambda x:int((x==0).sum())),zero_dock_points=('free',lambda x:int((x==0).sum())))
    summary.to_csv(out/'station_evidence_summary.csv')
    # Per-hour observed flags, never fill unobserved hours as operating.
    good=f[f.fresh & f.valid_counts].copy();good['hour']=good.timestamp.dt.floor('h');good['bin']=good.timestamp.dt.minute//5
    good['active']=(good.renting==1)&(good.returning==1)
    hour=good.groupby(['station_id','hour']).agg(observations=('bikes','size'),covered_5min_bins=('bin','nunique'),all_observed_flags_active=('active','all'),observed_disabled=('active',lambda x:bool((~x).any())),min_bikes=('bikes','min'),max_bikes=('bikes','max'),min_capacity=('capacity','min'),max_capacity=('capacity','max')).reset_index()
    hour['sample_supported_active_hour']=hour.covered_5min_bins.eq(12)&hour.all_observed_flags_active
    hour.to_parquet(out/'operating_hour_evidence.parquet',index=False)
    old=pd.read_parquet(ROOT/'data/processed/panel.parquet');unknown=old[old.active_flag==0][['station_id','hour']]
    recovered=unknown.merge(hour[hour.sample_supported_active_hour],on=['station_id','hour'])
    point_supported=unknown.merge(hour[hour.all_observed_flags_active],on=['station_id','hour'])
    point_supported.to_csv(out/'previously_unknown_point_supported.csv',index=False)
    recovered.to_csv(out/'previously_unknown_sample_supported.csv',index=False)
    # Official archived status snapshots use exact contemporary UID, additional direct point evidence.
    direct=[]
    for path in sorted((HISTORY/'wayback').glob('station_status_2025*.json')):
        body=json.loads(path.read_text());stamp=pd.Timestamp(body['last_updated'],unit='s',tz='UTC')
        if stamp.year!=2025:raise ValueError('Nonhistorical payload')
        for point in body['data']['stations']:
            sid=lookup.get(str(point['station_id']))
            if sid is not None:direct.append(dict(station_id=sid,feed_time=stamp,reported_at=pd.to_datetime(point.get('last_reported'),unit='s',utc=True),bikes=point.get('num_bikes_available'),docks=point.get('num_docks_available'),installed=point.get('is_installed'),renting=point.get('is_renting'),returning=point.get('is_returning'),source=path.name))
    pd.DataFrame(direct).to_csv(out/'official_status_points.csv',index=False)
    record=dict(archive_months=len(coverage),selected_stations=len(summary),historical_observations=len(f),official_capacity_points=len(mapping),official_status_points=len(direct),sample_supported_active_hours=int(hour.sample_supported_active_hour.sum()),previous_unknown_recovered=len(recovered),previous_unknown_point_supported=len(point_supported),previous_unknown_remaining=len(unknown)-len(recovered),attribution=ATTRIBUTION,license='ODbL-1.0',semantics='CityBikes change-event samples; flags-only changes are not published; no archive record does not establish downtime, uptime or zero demand. Five-minute complete-bin support is a sampling criterion, not continuous proof. A single active point gives weaker evidence and is reported separately.')
    save_json(out/'evidence_summary.json',record);print(json.dumps(record,indent=2));return f,hour

if __name__=='__main__':extract_history()
