"""Valida a entrega amostral sem refazer downloads e sem promover limites a conclusões."""
import argparse
import json
import subprocess
import sys
import zlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse,unquote
import duckdb
from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv


class Page(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.cases=[];self.ids=[];self.script='';self.in_script=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'href' in a:self.links.append(a['href'])
        if 'id' in a:self.ids.append(a['id'])
        if tag=='article':self.cases.append(dict(uf=a['data-uf'],group=a['data-group']))
        if tag=='script':self.in_script=True
    def handle_endtag(self,tag):
        if tag=='script':self.in_script=False
    def handle_data(self,data):
        if self.in_script:self.script+=data


def validate(folder,data='data'):
    folder=Path(folder).resolve();data=Path(data).resolve();root=Path(__file__).resolve().parents[1]
    audit=folder/'auditoria';con=duckdb.connect();result={};pairs=[]
    try:
        for stage in ('amostra','documentos','conferencia','relatorio'):
            path=audit/stage;manifest=json.loads((path/'manifesto.json').read_text(encoding='utf8'))
            for name,digest in manifest.items():assert sha256(path/name)==digest,(stage,name)
            summary=json.loads((path/'resumo.json').read_text(encoding='utf8'))
            for name,digest in summary['input_hashes'].items():assert sha256(folder/name)==digest,('entrada alterada',name)
            assert summary['preservation_verified']
            for file in path.glob('*.parquet'):
                columns={r[0]:r[1] for r in con.execute('DESCRIBE SELECT * FROM read_parquet(?)',[str(file)]).fetchall()}
                read_export_csv(con,file.with_suffix('.csv'),columns=columns).create_view('csv_checked',replace=True)
                con.read_parquet(str(file)).create_view('parquet_checked',replace=True)
                assert con.sql('SELECT count(*) FROM ((SELECT * FROM csv_checked EXCEPT ALL SELECT * FROM parquet_checked) UNION ALL (SELECT * FROM parquet_checked EXCEPT ALL SELECT * FROM csv_checked))').fetchall()[0][0]==0,file.name
                pairs.append(str(file.relative_to(folder)))
        sample=con.read_parquet(str(audit/'amostra/secoes.parquet')).df()
        turns=con.read_parquet(str(audit/'amostra/turnos.parquet')).df()
        inventory=con.read_parquet(str(audit/'documentos/inventario.parquet')).df()
        votes=con.read_parquet(str(audit/'conferencia/votacao.parquet')).df()
        units=con.read_parquet(str(audit/'conferencia/unidades.parquet')).df()
        docs=con.read_parquet(str(audit/'conferencia/documentos.parquet')).df()
        assert len(sample)==24 and sample.group.eq('prioritario').sum()==12 and sample.group.eq('comparacao').sum()==12
        assert sample.region.nunique()==6 and len(turns)==48 and len(units)==48 and len(inventory)==240 and len(docs)==240
        assert sample.loc[sample.uf.eq('ZZ'),'available_configurations'].eq(2).all()
        for _,pair in sample.groupby('pair_id'):
            assert len(pair)==2 and pair.uf.nunique()==1
            assert pair.loc[pair.group.eq('comparacao'),'alert_configurations'].eq(0).all()
        geo=['year','turn','uf','municipality','zone','section']
        expected=set(turns[geo].itertuples(index=False,name=None))
        assert expected==set(units[geo].itertuples(index=False,name=None))
        assert not votes.duplicated(geo+['candidate']).any() and not docs.duplicated(geo+['kind']).any()
        assert len(votes)==265 and votes.status.eq('concordante').all() and votes.comparison_complete.all()
        assert units.sum_matches_attendance.all() and units.denominators_match.all()
        assert votes[['rdv_votes','binary_bu_votes','image_votes','result_votes','csv_bu_votes']].nunique(axis=1).eq(1).all()
        catalog=json.loads((audit/'documentos/resumo.json').read_text(encoding='utf8'))['catalog']
        assert sha256(data/catalog['path'])==catalog['sha256']
        for row in inventory.to_dict('records'):
            assert row['status']=='obtido'
            path=(data/row['path']).resolve();assert path.is_relative_to(data)
            assert sha256(path)==row['sha256'] and path.stat().st_size==row['size']
            assert f'{zlib.crc32(path.read_bytes()):08x}'==row['crc32']
        assert docs.loc[docs.kind.eq('assinatura'),'status'].eq('limitado').all()
        assert docs.loc[docs.kind.eq('log'),'status'].eq('preservado').all()
        summary=json.loads((audit/'relatorio/resumo.json').read_text(encoding='utf8'))
        assert summary['cryptographic_signatures_verified']==0 and summary['signature_verification_status']!='válidas'
        assert summary['log_events_examined']==0 and summary['independent_paper_bu_obtained']==0
        assert summary['concordant_rows']==len(votes) and summary['concordant_units']==len(units)
        path=audit/'relatorio/relatorio.html';page=Page();page.feed(path.read_text(encoding='utf8'))
        assert len(page.cases)==24 and len(page.ids)==len(set(page.ids))
        for link in page.links:
            url=urlparse(link)
            if not url.scheme:
                target=path.parent/unquote(url.path) if url.path else path
                assert target.is_file(),link
                if url.fragment and not url.path:assert url.fragment in page.ids
        interface=subprocess.run(['node',str(Path(__file__).with_suffix('.cjs'))],input=json.dumps(dict(cases=page.cases,script=page.script)),text=True,capture_output=True,check=True)
        result['interface']=json.loads(interface.stdout)
        try:import pymupdf
        except ImportError:
            sys.path.insert(0,str(root/'outputs/publicacao/pdfqa'));import pymupdf
        with pymupdf.open(audit/'relatorio/relatorio.pdf') as pdf:
            texts=[p.get_text() for p in pdf];combined=' '.join('\n'.join(texts).split())
            assert all(len(t)>200 for t in texts)
            assert '265' in combined and '48' in combined and 'assinaturas' in combined.lower()
            assert 'não foram validadas' in combined and 'não constitui auditoria integral' in combined
            assert len(pdf.get_toc())>=3
            for p in pdf:
                for x0,y0,x1,y1,*_ in p.get_text('blocks'):
                    assert x0>=36 and x1<=p.rect.width-35 and y0>=18 and y1<=p.rect.height-20,(p.number,(x0,y0,x1,y1))
            result['pdf']=dict(pages=len(pdf),bookmarks=len(pdf.get_toc()),geometry='conteúdo dentro das margens')
        result.update(status='válido',csv_parquet_pairs=len(pairs),files=pairs,raw_files_verified=len(inventory),sections=len(sample),section_turns=len(units),vote_rows=len(votes),signature_status='não verificada; leitura limitada',reference='hashes das entradas preservados')
        return result
    finally:con.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='outputs/2026');parser.add_argument('--data',default='data');args=parser.parse_args()
    print(json.dumps(validate(args.output,args.data),ensure_ascii=False,indent=2))
