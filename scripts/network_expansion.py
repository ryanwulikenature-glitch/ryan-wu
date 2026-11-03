import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from src.common import ROOT,load_config,save_json
from src.prepare import select_stations,build_panel
from src.train import train
from src.simulate import simulate
cfg=load_config(ROOT/'configs/official_counts.json')|{'n_stations':60,'geofence_path':'data/geography/manhattan_official_26c.geojson','hours':336}
base=json.loads((ROOT/'configs/weather.json').read_text());cfg['fixed_xgboost_params']=base['fixed_xgboost_params']
out=ROOT/'outputs/network60';out.mkdir(parents=True,exist_ok=True);data=ROOT/'data/network60';data.mkdir(exist_ok=True)
paths=sorted((ROOT/'data/interim/event_partitions').glob('*.parquet'));summaries=[]
for path in paths:
    f=pd.read_parquet(path);local=f.hour.dt.tz_convert(cfg['timezone']);f=f[(local.dt.year==2025)&(local.dt.month<=8)].copy()
    if f.empty:continue
    f['month']=f.hour.dt.tz_convert(cfg['timezone']).dt.month
    s=f.groupby(['station_id','month'],as_index=False).agg(latitude=('latitude','median'),longitude=('longitude','median'),lat_min=('latitude','min'),lat_max=('latitude','max'),lon_min=('longitude','min'),lon_max=('longitude','max'),count=('count','sum'),station_name=('station_name','first'))
    s['hour']=s.month.map(lambda m:pd.Timestamp(year=2025,month=int(m),day=1,tz=cfg['timezone']).tz_convert('UTC'))
    summaries.append(s[['station_id','hour','latitude','longitude','count','station_name']])
    for lat,lon in [('lat_min','lon_min'),('lat_max','lon_max')]:
        x=s[['station_id','hour','station_name']].copy();x['latitude']=s[lat];x['longitude']=s[lon];x['count']=0;summaries.append(x)
st=select_stations(pd.concat(summaries,ignore_index=True),cfg);st.to_csv(data/'stations.csv',index=False)
events=pd.concat([pd.read_parquet(p,filters=[('station_id','in',st.station_id.tolist())]) for p in paths],ignore_index=True)
panel=build_panel(events,st,cfg);panel.to_parquet(data/'panel.parquet',index=False)
save_json(data/'config.json',cfg);save_json(data/'data_quality_summary.json',dict(data_kind='official',stations=60,panel_rows=len(panel),unknown_hours=int((panel.active_flag==0).sum()),source='lossless audited event partitions reused; training-only summaries and official polygon',geography_version='26c declared analysis boundary, not a historical inventory source'))
pred,metrics=train(data,out,cfg);summary,h=simulate(pred,st,cfg,out,hours=336)
save_json(out/'protocol.json',dict(config=cfg,scope='60-site scalability and fixed-resource stress experiment; different demand footprint from 30 sites, not an identical-demand treatment effect',selection='training-only activity and drift; official polygon',budget_per_hour=12,hours=336))
print(summary.to_csv(index=False));print('PASS: 60-station training-only selection, complete panel, fixed-architecture forecast and three-policy 336-hour network expansion.')
