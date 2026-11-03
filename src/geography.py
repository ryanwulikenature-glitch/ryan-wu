"""Official polygon membership; geometry version is explicit, never inventory evidence."""
import json
import numpy as np
from pathlib import Path
from matplotlib.path import Path as PolygonPath
from .common import ROOT

def membership(stations,geojson):
    path=Path(geojson);path=path if path.is_absolute() else ROOT/path
    data=json.loads(path.read_text());features=data.get('features',[data]);points=stations[['longitude','latitude']].to_numpy(float);inside=np.zeros(len(points),bool)
    for f in features:
        name=str(f.get('properties',{}).get('boroname',f.get('properties',{}).get('boro_name','Manhattan')))
        if name!='Manhattan':continue
        g=f['geometry'];polygons=[g['coordinates']] if g['type']=='Polygon' else g['coordinates']
        for polygon in polygons:
            mask=PolygonPath(polygon[0]).contains_points(points,radius=1e-10)
            for hole in polygon[1:]:mask &= ~PolygonPath(hole).contains_points(points,radius=1e-10)
            inside|=mask
    return inside
