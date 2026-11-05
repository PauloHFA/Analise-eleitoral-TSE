"""Dossiê de confronto documental, separado da interpretação causal dos logs."""
from pathlib import Path
import json
import re
from urllib.parse import urlsplit
import duckdb
import pandas as pd
from .analysis import export_frame
from .national_common import begin, finish, failed, records
from .sources import sha256, write_json

GEO=['year','turn','uf','municipality','zone','section']
SPECIFIC_TYPES={'ata_mrv','registro_atendimento','registro_substituicao'}


def key(record):
    values=[]
    for name in GEO:
        value=str(record[name]).strip()
        if name=='uf':
            if not re.fullmatch('[A-Za-z]{2}',value):raise ValueError('UF inválida')
            values.append(value.upper())
        else:
            if not re.fullmatch('[0-9]+',value) or int(value)<=0:raise ValueError('Chave numérica inválida')
            values.append(int(value))
    return tuple(values)


def case_id(record):
    year,turn,uf,municipality,zone,section=key(record)
    return f'{year}-{turn}-{uf}-{municipality}-{zone}-{section}'


def official_source(url):
    u=urlsplit(url);host=u.hostname or ''
    return u.scheme=='https' and not u.username and bool(re.fullmatch(r'(?:[a-z0-9-]+\.)*(?:tse|tre-[a-z]{2})\.jus\.br',host) or host=='www.justicaeleitoral.jus.br')


def evaluate(case, indicator, source, evidence):
    """Metadados/revisão são pressupostos declarados, nunca autenticação automática."""
    if not official_source(source.get('url','')):return 'origem_nao_verificada'
    if source.get('kind') not in SPECIFIC_TYPES:return 'fonte_geral_sem_confronto'
    try:
        if key(source['identity'])!=key(case):return 'documento_de_outra_unidade_ou_turno'
    except (KeyError,ValueError):return 'identificacao_documental_insuficiente'
    if evidence.get('indicator')!=indicator:return 'apontamento_diferente'
    if (evidence.get('review_status')!='revisao_documental_registrada'
            or not str(evidence.get('locator','')).strip() or not str(evidence.get('justification','')).strip()):
        return 'revisao_incompleta'
    return {'corrobora_registro':'registro_corrobora_no_escopo',
            'contradiz_registro':'divergencia_documental_a_revisar',
            'inconclusivo':'evidencia_inconclusiva'}.get(evidence.get('finding'),'evidencia_inconclusiva')


QUESTIONS={
 'nested_payloads':'Qual a origem do log compactado aninhado e como foi incorporado ao arquivo da seção?',
 'target_hardware_identifiers':'Há registro de troca ou composição de arquivos? Quais documentos identificam os equipamentos de origem e destino?',
 'target_clock_regressions':'Há anotação de ajuste de relógio, configuração de horário ou composição do arquivo que contextualize o retrocesso observado?',
 'boots_between_markers':'As mensagens de ligação entre marcos correspondem a atendimento ou retomada? Há horários e providências documentados?',
 'impressora_falha':'Há atendimento à impressora e registro das providências ou reimpressões realizadas?',
 'impressora_erro_desconhecido':'Qual atendimento foi registrado para o erro da impressora e quais providências foram adotadas?',
 'reinicio_solicitado':'Há anotação do reinício solicitado, da providência adotada e da retomada?',
 'target_error_records':'Há registro operacional que contextualize as mensagens ERRO, inclusive o problema de desmontagem de MR?',
}


def request_text(case, indicators):
    ident=f"{case['municipality_name_1']} ({case['uf']}), município TSE {case['municipality']}, zona {case['zone']}, seção {case['section']}, {case['turn']}º turno de {case['year']}"
    questions=[QUESTIONS.get(i,'Há documento operacional que contextualize este apontamento?') for i in sorted(set(indicators))]
    if case.get('opensession_erro',0):questions.append('Há registro de atendimento para a mensagem OpenSession e da providência adotada?')
    return ('MINUTA LOCAL — NÃO ENVIADA\n\nReferência: '+ident+'\n\n'
        'Documentos a localizar: ata da mesa receptora de votos e registros de atendimento, contingência ou substituição relacionados à unidade/turno. '
        'Se o documento não for localizado, registrar a resposta e a abrangência da consulta, sem inferir inexistência da ocorrência.\n\n'
        +'\n'.join(f'{n}. {text}' for n,text in enumerate(questions,1))
        +'\n\nPriorizar documentos com data, identificação territorial e localização verificável da anotação. Não são solicitados dados pessoais de eleitores, biometria ou escolhas individuais. '
        'A ausência de documento não será interpretada como comprovação de regularidade ou irregularidade. Nenhum pedido foi enviado por esta ferramenta.\n')


def run_atas(source,data='data',destination=None):
    source,data=Path(source).resolve(),Path(data).resolve();raw=data/'auditoria/atas/v1'
    destination=Path(destination).resolve() if destination else source/'auditoria/atas'
    names=['auditoria/logs/unidades.parquet','auditoria/logs/pendencias.parquet','auditoria/logs/manifesto.json']
    source,destination,state=begin(source,destination,names);con=duckdb.connect()
    try:
        raw_manifest=json.loads((raw/'manifesto.json').read_text(encoding='utf8'))
        for name,digest in raw_manifest.items():
            path=(raw/name).resolve()
            if not path.is_relative_to(raw) or sha256(path)!=digest:raise ValueError('Captura ausente, fora da pasta ou alterada')
        previous=json.loads((source/names[2]).read_text(encoding='utf8'))
        for name,digest in previous.items():
            if sha256(source/'auditoria/logs'/name)!=digest:raise ValueError('Etapa dos logs alterada')
        research=json.loads((raw/'pesquisa.json').read_text(encoding='utf8'));registry=json.loads((raw/'evidencias.json').read_text(encoding='utf8'))
        if research.get('version')!=1 or registry.get('version')!=1:raise ValueError('Versão de registro não suportada')
        units=con.read_parquet(str(source/names[0])).df();issues=con.read_parquet(str(source/names[1])).df()
        if units.duplicated(GEO).any():raise ValueError('Unidade de log duplicada')
        cases=issues[GEO].drop_duplicates().merge(units,on=GEO,how='left',validate='one_to_one',indicator=True)
        if not cases['_merge'].eq('both').all():raise ValueError('Apontamento sem unidade de origem')
        cases=cases.drop(columns='_merge');sources=research['sources'];source_map={s['source_id']:s for s in sources}
        if len(source_map)!=len(sources):raise ValueError('Fonte com identificador repetido')
        for item in sources:
            capture=(raw/item['capture_file']).resolve()
            if not capture.is_relative_to(raw) or sha256(capture)!=item['capture_sha256']:
                raise ValueError('Fonte de evidência não corresponde à captura preservada')
        searches=research['queries'];search_map={}
        for search in searches:
            if key(search) not in {key(r) for r in cases.to_dict('records')}:raise ValueError('Busca não pertence a caso do inventário')
            search_map.setdefault(key(search),[]).append(search['search_id'])
        evidence=registry['evidence'];matched_evidence=set();confrontation=[];requests=[];case_rows=[]
        evidence_ids=[e['evidence_id'] for e in evidence]
        if len(evidence_ids)!=len(set(evidence_ids)):raise ValueError('Evidência repetida')
        for case in cases.sort_values(GEO).to_dict('records'):
            selected=issues
            for name in GEO:selected=selected.loc[selected[name].eq(case[name])]
            indicators=selected.indicator.tolist();cid=case_id(case)
            initial=any(i!='target_error_records' for i in indicators) or case['opensession_erro']>0
            statuses=[]
            for issue in selected.to_dict('records'):
                rows=[e for e in evidence if key(e['case'])==key(case) and e.get('indicator')==issue['indicator']]
                outcomes=[]
                for item in rows:
                    if item['source_id'] not in source_map:raise ValueError('Evidência sem fonte registrada')
                    outcomes.append(evaluate(case,issue['indicator'],source_map[item['source_id']],item));matched_evidence.add(item['evidence_id'])
                status=('divergencia_documental_a_revisar' if 'divergencia_documental_a_revisar' in outcomes else
                        'registro_corrobora_no_escopo' if 'registro_corrobora_no_escopo' in outcomes else
                        'evidencia_insuficiente' if outcomes else 'sem_documento_especifico')
                statuses.append(status)
                confrontation.append(dict(**issue,case_id=cid,document_status=status,evidence_ids=';'.join(r['evidence_id'] for r in rows) or None,
                    cause_status='nao_confirmada_por_esta_rotina'))
            row={name:case[name] for name in GEO+['municipality_name_1','group','region','target_date','opensession_erro']}
            row.update(case_id=cid,priority='inicial' if initial else 'acompanhamento',issues=len(selected),
                indicators=';'.join(sorted(set(indicators))),individual_searches=len(search_map.get(key(case),[])),
                research_status='busca_individual_registrada' if key(case) in search_map else 'busca_individual_nao_realizada',
                document_status='confronto_com_evidencia_especifica' if any(s in ('registro_corrobora_no_escopo','divergencia_documental_a_revisar') for s in statuses) else 'sem_confronto_especifico_concluido',
                cause_status='nao_confirmada_por_esta_rotina',card=f'fichas/{cid}.html',request_draft=f'minutas/{cid}.txt')
            case_rows.append(row)
            (destination/'minutas').mkdir(exist_ok=True);(destination/row['request_draft']).write_text(request_text(case,indicators),encoding='utf8')
            for kind in ('ata_mrv','registro_atendimento_substituicao'):
                requests.append(dict(**{name:case[name] for name in GEO},case_id=cid,document_kind=kind,status='a_localizar',
                    note='Tipo de documento a procurar, não comprovação de existência ou pedido enviado'))
        if set(evidence_ids)!=matched_evidence:raise ValueError('Evidência não corresponde a apontamento existente')
        case_frame=pd.DataFrame(case_rows);confrontation=pd.DataFrame(confrontation)
        frames=dict(casos=case_frame,confronto=confrontation,buscas=pd.DataFrame(searches),
                    resultados_busca=pd.DataFrame(research['results']),fontes=pd.DataFrame(sources),documentos_necessarios=pd.DataFrame(requests))
        for name,frame in frames.items():export_frame(con,frame,destination/name)
        write_json(destination/'evidencias_registradas.json',registry)
        summary=dict(sections=len(case_frame[[g for g in GEO if g!='turn']].drop_duplicates()),section_turns=len(case_frame),
            issue_rows=len(confrontation),initial_units=int(case_frame.priority.eq('inicial').sum()),
            individual_searches=len(searches),units_with_individual_search=int(case_frame.individual_searches.gt(0).sum()),
            units_without_individual_search=int(case_frame.individual_searches.eq(0).sum()),search_results=len(research['results']),
            reviewed_context_sources=len(sources),specific_evidence_entries=len(evidence),
            issues_corrobated=int(confrontation.document_status.eq('registro_corrobora_no_escopo').sum()),
            documentary_differences_for_review=int(confrontation.document_status.eq('divergencia_documental_a_revisar').sum()),
            causes_confirmed=None,cause_interpretation='A confirmação causal não é automatizada; zero registros específicos não prova ausência de ocorrência',
            document_requirements=len(requests),cards=len(case_frame),local_request_drafts=len(case_frame),requests_sent=0,
            capture_manifest_sha256=sha256(raw/'manifesto.json'),capture_hashes=raw_manifest,
            status_counts=records(case_frame.groupby(['priority','research_status','document_status']).size().reset_index(name='units')),
            interpretation='Pesquisa e dossiê executados; confronto de casos permanece dependente de atas e registros específicos. Fontes gerais não explicam ocorrências individuais.')
        from .audit_atas_report import render
        render(destination,summary,case_frame,confrontation,frames['fontes'],frames['buscas'])
        # Fichas/minutas integram um manifesto próprio; finish cobre arquivos de topo.
        write_json(destination/'manifesto_fichas.json',{p.relative_to(destination).as_posix():sha256(p) for folder in ('fichas','minutas') for p in sorted((destination/folder).glob('*')) if p.is_file()})
        return finish(source,destination,state,summary,[Path(__file__),Path(__file__).with_name('audit_atas_report.py')])
    except Exception as exc:failed(destination,state,exc);raise
    finally:con.close()
