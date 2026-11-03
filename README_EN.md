# NYC Citi Bike demand forecasting and optimization

Official 2025 NYC completed-ride archives, 30 training-selected stations, four count predictors, integer rebalancing, and two explicit scenario simulators. The chronological experiment and tests were actually executed; results are not prefilled or synthetic evidence relabeled as real.

- [Eight-page English research report](reports/technical_report.pdf)
- [Readable results tables](reports/results/)
- [Data/feature dictionary](DATA_DICTIONARY.md)
- [Mathematical formulation](reports/optimization_formulation.md)
- [Tests and run evidence](reports/validation/)

## Executed evidence

45,771,102 raw rows; 45,588,101 retained rides; 262,800 station-hours. Train January-August, validate September-October, test November-December. The 43,950 test rows span 1,465 hours. Three policies run over the full test horizon in both the hourly count and paired-ride scenarios. Twenty-one sensitivity/ablation configurations each run three policies for 48 hours. Thirty tests pass; two EDA notebooks are executed. All figures, model errors and uncertainty tables are generated from saved data.

XGBoost test MAE is approximately 3.418 departures and 3.398 arrivals per station-hour. Under the count-scenario assumptions, the service proxy is 90.343% with no rebalancing, 90.922% with Greedy, and 91.733% with MILP. MILP uses more bike-km than Greedy; these are not real service rates or financial effects. The report retains weaker model results and the transport/service tradeoff.

## Reproduce

Python 3.12 recommended. Install from the exact dependency lock:

```bash
./scripts/install.sh
.venv/bin/python -m pytest -q
./scripts/validate.sh # synthetic interface/repeatability checks
.venv/bin/python -m src.download --year 2025
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv/bin/python -m src.prepare --config configs/official_counts.json
./scripts/official_pipeline.sh
.venv/bin/python scripts/eda_business.py
.venv/bin/python scripts/english_report.py
```

`official_pipeline.sh` reuses matching prepared caches. If caches are absent, download and prepare first. Full-year cleaning can take many minutes; source archives total 8.93 GB and large intermediate partitions also require disk. Notebook execution starts a temporary local kernel. No persistent server or external database is needed.

Raw archives, venv, large processed outputs, models and live snapshots are not committed. URLs/hashes are in reports/results/download_manifest.csv. Code regenerates them; small research evidence is committed. The downloadable project archive additionally contains processed panels/models/results, not the original 8.93 GB raw data.

## Observation and simulation assumptions

The audited panel leaves 19,634 operating-unknown hours missing. The explicit archive-count configuration uses observed retained-record counts in a temporary modeling copy; zero records do not prove operation or zero latent demand. No verified operating calendar or historical inventory is invented. Coordinates approximate the Manhattan area, not an administrative polygon. Capacity=25, starting fraction=.5, budget=12 bikes/hour and radius=3 km are assumptions.

All transforms fit on training, all lags precede the target, and hyperparameters use validation. Test sensitivities are exploratory. No target-hour observed weather is used. Oracle is an impossible-to-deploy information comparator, not a guaranteed true-service upper bound.

The count simulator uses shared seeded exogenous arrivals. The separate paired-event simulator suppresses returns after rejected departures, tracks in-transit/held bikes and external boundaries, and asserts fleet accounting. Held blocked returns remain unavailable through the horizon; this is assumed behavior. Bike-km is not truck routing distance and objective weights are not dollars.

## Prospective GBFS extension

```bash
.venv/bin/python -m src.collect_gbfs --samples 2 --interval 60
```

Two live samples have been collected for both current feeds, 2,518 stations per feed/sample. JSON, SQLite inventory rows and failure logs are retained separately under data/gbfs. Long-term observation needs continued scheduled execution. Current station IDs/capacities must not be treated as verified 2025 identifiers or history. Weather, multi-period stochastic optimization and truck VRP remain optional future research; they are not claimed as implemented.
