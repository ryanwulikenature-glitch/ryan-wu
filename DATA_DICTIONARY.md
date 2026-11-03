# Data dictionary and feature contract

## Raw completed rides

| Field | Type / unit | Rule |
|---|---|---|
| ride_id | string | Required; first valid occurrence wins globally in sorted input/member order; within-member and cross-member duplicates audited |
| started_at, ended_at | NYC local timestamp unless explicit offset | Parse; unresolved DST ambiguous/nonexistent times excluded and counted; internal start/end UTC |
| start_station_id, end_station_id | string | Both required, preserve leading zeros; outside-region endpoints retained |
| start_lat, end_lat | degrees | Numeric, 40–42 inclusive |
| start_lng, end_lng | degrees | Numeric, −75 to −72 inclusive |
| start_station_name, end_station_name | optional text | Display only; never used to join station identity |
| rideable_type, member_casual | optional text | Preserved in cleaned partitions; not used as mandatory model features |
| duration | minutes (computed) | Must be >0 and <= max_duration_minutes; thresholds are research assumptions |

Cleaning reasons are mutually exclusive in order: missing IDs, invalid/DST time, invalid duration, invalid coordinate. Invalid rows are removed before ride-ID deduplication. ZIP + extracted CSV duplicate content is removed by global ID checks; identical whole files additionally skipped by SHA256. Download manifest supplies URL, month, date, bytes, hash and CSV count. Processing manifest records consumed bytes/hash; monthly audit includes member/chunk row counts, retained ranges and represented months. “Complete year” means all 12 start months are represented, not verified historical operational coverage of every station/hour.

## Stations

`station_id`, `station_name`, `latitude`, `longitude`, `training_events` (both endpoints in Jan–Aug), `active_months`, `capacity` (bikes), `capacity_source=assumed`, `selection_reason`. Only training-period endpoint events affect selection; rank by active_months then training_events after rectangle, volume and drift filters. Drift uses training hourly median coordinates, so subhour relocations can remain undetected. Synthetic station fixtures have no real historical selection statistics.

## Station-hour panel

Unique key `(station_id, hour)`; `hour` is UTC-aware, exactly one-hour-spaced for each station. NYC 2025 has 8760 hours; DST dates have 23/25 local hours. Internal UTC folds remain distinct; raw naive fold events cannot be assigned reliably and are excluded.

- `observed_departures`, `observed_arrivals`: cleaned recorded endpoint counts, integer, including crossing-boundary trips; zeros mean no retained records in that hour, not confirmed latent zero demand.
- `departures`, `arrivals`: modeling targets, same count where active evidence exists, otherwise missing.
- `active_flag`: 1 for observed event hour or supplied verified operating-hour calendar; 0 means unknown/closed, **not an inferred absence of demand**.
- `activity_source`: observed-events-only / provided operating calendar / synthetic-known-operating.
- `netflow`: arrivals − departures; not a direct inventory observation.

The panel target rule conserves all observed selected-station counts, while leaving unverified zero hours missing. It can bias official forecasting toward active hours; operating-calendar evidence is needed to evaluate a genuinely full hourly operating panel.

## Features and splits

`hour_of_day`, `day_of_week` (Mon=0), `month`, `weekend`, US federal `holiday` (calendar proxy, not all NYC holidays), hour/week sine/cosine; `dep/arr_lag1/24/168` use elapsed UTC hours, so the seasonal lag is not always the same NYC wall-clock time across DST. `dep/arr_roll24/168_mean/std` use `shift(1)` and require complete windows. Missing predictors are imputed using training medians, unseen station categories ignored. Model labels never imputed. All models use the same rows with both observed targets and weekly-lag labels. Poisson GLM is scikit-learn regularized PoissonRegressor, not unpenalized inferential statsmodels GLM. Lags for partially observed current rides cannot reproduce actual live ingestion without endpoint arrival availability; raw ride-level truth is treated as known after each hour.

`split` by America/New_York month: 1–8 train, 9–10 validation, 11–12 test. A larger `year` change requires matching split calendar/source data. Features are not random-split.

## Forecast and simulation outputs

`test_predictions.csv.gz`: station_id/hour, observed targets, dep/arr predictions for each model, `pred_dep/pred_arr` selected separately by validation MAE. Nonnegative counts may be fractional predictions. Forecast metrics rows contain model, target, split, stratum, n, MAE (rides/station/hour), RMSE (same), WAPE (ratio); undefined metrics empty/JSON null.

`moves.csv`: UTC timestamp, strategy, source_station, target_station, integer bikes_moved, Haversine distance_km, solver_status, fallback, runtime_ms, proxy_objective. Empty move files still contain headers. No-move hours' solver status is in simulation_hourly.csv.

`simulation_hourly.csv`: scenario requests/arrival events, unmet_departures, blocked_arrivals, served counts, bikes_moved, bike_km, realized scenario_objective, forecast proxy_objective, sample_hash, inventory sums, solver metadata. `scenario_objective = shortage_weight*unmet + overflow_weight*blocked + distance_weight*bike_km`; weights are preference units, not money. Summary rate is 1−unmet/requests; no requests means undefined.

`inventory_trace.csv.gz`: per station/policy/hour before move, post move and end inventory, capacity. `policy_comparison.csv`: absolute difference and relative change against a named baseline (not generic “improvement”); zero baseline relative change undefined. `uncertainty_summary.csv`: paired local-day block bootstrap interval for mean daily objective difference; partial horizon days are kept as observed blocks.

`experiments.csv`: all scenario parameters, forecast source, seed in parameters, run status, output path, per-policy results; exact library versions in experiment_protocol.json and requirements-lock.txt. Oracle uses future hour counts only as a non-deployable information comparator.

`event_replay_hourly.csv`: docked, in_transit, held_off_dock, initial_fleet, cumulative boundary incoming/outgoing and accounted_fleet. Conservation: docked + transit + held = initial_fleet + incoming − outgoing. Rejected departures have suppressed returns, logged in event_replay_ledger.csv. Failed returns remain held through the horizon.

## Explicit archived-count scenario mode

`configs/official_counts.json` sets observation_mode=recorded_event_counts. It preserves the audited panel unchanged and uses observed_* counts for both model labels and features in a temporary modeling copy. Therefore zero archive events become zero **retained-record count**, not evidence of operation or zero latent demand. This estimand is distinct from the strict active-hour panel. Reports disclose the choice; full station-hour scenario replay is allowed under the explicit record-count observation model.

For bounded-memory processing, training candidate locations are summarized within source chunks/local months: one median coordinate point with event count and two diagonal extrema points with zero added count. Station selection uses only these training-period summaries. The conservative diagonal-envelope proxy is not a verified historical relocation trajectory. Endpoint event partitions are losslessly counted and selected-station totals reconciled to clean raw endpoint counts.
# Application-stage evidence and external evaluation

`outputs/coverage_audit/evidence_eligibility.parquet`: `station_id,hour` identify each original test forecast; `max_age_minutes` is the declared 5/15/30/60-minute past-state criterion; `timestamp` and `reported_at` are the archive/source times. `eligible` requires a preceding fresh, internally consistent, rent/return-enabled point within that criterion. False means unsupported by this rule, not closed. The corresponding metrics use identical fixed-model rows within each stratum. This criterion differs from the annual 12-bin sampling-support mask.

`outputs/external_202601/panel.parquet` and `predictions.parquet`: January2026 local-hour archived endpoint counts for the original30 sites, 744x30 rows. Zero is no retained record, not proven zero latent demand or verified opening. `dep_*`/`arr_*` are unchanged2025 model forecasts and last-hour/168-hour comparators. `validation.json` records the pre-download protocol commit, model hashes, selected-endpoint cleaning audit, December-origin carryover count and boundary/accounting rules.

`models/frozen_2025`: four exact fitted pipelines from January–October2025, copied without refitting; `history_tail.parquet` has5040 rows of prior168-hour completed-record counts, not operating truth; `carryover.parquet` is the retained December-origin arrival context. `MANIFEST.json` binds every model/context file to SHA256. The files support standalone external replication without the original full-year partitions.

`reports/validation/monitoring_audit.json`: actual first/last poll times, observed span, cadence gaps, failures and schedule-run linkage. Gap compliance does not imply continuous station availability. `polls.scope` can retain public GitHub run ID, attempt and trigger type; no schedule trigger is inferred from configuration alone.
