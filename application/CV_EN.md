# English CV project entries

Editable project entries for the target program. Use verbs, dates and roles matching actual participation. See the [contribution and tool-use record](../CONTRIBUTIONS.md).

## General / data science

**NYC Citi Bike Demand Forecasting & Rebalancing — Research Project**  
Python · Pandas/PyArrow · XGBoost · SciPy MILP · OR-Tools

- Developed a reproducible pipeline processing 45.6M 2025 NYC rides into a 262,800-row, 30-station hourly panel; evaluated four next-hour count models with chronological train/validation/test splits.
- Achieved pooled test departure MAE of 3.418 versus 4.476 for a last-hour baseline (23.6% lower); audited 2.91M historical state changes and identified a model-ranking reversal on 10,819 test rows lacking fresh start-state evidence.
- Froze model hashes and protocol before acquiring January 2026 records; evaluated unchanged models on 22,320 new station-hours, with departure MAE 2.705 versus 3.235 for last-hour (16.4% lower).
- Evaluated integer/stochastic rebalancing and delayed truck routing with paired-event fleet accounting; retained negative service results and validated the implementation with 60 tests and GitHub CI.

## Operations research / applied mathematics

**Evidence-Aware Bike-Share Rebalancing — Computational Research Project**

- Formulated constrained integer rebalancing and three-period stochastic MPC, benchmarking against no-intervention and distance-greedy policies on shared recorded-ride scenarios.
- Integrated co-loaded pickup-delivery routing, directed road travel, handling times and truck/driver limits into paired-event simulation; independently reconciled 181 routes and full fleet accounting.
- Showed that improved forecast-end inventory balance need not improve delayed service; quantified evidence coverage and preserved unsupported historical states rather than imputing operational certainty.

Keep “simulated”, “pooled” and named baselines when shortening. Do not turn a forecast error reduction into a claim of reduced real NYC stockouts.
