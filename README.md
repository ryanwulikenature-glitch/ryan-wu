# Evidence-Aware Citi Bike Forecasting and Rebalancing

[![Research checks](https://github.com/ryanwulikenature-glitch/ryan-wu/actions/workflows/research-checks.yml/badge.svg)](https://github.com/ryanwulikenature-glitch/ryan-wu/actions/workflows/research-checks.yml)

A computational study of how demand forecasts, incomplete station-state evidence and transport delays affect constrained bike-share rebalancing. The pipeline combines chronological count forecasting, integer and stochastic optimization, and paired customer/truck event simulation.

[Research brief](application/RESEARCH_BRIEF.pdf) · [Technical report](reports/technical_report.pdf) · [Results](reports/results/) · **[Contributions and tool use](CONTRIBUTIONS.md)** · [中文说明](README_ZH.md)

## Main findings

| Evaluation | Sample | Finding |
|---|---|---|
| November–December 2025 forecast test | 43,950 station-hours | XGBoost departure MAE 3.418 vs. last-hour 4.476: 23.6% lower |
| Frozen January 2026 external evaluation | 22,320 station-hours | Unchanged XGBoost MAE 2.705 vs. last-hour 3.235: 16.4% lower |
| Evidence-stratified 2025 evaluation | 10,819 unsupported test starts under the 15-minute criterion | XGBoost MAE 1.621 vs. last-hour 1.480; the pooled ranking reverses |
| Delayed road-fleet scenario | 48 hours, 30 sites, 181 checked routes | No-intervention service proxy 94.776% vs. road MILP 94.498%; the unfavorable result is retained |

The January 2026 protocol and fitted model hashes were [committed before acquiring target records](https://github.com/ryanwulikenature-glitch/ryan-wu/commit/4dd3f516474d3f034bce123c7f211f91a8e0680a). No refitting or retuning occurs in that evaluation. All methods use completed-ride records; forecasting errors and simulated service do not identify total latent demand or actual operator gains.

## Research design

The 2025 pipeline processes 45,771,102 raw rows and retains 45,588,101 rides. Thirty stations are selected using training-period activity, giving a 262,800-row hourly panel. January–August trains the models, September–October selects them, and November–December provides the original test. Last-hour, seasonal-naive, Poisson and XGBoost predictors use past-only lag and rolling features with training-fitted preprocessing.

Integer rebalancing and three-period stochastic MPC are compared with no intervention and distance-greedy transfers. The full count and paired-ride scenarios span 1,465 test hours. The road extension adds directed OSRM driving times, co-loaded pickup/delivery trucks, handling delays and driver/capacity limits. Event-level checks account for docked bikes, customer transit, held returns, truck cargo and external boundaries.

Historical calibration uses 2,907,502 CityBikes changes plus 120 dated official capacity and 180 status points. Evidence-age sensitivity uses 5/15/30/60-minute criteria and fixed existing forecasts. The 2025 sensitivity analyses are exploratory; the January 2026 evaluation has its separate frozen protocol.

## Reproduce

Python 3.12 on Linux. Install exact dependencies and run the automated checks:

```bash
./scripts/install.sh
.venv/bin/python -m pytest -q
```

Sixty tests passed in the recorded local and remote CI runs. [Validation receipts](reports/validation/) retain the corresponding evidence.

### Standalone frozen external evaluation

```bash
.venv/bin/python scripts/external_202601.py
```

The repository includes four hash-pinned fitted pipelines, the original station list and 168 hours of preceding count context in [models/frozen_2025](models/frozen_2025/). This evaluation downloads only the 353.83 MB January 2026 archive. It is retrospective rolling one-step evaluation with preceding archived counts, rather than a deployed online forecasting service.

### Full-year research

```bash
.venv/bin/python -m src.download --year 2025
.venv/bin/python -m src.prepare --config configs/official_counts.json
./scripts/official_pipeline.sh
./scripts/all_research.sh
```

The original 2025 trip archives total 8.93 GB; historical-state raw files add about 0.53 GB. Large processed datasets and routine model outputs are excluded from Git. Full reproduction needs additional disk and time. Matching caches can be reused. The wrapper's constituent research commands were executed individually; a fresh-machine run of the entire wrapper is not claimed.

The audited panel preserves unknown operating states. The explicit `recorded_event_counts` configuration models retained archive counts in a separate modeling copy. A strict operating-hour analysis requires a verified calendar; absent records do not establish station operation or zero demand.

## Evidence boundaries

- Of 19,634 originally operating-unknown station-hours, two meet the declared all-12-five-minute-bin sampling criterion; 19,632 remain unsupported. Even full bin support is sampling evidence, not continuous uptime proof. This annual mask differs from the 15-minute test start-state strata.
- Change archives suppress unchanged quantities and may suppress flag-only updates. The 260 common fresh-state one-hour comparisons reset to measured states; they are distinct from the continuous road scenario and original assumed-capacity baseline.
- Roads are a current driving-profile proxy. Historical traffic, truck restrictions, the virtual depot, frozen scenario capacity and blocked-return behavior remain modeling assumptions.
- Prospective GBFS collection is deployed with a local 60-second target and a GitHub five-minute target. [Actual timestamps and trigger audits](reports/validation/monitoring_audit.json) determine observed coverage; cron configuration alone does not establish regular or long-term collection.

## Navigation

- [Project overview](PROJECT_OVERVIEW.md) and [application materials](application/README.md)
- [Ten-page technical report](reports/technical_report.pdf)
- [Historical evidence and extensions](reports/historical_evidence_and_extensions.md)
- [Road-fleet methods and collector deployment](reports/operations_completion.md)
- [Mathematical formulation](reports/optimization_formulation.md) and [data dictionary](DATA_DICTIONARY.md)
- [Scoped claims and their sources](application/CLAIMS_AND_EVIDENCE.csv)
- [Collector operation and restoration](services/README.md)
- [Complete task/evidence ledger](reports/task_status.md)

## Sources

Official trip records: [Citi Bike System Data](https://citibikenyc.com/system-data). Historical changes: [CityBikes](https://data.citybik.es/), with [ODbL database attribution](data/historical/DATABASE_NOTICE.md). Independent official GBFS captures are retained via Internet Archive. Roads use OpenStreetMap/OSRM, with [road attribution and scope](data/road_network/DATABASE_NOTICE.md); weather uses archived 24-hour-lead GFS forecasts with source attribution in `data/weather`. Underlying operator terms apply.
