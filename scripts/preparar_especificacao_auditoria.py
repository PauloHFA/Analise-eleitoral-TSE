"""Preserva apenas os esquemas ASN.1 de um espelho, com origem e limites explícitos."""
import argparse
import hashlib
import io
import zipfile
from pathlib import Path
from datetime import datetime,timezone
import requests
from eleicoes.sources import write_json,sha256
from eleicoes.audit_count import SCHEMA_HASHES

URL='https://raw.githubusercontent.com/doccaz/urnas-br/main/docv2/formato-arquivos-bu-rdv-ass-digital-v2.zip'
DIGEST='1e423054f32b8ba056960c58ada167d702c2618cc4d1dfd5de88f5090c84a235'
parser=argparse.ArgumentParser();parser.add_argument('--data',default='data');args=parser.parse_args()
root=Path(args.data).resolve()/'auditoria/documentacao';root.mkdir(parents=True,exist_ok=True)
archive=root/'formato-v2-mirror-1e423054f32b8ba0.zip'
if not archive.exists():
    r=requests.get(URL,timeout=60);r.raise_for_status()
    if hashlib.sha256(r.content).hexdigest()!=DIGEST:raise ValueError('Espelho difere da versão revisada')
    archive.write_bytes(r.content)
if sha256(archive)!=DIGEST:raise ValueError('Pacote local alterado')
target=root/'spec-v2';target.mkdir(exist_ok=True)
with zipfile.ZipFile(archive) as z:
    for name,digest in SCHEMA_HASHES.items():
        content=z.read('spec/'+name+'.asn1')
        if hashlib.sha256(content).hexdigest()!=digest:raise ValueError('Esquema diferente da versão revisada')
        p=target/(name+'.asn1')
        if p.exists() and p.read_bytes()!=content:raise ValueError('Não substituir especificação diferente')
        if not p.exists():p.write_bytes(content)
metadata=root/'proveniencia_esquemas.json'
if not metadata.exists():write_json(metadata,dict(url=URL,archive_sha256=DIGEST,schemas=SCHEMA_HASHES,
    registered_at=datetime.now(timezone.utc).isoformat(),origin='Espelho de terceiros de pacote atribuído ao TSE; não é obtenção direta autenticada do TSE',
    limitation='O download direto consultado no TSE retornou HTTP 403. Esquemas conferidos por hash; incompatibilidades são limitações de leitura. Nenhum código do espelho é executado.'))
print('Três esquemas preservados e conferidos por SHA256; origem em espelho explicitada.')
