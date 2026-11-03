import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
TARGETS = ['departures','arrivals']

def features(panel, timezone='America/New_York'):
    f=panel.sort_values(['station_id','hour']).reset_index(drop=True).copy()
    f['station_id']=f.station_id.astype(str); f['hour']=pd.to_datetime(f.hour,utc=True)
    if f.duplicated(['station_id','hour']).any(): raise ValueError('Duplicate station-hour')
    for _,g in f.groupby('station_id',sort=False):
        if not g.hour.diff().dropna().eq(pd.Timedelta(hours=1)).all(): raise ValueError('Panel must have continuous UTC hours before lags')
    local=f.hour.dt.tz_convert(timezone)
    for name,values in [('hour_of_day',local.dt.hour),('day_of_week',local.dt.dayofweek),('month',local.dt.month)]: f[name]=values
    f['weekend']=(f.day_of_week>=5).astype(int)
    holidays=USFederalHolidayCalendar().holidays(local.min().date(),local.max().date())
    f['holiday']=local.dt.tz_localize(None).dt.normalize().isin(holidays).astype(int)
    f['hour_sin']=np.sin(2*np.pi*f.hour_of_day/24); f['hour_cos']=np.cos(2*np.pi*f.hour_of_day/24)
    f['week_sin']=np.sin(2*np.pi*(f.day_of_week*24+f.hour_of_day)/168)
    f['week_cos']=np.cos(2*np.pi*(f.day_of_week*24+f.hour_of_day)/168)
    for target,prefix in zip(TARGETS,['dep','arr']):
        group=f.groupby('station_id',sort=False)[target]
        for lag in [1,24,168]: f[f'{prefix}_lag{lag}']=group.shift(lag)
        for window in [24,168]:
            for stat in ['mean','std']:
                f[f'{prefix}_roll{window}_{stat}']=group.transform(lambda x:getattr(x.shift(1).rolling(window,min_periods=window),stat)())
    f['split']=np.select([local.dt.month<=8,local.dt.month<=10],['train','validation'],default='test')
    return f

NUMERIC=['hour_of_day','day_of_week','month','weekend','holiday','hour_sin','hour_cos','week_sin','week_cos'] + [f'{p}_lag{k}' for p in ['dep','arr'] for k in [1,24,168]] + [f'{p}_roll{w}_{s}' for p in ['dep','arr'] for w in [24,168] for s in ['mean','std']]
