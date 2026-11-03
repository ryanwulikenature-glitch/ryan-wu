"""Restricted pickup-delivery vehicle routing audit for fixed transfer orders.
Each job is picked up then delivered atomically before another pickup; no truck
co-loading. Jobs larger than a truck are split. Haversine travel-time proxy.
This audits route feasibility, not an integrated operational service policy.
"""
import time
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import lil_matrix

def route_transfers(moves,distance,depot=0,trucks=2,truck_capacity=6,speed_kmh=15,shift_minutes=60,minutes_per_bike_per_stop=1.5,time_limit=5):
    start=time.perf_counter();moves=np.asarray(moves);distance=np.asarray(distance,float)
    n=len(moves)
    if moves.shape!=(n,n) or distance.shape!=(n,n) or (moves<0).any() or not np.equal(moves,np.rint(moves)).all() or np.trace(moves)!=0:raise ValueError('Invalid fixed orders')
    if not np.isfinite(distance).all() or (distance<0).any() or not 0<=depot<n or trucks<1 or int(trucks)!=trucks or truck_capacity<1 or int(truck_capacity)!=truck_capacity or speed_kmh<=0 or shift_minutes<0 or minutes_per_bike_per_stop<0:raise ValueError('Invalid routing resources')
    jobs=[]
    for s,t in np.argwhere(moves>0):
        remaining=int(moves[s,t])
        while remaining:
            amount=min(truck_capacity,remaining);jobs.append((int(s),int(t),amount));remaining-=amount
    m=len(jobs)
    if not m:return [],dict(status='optimal_no_jobs',served_jobs=0,total_jobs=0,runtime_ms=(time.perf_counter()-start)*1000)
    nodes=range(m+1);arcs=[(i,j) for i in nodes for j in nodes if i!=j];E=len(arcs)
    offset=trucks*E;x=np.arange(offset).reshape(trucks,E);a=np.arange(offset,offset+trucks*m).reshape(trucks,m);offset+=a.size
    order=np.arange(offset,offset+trucks*m).reshape(trucks,m);offset+=order.size
    lb=np.zeros(offset);ub=np.ones(offset);ub[order.ravel()]=m;integer=np.ones(offset);integer[order.ravel()]=0
    lengths=[]
    for i,j in arcs:
        origin=depot if i==0 else jobs[i-1][1];target=depot if j==0 else jobs[j-1][0]
        lengths.append(distance[origin,target])
    internal=np.array([distance[s,t] for s,t,q in jobs]);service=internal/speed_kmh*60+np.array([2*q*minutes_per_bike_per_stop for s,t,q in jobs])
    obj=np.zeros(offset)
    for k in range(trucks):obj[x[k]]=lengths;obj[a[k]]=internal
    rows=[];low=[];high=[]
    def add(c,l=-np.inf,u=np.inf):rows.append(c);low.append(l);high.append(u)
    for j in range(m):add({int(a[k,j]):1 for k in range(trucks)},1,1)
    for k in range(trucks):
        out0={int(x[k,e]):1 for e,(i,j) in enumerate(arcs) if i==0};in0={int(x[k,e]):1 for e,(i,j) in enumerate(arcs) if j==0}
        add(out0,u=1);add({**out0,**{v:-c for v,c in in0.items()}},0,0)
        minutes={int(x[k,e]):lengths[e]/speed_kmh*60 for e in range(E)};minutes.update({int(a[k,j]):service[j] for j in range(m)});add(minutes,u=shift_minutes)
        for j in range(1,m+1):
            incoming={int(x[k,e]):1 for e,(i,t) in enumerate(arcs) if t==j};incoming[int(a[k,j-1])]=-1;add(incoming,0,0)
            outgoing={int(x[k,e]):1 for e,(s,t) in enumerate(arcs) if s==j};outgoing[int(a[k,j-1])]=-1;add(outgoing,0,0)
            add({int(order[k,j-1]):1,int(a[k,j-1]):-1},l=0);add({int(order[k,j-1]):1,int(a[k,j-1]):-m},u=0)
        for e,(i,j) in enumerate(arcs):
            if i and j:add({int(order[k,j-1]):1,int(order[k,i-1]):-1,int(x[k,e]):-(m+1)},l=-m)
    matrix=lil_matrix((len(rows),offset))
    for row,c in enumerate(rows):
        for key,val in c.items():matrix[row,key]=val
    result=milp(obj,integrality=integer,bounds=Bounds(lb,ub),constraints=LinearConstraint(matrix.tocsr(),low,high),options={'time_limit':time_limit,'mip_rel_gap':.01})
    if not result.success:return [],dict(status=f'{result.status}:{result.message}',served_jobs=0,total_jobs=m,runtime_ms=(time.perf_counter()-start)*1000,scope='no routes asserted; time limit is not proof of infeasibility')
    routes=[];visited=[]
    for k in range(trucks):
        next_node={i:j for e,(i,j) in enumerate(arcs) if result.x[x[k,e]]>.5}
        if 0 not in next_node:continue
        node=next_node[0];sequence=[];km=0;minutes=0;previous=depot
        while node:
            if node in visited:raise AssertionError('Duplicated/subtour job')
            visited.append(node);s,t,q=jobs[node-1];sequence.append(dict(job=node,source=s,target=t,bikes=q))
            km+=distance[previous,s]+distance[s,t];minutes+=(distance[previous,s]+distance[s,t])/speed_kmh*60+2*q*minutes_per_bike_per_stop;previous=t
            node=next_node[node]
        km+=distance[previous,depot];minutes+=distance[previous,depot]/speed_kmh*60
        assert minutes<=shift_minutes+1e-6 and all(j['bikes']<=truck_capacity for j in sequence)
        routes.append(dict(truck=k,jobs=sequence,truck_km=float(km),driver_minutes=float(minutes),max_load=max(j['bikes'] for j in sequence)))
    assert len(visited)==m
    return routes,dict(status='optimal_with_requested_gap_1pct',served_jobs=m,total_jobs=m,runtime_ms=(time.perf_counter()-start)*1000,total_truck_km=sum(r['truck_km'] for r in routes),total_driver_minutes=sum(r['driver_minutes'] for r in routes))
