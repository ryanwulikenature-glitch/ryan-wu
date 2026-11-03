"""Manage only this project's own Linux collector process; never kill unrelated PIDs."""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'data/telemetry'
def state():
    meta=json.loads((out/'service.json').read_text()) if (out/'service.json').exists() else {}
    pid=meta.get('pid');alive=False
    if pid and meta.get('state')=='running':
        try:alive=b'src.telemetry' in Path(f'/proc/{pid}/cmdline').read_bytes()
        except OSError:pass
    health=json.loads((out/'health.json').read_text()) if (out/'health.json').exists() else None
    return {'process_alive':alive,'process':meta,'latest_poll':health}
p=argparse.ArgumentParser();p.add_argument('action',choices=['start','status','stop']);a=p.parse_args();out.mkdir(parents=True,exist_ok=True)
if a.action=='start' and not state()['process_alive']:
    with open(out/'collector.log','ab') as log:
        subprocess.Popen([str(ROOT/'.venv/bin/python'),'-m','src.telemetry','--run','--interval','60'],cwd=ROOT,stdout=log,stderr=log,start_new_session=True)
    time.sleep(.5)
elif a.action=='stop' and state()['process_alive']:
    os.kill(state()['process']['pid'],signal.SIGTERM)
    deadline=time.monotonic()+5
    while state()['process_alive'] and time.monotonic()<deadline:time.sleep(.1)
print(json.dumps(state(),indent=2))
