from pathlib import Path
import hashlib
import json
import platform
import importlib.metadata
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

def load_config(path=None):
    return json.loads(Path(path or ROOT / 'configs/base.json').read_text())

def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False, default=str) + '\n')

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def versions():
    return {'python': platform.python_version(), **{p: importlib.metadata.version(p) for p in
            ['numpy', 'pandas', 'scipy', 'scikit-learn', 'xgboost', 'matplotlib', 'pyarrow']}}

def distances(stations):
    lat = np.radians(stations.latitude.to_numpy(float))
    lon = np.radians(stations.longitude.to_numpy(float))
    a = np.sin((lat[:, None] - lat) / 2)**2 + np.cos(lat[:, None]) * np.cos(lat) * np.sin((lon[:, None] - lon) / 2)**2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
