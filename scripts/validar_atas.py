"""Confere cobertura da pesquisa, fichas, minutas, confronto e preservação."""
import argparse,json,sys,subprocess
from pathlib import Path
from urllib.parse import urlparse
import duckdb
from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv
from eleicoes.audit_atas import key
from validar_assinaturas import Page


def validate(source,data):
    source,data=Path(source).resolve(),Path(data).resolve();root=Path(__file__).resolve().parents[1]
    dest=source/'auditoria/atas';raw=data/'auditoria/atas/v1';summary=json.loads((dest/'resumo.json').read_text(encoding='utf8'))
    for name,digest in json.loads((dest/'manifesto.json').read_text(encoding='utf8')).items():assert sha256(dest/name)==digest,name
    for name,digest in summary['input_hashes'].items():assert sha256(source/name)==digest,name
    for name,digest in summary['code_hashes'].items():assert sha256(root/'src/eleicoes'/name)==digest,name
    assert sha256(raw/'manifesto.json')==summary['capture_manifest_sha256']
    for name,digest in summary['capture_hashes'].items():assert sha256(raw/name)==digest,name
    for name,digest in json.loads((dest/'manifesto_fichas.json').read_text(encoding='utf8')).items():assert sha256(dest/name)==digest,name
    con=duckdb.connect();pairs=[]
    try:
        for path in sorted(dest.glob('*.parquet')):
            types={r[0]:r[1] for r in con.execute('DESCRIBE SELECT * FROM read_parquet(?)',[str(path)]).fetchall()}
            read_export_csv(con,path.with_suffix('.csv'),columns=types).create_view('csv_checked',replace=True)
            con.read_parquet(str(path)).create_view('parquet_checked',replace=True)
            assert con.sql('SELECT count(*) FROM ((SELECT * FROM csv_checked EXCEPT ALL SELECT * FROM parquet_checked) UNION ALL (SELECT * FROM parquet_checked EXCEPT ALL SELECT * FROM csv_checked))').fetchall()[0][0]==0,path.name
            pairs.append(path.stem)
        assert pairs==['buscas','casos','confronto','documentos_necessarios','fontes','resultados_busca']
        cases,issues,queries,needs,sources,results=[con.read_parquet(str(dest/(name+'.parquet'))).df() for name in ('casos','confronto','buscas','documentos_necessarios','fontes','resultados_busca')]
        assert (len(cases),len(issues),len(queries),len(needs),len(sources),len(results))==(28,33,6,56,12,18)
        assert not cases.case_id.duplicated().any() and needs.groupby('case_id').size().eq(2).all()
        assert cases.individual_searches.gt(0).sum()==6 and cases.individual_searches.eq(0).sum()==22
        assert cases.priority.eq('inicial').sum()==6
        assert {key(r) for r in queries.to_dict('records')}=={key(r) for r in cases.loc[cases.priority.eq('inicial')].to_dict('records')}
        assert cases.document_status.eq('sem_confronto_especifico_concluido').all()
        assert issues.document_status.eq('sem_documento_especifico').all()
        assert issues.cause_status.eq('nao_confirmada_por_esta_rotina').all() and summary['causes_confirmed'] is None
        assert summary['specific_evidence_entries']==0 and summary['requests_sent']==0
        assert not sources.specific_document.any() and queries.specific_documents_obtained.eq(0).all()
        original=con.read_parquet(str(source/'auditoria/logs/pendencias.parquet')).df()
        cols=original.columns.tolist();con.register('original_issues',original);con.register('dossier_issues',issues[cols])
        assert con.sql('SELECT count(*) FROM ((SELECT * FROM original_issues EXCEPT ALL SELECT * FROM dossier_issues) UNION ALL (SELECT * FROM dossier_issues EXCEPT ALL SELECT * FROM original_issues))').fetchall()[0][0]==0
        files=[]
        for case in cases.to_dict('records'):
            card=dest/case['card'];draft=dest/case['request_draft'];assert card.is_file() and draft.is_file()
            text=draft.read_text(encoding='utf8');assert 'MINUTA LOCAL — NÃO ENVIADA' in text and 'Nenhum pedido foi enviado' in text
            for value in (str(case['year']),str(case['turn'])+'º turno',case['municipality_name_1']):assert value in text
            files.append(card)
        assert len(list((dest/'fichas').glob('*.html')))==28 and len(list((dest/'minutas').glob('*.txt')))==28
    finally:con.close()
    previous=('amostra','documentos','conferencia','relatorio','assinaturas','ed521','ed521_referencia','cadeia','caminho_pkix','logs')
    for stage in previous:
        folder=source/'auditoria'/stage
        for name,digest in json.loads((folder/'manifesto.json').read_text(encoding='utf8')).items():assert sha256(folder/name)==digest,(stage,name)
    files.append(dest/'relatorio.html');links=0
    for path in files:
        page=Page();page.feed(path.read_text(encoding='utf8'))
        for link in page.links:
            u=urlparse(link)
            if not u.scheme and u.path:assert (path.parent/u.path).is_file(),link;links+=1
    filters=json.loads(subprocess.run(['node',str(root/'scripts/validar_atas.cjs'),str(dest/'relatorio.html')],capture_output=True,text=True,encoding='utf8',check=True).stdout)
    try:import pymupdf
    except ImportError:
        sys.path.insert(0,str(root/'outputs/publicacao/pdfqa'));import pymupdf
    with pymupdf.open(dest/'relatorio.pdf') as pdf:
        content=' '.join(' '.join(p.get_text() for p in pdf).split())
        for value in ('28','33','22','56','60','primeiro turno','Nenhum','não'):assert value in content,value
        for p in pdf:
            assert len(p.get_text())>150
            for x0,y0,x1,y1,*_ in p.get_text('blocks'):assert x0>=36 and x1<=p.rect.width-35 and y0>=18 and y1<=p.rect.height-20,(p.number,(x0,y0,x1,y1))
        pdf_info=dict(pages=len(pdf),bookmarks=len(pdf.get_toc()),geometry='dentro das margens')
    return dict(status='válido',csv_parquet_pairs=len(pairs),issue_rows=33,section_turns=28,individual_searches=6,
        units_without_individual_search=22,specific_evidence_entries=0,request_drafts=28,requests_sent=0,
        cards=28,previous_stage_manifests_preserved=len(previous),local_links=links,filters=filters,pdf=pdf_info)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='outputs/2026');p.add_argument('--data',default='data');a=p.parse_args()
    print(json.dumps(validate(a.output,a.data),ensure_ascii=False,indent=2))
