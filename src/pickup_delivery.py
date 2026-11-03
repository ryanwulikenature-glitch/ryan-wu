"""Co-loaded capacitated pickup-delivery routing with directed road times.
OR-Tools returns a feasible heuristic, not a global-optimality certificate.
"""
import math
import numpy as np
from ortools.constraint_solver import pywrapcp,routing_enums_pb2

def plan_routes(requests,held,travel_seconds,road_km,capacity=6,max_seconds=3600,service_seconds_per_bike=90,depot=0,search_ms=200):
    travel=np.asarray(travel_seconds,float);km=np.asarray(road_km,float);K=len(held);n=len(travel)
    if K<1 or travel.shape!=(n,n) or km.shape!=(n,n) or not np.isfinite(travel).all() or not np.isfinite(km).all() or (travel<0).any() or (km<0).any() or capacity<1:raise ValueError('Invalid routing network/resources')
    nodes=[dict(station=depot,quantity=0,kind='depot',job_id='depot')];pairs=[];owners=[]
    for k,cargo in enumerate(held):
        if sum(j['quantity'] for j in cargo)>capacity:raise ValueError('Initial truck over capacity')
        for job in cargo:
            nodes.append(dict(station=job['target'],quantity=job['quantity'],kind='delivery',job_id=job['job_id']));owners.append((len(nodes)-1,k))
    for job in requests:
        if not 0<=job['source']<n or not 0<=job['target']<n or job['source']==job['target'] or job['quantity']<1 or job['quantity']>capacity:raise ValueError('Invalid pickup-delivery request')
        p=len(nodes);nodes.append(dict(station=job['source'],quantity=job['quantity'],kind='pickup',job_id=job['job_id']))
        d=len(nodes);nodes.append(dict(station=job['target'],quantity=job['quantity'],kind='delivery',job_id=job['job_id']));pairs.append((p,d))
    if len(nodes)==1:return [],dict(status='no_jobs',requested=0,assigned=0,unassigned=0)
    manager=pywrapcp.RoutingIndexManager(len(nodes),K,0);routing=pywrapcp.RoutingModel(manager)
    def service(node):return 0 if not node else int(math.ceil(nodes[node]['quantity']*service_seconds_per_bike))
    def transit(a,b):
        i,j=manager.IndexToNode(a),manager.IndexToNode(b)
        return int(math.ceil(travel[nodes[i]['station'],nodes[j]['station']]))+service(i)
    callback=routing.RegisterTransitCallback(transit);routing.SetArcCostEvaluatorOfAllVehicles(callback)
    routing.AddDimension(callback,0,int(max_seconds),True,'Time');clock=routing.GetDimensionOrDie('Time')
    def demand(index):
        node=nodes[manager.IndexToNode(index)];return node['quantity'] if node['kind']=='pickup' else -node['quantity'] if node['kind']=='delivery' else 0
    load_cb=routing.RegisterUnaryTransitCallback(demand);routing.AddDimensionWithVehicleCapacity(load_cb,0,[int(capacity)]*K,False,'Load');load=routing.GetDimensionOrDie('Load')
    for k,cargo in enumerate(held):load.CumulVar(routing.Start(k)).SetValue(sum(j['quantity'] for j in cargo));load.CumulVar(routing.End(k)).SetValue(0)
    for node,k in owners:routing.VehicleVar(manager.NodeToIndex(node)).SetValue(k)
    for p,d in pairs:
        a,b=manager.NodeToIndex(p),manager.NodeToIndex(d);routing.AddPickupAndDelivery(a,b)
        routing.solver().Add(routing.VehicleVar(a)==routing.VehicleVar(b));routing.solver().Add(clock.CumulVar(a)<=clock.CumulVar(b));routing.solver().Add(routing.ActiveVar(a)==routing.ActiveVar(b))
        # Lexicographic preference for feasible requested bikes, then road/service time.
        routing.AddDisjunction([a],100000*nodes[p]['quantity']);routing.AddDisjunction([b],100000*nodes[d]['quantity'])
    params=pywrapcp.DefaultRoutingSearchParameters()
    # Insertion heuristics start from empty routes and can reject the mandatory
    # delivery-only nodes of a truck that already carries bikes. Automatic uses
    # a constructive strategy that supports these nonzero starting loads.
    params.first_solution_strategy=(routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC if owners else routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION)
    params.local_search_metaheuristic=routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH;params.time_limit.FromMilliseconds(int(search_ms))
    solution=routing.SolveWithParameters(params)
    if not solution:return [],dict(status=f'no_solution_status_{routing.status()}',requested=len(requests),assigned=0,unassigned=len(requests))
    routes=[];assigned=set()
    for k in range(K):
        index=routing.Start(k);visits=[];legs=[];previous=depot;depart=0;current=sum(j['quantity'] for j in held[k]);max_load=current
        while not routing.IsEnd(index):
            nxt=solution.Value(routing.NextVar(index));node_index=manager.IndexToNode(nxt)
            arrival=solution.Value(clock.CumulVar(nxt));station=depot if routing.IsEnd(nxt) else nodes[node_index]['station']
            legs.append(dict(source=previous,target=station,depart_seconds=depart,arrival_seconds=arrival,km=float(km[previous,station])))
            if not routing.IsEnd(nxt):
                node=nodes[node_index];visit=node|{'arrival_seconds':arrival,'service_seconds':service(node_index)};visits.append(visit)
                current+=node['quantity'] if node['kind']=='pickup' else -node['quantity'];assert 0<=current<=capacity;max_load=max(max_load,current)
                if node['kind']=='pickup':assigned.add(node['job_id'])
                depart=arrival+service(node_index)
            previous=station;index=nxt
        elapsed=solution.Value(clock.CumulVar(routing.End(k)));assert elapsed<=max_seconds and current==0
        if visits:routes.append(dict(truck=k,visits=visits,legs=legs,driver_seconds=elapsed,initial_load=sum(j['quantity'] for j in held[k]),end_load=current,max_planned_load=max_load,truck_km=sum(l['km'] for l in legs)))
    for job in requests:
        containing=[r for r in routes if any(v['job_id']==job['job_id'] for v in r['visits'])]
        if job['job_id'] in assigned:
            assert len(containing)==1
            v=[v for v in containing[0]['visits'] if v['job_id']==job['job_id']];assert [x['kind'] for x in v]==['pickup','delivery']
    return routes,dict(status=f'feasible_heuristic_status_{routing.status()}',requested=len(requests),assigned=len(assigned),unassigned=len(requests)-len(assigned),optimality='not certified')
