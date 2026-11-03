# Integer rebalancing formulation

All inventory, capacity, budget and safety values are scenario assumptions. This objective predicts net end inventory, not actual loss within the hour.

Given integer docked I_i in [0,C_i], capacity C_i, nonnegative forecasts D_i, A_i, Haversine d_ij, integer bike budget B, and radius R, set L_i=l*C_i, U_i=u*C_i, M_i=(L_i+U_i)/2 and E0_i=I_i+A_i−D_i.

To disallow transshipment, donors have s_i=min(I_i,max(0,floor(E0_i−M_i))); receivers have r_i=min(C_i−I_i,max(0,ceil(M_i−E0_i))). Allowed edges require s_i>0, r_j>0, i≠j, d_ij≤R. A station cannot be both donor and receiver. These extra donor/receiver bounds restrict the feasible set explicitly; they are shared by Greedy and MILP.

Variables: x_ij nonnegative integer, u_i,v_i nonnegative continuous.

Minimize:

```
w_short * sum(u_i) + w_full * sum(v_i) + w_dist * sum(d_ij*x_ij)
```

Subject to:

```
Ipost_i = I_i + sum_j x_ji - sum_j x_ij
E_i = Ipost_i + A_i - D_i
u_i >= L_i - E_i
v_i >= E_i - U_i
sum_j x_ij <= s_i
sum_j x_ji <= r_i
sum_ij x_ij <= B
0 <= Ipost_i <= C_i
```

The last inventory constraints are implied by the donor/receiver bounds and also checked explicitly after solving. No forbidden edge variables are created. A zero move solution always exists because slack is unbounded above. Therefore this scenario MILP should be feasible for valid inputs; invalid inputs fail explicitly. SciPy milp / HiGHS solves to zero requested MIP gap with a configurable time limit (default 5 seconds). Only success is accepted as an optimal result. Time-limit/error statuses are retained and Greedy fallback logged, not called optimal. All-none cases have `optimal_no_edges` status. Greedy sorts allowed edges by distance then station indices and transfers up to remaining supply, receiving space and total budget; it does not optimize realized service.

## Three-station hand example

I=[3,27,8], C=[30,30,30], D=[15,5,17], A=[2,3,3]. Without moves E0=[−10,25,−6]. For l=.3,u=.7, L=9,U=21,M=15; donors=[0,10,0], receiving bounds=[25,0,21]. For B=3, distances d(1→0)=d(1→2)=1 km, weights (5,5,.1), zero-move penalty is 5*(19+15+4)=190. Each donor-to-receiver bike reduces shortage by 1 and excess by 1; moving 3 gives 160+.3=160.3. Any split across the two receiving stations with total 3 is optimal at these distances. Donor inventory becomes 24, all capacities respected; the test exhaustively enumerates every feasible split and matches the solver objective.

Instantaneous transfer and great-circle distance are proxies; no truck fleet, loading time, travel-time route, financial cost, or nonlinear within-hour service objective is claimed. A future-count oracle input cannot guarantee a true service upper bound under this proxy objective.
