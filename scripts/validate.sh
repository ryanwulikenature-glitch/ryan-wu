#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
export MPLCONFIGDIR=/tmp/citibike-mpl XDG_CACHE_HOME=/tmp/citibike-cache
mkdir -p reports/validation
.venv/bin/python -m pytest -q --junitxml=reports/validation/pytest.xml | tee reports/validation/pytest.txt
.venv/bin/python -m src.run --demo --hours 336 --experiment-hours 48 | tee reports/validation/demo.txt
.venv/bin/python scripts/check_outputs.py | tee reports/validation/output_checks.txt
.venv/bin/python scripts/event_demo.py | tee reports/validation/event_demo.txt
.venv/bin/python scripts/execute_notebook.py | tee reports/validation/notebook.txt
cp outputs/demo/final_report.md reports/final_report.md
cp outputs/demo/eda_findings.md reports/eda_findings.md
