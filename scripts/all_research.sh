#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
export MPLCONFIGDIR=/tmp/citibike-mpl XDG_CACHE_HOME=/tmp/citibike-cache
mkdir -p reports/validation
.venv/bin/python -m pytest -q --junitxml=reports/validation/pytest.xml | tee reports/validation/pytest.txt
# Full raw inputs are required by the independently rerun duration study.
.venv/bin/python -m src.download --year 2025
# Source/cleaning caches are retained; create them if absent, never replace user edits.
if [ ! -f data/processed/panel.parquet ]; then
 .venv/bin/python -m src.prepare --config configs/official_counts.json
fi
if [ ! -f outputs/official/test_predictions.csv.gz ]; then ./scripts/official_pipeline.sh; fi
.venv/bin/python scripts/eda_business.py
.venv/bin/python -m src.history_sources | tee reports/validation/history_download.log
.venv/bin/python -m src.history_evidence | tee reports/validation/history_evidence.log
.venv/bin/python -m src.history_calibrated | tee reports/validation/history_calibrated.log
.venv/bin/python scripts/download_weather.py
.venv/bin/python -m src.train --config configs/weather.json --out outputs/weather
.venv/bin/python scripts/weather_experiment.py | tee reports/validation/weather_experiment.log
.venv/bin/python -m src.duration_study | tee reports/validation/duration_study.log
.venv/bin/python scripts/stochastic_experiment.py | tee reports/validation/stochastic.log
.venv/bin/python scripts/routing_experiment.py | tee reports/validation/routing.log
.venv/bin/python scripts/network_expansion.py | tee reports/validation/network60.log
# Retained directed OSRM matrix is a dated road proxy, not historical traffic.
.venv/bin/python scripts/transport_experiment.py | tee reports/validation/transport_experiment.log
.venv/bin/python scripts/check_transport.py | tee reports/validation/transport_checks.log
.venv/bin/python scripts/missingness_experiment.py | tee reports/validation/coverage_audit.log
.venv/bin/python scripts/history_report.py | tee reports/validation/history_report.log
.venv/bin/python scripts/check_extensions.py | tee reports/validation/extensions_checks.log
.venv/bin/python scripts/english_report.py
.venv/bin/python scripts/execute_notebook.py notebooks/03_historical_evidence.ipynb | tee reports/validation/history_notebook.log
.venv/bin/python scripts/package.py
