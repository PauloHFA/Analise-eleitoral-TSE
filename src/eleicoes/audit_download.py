"""Leitura seletiva de ZIPs oficiais, sem atribuir hash ao arquivo não baixado."""
import hashlib
import io
import re
import requests
import json
import zipfile
from datetime import datetime,timezone
from pathlib import Path
import duckdb
import pandas as pd
from .analysis import export_frame
from .national_common import begin,finish,failed,records
from .sources import sha256,write_json


class RemoteZIP(io.RawIOBase):
    def __init__(self,url,session=None):
        self.url=url;self.session=session or requests.Session();self.position=0;self.bytes_received=0;self.requests=[]
        self.size=None;self.etag=None;self.modified=None
        tail=self._request(None,None)
        self.tail=tail;self.tail_start=self.size-len(tail);self.cache=b'';self.cache_start=0

    def _request(self,start,end):
        value='bytes=-65557' if start is None else f'bytes={start}-{end}'
        headers={'Range':value,'Accept-Encoding':'identity'}
        if self.etag:headers['If-Match']=self.etag
        with self.session.get(self.url,headers=headers,stream=True,timeout=(15,90)) as r:
            if r.status_code!=206:raise ValueError(f'Servidor não confirmou leitura parcial: HTTP {r.status_code}')
            match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',r.headers.get('Content-Range',''))
            if not match:raise ValueError('Content-Range ausente ou inválido')
            a,b,total=map(int,match.groups());tag=r.headers.get('ETag');modified=r.headers.get('Last-Modified')
            if self.size is None:
                self.size=total;self.etag=tag;self.modified=modified
                if not tag or tag.startswith('W/'):raise ValueError('ETag forte necessário para fixar a versão remota')
            elif total!=self.size or tag!=self.etag:raise ValueError('Versão remota alterada durante a leitura')
            if start is not None and (a!=start or b!=end):raise ValueError('Intervalo recebido diferente do solicitado')
            if start is None and (b!=total-1 or a!=max(0,total-65557)):raise ValueError('Cauda ZIP incompleta')
            if b-a+1>128*1024*1024:raise ValueError('Intervalo excede limite de 128 MiB')
            data=r.raw.read(b-a+2)
            if len(data)!=b-a+1:raise ValueError('Leitura parcial truncada')
            self.bytes_received+=len(data)
            self.requests.append(dict(start=a,end=b,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
            return data

    def seekable(self):return True
    def readable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        pos=offset if whence==0 else self.position+offset if whence==1 else self.size+offset if whence==2 else -1
        if pos<0:raise ValueError('Posição negativa')
        self.position=pos;return pos
    def read(self,size=-1):
        end=self.size if size<0 else min(self.size,self.position+size)
        if end<=self.position:return b''
        if self.position>=self.tail_start:data=self.tail[self.position-self.tail_start:end-self.tail_start]
        elif self.cache_start<=self.position and end<=self.cache_start+len(self.cache):
            data=self.cache[self.position-self.cache_start:end-self.cache_start]
        elif end-self.position<262144:
            self.cache_start=self.position;self.cache=self._request(self.position,min(self.size-1,self.position+262143))
            data=self.cache[:end-self.position]
        else:data=self._request(self.position,end-1)
        self.position=end;return data
    def metadata(self):
        return dict(url=self.url,archive_bytes=self.size,etag=self.etag,last_modified=self.modified,
                    bytes_received=self.bytes_received,ranges=self.requests,archive_sha256=None,
                    hash_scope='Somente intervalos recebidos e membros extraídos; ZIP completo não baixado')


CATALOG='https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026-arquivos-transmitidos-para-totalizacao'
KINDS={'rdv':'rdv.dat','bu':'bu.dat','imagem':'imgbu.dat','assinatura':'vota.vsc','log':'log.jez'}


def identify(name,uf,municipality,zone,section,kind):
    # Aceitar unicamente o sufixo/formato documentado, sem buscas parciais por seção.
    key=f'{uf.lower()}{str(municipality).zfill(5)}{str(zone).zfill(4)}{str(section).zfill(4)}'
    return bool(re.fullmatch(r'o\d{5}'+re.escape(key+'-'+KINDS[kind]),name))


def run_download(source,data='data',destination=None):
    source=Path(source).resolve();raw=Path(data).resolve()/'auditoria/urnas'
    destination=Path(destination).resolve() if destination else source/'auditoria/documentos'
    names=['auditoria/amostra/secoes.parquet','auditoria/amostra/turnos.parquet','auditoria/amostra/manifesto.json']
    source,destination,state=begin(source,destination,names)
    session=requests.Session();con=duckdb.connect();rows=[];archives=[]
    try:
        catalog=session.get(CATALOG,timeout=60);catalog.raise_for_status();payload=catalog.json()
        if not payload.get('success'):raise ValueError('Catálogo não confirmou consulta')
        resources=payload['result']['resources'];raw.mkdir(parents=True,exist_ok=True)
        cat_path=raw/'catalogo.json'
        if cat_path.exists():raise FileExistsError('Diretório de originais já preenchido; preserve-o e escolha outro --data')
        cat_path.write_bytes(catalog.content)
        sample=con.execute('SELECT * FROM read_parquet(?)',[str(source/names[0])]).df()
        selected=con.execute('SELECT * FROM read_parquet(?)',[str(source/names[1])]).df()
        for (uf,turn),group in selected.groupby(['uf','turn'],sort=True):
            hits=[r for r in resources if r['url'].endswith(f'2026_{turn}t_{uf}.zip')]
            if len(hits)!=1:raise ValueError(f'Recurso não único: {uf}/{turn}')
            url=hits[0]['url']
            if not url.startswith('https://cdn.tse.jus.br/estatistica/'):raise ValueError('Recurso fora do CDN oficial')
            stamp=datetime.now(timezone.utc).isoformat();remote=None;archive_error=None
            try:
                with RemoteZIP(url,session) as remote,zipfile.ZipFile(remote) as z:
                    infos=z.infolist()
                    for case in group.to_dict('records'):
                        for kind in KINDS:
                            entry=dict(year=2026,turn=int(turn),uf=uf,municipality=case['municipality'],zone=case['zone'],section=case['section'],kind=kind,url=url,obtained_at=stamp,status='ausente',member=None,path=None,sha256=None,size=None,crc32=None,reason=None)
                            matching=[i for i in infos if identify(i.filename,uf,case['municipality'],case['zone'],case['section'],kind)]
                            try:
                                if len(matching)>1:raise ValueError('Mais de um membro para a unidade/tipo; nenhuma versão escolhida arbitrariamente')
                                if matching:
                                    info=matching[0]
                                    if info.file_size>8*1024*1024 or info.flag_bits&1:raise ValueError('Membro excede limite ou está cifrado')
                                    content=z.read(info) # zipfile verifica CRC32 do membro completo.
                                    target=raw/f'{uf}/{turn}'/info.filename;target.parent.mkdir(parents=True,exist_ok=True)
                                    if target.exists():raise FileExistsError('Original já existe')
                                    target.write_bytes(content)
                                    entry.update(status='obtido',member=info.filename,path=target.relative_to(Path(data).resolve()).as_posix(),sha256=sha256(target),size=len(content),crc32=f'{info.CRC:08x}')
                            except Exception as exc:entry.update(status='limitado',reason=f'{type(exc).__name__}: {exc}')
                            rows.append(entry)
            except Exception as exc:
                archive_error=f'{type(exc).__name__}: {exc}'
                for case in group.to_dict('records'):
                    for kind in KINDS:
                        if not any(r['uf']==uf and r['turn']==turn and r['municipality']==case['municipality'] and r['zone']==case['zone'] and r['section']==case['section'] and r['kind']==kind for r in rows):
                            rows.append(dict(year=2026,turn=int(turn),uf=uf,municipality=case['municipality'],zone=case['zone'],section=case['section'],kind=kind,url=url,obtained_at=stamp,status='limitado',reason=archive_error))
            metadata=remote.metadata() if remote else dict(url=url)
            metadata.update(uf=uf,turn=int(turn),obtained_at=stamp,error=archive_error);archives.append(metadata)
            write_json(destination/'progresso.json',dict(archives=archives,documents=rows))
            print(f'{uf}/{turn}: {sum(r["status"]=="obtido" for r in rows)} documentos obtidos',flush=True)
        frame=pd.DataFrame(rows)
        if len(frame)!=len(selected)*len(KINDS) or frame.duplicated(['year','turn','uf','municipality','zone','section','kind']).any():raise ValueError('Inventário não fecha a amostra/tipos')
        export_frame(con,frame,destination/'inventario')
        write_json(destination/'arquivos_remotos.json',archives)
        summary=dict(sections=len(sample),section_turns=len(selected),expected_documents=len(frame),
            statuses=records(frame.groupby(['kind','status']).size().reset_index(name='documents')),
            obtained_documents=int(frame.status.eq('obtido').sum()),remote_archives=len(archives),
            catalog=dict(url=CATALOG,path='auditoria/urnas/catalogo.json',sha256=sha256(cat_path),size=cat_path.stat().st_size),
            network_bytes=sum(a.get('bytes_received',0) for a in archives),sample_manifest_sha256=sha256(source/names[2]),
            interpretation='Obtenção e CRC32/SHA256 dos membros. Ainda não constitui recontagem do RDV, conferência do BU nem validação das assinaturas. ZIPs completos não baixados; ETag fixa versão por arquivo remoto.')
        return finish(source,destination,state,summary,[Path(__file__)])
    except Exception as exc:failed(destination,state,exc);raise
    finally:con.close();session.close()
