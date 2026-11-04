"""Obtém o PDF técnico do ITI na versão conferida, sem substituir cópias diferentes."""
import argparse,hashlib
from pathlib import Path
from datetime import datetime,timezone
import requests
from eleicoes.sources import write_json,sha256

URL='https://www.gov.br/iti/pt-br/central-de-conteudo/doc-icp-01-01-v-4-2-padroes-e-algoritmos-criptograficos-da-icp-brasil-copy-pdf'
DIGEST='000be4d4aee6f7f4a9ac645539f8b0da889a5d93a45ff4b0c427382ca10f7ea9'
parser=argparse.ArgumentParser();parser.add_argument('--data',default='data');a=parser.parse_args()
root=Path(a.data).resolve()/'auditoria/documentacao/ed521';root.mkdir(parents=True,exist_ok=True)
path=root/'doc-icp-01-01-v4-2.pdf'
if path.exists():
    if sha256(path)!=DIGEST:raise ValueError('PDF local diferente; preservar e escolher outra pasta --data')
else:
    with requests.get(URL,stream=True,timeout=60) as response:
        response.raise_for_status();content=response.raw.read(2*1024*1024+1)
    if len(content)>2*1024*1024 or not content.startswith(b'%PDF') or hashlib.sha256(content).hexdigest()!=DIGEST:raise ValueError('Documento remoto difere da versão técnica conferida')
    path.write_bytes(content)
    write_json(root/'origem.json',dict(url=URL,obtained_at=datetime.now(timezone.utc).isoformat(),sha256=DIGEST,bytes=len(content)))
print('Documento técnico do ITI conferido por SHA256; versão 4.2, referência técnica do perfil, sem afirmação de vigência normativa.')
