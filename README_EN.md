[Research project overview](PROJECT_OVERVIEW.md) · [Two-page research brief](application/RESEARCH_BRIEF.pdf) · [申请经历与金融工程/DS/OR材料](application/README.md)

[![Research checks](https://github.com/ryanwulikenature-glitch/ryan-wu/actions/workflows/research-checks.yml/badge.svg)](https://github.com/ryanwulikenature-glitch/ryan-wu/actions/workflows/research-checks.yml)

新增：冻结模型后的2026年1月外部评估（22,320站点小时；借车MAE 2.705 vs last-hour 3.235），以及5/15/30/60分钟历史初态证据分层。指标来源、范围、负结果与AI辅助贡献见申请材料。

# Historical-evidence extension: current version

The original baseline below remains reproducible. The [final engineering supplement](reports/operations_completion.md) reports the executed road/service integration and deployed prospective collection; its [offline HTML](reports/operations_completion.html) includes plots. New evidence and experiments are in [the supplement](reports/historical_evidence_and_extensions.md) and [the ten-page report](reports/technical_report.pdf). Sixty tests pass.

We acquired 12 months of CityBikes NYC changes: 2,907,502 records for all 30 selected sites, plus 120 dated official capacity and 180 dated official status points from four/six archived feeds. Internally inconsistent capacities/counts are rejected. Exact UID/short_name identities, freshness and past-only joins are tested. Capacity corroboration matches 102/102 comparable preceding official points; unmatched points are retained. Historical common-state comparisons use 260 eligible hours and reset to measured stocks each hour.

This does not resolve every historical state: unchanged counts are suppressed, including possible flag-only changes. Of 19,634 previously unknown site-hours, 3,406 have active point evidence, only two satisfy the declared all-12-five-minute-bin criterion, and the remaining 19,632 do not meet that stronger standard. Missing states are not fabricated; event-sampled empty observations are not time-weighted stockout rates.

Additional executed experiments: 24-hour-lead GFS weather, six full raw-data duration cutoffs, 3-period/4-scenario stochastic MPC on 48 hours, restricted 2-truck fixed-order routing audit on 48 hours, and 60-site forecasting plus 336-hour simulation. Routing infeasibilities are reported, not silently called served. All new analyses are exploratory on the previously inspected test. Use scripts/all_research.sh to reproduce constituent steps; original raw archives are downloaded, not included in the package.

Bike-share data by CityBikes contributors and available from https://data.citybik.es . CityBikes contributors. (2026) Bike-share data retrieved from https://data.citybik.es . The adapted historical database is ODbL-1.0, with underlying operator terms also applying. See data/historical/DATABASE_NOTICE.md. This notice does not relicense the software or independent official snapshots.

---

# NYC Citi Bike demand forecasting and optimization

Official 2025 NYC completed-ride archives, 30 training-selected stations, four count predictors, integer rebalancing, and two explicit scenario simulators. The chronological experiment and tests were actually executed; results are not prefilled or synthetic evidence relabeled as real.

- [Ten-page English research report](reports/technical_report.pdf)
- [Readable results tables](reports/results/)
- [Data/feature dictionary](DATA_DICTIONARY.md)
- [Mathematical formulation](reports/optimization_formulation.md)
- [Tests and run evidence](reports/validation/)

## Executed evidence

45,771,102 raw rows; 45,588,101 retained rides; 262,800 station-hours. Train January-August, validate September-October, test November-December. The 43,950 test rows span 1,465 hours. Three policies run over the full test horizon in both the hourly count and paired-ride scenarios. Twenty-one sensitivity/ablation configurations each run three policies for 48 hours. Sixty tests pass; two EDA notebooks are executed. All figures, model errors and uncertainty tables are generated from saved data.

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

Raw archives, venv, large processed outputs and routine model/live outputs are not committed. Four small hash-frozen fitted pipelines and 168-hour past-count context are now committed under models/frozen_2025 for standalone January2026 external replication. URLs/hashes are in reports/results/download_manifest.csv. Code regenerates them; small research evidence is committed. The downloadable project archive additionally contains processed panels/models/results, not the original 8.93 GB raw data.

## Observation and simulation assumptions

The audited panel leaves 19,634 operating-unknown hours missing. The explicit archive-count configuration uses observed retained-record counts in a temporary modeling copy; zero records do not prove operation or zero latent demand. No verified operating calendar or historical inventory is invented. Coordinates approximate the Manhattan area, not an administrative polygon. Capacity=25, starting fraction=.5, budget=12 bikes/hour and radius=3 km are assumptions.

All transforms fit on training, all lags precede the target, and hyperparameters use validation. Test sensitivities are exploratory. No target-hour observed weather is used. Oracle is an impossible-to-deploy information comparator, not a guaranteed true-service upper bound.

The count simulator uses shared seeded exogenous arrivals. The separate paired-event simulator suppresses returns after rejected departures, tracks in-transit/held bikes and external boundaries, and asserts fleet accounting. Held blocked returns remain unavailable through the horizon; this is assumed behavior. Bike-km is not truck routing distance and objective weights are not dollars.

## Prospective GBFS extension

```bash
.venv/bin/python -m src.collect_gbfs --samples 2 --interval 60
```

Two live samples have been collected for both current feeds, 2,518 stations per feed/sample. JSON, SQLite inventory rows and failure logs are retained separately under data/gbfs. A new local 60-second-target daemon and public five-minute-target GitHub Actions workflow are deployed; real archived output has been restored to SQLite. Actual dated evidence and gaps are reported in the final engineering supplement; scheduled continuity is not guaranteed. Current station IDs/capacities must not be treated as verified 2025 identifiers or history. Newly executed work includes archived 24-hour-lead weather ablation, raw duration-cutoff sensitivity, stochastic three-period MPC, restricted atomic pickup-delivery routing audits, polygon checks and a 60-site stress test. A new directed-OSRM co-loaded pickup/delivery heuristic is integrated with 48-hour paired-event service, with 181 routes independently checked. Road MILP performs worse than no intervention in this scenario; that negative result is retained. The driving network is a current proxy, not verified 2025 traffic or truck-specific restrictions. Real operator dispatch and long-term collection continuity are not claimed.

Published repository: https://github.com/ryanwulikenature-glitch/ryan-wu (main). Source, reports and small evidence tables are pushed; raw data/models are regenerated or included in the separate project ZIP.

## Frozen external replication

After installing requirements-lock.txt, run `python scripts/external_202601.py`. The repository contains exact pre-download hash-frozen models, station list and preceding168-hour recorded-count context; only the353.83MB January2026 archive is downloaded. No refitting occurs. The plan was committed before target acquisition at4dd3f516. Results/31-day paired intervals are in reports/results/external_202601. This does not backfill missing operating states or validate online lag availability.
