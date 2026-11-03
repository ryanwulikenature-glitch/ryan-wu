import io
import zipfile
import hashlib
import pandas as pd
import pytest
from src.download import download

def zip_bytes():
    f=io.BytesIO()
    with zipfile.ZipFile(f,'w') as z:z.writestr('a.csv','ride_id\nr1\n')
    return f.getvalue()

class Response:
    def __init__(self,body):self.body=body
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def raise_for_status(self):pass
    def iter_content(self,size):yield self.body

def test_atomic_download_manifest_crc_and_existing_file(tmp_path,monkeypatch):
    body=zip_bytes();calls=[]
    def get(url,**kwargs):calls.append(url);assert kwargs['stream'];return Response(body)
    monkeypatch.setattr('src.download.requests.get',get)
    download(months=[1],root=tmp_path);download(months=[1],root=tmp_path)
    assert len(calls)==1
    m=pd.read_csv(tmp_path/'interim/download_manifest.csv')
    assert len(m)==1 and m.sha256.iloc[0]==hashlib.sha256(body).hexdigest()
    assert m.csv_count.iloc[0]==1 and m.url.str.contains('202501').all()
    (tmp_path/'raw/202501-citibike-tripdata.zip').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='hash changed'):download(months=[1],root=tmp_path)

def test_invalid_archive_never_promoted(tmp_path,monkeypatch):
    monkeypatch.setattr('src.download.requests.get',lambda *a,**k:Response(b'not-a-zip'))
    with pytest.raises(zipfile.BadZipFile):download(months=[1],root=tmp_path)
    assert not list((tmp_path/'raw').iterdir())

def test_redownload_cannot_silently_replace_recorded_checksum(tmp_path,monkeypatch):
    body=zip_bytes();monkeypatch.setattr('src.download.requests.get',lambda *a,**k:Response(body));download(months=[1],root=tmp_path)
    (tmp_path/'raw/202501-citibike-tripdata.zip').unlink()
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as z:z.writestr('other.csv','ride_id\nr2\n')
    monkeypatch.setattr('src.download.requests.get',lambda *a,**k:Response(buffer.getvalue()))
    with pytest.raises(ValueError,match='recorded SHA256'):download(months=[1],root=tmp_path)
    assert not list((tmp_path/'raw').iterdir())
