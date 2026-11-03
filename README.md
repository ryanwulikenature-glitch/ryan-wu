# Prospective Citi Bike inventory evidence archive

This branch starts at actual collection time, not 2025. Each gzip JSONL member stores the poll, source/hash/time evidence and all 30 study-site observations including unchanged quantities, flag-only changes, absent/stale states and failures. No rider information or credentials. Source: https://gbfs.citibikenyc.com/gbfs/en/ ; underlying NYCBS data-use terms apply.

GitHub Actions targets five-minute collection but can be delayed/disabled; audit actual timestamps and missing heartbeats. It is not a per-minute uptime guarantee. A separate managed-cloud process targets 60 seconds while its machine is active. Future coverage grows only as time passes.

Reconstruct the cumulative SQLite database with scripts/import_telemetry_archive.py from main. GitHub scheduling requires Actions to remain enabled and the public repository active.
