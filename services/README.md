# Prospective official GBFS collector

The deployed workflow is `.github/workflows/collect-gbfs.yml`, with target cron `2-59/5 * * * *` (UTC, offset from busy minute boundaries), `workflow_dispatch`, and source-change triggers. Its real output lives on the independent `gbfs-history` branch. Source changes do not erase that branch. Read `STATUS.json`, actual archived timestamps and Actions results to assess freshness; a cron definition alone does not prove regular execution. GitHub may delay or disable schedules. The source repository is public; automatic jobs skip private repositories to avoid implicitly consuming paid private compute.

The managed-cloud process separately targets 60 seconds while the machine is running:

```bash
.venv/bin/python services/collectorctl.py start
.venv/bin/python services/collectorctl.py status
.venv/bin/python services/collectorctl.py stop
```

PID ownership and an exclusive flock prevent interfering with unrelated processes or duplicate collectors. `start` is idempotent. `stop` requests orderly termination; inspect the returned `process_alive` before assuming it has stopped. An in-progress HTTP request may take up to its timeout. The process is detached from the shell, not installed as a host-level boot service; future cloud start instructions restart it when needed.

`data/telemetry/health.json`, `service.json`, `collector.log`, `worker_errors.jsonl` (when present), and `retention.json` record live health. Missing/removed station IDs and stale reports are retained as unknown-quality rows, not source failures or station closures. Every selected station is stored on every poll, including unchanged bike/dock counts and flag-only changes. Feed retrieval failures are archived as failed heartbeat evidence.

Local full-network raw JSON retention is 7 days. The normalized SQLite working set is 30 days; older rows move to append-only daily gzip JSONL archives under `data/telemetry/archive`. Before pruning, all fields and row counts must match a re-read archive; checksum or completeness failure prevents deletion. Preserve this directory on durable storage when relocating the machine. The external GitHub collector independently writes its normalized observations durably on `gbfs-history`.

Restore the archive to SQLite using Python's standard library (the full ML environment is unnecessary):

```bash
python3 scripts/import_telemetry_archive.py --archive /path/to/gbfs-history-checkout --db /tmp/inventory.sqlite
```

For a consistent local live snapshot, use `scripts/snapshot_telemetry.py`; it uses SQLite's backup API, not a potentially incomplete copy of a WAL database. The delivered static snapshot is dated evidence, not a continuously updating file.

Only official public station fields are collected; no rider identities or credentials. Data starts at actual polling time and never backfills missing 2025 states. Underlying NYCBS/Citi Bike data-use terms apply.
