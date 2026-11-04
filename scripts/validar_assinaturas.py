"""Validação local da leitura observada e do alcance das verificações criptográficas."""
import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import urlparse
import duckdb
from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv
from eleicoes.audit_signature import parse_vsc,certificate,verify_signature


class Page(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='a' and a.get('href'):self.links.append(a['href'])


def validate(source,data):
    source=Path(source).resolve();data=Path(data).resolve();dest=source/'auditoria/assinaturas';con=duckdb.connect()
    try:
        summary=json.loads((dest/'resumo.json').read_text(encoding='utf8'))
        manifest=json.loads((dest/'manifesto.json').read_text(encoding='utf8'))
        for name,digest in manifest.items():assert sha256(dest/name)==digest,name
        for name,digest in summary['input_hashes'].items():assert sha256(source/name)==digest,name
        for name,digest in summary['code_hashes'].items():assert sha256(source.parents[1]/'src/eleicoes'/name)==digest,name
        pairs=[]
        for path in dest.glob('*.parquet'):
            cols={r[0]:r[1] for r in con.execute('DESCRIBE SELECT * FROM read_parquet(?)',[str(path)]).fetchall()}
            read_export_csv(con,path.with_suffix('.csv'),columns=cols).create_view('csv_checked',replace=True)
            con.read_parquet(str(path)).create_view('parquet_checked',replace=True)
            assert con.sql('SELECT count(*) FROM ((SELECT * FROM csv_checked EXCEPT ALL SELECT * FROM parquet_checked) UNION ALL (SELECT * FROM parquet_checked EXCEPT ALL SELECT * FROM csv_checked))').fetchall()[0][0]==0,path.name
            pairs.append(path.stem)
        files=con.read_parquet(str(dest/'arquivos_assinados.parquet')).df();env=con.read_parquet(str(dest/'envelopes.parquet')).df()
        certs=con.read_parquet(str(dest/'certificados.parquet')).df();units=con.read_parquet(str(dest/'unidades.parquet')).df()
        geo=['year','turn','uf','municipality','zone','section'];selected=files.loc[files.scope.eq('documento_obtido')]
        assert len(units)==48 and units.status.eq('lido').all() and not units.duplicated(geo).any()
        assert units.selected_documents.eq(4).all() and units.sw_hw_digest_differences.eq(0).all()
        assert len(env)==96 and not env.duplicated(geo+['role']).any() and env.hash_status.eq('concordante').all()
        assert len(files)==1008 and len(selected)==384 and selected.hash_status.eq('concordante').all()
        assert not files.duplicated(geo+['role','member']).any()
        assert files.loc[files.scope.ne('documento_obtido'),'hash_status'].eq('fora_do_escopo').all()
        assert selected.crypto_status.eq('valida_com_chave_embutida').sum()==56
        assert env.crypto_status.eq('valida_com_chave_embutida').sum()==14
        assert env.loc[env.role.eq('hw') & env.algorithm.eq(4),'crypto_status'].eq('nao_verificado_algoritmo').all()
        assert env.loc[env.role.eq('sw'),'crypto_status'].eq('nao_verificado_algoritmo').all()
        assert len(certs)==48 and certs.chain_status.eq('nao_validada').all() and certs.revocation_status.eq('nao_consultada').all()
        assert certs.time_status.eq('compativel_em_todos_os_fusos_considerados').all()
        inventory=con.read_parquet(str(source/'auditoria/documentos/inventario.parquet')).df()
        rechecked=0
        for row in inventory.loc[inventory.kind.eq('assinatura')].to_dict('records'):
            raw=(data/row['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==row['sha256']
            obj=parse_vsc(raw);cert,info=certificate(obj['hw']['certificate'])
            case=certs
            for k in geo:case=case.loc[case[k].eq(row[k])]
            assert len(case)==1 and case.iloc[0].sha256==info['sha256']
            if obj['platform']['algorithm']==2:
                dig=obj['hw']['auto']['signature']
                assert verify_signature(cert,2,dig['hash'],dig['signature'])[0]=='valida_com_chave_embutida'
                rechecked+=1
        assert rechecked==14
        page=Page();page.feed((dest/'relatorio.html').read_text(encoding='utf8'))
        local_links=0
        for link in page.links:
            u=urlparse(link)
            if not u.scheme and u.path:assert (dest/u.path).is_file(),link;local_links+=1
        try:import pymupdf
        except ImportError:
            sys.path.insert(0,str(source.parents[1]/'outputs/publicacao/pdfqa'));import pymupdf
        with pymupdf.open(dest/'relatorio.pdf') as pdf:
            texts=[p.get_text() for p in pdf];text=' '.join(' '.join(texts).split())
            assert all(len(t)>150 for t in texts)
            for value in ('384','192','96','14','34','56','Ed521','CEPESC'):assert value in text,value
            assert 'cadeia' in text.lower() and 'não foram validadas' in text and 'não foi localizada uma especificação oficial' in text
            for page in pdf:
                for x0,y0,x1,y1,*_ in page.get_text('blocks'):
                    assert x0>=36 and x1<=page.rect.width-35 and y0>=18 and y1<=page.rect.height-20,(page.number,(x0,y0,x1,y1))
            pdf_info=dict(pages=len(pdf),bookmarks=len(pdf.get_toc()),geometry='dentro das margens')
        return dict(status='válido',csv_parquet_pairs=len(pairs),section_turns=48,listed_entries=1008,selected_file_checks=384,
            internal_hash_checks=96,ecdsa_checks=70,ecdsa_list_signatures_rechecked=rechecked,
            ed521_units_not_verified=34,cepesc_units_not_verified=48,chain_status='não validada',local_links=local_links,pdf=pdf_info,
            prior_inputs='hashes preservados')
    finally:con.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='outputs/2026');p.add_argument('--data',default='data');a=p.parse_args()
    print(json.dumps(validate(a.output,a.data),ensure_ascii=False,indent=2))
