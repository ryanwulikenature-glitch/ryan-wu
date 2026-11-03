import os
import sys
from pathlib import Path
import nbformat
from nbclient import NotebookClient
root=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR','/tmp/citibike-mpl')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/citibike-cache')
path=root/(sys.argv[1] if len(sys.argv)>1 else 'notebooks/01_eda.ipynb')
nb=nbformat.read(path,as_version=4)
client=NotebookClient(nb,timeout=120,kernel_name='python3',resources={'metadata':{'path':str(root)}})
client.create_kernel_manager()
client.km.kernel_spec.argv=[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}']
client.execute()
nbformat.write(nb,path)
print(f'PASS: executed {sum(c.cell_type=="code" for c in nb.cells)} EDA notebook cells with current venv kernel.')
