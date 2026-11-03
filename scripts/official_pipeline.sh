#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
export MPLCONFIGDIR=/tmp/citibike-mpl XDG_CACHE_HOME=/tmp/citibike-cache
.venv/bin/python -m src.run --config configs/official_counts.json --prepared --hours 1465 --experiment-hours 48
.venv/bin/python scripts/official_event_replay.py
.venv/bin/python scripts/check_official_outputs.py
.venv/bin/python scripts/finalize_official.py
.venv/bin/python scripts/execute_notebook.py notebooks/02_eda_official.ipynb
