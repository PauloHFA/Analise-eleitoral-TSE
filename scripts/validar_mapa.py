import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess

import duckdb

from eleicoes.electoral_map import winner_color
from eleicoes.sources import sha256
from validar_investigacao import Scripts


class MapHTML(Scripts):
    def __init__(self):
        super().__init__()
        self.codes=[]
        self.circles=[]

    def handle_starttag(self,tag,attrs):
        super().handle_starttag(tag,attrs)
        attrs=dict(attrs)
        if 'data-code' in attrs:
            if tag=='path':
                assert attrs.get('d','').startswith('M')
                self.codes.append(attrs['data-code'])
            elif tag=='circle':
                self.circles.append(attrs['data-code'])


def validate_map(folder):
    root=Path(folder)
    payload=json.loads((root/'mapa_dados.json').read_text(encoding='utf-8'))
    summary,features=payload['summary'],payload['features']
    assert sha256(root/'indicadores_municipio.parquet')==summary['results_sha256']
    assert len(features)==summary['mapped']
    assert len({r['ibge_code'] for r in features})==len(features)
    assert len({(r['uf'],r['municipality']) for r in features})==len(features)
    assert all(all(math.isfinite(v) for v in r['bounds']) and r['bounds'][2]>0 and r['bounds'][3]>0 for r in features)
    con=duckdb.connect()
    columns=[f'votes_{c}_{t}' for c in (13,22) for t in (1,2)]
    original={(r[0],r[1]):r[2:] for r in con.execute("SELECT uf,municipality,"+','.join(columns)+" FROM read_parquet(?) WHERE uf<>'ZZ'",[str(root/'indicadores_municipio.parquet')]).fetchall()}
    for feature in features:
        assert tuple(feature[c] for c in columns)==original[(feature['uf'],feature['municipality'])], 'Votação municipal trocada no mapa'
    for column in columns:
        expected=con.execute(f"SELECT sum({column}) FROM read_parquet(?) WHERE uf<>'ZZ'",[str(root/'indicadores_municipio.parquet')]).fetchone()[0]
        assert sum(r[column] for r in features)==expected, 'Votos ausentes ou duplicados no mapa: '+column
    con.close()
    parser=MapHTML();parser.feed((root/'mapa_eleitoral.html').read_text(encoding='utf-8'))
    data=next(s for s in parser.scripts if s.get('id')=='map-data')
    script=next(s for s in parser.scripts if "const data=JSON.parse(document.getElementById('map-data')" in s['text'])
    assert set(parser.codes)=={r['ibge_code'] for r in features}
    assert len(parser.codes)==len(features)
    for scope in ('br','rj','mg'):
        assert (root/'graficos'/f'mapa_{scope}.png').read_bytes().startswith(b'\x89PNG')
    colors={str(t):{r['ibge_code']:winner_color(r[f'votes_22_{t}'],r[f'votes_13_{t}']) for r in features} for t in (1,2)}
    node=shutil.which('node')
    result={'status':'Node ausente; teste interativo não executado'}
    if node:
        run=subprocess.run([node,str(Path(__file__).with_suffix('.cjs'))],input=json.dumps(dict(ids=parser.ids,codes=parser.codes,circles=parser.circles,data=json.loads(data['text']),script=script['text'],colors=colors),ensure_ascii=False),encoding='utf-8',capture_output=True,check=True,timeout=40)
        result=json.loads(run.stdout)
    return dict(status='mapa válido',mapped=len(features),total=summary['electoral_municipalities'],votes_reconciled=True,interactive=result)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',nargs='?',default='outputs/2026')
    print(json.dumps(validate_map(parser.parse_args().folder),ensure_ascii=False,indent=2))
