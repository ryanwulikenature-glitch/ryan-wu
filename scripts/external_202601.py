"""Evaluate frozen 2025 models on newly acquired January 2026 archived counts."""
import hashlib,json,subprocess,sys,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import joblib,numpy as np,pandas as pd,requests
import pyarrow as pa
import pyarrow.dataset as ds
from src.common import ROOT,load_config,save_json,sha256
from src.prepare import csv_chunks,clean_chunk
from src.features import features
from src.metrics import forecast_metrics,block_bootstrap

protocol=json.loads((ROOT/'configs/external_202601.json').read_text())
frozen=ROOT/'models/frozen_2025'
def model_path(path):return ROOT/path if (ROOT/path).exists() else frozen/Path(path).name
for path,digest in protocol['model_sha256'].items():assert sha256(model_path(path))==digest,'Frozen model changed'
station_path=ROOT/'data/processed/stations.csv' if (ROOT/'data/processed/stations.csv').exists() else frozen/'stations.csv'
assert sha256(station_path)==protocol['station_file_sha256']
for path,key in [('src/features.py','features_source_sha256'),('src/prepare.py','cleaning_source_sha256')]:assert sha256(ROOT/path)==protocol[key]
if (frozen/'MANIFEST.json').exists():
    for name,digest in json.loads((frozen/'MANIFEST.json').read_text())['sha256'].items():assert sha256(frozen/name)==digest
revision=subprocess.run(['git','log','-1','--format=%H','--','configs/external_202601.json'],cwd=ROOT,capture_output=True,text=True)
captured=ROOT/'reports/results/external_202601/source.json'
previous=json.loads(captured.read_text()) if captured.exists() else None
freeze_commit=revision.stdout.strip() if revision.returncode==0 and revision.stdout.strip() else previous['protocol_freeze_commit'] if previous else None
if not freeze_commit:raise ValueError('No verifiable frozen protocol reference')
out=ROOT/'outputs/external_202601';out.mkdir(parents=True,exist_ok=True);raw=ROOT/'data/holdout/raw';raw.mkdir(parents=True,exist_ok=True)
archive=raw/'202601-citibike-tripdata.zip';source=raw/'source.json'
if not archive.exists():
    print('Downloading new external January 2026 archive after protocol freeze',flush=True)
    with requests.get(protocol['url'],stream=True,timeout=90) as response:
        response.raise_for_status();digest=hashlib.sha256();size=0
        with open(archive.with_suffix('.part'),'wb') as f:
            for block in response.iter_content(1024*1024):f.write(block);digest.update(block);size+=len(block)
        if response.headers.get('Content-Length'):assert size==int(response.headers['Content-Length'])
        if previous:assert digest.hexdigest()==previous['sha256'],'Source differs from captured external archive; refusing replacement'
        archive.with_suffix('.part').replace(archive)
        save_json(source,dict(url=protocol['url'],retrieved_utc=datetime.now(timezone.utc).isoformat(),bytes=size,sha256=digest.hexdigest(),last_modified=response.headers.get('Last-Modified'),protocol_freeze_commit=freeze_commit))
manifest=json.loads(source.read_text());assert sha256(archive)==manifest['sha256'];assert pd.Timestamp(manifest['retrieved_utc'])>pd.Timestamp(protocol['frozen_utc'])
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
save_json(out/'source.json',manifest)
st=pd.read_csv(station_path,dtype={'station_id':str});ids=set(st.station_id);start=pd.Timestamp(protocol['period_start']);stop=pd.Timestamp(protocol['period_stop'])
paths=json.loads((ROOT/'data/processed/clean_partitions.json').read_text()) if (ROOT/'data/processed/clean_partitions.json').exists() else []
paths=[str(ROOT/'data/interim'/Path(p).name) for p in paths]
if paths and all(Path(p).exists() for p in paths):
    old=ds.dataset(paths,format='parquet');condition=(ds.field('start')<pa.scalar(start))&(ds.field('end')>=pa.scalar(start))&(ds.field('end')<pa.scalar(stop))&ds.field('end_station_id').isin(list(ids))
    carry=old.to_table(filter=condition,columns=['ride_id','start','end','start_station_id','end_station_id']).to_pandas()
else:carry=pd.read_parquet(frozen/'carryover.parquet')
seen=set(carry.ride_id.astype(str));parts=[carry];audit=Counter();cfg=load_config(ROOT/'configs/official_counts.json');member_rows=Counter()
assert cfg['max_duration_minutes']==protocol['cutoff_minutes'] and cfg['timezone']==protocol['timezone'],'Cleaning configuration differs from frozen protocol'
for member,chunk in csv_chunks(archive):
    audit['all_raw_rows']+=len(chunk);member_rows[member]+=len(chunk);selected=chunk.start_station_id.isin(ids)|chunk.end_station_id.isin(ids)
    cleaned,counts=clean_chunk(chunk.loc[selected],cfg);audit.update(counts);keep=[]
    for rid in cleaned.ride_id.astype(str):keep.append(rid not in seen);seen.add(rid)
    audit['selected_duplicates_removed']+=len(keep)-sum(keep)
    cleaned=cleaned.loc[keep,['ride_id','start','end','start_station_id','end_station_id']]
    if len(cleaned):parts.append(cleaned)
rides=pd.concat(parts,ignore_index=True);assert rides.ride_id.is_unique
panel=pd.MultiIndex.from_product([sorted(ids),pd.date_range(start,stop,freq='h',inclusive='left')],names=['station_id','hour']).to_frame(index=False)
for target,idcol,timecol in [('departures','start_station_id','start'),('arrivals','end_station_id','end')]:
    r=rides[rides[idcol].isin(ids)&rides[timecol].between(start,stop,inclusive='left')].copy();r['hour']=r[timecol].dt.floor('h')
    counts=r.groupby([idcol,'hour']).size();counts.index.names=['station_id','hour']
    panel[target]=counts.reindex(pd.MultiIndex.from_frame(panel[['station_id','hour']]),fill_value=0).to_numpy();assert panel[target].sum()==len(r)
panel.to_parquet(out/'panel.parquet',index=False)
history=pd.read_parquet(ROOT/'data/processed/panel.parquet') if (ROOT/'data/processed/panel.parquet').exists() else pd.read_parquet(frozen/'history_tail.parquet')
history=history[(history.hour>=start-pd.Timedelta(hours=168))&(history.hour<start)].copy()
assert len(history)==len(ids)*168
for target in ['departures','arrivals']:
    if 'observed_'+target in history:history[target]=history['observed_'+target]
full=pd.concat([history[panel.columns],panel],ignore_index=True);f=features(full,cfg['timezone']);f=f[f.hour>=start].copy();f['split']='external_202601'
assert len(f)==744*30 and f[['dep_lag168','arr_lag168']].notna().all().all()
pred=f[['station_id','hour','departures','arrivals']].copy();records=[];comparisons=[];local=f.hour.dt.tz_convert(cfg['timezone'])
strata={'all':np.ones(len(f),bool),'weekday':local.dt.dayofweek<5,'weekend':local.dt.dayofweek>=5,'peak':local.dt.hour.isin([7,8,9,16,17,18])}
for target,prefix in [('departures','dep'),('arrivals','arr')]:
    pp={'last_hour':f[prefix+'_lag1'].to_numpy(),'seasonal_naive':f[prefix+'_lag168'].to_numpy()}
    for kind in ['poisson','xgboost']:pp[kind]=np.maximum(0,joblib.load(model_path(f'outputs/official/{target}_{kind}.joblib')).predict(f))
    for kind,values in pp.items():
        pred[prefix+'_'+kind]=values
        for stratum,mask in strata.items():records.append(dict(model=kind,target=target,split='external_202601',stratum=stratum,**forecast_metrics(f.loc[mask,target],np.asarray(values)[mask])))
    for baseline in ['last_hour','seasonal_naive']:
        delta=np.abs(f[target].to_numpy()-pp['xgboost'])-np.abs(f[target].to_numpy()-pp[baseline]);daily=pd.DataFrame({'day':local.dt.date,'delta':delta}).groupby('day').delta.mean();lo,hi=block_bootstrap(daily.to_numpy())
        comparisons.append(dict(target=target,baseline=baseline,model='xgboost',local_days=len(daily),mean_daily_mae_difference=float(daily.mean()),ci_low=lo,ci_high=hi))
pd.DataFrame(records).to_csv(out/'forecast_metrics.csv',index=False);pd.DataFrame(comparisons).to_csv(out/'paired_daily_comparisons.csv',index=False);pred.to_parquet(out/'predictions.parquet',index=False)
for path,digest in protocol['model_sha256'].items():assert sha256(model_path(path))==digest,'Evaluation changed model'
save_json(out/'validation.json',dict(protocol_freeze_commit=freeze_commit,protocol=protocol,source=manifest,audit=dict(audit),csv_member_rows=dict(member_rows),december_origin_carryover=len(carry),selected_rides_including_carryover=len(rides),station_hours=len(panel),hours=744,stations=len(ids),departure_records=int(panel.departures.sum()),arrival_records=int(panel.arrivals.sum()),model_hashes_unchanged=True,models_refitted=False,rolling_protocol='One-step archived-count forecasting; prior January observations become available only for subsequent-hour lags',operating_state='No January operating calendar inferred; zero means no retained completed record, not proven station operation or latent zero demand'))
small=ROOT/'reports/results/external_202601';small.mkdir(parents=True,exist_ok=True)
for name in ['forecast_metrics.csv','paired_daily_comparisons.csv','source.json','validation.json']:(small/name).write_bytes((out/name).read_bytes())
print(pd.DataFrame(records).query('stratum=="all"').to_csv(index=False));print('PASS: frozen models unchanged; 744 x 30 new external hours; cleaning, endpoint counts, past-only lags and full-period metrics reconciled.',flush=True)
