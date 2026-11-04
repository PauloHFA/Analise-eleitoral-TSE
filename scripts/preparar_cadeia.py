"""Preserva candidatos intermediários e tentativas públicas, sem alterar confiança."""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
import argparse,ast,base64,hashlib,json,zipfile
import requests
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from eleicoes.sources import sha256,write_json

PACKAGE_SHA='1e423054f32b8ba056960c58ada167d702c2618cc4d1dfd5de88f5090c84a235'
CANDIDATES={'AC URNA':'dc20a4c3b8aef01794b80efe8e143e1fbf719707e00bb0d4ba8865191dc2731d',
 'AC UE2020':'77f31bef3d8eb35f0cc969a2b9bba3ff2a498cc339d29a375d3181e0547c0376',
 'AC UE2022':'6ae65790dae7cc5d97394e461204744c8e2f7a810d0303af828d4d3dbecfa293'}
HASH_URL='https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/hash/arquivos/2026/sistemas-em-ambiente-pc/pc1holo'


def run(data,destination=None):
    data=Path(data).resolve();root=Path(destination).resolve() if destination else data/'auditoria/cadeia/v1';package=data/'auditoria/documentacao/formato-v2-mirror-1e423054f32b8ba0.zip'
    if root.exists() and any(root.iterdir()):raise FileExistsError('Versão de fontes preenchida; preserve e use outro --data')
    if sha256(package)!=PACKAGE_SHA:raise ValueError('Pacote técnico diferente da versão conferida')
    with zipfile.ZipFile(package) as z:source=z.read('python/lib/mr_util.py').decode('utf8')
    tree=ast.parse(source)
    values=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_AC_RAIZ_UE_PEMS' for t in n.targets))
    root.mkdir(parents=True);candidates=[];crl_urls=set()
    for value in values:
        cert=x509.load_der_x509_certificate(base64.b64decode(''.join(value.split()),validate=True));name=cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
        der=cert.public_bytes(serialization.Encoding.DER);digest=hashlib.sha256(der).hexdigest()
        if CANDIDATES.get(name)!=digest:raise ValueError('Candidato não corresponde ao certificado revisado')
        file=name.lower().replace(' ','-')+'.pem';(root/file).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        candidates.append(dict(name=name,file=file,der_sha256=digest,file_sha256=sha256(root/file),
            origin='Extraído como dado de pacote técnico obtido de espelho; não é âncora de confiança',trust_anchor=False))
        for point in cert.extensions.get_extension_for_class(x509.CRLDistributionPoints).value:
            for uri in point.full_name or []:
                if isinstance(uri,x509.UniformResourceIdentifier):crl_urls.add(uri.value)
    crl_urls.update('http://lcr.'+name+'.tse.jus.br/'+name+'.crl' for name in ('acurna','acue2020','acue2022'))
    attempts=[dict(url=u,kind='crl',source='Ponto de distribuição de LCR dos certificados') for u in sorted(crl_urls)]
    attempts += [dict(url=u.replace('http://','https://',1),kind='crl',source='Alternativa HTTPS ao ponto de distribuição HTTP; sem desativar TLS') for u in sorted(crl_urls)]
    attempts += [dict(url=f'{scheme}://dpc.acue2020.tse.jus.br/{name}.crt',kind='candidate_certificate',source='Endereço candidato citado em referência de terceiros, sem obtenção direta confirmada') for scheme,names in (('http',('acraizue','acraizuev2','acurnav2','acurna','acue2020','acue2022')),('https',('acraizue','acraizuev2','acurnav2'))) for name in names]
    attempts += [dict(url=u,kind='hash_archive',source='Recurso vinculado na página de hashes do TSE') for u in (HASH_URL,HASH_URL+'/@@download/file/pc1holo.zip')]
    def fetch(item):
        row=dict(item,attempted_at=datetime.now(timezone.utc).isoformat(),tls_verification=True,redirects_followed=False)
        host=urlsplit(row['url']).hostname
        if not host or not host.endswith('.tse.jus.br'):raise ValueError('Endereço fora do domínio autorizado')
        try:
            with requests.get(row['url'],stream=True,timeout=(5,12),allow_redirects=False) as r:
                content=r.raw.read(2*1024*1024+1)
                row.update(http_status=r.status_code,bytes=len(content),content_type=r.headers.get('Content-Type'),body_sha256=hashlib.sha256(content).hexdigest(),body_truncated=len(content)>2*1024*1024,location=r.headers.get('Location'))
                if r.status_code==200 and len(content)<=2*1024*1024:
                    file='obtido-'+hashlib.sha256(row['url'].encode()).hexdigest()[:16]+'.bin';(root/file).write_bytes(content);row['saved_file']=file
        except requests.RequestException as exc:row.update(error_type=type(exc).__name__,error=str(exc))
        return row
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(fetch,attempts))
    metadata=dict(obtained_at=datetime.now(timezone.utc).isoformat(),package_sha256=PACKAGE_SHA,
        package_origin='Espelho de terceiros preservado em rodada anterior; nenhum código executado',candidates=candidates,attempts=results,
        anchors_trusted=[],trust_policy='Nenhum intermediário, raiz candidata, hash de espelho ou certificado embutido é promovido a âncora automaticamente')
    write_json(root/'fontes.json',metadata)
    write_json(root/'manifesto.json',{p.name:sha256(p) for p in sorted(root.iterdir()) if p.is_file() and p.name!='manifesto.json'})
    print(json.dumps(dict(candidates=len(candidates),attempts=len(results),http_200=sum(r.get('http_status')==200 for r in results),tls_errors=sum(r.get('error_type')=='SSLError' for r in results)),ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',default='data');p.add_argument('--dest');a=p.parse_args();run(a.data,a.dest)
