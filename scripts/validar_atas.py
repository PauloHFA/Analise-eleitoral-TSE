"""Confere cobertura da pesquisa, fichas, minutas, confronto e preservação."""
import argparse,json,sys,subprocess
from pathlib import Path
from urllib.parse import urlparse
import duckdb
from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv
from eleicoes.audit_atas import key
from validar_assinaturas import Page


def validate(source,data,expanded=False,confrontation=False,destination=None):
    source,data=Path(source).resolve(),Path(data).resolve();root=Path(__file__).resolve().parents[1]
    version='v3' if confrontation else 'v2' if expanded else 'v1'
    expanded_capture=version in ('v2','v3')
    dest=Path(destination).resolve() if destination else source/({'v1':'auditoria/atas','v2':'auditoria/atas_ampliacao','v3':'auditoria/atas_confronto'}[version])
    raw=data/'auditoria/atas'/version;summary=json.loads((dest/'resumo.json').read_text(encoding='utf8'))
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
        assert pairs==['buscas','casos','confronto','documentos_necessarios','fontes','resultados_busca']+(['tentativas_busca'] if version in ('v2','v3') else [])
        cases,issues,queries,needs,sources,results=[con.read_parquet(str(dest/(name+'.parquet'))).df() for name in ('casos','confronto','buscas','documentos_necessarios','fontes','resultados_busca')]
        expected_counts=(28,33,28,56,34+summary['registered_evidence_entries'],55) if version=='v3' else (
            (28,33,28,56,34,55) if expanded_capture else (28,33,6,56,12,18))
        assert (len(cases),len(issues),len(queries),len(needs),len(sources),len(results))==expected_counts
        assert not cases.case_id.duplicated().any() and needs.groupby('case_id').size().eq(2).all()
        assert cases.individual_searches.gt(0).sum()==(28 if expanded_capture else 6) and cases.individual_searches.eq(0).sum()==(0 if expanded_capture else 22)
        assert cases.priority.eq('inicial').sum()==6
        assert {key(r) for r in queries.to_dict('records')}=={key(r) for r in cases.loc[cases.individual_searches.gt(0)].to_dict('records')}
        if version in ('v2','v3'):
            from eleicoes.atas_expansion import check_coverage,check_payload
            pending=con.read_parquet(str(source/'auditoria/atas/casos.parquet')).df().to_dict('records')
            plan=json.loads((raw/'novas/plano.json').read_text(encoding='utf8'))['queries']
            latest=json.loads((raw/'novas/execucoes.json').read_text(encoding='utf8'));history=json.loads((raw/'novas/tentativas.json').read_text(encoding='utf8'))
            check_coverage(pending,plan,latest,history)
            assert len(latest)==22 and len(history)==34 and sum(r['status']=='falha' for r in history)==12
            attempts=con.read_parquet(str(dest/'tentativas_busca.parquet')).df()
            assert len(attempts)==34 and attempts.status.eq('falha').sum()==12 and attempts.search_id.nunique()==22
            assert sum(r['status']=='concluida_sem_resultados' for r in latest)==5
            for item in latest:check_payload(item,json.loads((raw/'novas'/item['capture_file']).read_text(encoding='utf8')))
            assert summary['previous_capture_manifest_sha256']==sha256(data/'auditoria/atas/v1/manifesto.json')
            assert summary['limited_context_captures']==1 and summary['context_sources_unique_urls']>=34
        if version=='v3':
            assert summary['capture_version']=='v3'
            assert summary['previous_capture_manifest_sha256']==sha256(data/'auditoria/atas/v1/manifesto.json')
            registry=json.loads((dest/'evidencias_registradas.json').read_text(encoding='utf8'))
            research=json.loads((raw/'pesquisa.json').read_text(encoding='utf8'))
            assert summary['registered_evidence_entries']==len(registry['evidence'])>0
            assert research['evidence_revision']['based_on_capture_manifest_sha256']==sha256(data/'auditoria/atas/v2/manifesto.json')
            sources_by_id={item['source_id']:item for item in research['sources']}
            from eleicoes.audit_atas import SPECIFIC_TYPES
            from eleicoes.atas_evidence import RESPONSE_TYPES
            from eleicoes.audit_atas_v3 import evaluate
            checked_specific=checked_responses=0
            issue_map={(key(r),r['indicator']):r for r in issues.to_dict('records')}
            outcomes={}
            for item in registry['evidence']:
                source_record=sources_by_id[item['source_id']]
                file=(raw/source_record['capture_file']).resolve()
                assert file.is_relative_to(raw) and sha256(file)==source_record['capture_sha256']
                assert item['source_id']==source_record['source_id']
                outcome=evaluate(item['case'],item['indicator'],source_record,item)
                assert outcome in ('registro_corrobora_no_escopo','divergencia_documental_a_revisar','evidencia_inconclusiva')
                assert (key(item['case']),item['indicator']) in issue_map
                assert item['case']['year']==source_record['year'] and item['case']['turn']==source_record['turn']
                assert item['case']['uf']==source_record['uf']
                outcomes.setdefault((key(item['case']),item['indicator']),[]).append(outcome)
                if source_record['kind'] in SPECIFIC_TYPES:checked_specific+=1
                if source_record['kind'] in RESPONSE_TYPES:
                    checked_responses+=1
                    assert outcome=='evidencia_inconclusiva' and item['finding']=='inconclusivo'
            assert summary['specific_evidence_entries']==checked_specific
            assert summary['official_response_entries']==checked_responses
            for identity_indicator,row in issue_map.items():
                values=outcomes.get(identity_indicator,[])
                expected=('divergencia_documental_a_revisar' if 'divergencia_documental_a_revisar' in values else
                    'registro_corrobora_no_escopo' if 'registro_corrobora_no_escopo' in values else
                    'evidencia_insuficiente' if values else 'sem_documento_especifico')
                assert row['document_status']==expected
            assert not summary['causes_confirmed'] and summary['requests_sent']==0
        else:
            assert cases.document_status.eq('sem_confronto_especifico_concluido').all()
            assert issues.document_status.eq('sem_documento_especifico').all()
        assert issues.cause_status.eq('nao_confirmada_por_esta_rotina').all() and summary['causes_confirmed'] is None
        if version!='v3':
            assert summary['specific_evidence_entries']==0 and summary['requests_sent']==0
            assert not sources.specific_document.any() and queries.specific_documents_obtained.eq(0).all()
        else:
            assert summary['requests_sent']==0
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
    if version in ('v2','v3'):previous+=('atas',)
    if version=='v3':previous+=('atas_ampliacao',)
    for stage in previous:
        folder=source/'auditoria'/stage
        for name,digest in json.loads((folder/'manifesto.json').read_text(encoding='utf8')).items():assert sha256(folder/name)==digest,(stage,name)
        if stage=='atas':
            for name,digest in json.loads((folder/'manifesto_fichas.json').read_text(encoding='utf8')).items():assert sha256(folder/name)==digest,name
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
        expected_pdf=('Confronto documental','28','33','inconclusivo','não') if version=='v3' else (
            '28','33','22','56','60','primeiro turno','Nenhum','não')
        for value in expected_pdf:assert value in content,value
        for p in pdf:
            assert len(p.get_text())>150
            for x0,y0,x1,y1,*_ in p.get_text('blocks'):assert x0>=36 and x1<=p.rect.width-35 and y0>=18 and y1<=p.rect.height-20,(p.number,(x0,y0,x1,y1))
        pdf_info=dict(pages=len(pdf),bookmarks=len(pdf.get_toc()),geometry='dentro das margens')
    return dict(status='válido',csv_parquet_pairs=len(pairs),issue_rows=33,section_turns=28,individual_searches=len(queries),
        units_without_individual_search=int(cases.individual_searches.eq(0).sum()),specific_evidence_entries=summary['specific_evidence_entries'],
        registered_evidence_entries=summary.get('registered_evidence_entries',summary['specific_evidence_entries']),request_drafts=28,requests_sent=0,
        cards=28,previous_stage_manifests_preserved=len(previous),local_links=links,filters=filters,pdf=pdf_info)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='outputs/2026');p.add_argument('--data',default='data')
    p.add_argument('--dest')
    group=p.add_mutually_exclusive_group();group.add_argument('--ampliacao',action='store_true');group.add_argument('--confronto',action='store_true')
    a=p.parse_args()
    print(json.dumps(validate(a.output,a.data,a.ampliacao,a.confronto,a.dest),ensure_ascii=False,indent=2))
