"""Valida o alcance da conferência de vínculos e preserva resultados anteriores."""
import argparse,json,sys
from pathlib import Path
from urllib.parse import urlparse
import duckdb
from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv
from eleicoes.audit_signature import certificate,parse_vsc
from eleicoes.certificate_chain import issuer_binding
from validar_assinaturas import Page


def validate(source,data):
    source=Path(source).resolve();data=Path(data).resolve();root=Path(__file__).resolve().parents[1];dest=source/'auditoria/cadeia';raw=data/'auditoria/cadeia/v1';con=duckdb.connect();pairs=[]
    try:
        summary=json.loads((dest/'resumo.json').read_text(encoding='utf8'))
        for name,digest in json.loads((dest/'manifesto.json').read_text(encoding='utf8')).items():assert sha256(dest/name)==digest,name
        for name,digest in summary['input_hashes'].items():assert sha256(source/name)==digest,name
        assert sha256(raw/'manifesto.json')==summary['source_manifest_sha256']
        for name,digest in summary['sources_hashes'].items():assert sha256(raw/name)==digest,name
        for name,digest in summary['code_hashes'].items():assert sha256(root/'src/eleicoes'/name)==digest,name
        for path in dest.glob('*.parquet'):
            cols={r[0]:r[1] for r in con.execute('DESCRIBE SELECT * FROM read_parquet(?)',[str(path)]).fetchall()}
            read_export_csv(con,path.with_suffix('.csv'),columns=cols).create_view('csv_checked',replace=True)
            con.read_parquet(str(path)).create_view('parquet_checked',replace=True)
            assert con.sql('SELECT count(*) FROM ((SELECT * FROM csv_checked EXCEPT ALL SELECT * FROM parquet_checked) UNION ALL (SELECT * FROM parquet_checked EXCEPT ALL SELECT * FROM csv_checked))').fetchall()[0][0]==0,path.name
            pairs.append(path.stem)
        links=con.read_parquet(str(dest/'vinculos.parquet')).df();pending=con.read_parquet(str(dest/'pendencias_vigencia.parquet')).df();cas=con.read_parquet(str(dest/'intermediarios.parquet')).df();attempts=con.read_parquet(str(dest/'tentativas.parquet')).df()
        geo=['year','turn','uf','municipality','zone','section']
        assert len(links)==48 and not links.duplicated(geo).any() and links.leaf_sha256.nunique()==25
        assert links.signature_status.eq('confere_com_candidato').all() and links.aki_ski_match.all()
        assert links.ca_basic_constraint.all() and links.ca_key_cert_sign.all() and not links.aia_present.any()
        assert links.issuer_time_status.eq('compativel_em_todos_os_fusos_considerados').sum()==34
        assert links.issuer_time_status.eq('fora_do_intervalo_de_validade').sum()==14
        assert len(pending)==14 and pending.issuer_candidate.eq('AC URNA').all() and len(cas)==3
        assert links.path_status.eq('incompleto_sem_ancora').all() and not links.root_verified.any()
        assert links.revocation_status.eq('indeterminado_lcr_nao_obtida').all()
        assert len(attempts)==21 and attempts.http_status.eq(403).sum()==13 and attempts.error_type.eq('SSLError').sum()==8
        assert attempts.tls_verification.all() and not attempts.http_status.eq(200).any()
        provenance=json.loads((raw/'fontes.json').read_text(encoding='utf8'))
        assert provenance['anchors_trusted']==[]
        candidates={entry['name']:certificate((raw/entry['file']).read_bytes())[0] for entry in provenance['candidates']}
        inv=con.read_parquet(str(source/'auditoria/documentos/inventario.parquet')).df();rechecks=0
        for row in inv.loc[inv.kind.eq('assinatura')].to_dict('records'):
            p=(data/row['path']).resolve();assert p.is_relative_to(data) and sha256(p)==row['sha256']
            obj=parse_vsc(p.read_bytes());leaf,info=certificate(obj['hw']['certificate']);ca=candidates[info['issuer_cn']]
            result=issuer_binding(leaf,ca,obj['hw']['created']);assert result['signature_status']=='confere_com_candidato';rechecks+=1
        assert rechecks==48
        for stage in ('amostra','documentos','conferencia','relatorio','assinaturas','ed521','ed521_referencia'):
            path=source/'auditoria'/stage
            for name,digest in json.loads((path/'manifesto.json').read_text(encoding='utf8')).items():assert sha256(path/name)==digest,(stage,name)
        page=Page();page.feed((dest/'relatorio.html').read_text(encoding='utf8'));local_links=0
        for link in page.links:
            u=urlparse(link)
            if not u.scheme and u.path:assert (dest/u.path).is_file(),link;local_links+=1
        try:import pymupdf
        except ImportError:
            sys.path.insert(0,str(root/'outputs/publicacao/pdfqa'));import pymupdf
        with pymupdf.open(dest/'relatorio.pdf') as pdf:
            text=' '.join(' '.join(p.get_text() for p in pdf).split())
            for value in ('48','25','14','34','18/07/2026','indeterminadas','não equivale à validação integral'):assert value in text,value
            for p in pdf:
                assert len(p.get_text())>150
                for x0,y0,x1,y1,*_ in p.get_text('blocks'):assert x0>=36 and x1<=p.rect.width-35 and y0>=18 and y1<=p.rect.height-20,(p.number,(x0,y0,x1,y1))
            pdfinfo=dict(pages=len(pdf),bookmarks=len(pdf.get_toc()),geometry='dentro das margens')
        return dict(status='válido',csv_parquet_pairs=len(pairs),section_turns=48,unique_leaf_certificates=25,candidate_intermediates=3,
            certificate_signature_rechecks=48,issuer_time_compatible=34,issuer_time_outside=14,
            access_attempts=21,http_403=13,tls_errors=8,complete_paths_verified=0,revocation='indeterminada em 48 unidades',
            previous_stages='sete manifestos e seus artefatos preservados',local_links=local_links,pdf=pdfinfo)
    finally:con.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='outputs/2026');p.add_argument('--data',default='data');a=p.parse_args()
    print(json.dumps(validate(a.output,a.data),ensure_ascii=False,indent=2))
