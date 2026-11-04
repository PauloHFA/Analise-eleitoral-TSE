import io
import re
import zipfile
import pytest
from eleicoes.audit_download import RemoteZIP,identify


class Response:
    def __init__(self,data,a,b,tag='"version1"',status=206):
        self.status_code=status
        self.headers={'Content-Range':f'bytes {a}-{b}/{len(data)}','ETag':tag}
        self.raw=io.BytesIO(data[a:b+1])
    def __enter__(self):return self
    def __exit__(self,*args):pass


class Session:
    def __init__(self,data):self.data=data;self.calls=0;self.change=False;self.status=206
    def get(self,url,headers,**kwargs):
        self.calls+=1
        v=headers['Range']
        if v.startswith('bytes=-'):a=max(0,len(self.data)-int(v[7:]));b=len(self.data)-1
        else:a,b=map(int,re.fullmatch(r'bytes=(\d+)-(\d+)',v).groups())
        return Response(self.data,a,b,'"changed"' if self.change and self.calls>1 else '"version1"',self.status)


def archive():
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        z.writestr('one',b'A'*150000)
        z.writestr('two',b'B'*150000)
    return buf.getvalue()


def test_remote_zip_retrieves_exact_bytes_and_records_limited_hash_scope():
    source=archive();s=Session(source)
    with RemoteZIP('https://example.org/a.zip',s) as r,zipfile.ZipFile(r) as z:
        assert z.read('one')==b'A'*150000
        assert z.read('two')==b'B'*150000
        meta=r.metadata()
        assert meta['archive_sha256'] is None
        assert meta['ranges'] and meta['etag']=='"version1"'
        assert all(len(x['sha256'])==64 for x in meta['ranges'])


def test_remote_version_change_is_rejected():
    s=Session(archive());r=RemoteZIP('https://example.org/a.zip',s);s.change=True
    with pytest.raises(ValueError,match='alterada'):r.read(100)


def test_server_ignoring_range_is_rejected_before_reading_body():
    s=Session(archive());s.status=200
    with pytest.raises(ValueError,match='HTTP 200'):RemoteZIP('https://example.org/a.zip',s)


def test_crc_catches_corrupted_member():
    data=bytearray(archive());data[100]^=1
    with RemoteZIP('https://example.org/a.zip',Session(bytes(data))) as r,zipfile.ZipFile(r) as z:
        with pytest.raises(zipfile.BadZipFile,match='CRC'):z.read('one')


def test_identity_is_exact_and_excludes_directories_and_other_versions():
    assert identify('o03220sp7107200020491-rdv.dat','SP','71072','2','491','rdv')
    assert not identify('o03220sp71072000204910-rdv.dat','SP','71072','2','491','rdv')
    assert not identify('../o03220sp7107200020491-rdv.dat','SP','71072','2','491','rdv')
    assert not identify('s03220sp7107200020491-rdv.dat','SP','71072','2','491','rdv')
