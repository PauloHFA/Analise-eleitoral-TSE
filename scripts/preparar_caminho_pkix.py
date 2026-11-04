"""Pesquisa complementar de fontes, sem inventar âncoras ou alterar a captura anterior."""
import argparse,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import requests
from eleicoes.sources import sha256,write_json


def run(data):
    data=Path(data).resolve();dest=data/'auditoria/pkix/v1'
    if dest.exists() and any(dest.iterdir()):raise FileExistsError('Captura preenchida; usar outra árvore --data')
    previous=data/'auditoria/cadeia/v1'
    for name,digest in json.loads((previous/'manifesto.json').read_text(encoding='utf8')).items():
        if sha256(previous/name)!=digest:raise ValueError('Captura anterior alterada')
    dest.mkdir(parents=True,exist_ok=True)
    urls=[('https://acue2020.tse.jus.br/dpc/'+n+'.crt','certificado','Base /dpc/ identificada na extração HTTP do índice; arquivo candidato') for n in ('acraizue','acraizuev2','acurnav2','acurna','acue2020','acue2022')]
    urls += [('https://'+n+'.tse.jus.br/lcr/'+n+'.crl','lcr','Rota candidata derivada do padrão canônico, sem publicação confirmada') for n in ('acurna','acue2020','acue2022','acraizue','acurnav2')]
    def fetch(item):
        url,kind,origin=item;row=dict(url=url,kind=kind,origin=origin,attempted_at=datetime.now(timezone.utc).isoformat(),tls_verification=True,redirects_followed=False)
        try:
            with requests.get(url,stream=True,timeout=(5,15),allow_redirects=False) as r:
                b=r.raw.read(2*1024*1024+1);row.update(http_status=r.status_code,bytes=len(b),body_sha256=hashlib.sha256(b).hexdigest(),body_truncated=len(b)>2*1024*1024,location=r.headers.get('Location'))
                if r.status_code==200 and len(b)<=2*1024*1024:
                    name=hashlib.sha256(url.encode()).hexdigest()[:16]+'.bin';(dest/name).write_bytes(b);row['saved_file']=name
        except requests.RequestException as exc:row.update(error_type=type(exc).__name__,error=str(exc))
        return row
    with ThreadPoolExecutor(max_workers=3) as pool:attempts=list(pool.map(fetch,urls))
    write_json(dest/'fontes.json',dict(previous_manifest_sha256=sha256(previous/'manifesto.json'),attempts=attempts,
        selection='Nenhum arquivo novo é promovido a âncora automaticamente; diretórios consultados não comprovam disponibilidade dos arquivos candidatos'))
    write_json(dest/'confianca.json',dict(version=1,anchors=[],policy='Âncoras somente por seleção explícita com impressão digital e proveniência. Nunca usar a lista TLS do sistema, um espelho ou um autoassinado implicitamente.'))
    write_json(dest/'manifesto.json',{p.name:sha256(p) for p in sorted(dest.iterdir()) if p.is_file() and p.name!='manifesto.json'})
    print(json.dumps(dict(attempts=len(attempts),http_200=sum(r.get('http_status')==200 for r in attempts),anchors_selected=0),ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',default='data');a=p.parse_args();run(a.data)
