"""Publish small hash-pinned model/context files for standalone external replication."""
import json,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd,pyarrow as pa,pyarrow.dataset as ds
from src.common import ROOT,save_json,sha256
p=json.loads((ROOT/'configs/external_202601.json').read_text());start=pd.Timestamp(p['period_start']);stop=pd.Timestamp(p['period_stop'])
dest=ROOT/'models/frozen_2025';dest.mkdir(parents=True,exist_ok=True)
for path,digest in p['model_sha256'].items():
    assert sha256(ROOT/path)==digest;shutil.copyfile(ROOT/path,dest/Path(path).name)
shutil.copyfile(ROOT/'data/processed/stations.csv',dest/'stations.csv')
shutil.copyfile(ROOT/'outputs/official/training_config.json',dest/'training_config.json')
panel=pd.read_parquet(ROOT/'data/processed/panel.parquet');tail=panel[(panel.hour>=start-pd.Timedelta(hours=168))&(panel.hour<start)].copy()
for target in ['departures','arrivals']:tail[target]=tail['observed_'+target]
tail=tail[['station_id','hour','departures','arrivals']];assert len(tail)==5040 and tail.hour.lt(start).all();tail.to_parquet(dest/'history_tail.parquet',index=False)
ids=tail.station_id.unique().tolist();paths=json.loads((ROOT/'data/processed/clean_partitions.json').read_text());dataset=ds.dataset(paths,format='parquet')
condition=(ds.field('start')<pa.scalar(start))&(ds.field('end')>=pa.scalar(start))&(ds.field('end')<pa.scalar(stop))&ds.field('end_station_id').isin(ids)
carry=dataset.to_table(filter=condition,columns=['ride_id','start','end','start_station_id','end_station_id']).to_pandas();carry.to_parquet(dest/'carryover.parquet',index=False)
save_json(dest/'MANIFEST.json',dict(sha256={f.name:sha256(f) for f in sorted(dest.iterdir()) if f.name not in ['MANIFEST.json','README.md']},source_protocol='configs/external_202601.json',models='Exact copies of pre-download hash-frozen Jan-Oct2025 fitted pipelines, never refitted on2026',history='Last168 observed-count hours of original2025 panel, all preceding2026 start; not a verified operating calendar',history_source_sha256=sha256(ROOT/'data/processed/panel.parquet'),carryover_rows=len(carry)))
(dest/'README.md').write_text('''# Frozen 2025 model/context artifacts\n\nThese four fitted pipelines exactly match hashes committed before acquiring January2026 targets. They were fitted/refitted on January–October2025 only. history_tail.parquet contains30x168 preceding recorded-count rows; carryover.parquet preserves independently extracted December-origin arrivals (zero in the captured archive). stations.csv preserves the original training-only site list.\n\nNo original raw trip ZIPs are included. All artifacts and context hashes are in MANIFEST.json. scripts/external_202601.py can use these files in a clean checkout, downloading only the353.83MB January2026 archive. The full project bundle remains necessary for the other full-year reproductions. Source context is aggregated official Citi Bike trip records; underlying operator data-use terms apply. Counts are completed archive records, not latent demand or verified continuous station operation.\n''')
print('Exported frozen models and5040 past-only count-context rows; model hashes match public pre-download protocol.')
