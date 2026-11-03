import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from src.common import ROOT
p=pd.read_parquet(ROOT/'data/processed/panel.parquet');st=pd.read_csv(ROOT/'data/processed/stations.csv',dtype={'station_id':str});out=ROOT/'outputs/official'
local=p.hour.dt.tz_convert('America/New_York');p['hour_local']=local.dt.hour;p['day_type']=local.dt.dayofweek.map(lambda x:'Weekday' if x<5 else 'Weekend');p['net']=p.observed_arrivals-p.observed_departures
curve=p.groupby(['day_type','hour_local'])[['observed_departures','observed_arrivals']].mean();curve.to_csv(out/'weekday_weekend_profiles.csv')
fig,axes=plt.subplots(1,2,figsize=(11,4))
for ax,target in zip(axes,['observed_departures','observed_arrivals']):
    curve[target].unstack(0).plot(ax=ax);ax.set_ylabel('Retained records / station-hour');ax.set_title(target.replace('observed_',''));ax.set_xlabel('NYC local hour')
fig.suptitle('Official 2025 archive counts: zero records do not prove operation',fontsize=10);fig.tight_layout();fig.savefig(out/'figures/eda_weekday_weekend.png',dpi=140);plt.close(fig)
weekday=p[p.day_type=='Weekday'];morning=weekday[weekday.hour_local.isin([7,8,9])].groupby('station_id').net.mean();evening=weekday[weekday.hour_local.isin([16,17,18])].groupby('station_id').net.mean()
peaks=pd.concat([morning.rename('morning_net'),evening.rename('evening_net')],axis=1).reset_index().merge(st[['station_id','station_name','latitude','longitude']],on='station_id',validate='one_to_one')
peaks.to_csv(out/'peak_station_flows.csv',index=False)
fig,axes=plt.subplots(1,2,figsize=(11,4))
for ax,column in zip(axes,['morning_net','evening_net']):
    v=peaks[column];plot=ax.scatter(peaks.longitude,peaks.latitude,c=v,cmap='coolwarm',vmin=-max(abs(v)),vmax=max(abs(v)));fig.colorbar(plot,ax=ax,label='Arrivals minus departures / hour');ax.set_title(column);ax.set_xlabel('Longitude');ax.set_ylabel('Latitude')
fig.suptitle('Descriptive weekday peak imbalance, not causal evidence',fontsize=10);fig.tight_layout();fig.savefig(out/'figures/eda_peak_map.png',dpi=140);plt.close(fig)
rows=['# EDA: operational hypotheses from actual archive counts','','These are descriptive associations across the full year. They were not used to tune test models. Zero archive records are not verified station operation.','', '## Morning outflow: largest negative mean netflow','```csv',peaks.nsmallest(5,'morning_net')[['station_id','station_name','morning_net']].to_csv(index=False),'```','## Evening inflow: largest mean netflow','```csv',peaks.nlargest(5,'evening_net')[['station_id','station_name','evening_net']].to_csv(index=False),'```']
rows+=['## Interpretation',f'Morning station netflows range from {morning.min():.2f} to {morning.max():.2f} recorded bikes/hour; evening from {evening.min():.2f} to {evening.max():.2f}. Opposite-signed sites are candidate complements, subject to radius and inventory constraints. This supports testing rebalancing during commuting peaks; it does not identify real shortages. Weekday/weekend profiles show timing differences without claiming statistical significance or attributing differences to weather.']
(ROOT/'reports/eda_business_findings.md').write_text('\n'.join(rows))
print('PASS: weekday/weekend curves, peak spatial maps and named-station findings generated.')
