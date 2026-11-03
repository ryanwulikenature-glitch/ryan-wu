"""Continuous paired-ride and road-fleet simulation with causal pickup/delivery delays."""
import heapq,time
import numpy as np
import pandas as pd
from .optimize import plan,validate_moves
from .pickup_delivery import plan_routes

POLICIES=['none','instant_milp_relaxation','road_greedy','road_milp']

def simulate_transport(rides,predictions,stations,cfg,travel_seconds,road_km,initial_inventory,capacities,hours=48):
    stations=stations.sort_values('station_id').reset_index(drop=True);ids=stations.station_id.astype(str).tolist();lookup={s:k for k,s in enumerate(ids)};n=len(ids)
    p=predictions.copy();p['hour']=pd.to_datetime(p.hour,utc=True);times=sorted(p.hour.unique())[:hours]
    if not times or len(times)<hours:raise ValueError('Insufficient transport horizon')
    if len(times)>1 and not pd.Series(times).diff().dropna().eq(pd.Timedelta(hours=1)).all():raise ValueError('Non-contiguous transport hours')
    start=times[0];stop=times[-1]+pd.Timedelta(hours=1);c=np.asarray(capacities,int);initial=np.asarray(initial_inventory,int)
    if c.shape!=(n,) or initial.shape!=(n,) or (initial<0).any() or (initial>c).any():raise ValueError('Invalid initial fleet')
    distance=np.asarray(road_km,float);travel=np.asarray(travel_seconds,float)
    rides=rides.copy();rides['start']=pd.to_datetime(rides.start,utc=True);rides['end']=pd.to_datetime(rides.end,utc=True)
    if rides.ride_id.duplicated().any() or (rides.end<=rides.start).any():raise ValueError('Invalid paired rides')
    rides=rides[(rides.start<stop)&(rides.end>=start)];base_events=[];initial_transit=set()
    for row in rides.itertuples():
        s=lookup.get(str(row.start_station_id));t=lookup.get(str(row.end_station_id));rid=str(row.ride_id)
        if s is None and t is None:continue
        if row.start<start:initial_transit.add(rid)
        elif s is not None:base_events.append((row.start,5,'customer_departure',(rid,s,t)))
        if row.end<stop:base_events.append((row.end,1,'customer_return',(rid,s,t)))
    frames={t:p[p.hour==t].set_index('station_id').reindex(ids) for t in times}
    if any(f[['pred_dep','pred_arr']].isna().any().any() for f in frames.values()):raise ValueError('Missing forecasts')
    rows=[];truck_logs=[];route_logs=[];closing=[]
    for policy in POLICIES:
        inv=initial.copy();transit=set(initial_transit);held=set();rejected=set();incoming=outgoing=0;initial_fleet=int(inv.sum())+len(transit)
        fleet=[dict(ready=True,cargo={},work={}) for _ in range(cfg.get('trucks',2))];queue=[];serial=0;statistics=None;active_hour=None
        def push(stamp,priority,kind,data):
            nonlocal serial;serial+=1;heapq.heappush(queue,(stamp,priority,serial,kind,data))
        for stamp,priority,kind,data in base_events:push(stamp,priority,kind,data)
        for stamp in times:push(stamp,9,'dispatch',None)
        def cargo_count():return sum(sum(v['quantity'] for v in truck['cargo'].values()) for truck in fleet)
        def verify():
            assert ((inv>=0)&(inv<=c)).all()
            assert all(0<=sum(v['quantity'] for v in truck['cargo'].values())<=cfg.get('truck_capacity',6) for truck in fleet)
            assert int(inv.sum())+len(transit)+len(held)+cargo_count()==initial_fleet+incoming-outgoing
        def handle(stamp,kind,data):
            nonlocal incoming,outgoing,inv
            if kind=='customer_departure':
                rid,s,t=data;statistics['departure_requests']+=1
                if inv[s]>0:inv[s]-=1;transit.add(rid);statistics['served_departures']+=1
                else:rejected.add(rid);statistics['unmet_departures']+=1
            elif kind=='customer_return':
                rid,s,t=data
                if rid in rejected:statistics['suppressed_returns']+=1
                else:
                    if rid not in transit:
                        if s is not None:raise ValueError('Unmatched return')
                        incoming+=1;transit.add(rid)
                    transit.remove(rid)
                    if t is None:outgoing+=1
                    elif inv[t]<c[t]:inv[t]+=1;statistics['served_returns']+=1
                    else:held.add(rid);statistics['blocked_arrivals']+=1
            elif kind=='pickup':
                k,job,source,target,requested=data;truck=fleet[k];q=min(requested,int(inv[source]),cfg.get('truck_capacity',6)-sum(x['quantity'] for x in truck['cargo'].values()))
                inv[source]-=q
                if q:truck['cargo'][job]=dict(job_id=job,target=target,quantity=q)
                statistics['picked_bikes']+=q;statistics['failed_pickup_bikes']+=requested-q
                truck_logs.append(dict(timestamp=stamp,strategy=policy,truck=k,event='pickup',job=job,station=ids[source],requested=requested,actual=q,cargo_after=sum(x['quantity'] for x in truck['cargo'].values()),stock_after=int(inv[source]),capacity=int(c[source])))
            elif kind=='delivery':
                k,job,target,requested=data;truck=fleet[k];item=truck['cargo'].get(job);onboard=item['quantity'] if item else 0;q=min(onboard,int(c[target]-inv[target]))
                inv[target]+=q
                if item:
                    item['quantity']-=q
                    if not item['quantity']:del truck['cargo'][job]
                statistics['delivered_bikes']+=q;statistics['blocked_transfer_attempts']+=onboard-q
                truck_logs.append(dict(timestamp=stamp,strategy=policy,truck=k,event='delivery_after_unload',job=job,station=ids[target],requested=requested,onboard=onboard,actual=q,cargo_after=sum(x['quantity'] for x in truck['cargo'].values()),stock_after=int(inv[target]),capacity=int(c[target])))
            elif kind=='road_departure':
                k,km=data;load=sum(x['quantity'] for x in fleet[k]['cargo'].values());statistics['truck_km']+=km;statistics['bike_km']+=km*load
                truck_logs.append(dict(timestamp=stamp,strategy=policy,truck=k,event='road_departure',km=km,cargo_after=load))
            elif kind=='depot_return':fleet[data]['ready']=True
            elif kind=='dispatch':
                if policy=='none':return
                frame=frames[stamp];model='greedy' if policy=='road_greedy' else 'milp'
                x,info=plan(model,inv,c,frame.pred_dep.to_numpy(),frame.pred_arr.to_numpy(),distance,cfg)
                statistics['flow_solver_fallbacks']+=int(info['fallback'])
                if policy=='instant_milp_relaxation':
                    inv=validate_moves(inv,c,x,distance,cfg);statistics['instant_bikes']+=int(x.sum());statistics['bike_km']+=float((x*distance).sum());return
                if not all(t['ready'] for t in fleet):statistics['dispatch_busy_skips']+=1;return
                requests=[]
                for source,target in np.argwhere(x>0):
                    for unit in range(int(x[source,target])):requests.append(dict(job_id=f'{stamp.isoformat()}_{source}_{target}_{unit}',source=int(source),target=int(target),quantity=1))
                carried=[[dict(v) for v in truck['cargo'].values()] for truck in fleet]
                shift_id=int(stamp.timestamp()//cfg.get('driver_shift_seconds',28800));remaining=min([cfg.get('driver_shift_seconds',28800)-truck['work'].get(shift_id,0) for truck in fleet]+[3600])
                routes,status=plan_routes(requests,carried,travel,distance,capacity=cfg.get('truck_capacity',6),max_seconds=max(0,remaining),service_seconds_per_bike=cfg.get('service_seconds_per_bike',90),search_ms=cfg.get('routing_search_ms',200))
                statistics['planned_bikes']+=len(requests);statistics['unassigned_bikes']+=status['unassigned'];statistics['route_solver_failures']+=int(status['status'].startswith('no_solution'))
                route_logs.append(dict(timestamp=stamp,strategy=policy,status=status,routes=routes))
                target_by_job={r['job_id']:r['target'] for r in requests}
                for truck in carried:
                    for job in truck:target_by_job[job['job_id']]=job['target']
                for route in routes:
                    k=route['truck'];fleet[k]['ready']=False;fleet[k]['work'][shift_id]=fleet[k]['work'].get(shift_id,0)+route['driver_seconds'];assert fleet[k]['work'][shift_id]<=cfg.get('driver_shift_seconds',28800)
                    statistics['driver_seconds']+=route['driver_seconds']
                    for leg in route['legs']:push(stamp+pd.Timedelta(seconds=leg['depart_seconds']),4,'road_departure',(k,leg['km']))
                    for visit in route['visits']:
                        if visit['kind']=='pickup':push(stamp+pd.Timedelta(seconds=visit['arrival_seconds']),3,'pickup',(k,visit['job_id'],visit['station'],target_by_job[visit['job_id']],visit['quantity']))
                        else:push(stamp+pd.Timedelta(seconds=visit['arrival_seconds']+visit['service_seconds']),2,'delivery',(k,visit['job_id'],visit['station'],visit['quantity']))
                    push(stamp+pd.Timedelta(seconds=route['driver_seconds']),0,'depot_return',k)
            verify()
        counters=['departure_requests','served_departures','unmet_departures','served_returns','blocked_arrivals','suppressed_returns','picked_bikes','delivered_bikes','failed_pickup_bikes','blocked_transfer_attempts','planned_bikes','unassigned_bikes','truck_km','bike_km','driver_seconds','flow_solver_fallbacks','route_solver_failures','dispatch_busy_skips','instant_bikes']
        for hour in times:
            statistics={k:0 for k in counters};before=int(inv.sum());truck_before=cargo_count()
            while queue and queue[0][0]<hour+pd.Timedelta(hours=1):
                stamp,_,_,kind,data=heapq.heappop(queue);handle(stamp,kind,data)
            verify();rows.append(dict(timestamp=hour,strategy=policy,stock_start=before,stock_end=int(inv.sum()),truck_stock_start=truck_before,truck_stock_end=cargo_count(),in_transit=len(transit),held_returns=len(held),boundary_incoming=incoming,boundary_outgoing=outgoing,initial_fleet=initial_fleet,accounted_fleet=int(inv.sum())+len(transit)+len(held)+cargo_count(),**statistics))
        # Finish truck events exactly on the right boundary, separately from customer service window.
        statistics={k:0 for k in counters}
        while queue and queue[0][0]==stop:
            stamp,_,_,kind,data=heapq.heappop(queue);handle(stamp,kind,data)
        verify();closing.append(dict(strategy=policy,timestamp=stop,docked=int(inv.sum()),truck_stock=cargo_count(),in_transit=len(transit),held_returns=len(held),initial_fleet=initial_fleet,boundary_incoming=incoming,boundary_outgoing=outgoing,accounted_fleet=int(inv.sum())+len(transit)+len(held)+cargo_count(),**statistics))
        assert not queue,'A truck route exceeded the simulation horizon'
    return pd.DataFrame(rows),truck_logs,route_logs,pd.DataFrame(closing)
