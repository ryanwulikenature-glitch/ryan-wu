# NYC Citi Bike — reproducible technical report

## 1. Problem Definition

Observed completed rides; simulated service outcomes under assumptions

Compare next-hour departure/arrival forecasts and three rebalancing strategies for 30 stations. Data kind: **official**. No historic empty/full inventory observations are available.

## 2. Data

```json
{
  "data_kind": "official",
  "months": [
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12
  ],
  "complete_year": true,
  "raw_rows": 45771102,
  "retained_rides": 45588101,
  "stations": 30,
  "panel_rows": 262800,
  "unknown_hours": 19634,
  "count_conservation": "passed",
  "dst_policy": "exclude unresolvable local folds/gaps; retain UTC hours",
  "zero_policy": "unobserved hours missing unless operating calendar confirms activity"
}
```

UTC hourly index with America/New_York calendar features; unresolved local DST folds/gaps are excluded during raw ingestion. Official zero counts require operation evidence; unverified hours remain missing. Training-only activity/geography/drift selection applies to raw data; demo stations are generated fixtures.

## 3. Forecasting

Jan–Aug training, Sep–Oct validation, Nov–Dec test. Lag 1/24/168 and shifted 24/168 rolling statistics, station one-hot, calendar and US federal holidays. Last-hour, seasonal-naive, regularized Poisson GLM and XGBoost count:poisson; separate targets. All transforms fit on training, hyperparameters use validation; final models refit train+validation. Rolling test features can use previously observed test hours. No weather features because forecast-vintage inputs are absent. Train metrics are in-sample diagnostics.

Selected on validation: {"departures": "xgboost", "arrivals": "xgboost"}. Test metrics:

```csv
model,target,split,stratum,n,mae,rmse,wape
last_hour,departures,test,all,43950,4.475767918088737,7.134479403537404,0.4519751943256675
seasonal_naive,departures,test,all,43950,5.71872582480091,9.154236478606892,0.5774924578894038
poisson,departures,test,all,43950,4.931488840370346,6.652226065690838,0.4979951301614958
xgboost,departures,test,all,43950,3.417683828450714,5.056675367195367,0.3451269906700906
last_hour,arrivals,test,all,43950,4.40910125142207,7.200692041068495,0.4487019181787027
seasonal_naive,arrivals,test,all,43950,5.721706484641638,9.242284240109235,0.5822820861930034
poisson,arrivals,test,all,43950,4.838437654731114,6.638733547781719,0.4923942846551086
xgboost,arrivals,test,all,43950,3.398161859152938,5.111224447587446,0.3458214401385878

```

## 4. Optimization

See `reports/optimization_formulation.md`. Integer supply-to-deficit moves, inventory/capacity, budget and radius constraints; HiGHS via SciPy. Objective is forecast-end safety-band slack plus bike-km, not realized service or money. Every solver status and fallback is logged.

## 5. Simulation

**Hourly count-based scenario simulation**: instant moves followed by seeded random interleaving of exogenous arrivals and departures at each station. Same event sample hash, initial inventory and restrictions for all policies. This count model does not suppress arrivals after rejected departures and does not claim fleet conservation; station inventory balance is checked. Optional paired-event replay is implemented separately and must not be mixed with these count results.

## 6. Results

```csv
strategy,departure_requests,arrival_events,unmet_departures,blocked_arrivals,bikes_moved,bike_km,scenario_objective,proxy_service_rate,mean_runtime_ms,fallback_hours,data_kind,simulation_kind,hours
none,435223,431868,42028,38689,0,0.0,403585.0,0.9034334122966848,0.4123486614333675,0,official,hourly count-based scenario simulation,1465
greedy,435223,431868,39510,36167,17259,8590.202819612634,379244.0202819613,0.9092189521233942,0.5063816839587714,0,official,hourly count-based scenario simulation,1465
milp,435223,431868,35982,32639,16442,15846.87908321013,344689.68790832104,0.917325141364312,7.881863659383919,0,official,hourly count-based scenario simulation,1465

```

Absolute and relative policy differences are in policy_comparison.csv; percentages with zero baseline are undefined. Objective weights are preference units, bike-km is not truck route length. These outputs do not prove a complex model or MILP improves reality.

## 7. Robustness

Predeclared one-factor scenarios vary capacity, budget, radius, initial inventory, weights, seeds and dates. Ablations replace predictors with seasonal naive, departures-only, fixed XGBoost, and a non-deployable future-count oracle. The oracle is an information benchmark, not a mathematical service upper bound: the optimization objective is only a proxy. Test-period sensitivities are exploratory. Paired daily block bootstrap reports scenario-objective differences; it quantifies within-scenario variability only. Weather ablation is unavailable, not a passing result. Failures: [].

## 8. Limitations

Completed rides are a censored sample of potential demand. Capacities, starting inventories, instantaneous transport and costs are assumed. Current GBFS cannot reconstruct 2025 capacities. Random hourly ordering differs from actual ride causality; optional event replay still has external-boundary assumptions and blocked returns remain held off dock. Approximate rectangle selection can include non-Manhattan locations. Unresolved DST times are excluded, not assigned arbitrary folds. No causal operational or financial improvement is established.

## 9. Conclusion and completion status

The saved outputs provide observed-rides forecasting and assumption-dependent scenario results. Read the metrics and uncertainty tables before drawing any performance conclusion.

All numeric results above were read from generated files. See tests output for executed checks and README for reproduction. Routing, stochastic multi-period optimization and network expansion remain future work. The prospective GBFS collector has two live samples; long-term inventory monitoring is not claimed.

## Explicit recorded-event estimand

The audited panel preserves unknown operating hours as missing. For this experiment only, training and simulation use observed_departures/observed_arrivals: counts in the retained completed-ride archive, including zero recorded events. This is an explicit alternate observation model; it does not reclassify station operation as verified or imply zero latent demand. Both lag features and labels use the same recorded-event definition. Quality-audited EDA remains conditional on eventful hours for per-station means; daily archive totals retain all observed counts. The strict operating-hour workflow remains available separately.

## Executed paired-event upgrade

The full same test horizon was also replayed by cleaned ride_id, including external boundaries and initial in-transit rides. Rejected departures suppress the corresponding arrival. Full fleet accounting is asserted at each processed event. Blocked returns remain held off dock through the horizon; the alternative scenario is not historical observed loss.

```csv
strategy,unmet_departures,blocked_arrivals,served_departures,bikes_moved,bike_km,departure_requests,proxy_service_rate,simulation_kind,hours
greedy,40827,31632,394396,17181,8580.944420290232,435223,0.906192917194174,paired recorded-ride counterfactual scenario,1465
milp,37832,29174,397391,16267,15525.929139137104,435223,0.9130744468927424,paired recorded-ride counterfactual scenario,1465
none,42891,33379,392332,0,0.0,435223,0.9014505207675144,paired recorded-ride counterfactual scenario,1465
```
