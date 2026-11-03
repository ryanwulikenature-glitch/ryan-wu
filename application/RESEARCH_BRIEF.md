# Evidence-Aware Citi Bike Demand Forecasting and Rebalancing

**Computational research project | Python, XGBoost, MILP, stochastic MPC, pickup-delivery routing**

## Research question

Can next-hour forecasts of completed-ride counts improve simulated rebalancing service, and how do incomplete station-state evidence and delayed vehicle movement change the conclusions?

## Data and methods

The pipeline processed 45,771,102 official 2025 NYC trip rows and retained 45,588,101 after auditable cleaning. Thirty stable sites were selected on January–August only, yielding 262,800 station-hours. January–August training, September–October validation and November–December testing avoid random temporal splits. Last-hour, seasonal naive, Poisson and XGBoost models predict departures and arrivals; lag/rolling features precede the forecast hour. The test contains 43,950 station-hours.

Separate integer rebalancing and stochastic three-period MPC policies are evaluated with shared requests. Count and paired-ride simulations cover 1,465 test hours; the paired replay suppresses returns after rejected departures and tracks transit, external boundaries and held bikes. A 48-hour extension combines co-loaded trucks with directed OSRM driving times, handling delays, depot returns and capacity/driver constraints; 181 saved routes reconcile with actual cargo events.

## Findings

1. **Predictive performance:** pooled departure MAE is 3.418, compared with 4.476 for last-hour (23.6% lower); arrival MAE is 3.398. These are completed-ride count errors, not recovered latent demand.
2. **Evidence matters:** 2,907,502 historical status changes plus dated official snapshots improve calibration. At the 15-minute criterion, 33,131/43,950 test start states have valid enabled historical point support. XGBoost departure MAE is 4.004 versus 5.454 on that subset. On the other 10,819 rows, ranking reverses: 1.621 versus 1.480. This is a conditional descriptive result; evidence coverage and activity are associated, and missingness is not assumed random.
3. **Optimization has limits:** in the delayed-road scenario, no intervention serves 94.776% of recorded departure requests versus 94.498% for road MILP. A forecast-end balance objective does not guarantee improved pathwise service. The unfavorable comparison is retained.
4. **Frozen cross-year validation:** before downloading new January 2026 records, the station list, cleaning rules, fitted model hashes and evaluation plan were frozen in Git. On all 744 hours / 22,320 station-hours, unchanged XGBoost achieves departure MAE 2.705 versus 3.235 for last-hour (16.4% lower). No fitting or tuning occurs. This is retrospective rolling one-step evaluation, not an online deployment.

## Evidence boundary and reproducibility

The 19,632 remaining unsupported station-hours (7.47% of the annual panel) stay unknown. This annual strong-sampling mask differs from the 10,819 test rows failing the 15-minute start-state criterion. Change-filtered archives cannot prove continuous opening states or identify all rejected requests. The evidence-age audit is exploratory on an already examined test set; it is not a fresh holdout. Current driving roads, frozen capacity and an assumed depot are scenario inputs. Prospective collection is deployed, while long-term cadence is assessed only from actual dated receipts. 60 local tests passed and [remote CI succeeded](https://github.com/ryanwulikenature-glitch/ryan-wu/actions/runs/41604131111). Source, exact dependencies, executed notebooks, manifests, reports and integrity-checked delivery are available in the [repository](https://github.com/ryanwulikenature-glitch/ryan-wu).

Implementation and experiment execution were AI-assisted. No peer-reviewed publication, real operator deployment, causal service improvement or sole manual authorship is claimed.
