"""Confere produção Ed521, referência independente e preservação das entregas."""
import argparse,json,sys
from pathlib import Path
from urllib.parse import urlparse
import duckdb
from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv
from eleicoes.ed521_reference import reference_metadata
from validar_assinaturas import Page


def validate(source,data):
    source=Path(source).resolve();data=Path(data).resolve();root=Path(__file__).resolve().parents[1];con=duckdb.connect();pairs=[]
    try:
        for stage in ('ed521','ed521_referencia'):
            dest=source/'auditoria'/stage
            summary=json.loads((dest/'resumo.json').read_text(encoding='utf8'))
            manifest=json.loads((dest/'manifesto.json').read_text(encoding='utf8'))
            for name,digest in manifest.items():assert sha256(dest/name)==digest,(stage,name)
            for name,digest in summary['input_hashes'].items():assert sha256(source/name)==digest,name
            for path in dest.glob('*.parquet'):
                cols={r[0]:r[1] for r in con.execute('DESCRIBE SELECT * FROM read_parquet(?)',[str(path)]).fetchall()}
                read_export_csv(con,path.with_suffix('.csv'),columns=cols).create_view('csv_checked',replace=True)
                con.read_parquet(str(path)).create_view('parquet_checked',replace=True)
                assert con.sql('SELECT count(*) FROM ((SELECT * FROM csv_checked EXCEPT ALL SELECT * FROM parquet_checked) UNION ALL (SELECT * FROM parquet_checked EXCEPT ALL SELECT * FROM csv_checked))').fetchall()[0][0]==0,path.name
                pairs.append(stage+'/'+path.stem)
        dest=source/'auditoria/ed521';read=lambda n:con.read_parquet(str(dest/(n+'.parquet'))).df()
        files=read('arquivos_assinados');env=read('envelopes');certs=read('certificados');units=read('unidades');selected=files.loc[files.scope.eq('documento_obtido')]
        assert len(units)==48 and units.status.eq('lido').all()
        assert len(files)==1008 and len(selected)==384 and selected.hash_status.eq('concordante').all()
        assert len(env)==96 and env.hash_status.eq('concordante').all()
        assert selected.loc[selected.role.eq('hw'),'crypto_status'].eq('valida_com_chave_embutida').all()
        assert env.loc[env.role.eq('hw'),'crypto_status'].eq('valida_com_chave_embutida').all()
        assert selected.loc[selected.role.eq('hw')&selected.algorithm.eq(4)].shape[0]==136
        assert env.loc[env.role.eq('hw')&env.algorithm.eq(4)].shape[0]==34
        assert env.loc[env.role.eq('sw'),'crypto_status'].eq('nao_verificado_algoritmo').all()
        assert certs.chain_status.eq('nao_validada').all() and certs.revocation_status.eq('nao_consultada').all()
        # As mesmas entradas e valores; somente a verificação Ed521 foi ampliada.
        for name in ('arquivos_assinados','envelopes','certificados','unidades'):
            previous=source/'auditoria/assinaturas'/(name+'.parquet');current=dest/(name+'.parquet')
            columns=[r[0] for r in con.execute('DESCRIBE SELECT * FROM read_parquet(?)',[str(current)]).fetchall() if r[0] not in ('crypto_status','crypto_reason')]
            fields=','.join('"'+c+'"' for c in columns)
            bad=con.execute(f'SELECT count(*) FROM ((SELECT {fields} FROM read_parquet(?) EXCEPT ALL SELECT {fields} FROM read_parquet(?)) UNION ALL (SELECT {fields} FROM read_parquet(?) EXCEPT ALL SELECT {fields} FROM read_parquet(?)))',[str(previous),str(current),str(current),str(previous)]).fetchall()[0][0]
            assert bad==0,name
        for stage in ('amostra','documentos','conferencia','relatorio','assinaturas'):
            path=source/'auditoria'/stage
            for name,digest in json.loads((path/'manifesto.json').read_text(encoding='utf8')).items():assert sha256(path/name)==digest,(stage,name)
        cross=con.read_parquet(str(source/'auditoria/ed521_referencia/comparacao.parquet')).df()
        assert len(cross)==340 and cross.agreement.all() and cross.expected_result.all()
        assert cross.mutation.eq('original').sum()==170 and cross.mutation.eq('mensagem_alterada').sum()==170
        reference=json.loads((source/'auditoria/ed521_referencia/resumo.json').read_text(encoding='utf8'))
        assert reference['policy_boundary']['expected_difference'] and reference['policy_boundary']['python_result'] is False and reference['policy_boundary']['noble_result'] is True
        metadata=reference_metadata();summary=json.loads((dest/'resumo.json').read_text(encoding='utf8'))
        assert summary['ed521_reference']==metadata and metadata['vectors']==12
        assert sha256(data/'auditoria/documentacao/ed521/doc-icp-01-01-v4-2.pdf')==metadata['source_pdf_sha256']
        page=Page();page.feed((dest/'relatorio.html').read_text(encoding='utf8'));local_links=0
        for link in page.links:
            url=urlparse(link)
            if not url.scheme and url.path:assert (dest/url.path).is_file(),link;local_links+=1
        try:import pymupdf
        except ImportError:
            sys.path.insert(0,str(root/'outputs/publicacao/pdfqa'));import pymupdf
        with pymupdf.open(dest/'relatorio.pdf') as pdf:
            text=' '.join(' '.join(p.get_text() for p in pdf).split())
            for value in ('170','34','136','70','240','Ed521','CEPESC','não foram validadas','não são vetores oficiais'):assert value in text,value
            for p in pdf:
                assert len(p.get_text())>150
                for x0,y0,x1,y1,*_ in p.get_text('blocks'):assert x0>=36 and x1<=p.rect.width-35 and y0>=18 and y1<=p.rect.height-20,(p.number,(x0,y0,x1,y1))
            pdfinfo=dict(pages=len(pdf),bookmarks=len(pdf.get_toc()),geometry='dentro das margens')
        return dict(status='válido',csv_parquet_pairs=len(pairs),section_turns=48,ed521_checks=170,ecdsa_checks=70,
            independent_originals=170,independent_mutations=170,expected_policy_boundary_difference=True,
            official_source_pdf_sha256=metadata['source_pdf_sha256'],vectors=12,vectors_authority='gerados pelo projeto com referência independente; não oficiais',
            local_links=local_links,pdf=pdfinfo,previous_stages='cinco manifestos e seus artefatos preservados',trust_chain='não validada')
    finally:con.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='outputs/2026');p.add_argument('--data',default='data');a=p.parse_args()
    print(json.dumps(validate(a.output,a.data),ensure_ascii=False,indent=2))
