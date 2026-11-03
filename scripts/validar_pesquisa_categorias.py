"""Conferência da pesquisa revisada e dos artefatos; não certifica causa jurídica."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlparse

import duckdb

from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        self.links.extend(v for k,v in attrs if k=='href')


def validate(source,destination=None):
    source=Path(source).resolve()
    folder=Path(destination).resolve() if destination else source/'pesquisa_categorias'
    root=Path(__file__).resolve().parents[1]
    def read(path):
        return json.loads(Path(path).read_text(encoding='utf-8'),parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))
    summary=read(folder/'resumo.json')
    state=read(folder/'estado_execucao.json')
    assert summary['status']==state['status']=='concluído'
    assert summary['preservation_verified']
    for name,digest in summary['input_hashes'].items():assert sha256(name)==digest,name
    for name,digest in read(folder/'manifesto.json').items():assert sha256(folder/name)==digest,name
    assert sha256(root/'src/eleicoes/research.py')==summary['code_hash']
    sources=read(folder/'fontes.json')
    candidate=read(folder/'candidatura.json')
    assert candidate['candidate']['id']==280002554479
    assert candidate['candidate']['cargo']['codigo']==1
    assert candidate['candidate']['descricaoSituacao']=='Renúncia'
    sensitive={'cpf','tituloEleitor','bens','emails','fotoUrl','interactiveLiveViewUrl','liveViewUrl','cdpUrl'}
    def no_sensitive(obj):
        if isinstance(obj,dict):
            assert not sensitive.intersection(obj)
            for value in obj.values():no_sensitive(value)
        elif isinstance(obj,list):
            for value in obj:no_sensitive(value)
    for path in folder.glob('*.json'):no_sensitive(read(path))
    assert candidate['source_capture_sha256']==next(s['capture_sha256'] for s in sources if s['id']=='cadastro')
    checked_captures=0
    for entry in sources:
        path=(root/entry['archive_local']).resolve()
        assert path.is_relative_to(root/'data/documentacao')
        if path.exists():
            assert sha256(path)==entry['capture_sha256']
            checked_captures+=1
        assert not entry['original_binary_obtained']
    con=duckdb.connect()
    try:
        expected=con.read_parquet(str(folder/'unidades.parquet'))
        expected.create_view('units')
        schema={name:str(t) for name,t in zip(expected.columns,expected.types)}
        read_export_csv(con,folder/'unidades.csv',columns=schema).create_view('actual')
        for a,b in (('units','actual'),('actual','units')):
            assert con.execute(f'SELECT count(*) FROM (SELECT * FROM {a} EXCEPT ALL SELECT * FROM {b})').fetchall()[0][0]==0
        count,votes=con.execute('SELECT count(*),sum(technical_votes) FROM units').fetchall()[0]
        assert count==summary['technical_units']==2148 and votes==summary['technical_votes']==5246
        assert con.execute("SELECT count(*) FROM units WHERE cause_confirmed OR candidate<>28 OR candidate_id<>280002554479 OR primary_act_status<>'não obtido nesta pesquisa'").fetchall()[0][0]==0
        con.read_parquet(str(source/'dossie_categorias/unidades.parquet')).create_view('reference')
        assert con.execute('''SELECT count(*) FROM (SELECT year,turn,uf,municipality,zone,technical_votes FROM units
            EXCEPT ALL SELECT year,turn,uf,municipality,zone,official_null_technical FROM reference WHERE technical_arithmetic_match)''').fetchall()[0][0]==0
        assert not summary['assessment']['cause_confirmed'] and not summary['primary_act_obtained']
        assert summary['assessment']['persistence_status']=='não avaliada nesta pesquisa'
        page=(folder/'relatorio.html').read_text(encoding='utf-8')
        links=Links();links.feed(page)
        for link in links.links:
            parsed=urlparse(link)
            if not parsed.scheme and parsed.path:assert (folder/parsed.path).is_file(),link
        assert (folder/'relatorio.pdf').read_bytes().startswith(b'%PDF')
        return dict(status='válido',units=count,votes=votes,typed_csv_parquet='EXCEPT ALL nos dois sentidos',
            sources=len(sources),local_captures_verified=checked_captures,links=len(links.links),
            cause_confirmed=False,primary_act_status=summary['assessment']['primary_act_status'],
            preservation='entradas e artefatos conferidos por SHA256')
    finally:con.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='outputs/2026')
    parser.add_argument('--dest')
    args=parser.parse_args()
    print(json.dumps(validate(args.output,args.dest),ensure_ascii=False,indent=2))
