import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.telemetry_archive import export_archives
p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);a=p.parse_args()
count=export_archives(a.db,a.archive)
(a.archive/'README.md').write_text('''# Prospective Citi Bike inventory evidence archive\n\nThis branch starts at actual collection time, not 2025. Each gzip JSONL member stores the poll, source/hash/time evidence and all 30 study-site observations including unchanged quantities, flag-only changes, absent/stale states and failures. No rider information or credentials. Source: https://gbfs.citibikenyc.com/gbfs/en/ ; underlying NYCBS data-use terms apply.\n\nGitHub Actions targets five-minute collection but can be delayed/disabled; audit actual timestamps and missing heartbeats. It is not a per-minute uptime guarantee. A separate managed-cloud process targets 60 seconds while its machine is active. Future coverage grows only as time passes.\n\nReconstruct the cumulative SQLite database with scripts/import_telemetry_archive.py from main. GitHub scheduling requires Actions to remain enabled and the public repository active.\n''')
print('Verified archive export:',count,'new polls')
