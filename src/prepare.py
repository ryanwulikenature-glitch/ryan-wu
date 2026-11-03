"""Chunked raw ingestion; global disk-backed dedup; auditable UTC panel."""
import argparse
import json
import sqlite3
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
from .common import ROOT, load_config, save_json, sha256, distances

REQUIRED = ['ride_id', 'started_at', 'ended_at', 'start_station_id', 'end_station_id',
            'start_lat', 'start_lng', 'end_lat', 'end_lng']

def csv_chunks(path, chunksize=200_000):
    kw = dict(dtype={'ride_id': 'string', 'start_station_id': 'string', 'end_station_id': 'string'}, chunksize=chunksize)
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as z:
            for name in sorted(z.namelist()):
                if name.lower().endswith('.csv') and not name.startswith('__MACOSX'):
                    with z.open(name) as f:
                        for chunk in pd.read_csv(f, **kw): yield name, chunk
    else:
        for chunk in pd.read_csv(path, **kw): yield path.name, chunk

def local_to_utc(series, tz):
    parsed = pd.to_datetime(series, errors='coerce', format='mixed')
    if isinstance(parsed.dtype, pd.DatetimeTZDtype): return parsed.dt.tz_convert('UTC')
    # No offset/fold in official timestamps: unresolved DST folds/gaps are excluded and audited.
    return parsed.dt.tz_localize(tz, ambiguous='NaT', nonexistent='NaT').dt.tz_convert('UTC')

def clean_chunk(frame, cfg):
    missing = set(REQUIRED) - set(frame)
    if missing: raise ValueError(f'Missing columns: {sorted(missing)}')
    f = frame.copy(); audit = Counter(raw_rows=len(f))
    for c in ['ride_id','start_station_id','end_station_id']:
        f[c] = f[c].astype('string').str.strip().replace('', pd.NA)
    f['start'] = local_to_utc(f.started_at, cfg['timezone'])
    f['end'] = local_to_utc(f.ended_at, cfg['timezone'])
    minutes = (f.end - f.start).dt.total_seconds() / 60
    checks = [('missing_id', f[['ride_id','start_station_id','end_station_id']].isna().any(axis=1)),
              ('invalid_time_or_dst', f.start.isna() | f.end.isna()),
              ('invalid_duration', (minutes <= 0) | (minutes > cfg['max_duration_minutes']))]
    coords = f[['start_lat','start_lng','end_lat','end_lng']].apply(pd.to_numeric, errors='coerce')
    f[coords.columns] = coords
    checks.append(('invalid_coordinate', ~coords.start_lat.between(40,42) | ~coords.end_lat.between(40,42) |
                   ~coords.start_lng.between(-75,-72) | ~coords.end_lng.between(-75,-72)))
    valid = pd.Series(True, index=f.index)
    for reason, bad in checks:
        audit[reason] = int((valid & bad).sum()); valid &= ~bad
    f = f.loc[valid].copy(); audit['clean_before_dedup'] = len(f)
    return f, audit

def select_stations(events, cfg):
    local = events.hour.dt.tz_convert(cfg['timezone'])
    train = events[(local.dt.year == cfg['year']) & (local.dt.month <= 8)].copy()
    train['month'] = train.hour.dt.tz_convert(cfg['timezone']).dt.month
    stats = train.groupby('station_id').agg(latitude=('latitude','median'), longitude=('longitude','median'),
                    training_events=('count','sum'), active_months=('month','nunique'), station_name=('station_name','first'))
    lowlon, lowlat, highlon, highlat = cfg['bbox']
    stats = stats[stats.longitude.between(lowlon,highlon) & stats.latitude.between(lowlat,highlat) &
                  (stats.active_months >= cfg['min_active_months']) & (stats.training_events >= cfg['min_training_events'])]
    if cfg.get('geofence_path'):
        from .geography import membership
        stats=stats.loc[membership(stats,cfg['geofence_path'])]
    stable = []
    for sid, points in train[train.station_id.isin(stats.index)].groupby('station_id',sort=False):
        row=stats.loc[sid]
        points = points[['latitude','longitude']].drop_duplicates()
        lat=np.radians(points.latitude.to_numpy());lon=np.radians(points.longitude.to_numpy())
        ref_lat,ref_lon=np.radians([row.latitude,row.longitude])
        delta=np.sin((lat-ref_lat)/2)**2+np.cos(lat)*np.cos(ref_lat)*np.sin((lon-ref_lon)/2)**2
        drift=6371.0088*2*np.arcsin(np.sqrt(np.clip(delta,0,1)))
        if drift.max() <= cfg['max_coordinate_drift_km']: stable.append(sid)
    stats = stats.loc[stable].sort_values(['active_months','training_events'], ascending=False).head(cfg['n_stations']).reset_index()
    if len(stats) < cfg['n_stations']: raise ValueError(f'Only {len(stats)} eligible training-period stations; requested {cfg["n_stations"]}')
    stats['capacity'] = cfg['capacity']; stats['capacity_source'] = 'assumed'
    stats['selection_reason'] = 'training_only_activity_bbox_and_drift_filter'
    return stats

def build_panel(events, stations, cfg, calendar=None):
    tz = cfg['timezone']; year = cfg['year']
    start = pd.Timestamp(f'{year}-01-01', tz=tz).tz_convert('UTC')
    stop = pd.Timestamp(f'{year+1}-01-01', tz=tz).tz_convert('UTC')
    idx = pd.MultiIndex.from_product([stations.station_id, pd.date_range(start, stop, freq='h', inclusive='left')], names=['station_id','hour'])
    relevant = events[events.station_id.isin(stations.station_id) & events.hour.between(start, stop, inclusive='left')]
    counts = relevant.groupby(['station_id','hour','direction'])['count'].sum().unstack('direction', fill_value=0)
    panel = counts.reindex(idx, fill_value=0).reset_index()
    for c in ['departures','arrivals']:
        if c not in panel: panel[c] = 0
        panel[c] = panel[c].fillna(0).astype(int)
        assert panel[c].sum() == relevant.loc[relevant.direction == c,'count'].sum()
        panel[f'observed_{c}'] = panel[c]
    panel['active_flag'] = ((panel.departures + panel.arrivals) > 0).astype(int)
    panel['activity_source'] = 'hour_with_observed_events_only'
    if calendar is not None:
        cal = calendar.copy(); cal['station_id'] = cal.station_id.astype(str)
        if not cal.active_flag.isin([0,1]).all(): raise ValueError('Calendar active_flag must be 0 or 1')
        if any(pd.Timestamp(value).tzinfo is None for value in cal.hour): raise ValueError('Calendar hours require explicit timezone')
        cal['hour'] = pd.to_datetime(cal.hour, utc=True)
        if cal.duplicated(['station_id','hour']).any(): raise ValueError('Duplicate calendar keys')
        panel = panel.merge(cal[['station_id','hour','active_flag']].rename(columns={'active_flag':'confirmed_active'}), on=['station_id','hour'], how='left', validate='one_to_one')
        inconsistent = (panel.confirmed_active == 0) & ((panel.departures+panel.arrivals)>0)
        if inconsistent.any(): raise ValueError('Calendar closed hours contain observed events')
        known = panel.confirmed_active.notna()
        panel.loc[known, 'active_flag'] = panel.loc[known, 'confirmed_active'].astype(int)
        panel.loc[known, 'activity_source'] = 'provided_operating_calendar'
        panel = panel.drop(columns='confirmed_active')
    panel.loc[panel.active_flag == 0, ['departures','arrivals']] = np.nan
    panel['netflow'] = panel.arrivals - panel.departures
    return panel

def prepare(raw, out, cfg, calendar=None, allow_incomplete=False):
    raw, out = Path(raw), Path(out); interim = out.parent / 'interim'
    out.mkdir(parents=True, exist_ok=True); interim.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in raw.iterdir() if p.suffix.lower() in {'.zip','.csv'} and not p.name.startswith('JC'))
    if not files: raise ValueError('No raw CSV/ZIP files. Run download first or use the separate demo command.')
    manifests=[]; audits=[]; event_parts=[]; candidates=[]; clean_parts=[]; seen_hashes=set(); months=set()
    event_dir=interim/'event_partitions';event_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=interim) as tmp:
        db = sqlite3.connect(str(Path(tmp)/'dedup.sqlite'))
        db.execute('CREATE TABLE seen (ride_id TEXT PRIMARY KEY, source TEXT)')
        for path in files:
            digest = sha256(path)
            if digest in seen_hashes:
                manifests.append(dict(filename=path.name, sha256=digest, bytes=path.stat().st_size, skipped_duplicate_file=True)); continue
            seen_hashes.add(digest)
            for member, chunk in csv_chunks(path):
                f, audit = clean_chunk(chunk, cfg)
                keep=[]; intra=cross=0
                source=f'{path.name}:{member}'
                for rid in f.ride_id:
                    try: db.execute('INSERT INTO seen VALUES (?,?)',(str(rid),source)); keep.append(True)
                    except sqlite3.IntegrityError:
                        old = db.execute('SELECT source FROM seen WHERE ride_id=?',(str(rid),)).fetchone()[0]
                        intra += old == source; cross += old != source; keep.append(False)
                f=f.loc[keep]; db.commit()
                audit.update(duplicate_within_member=intra, duplicate_across_members=cross, retained=len(f))
                audits.append(dict(filename=path.name,member=member,**audit,
                                   observed_months=','.join(map(str,sorted(f.start.dt.tz_convert(cfg['timezone']).dt.month.unique()))),
                                   min_start=f.start.min(),max_start=f.start.max()))
                if f.empty: continue
                local=f.start.dt.tz_convert(cfg['timezone'])
                months.update(local[local.dt.year==cfg['year']].dt.month.unique().tolist())
                # Retain paired clean rides for the optional causal event replay, as partitioned Parquet.
                part=interim/f'clean_rides_{len(clean_parts):05d}.parquet'
                f.to_parquet(part,index=False); clean_parts.append(str(part))
                for direction,prefix,time in [('departures','start','start'),('arrivals','end','end')]:
                    e=pd.DataFrame({'station_id':f[f'{prefix}_station_id'].astype(str), 'hour':f[time].dt.floor('h'),
                                    'latitude':f[f'{prefix}_lat'],'longitude':f[f'{prefix}_lng'],
                                    'station_name':f.get(f'{prefix}_station_name',f[f'{prefix}_station_id'])})
                    e=e.groupby(['station_id','hour'],as_index=False).agg(latitude=('latitude','median'),longitude=('longitude','median'),station_name=('station_name','first'),count=('station_id','size'))
                    assert int(e['count'].sum())==len(f)
                    e['direction']=direction
                    event_path=event_dir/f'events_{len(event_parts):05d}.parquet'
                    e.to_parquet(event_path,index=False);event_parts.append(event_path)
                    local_hour=e.hour.dt.tz_convert(cfg['timezone'])
                    t=e[(local_hour.dt.year==cfg['year'])&(local_hour.dt.month<=8)].copy()
                    if not t.empty:
                        t['month']=t.hour.dt.tz_convert(cfg['timezone']).dt.month
                        small=t.groupby(['station_id','month'],as_index=False).agg(
                            latitude=('latitude','median'),longitude=('longitude','median'),
                            lat_min=('latitude','min'),lat_max=('latitude','max'),
                            lon_min=('longitude','min'),lon_max=('longitude','max'),
                            count=('count','sum'),station_name=('station_name','first'))
                        small['hour']=small.month.map(lambda m:pd.Timestamp(year=cfg['year'],month=int(m),day=1,tz=cfg['timezone']).tz_convert('UTC'))
                        candidates.append(small[['station_id','hour','latitude','longitude','count','station_name']])
                        for lat,lon in [('lat_min','lon_min'),('lat_max','lon_max')]:
                            extreme=small[['station_id','hour','station_name']].copy()
                            extreme['latitude']=small[lat];extreme['longitude']=small[lon];extreme['count']=0
                            candidates.append(extreme)
                print(f'Cleaned {path.name}/{member}: retained {len(f):,}',flush=True)
            manifests.append(dict(filename=path.name,sha256=digest,bytes=path.stat().st_size,skipped_duplicate_file=False))
        db.close()
    pd.DataFrame(manifests).to_csv(interim/'file_manifest.csv',index=False)
    audit=pd.DataFrame(audits); audit.to_csv(interim/'monthly_audit.csv',index=False)
    if not allow_incomplete and months != set(range(1,13)):
        raise ValueError(f'Year coverage incomplete: months={sorted(months)}; audits saved. Explicit --allow-incomplete for exploratory runs only.')
    if not event_parts: raise ValueError('No valid rides after cleaning')
    stations=select_stations(pd.concat(candidates,ignore_index=True),cfg); stations.to_csv(out/'stations.csv',index=False)
    stations['selection_reason']='training_only_activity_bbox_and_chunk_hourly_coordinate_envelope'
    stations.to_csv(out/'stations.csv',index=False)
    events=pd.concat([pd.read_parquet(path,filters=[('station_id','in',stations.station_id.tolist())]) for path in event_parts],ignore_index=True)
    cal=pd.read_csv(calendar,dtype={'station_id':str}) if calendar else None
    panel=build_panel(events,stations,cfg,cal); panel.to_parquet(out/'panel.parquet',index=False)
    summary={'data_kind':cfg['data_kind'],'months':sorted(months),'complete_year':months==set(range(1,13)),
             'raw_rows':int(audit.raw_rows.sum()),'retained_rides':int(audit.retained.sum()),
             'stations':len(stations),'panel_rows':len(panel),'unknown_hours':int((panel.active_flag==0).sum()),
             'count_conservation':'passed','dst_policy':'exclude unresolvable local folds/gaps; retain UTC hours',
             'zero_policy':'unobserved hours missing unless operating calendar confirms activity'}
    save_json(out/'data_quality_summary.json',summary)
    pd.DataFrame([summary]).to_csv(out/'data_quality_summary.csv',index=False)
    save_json(out/'clean_partitions.json',clean_parts); save_json(out/'config.json',cfg)
    print(json.dumps(summary,ensure_ascii=False))
    return panel,stations

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--config'); p.add_argument('--raw',type=Path,default=ROOT/'data/raw'); p.add_argument('--out',type=Path,default=ROOT/'data/processed'); p.add_argument('--calendar'); p.add_argument('--allow-incomplete',action='store_true'); a=p.parse_args()
    prepare(a.raw,a.out,load_config(a.config),a.calendar,a.allow_incomplete)
