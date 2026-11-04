"""Síntese editorial da conferência amostral, com limites antes dos casos."""
import html
import json
import platform
from importlib.metadata import version
from pathlib import Path
import duckdb
import pandas as pd
from reportlab.platypus import PageBreak,KeepTogether,Spacer
from .national_common import begin,finish,failed,records
from .pdf_layout import AnalysisPDF,pdf_styles,p,heading,table,WIDTH
from .sources import write_json

GEO=['year','turn','uf','municipality','zone','section']
OFFICIAL='https://dadosabertos.tse.jus.br/dataset/resultados-2026-arquivos-transmitidos-para-totalizacao'
AUDIT='https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/como-realizar-auditoria'
LIMIT='As assinaturas digitais não foram validadas: os arquivos obtidos não foram decodificados com o esquema de assinaturas consultado. Isso limita o leitor e não demonstra assinatura inválida. Os logs foram preservados, sem análise de eventos. Não foi obtido BU em papel de fonte independente.'
METHOD='A seleção foi registrada em commit antes da obtenção dos documentos: 12 prioridades e 12 controles. Os prioritários têm alerta em todas as variantes disponíveis de 15/30/50 pares; no exterior somente 15 e 30 estão disponíveis. Os controles não têm alerta nos critérios registrados e foram pareados na mesma UF, preferindo o município, por tamanho, comparecimento e participações dos finalistas no primeiro turno. A amostra dirigida não permite estimar frequência nacional de irregularidades.'
COUNT='O leitor identifica seção, eleição e cargo Presidente, reconta votos nominais, brancos e nulos no RDV e compara com o BU binário, o texto da imagem digital do BU e os CSV preservados de resultados e de BU. Brancos/nulos após suspensão são reunidos nas categorias correspondentes. Tipos desconhecidos, registros ausentes ou repetidos e leitura incompleta geram limitação. Zeros implícitos só são usados em uma unidade oficial instalada com votação e cargo identificado.'
ORIGIN='Os documentos foram extraídos de 22 ZIPs do catálogo oficial, apenas nos intervalos necessários, com ETag forte, conferência de Content-Range e CRC32. Cada membro tem SHA256; não há hash do ZIP completo, pois ele não foi baixado integralmente. A versão do documento pode diferir da versão das bases CSV: a conferência compara os valores e conserva as gerações e fontes.'
SCHEMAS='Os esquemas ASN.1 foram obtidos de um espelho de terceiros de pacote atribuído ao TSE, fixados por SHA256. O download direto do pacote consultado no TSE retornou HTTP 403. A origem do espelho não equivale à autenticação pelo TSE; incompatibilidades são declaradas, sem adaptar o formato silenciosamente.'
INTERPRET='Concordância confirma os totais publicados para esta amostra e estas versões. Não explica por que eleitores mudaram suas escolhas, não demonstra transferências individuais e não constitui auditoria integral da eleição. RDV, BU e imagem digital são documentos do mesmo equipamento; sua concordância não é uma fonte independente.'


def n(value):return f'{int(value):,}'.replace(',','.')


def synthesize(sample,units,votes,documents,acquisition):
    labeled=units.merge(sample[['year','uf','municipality','zone','section','group','region']],on=['year','uf','municipality','zone','section'],validate='many_to_one')
    labeled['territory']=labeled.uf.map(lambda u:'Exterior' if u=='ZZ' else 'Brasil')
    groups=labeled.groupby(['territory','group']).agg(section_turns=('turn','size'),concordant=('vote_status',lambda s:int(s.eq('concordante').sum())),attendance=('sum_matches_attendance','sum'),denominators=('denominators_match','sum')).reset_index()
    return dict(sections=len(sample),priority_sections=int(sample.group.eq('prioritario').sum()),control_sections=int(sample.group.eq('comparacao').sum()),
        section_turns=len(units),obtained_documents=acquisition['obtained_documents'],vote_rows=len(votes),
        concordant_rows=int(votes.status.eq('concordante').sum()),concordant_units=int(units.vote_status.eq('concordante').sum()),
        attendance_reconciled=int(units.sum_matches_attendance.sum()),denominators_reconciled=int(units.denominators_match.sum()),
        cryptographic_signatures_verified=0,signature_verification_status='não realizada por incompatibilidade de formato com o esquema consultado',
        log_events_examined=0,independent_paper_bu_obtained=0,group_results=records(groups),
        document_statuses=records(documents.groupby(['kind','status']).size().reset_index(name='documents')),
        acquisition_network_bytes=acquisition['network_bytes'],remote_archives=acquisition['remote_archives'],
        interpretation=INTERPRET,remaining=[LIMIT,SCHEMAS],sample_not_probabilistic=True)


def render(destination,summary,sample,units,votes,documents):
    esc=lambda v:html.escape(str(v));styles=pdf_styles()
    outcome=f"{n(summary['concordant_units'])} de {n(summary['section_turns'])} unidades seção/turno com valores presidenciais concordantes nas cinco leituras; {n(summary['concordant_rows'])} de {n(summary['vote_rows'])} linhas por candidato ou categoria concordantes."
    lead=f"A conferência abrange {n(summary['sections'])} seções, nos dois turnos, com {n(summary['obtained_documents'])} documentos obtidos. São {n(summary['priority_sections'])} prioridades e {n(summary['control_sections'])} controles, nas cinco regiões e no exterior."
    headers=['Território','Grupo','Seção/turno','Totais concordantes','Aptos/comparecimento']
    group_rows=[[r['territory'],'Prioritário' if r['group']=='prioritario' else 'Comparação',r['section_turns'],r['concordant'],r['denominators']] for r in summary['group_results']]
    kind_rows=[['RDV',48,'Recontagem presidencial agregada'],['BU binário',48,'Votos, aptos e comparecimento'],['Imagem digital do BU',48,'Texto presidencial; não é papel independente'],['Arquivo de assinaturas',48,'Preservado; formato não suportado pelo leitor'],['Log',48,'Preservado; eventos não analisados']]
    # Derivar a quantidade por tipo do inventário, sem pressupor cobertura de 48 documentos.
    for row,kind in zip(kind_rows,['rdv','bu','imagem','assinatura','log']):row[1]=int(documents.kind.eq(kind).sum())
    blocks=[];cards=[]
    for row in sample.sort_values(['region','pair_id','group']).to_dict('records'):
        chosen=units
        chosen_votes=votes
        for key in ('year','uf','municipality','zone','section'):
            chosen=chosen.loc[chosen[key].eq(row[key])];chosen_votes=chosen_votes.loc[chosen_votes[key].eq(row[key])]
        label='Prioritário' if row['group']=='prioritario' else 'Comparação'
        title=f"{row['pair_id']} · {label} · {row['uf']} · {row['municipality_name_1']}"
        identification=f"Município TSE {row['municipality']} · zona {row['zone']} · seção {row['section']} · {row['region']}"
        values=[]
        for turn in (1,2):
            u=chosen.loc[chosen.turn.eq(turn)].iloc[0];v=chosen_votes.loc[chosen_votes.turn.eq(turn)]
            def count(candidate):
                found=v.loc[v.candidate.eq(candidate),'rdv_votes']
                return int(found.iloc[0]) if len(found)==1 and pd.notna(found.iloc[0]) else 0 if u.vote_status=='concordante' else '—'
            values.append([f'{turn}º',count(22),count(13),int(v.loc[~v.candidate.isin([13,22,95,96]),'rdv_votes'].sum()),count(95),count(96),u.reference_attendance,u.reference_aptos])
        status='Totais concordantes nos dois turnos' if chosen.vote_status.eq('concordante').all() else 'Consultar a situação detalhada da unidade'
        detail=f"Margem (Flávio − Lula) entre finalistas: {row['margin_1_pp']:.2f} → {row['margin_2_pp']:.2f} pp. Alerta em {int(row['alert_configurations'])}/{int(row['available_configurations'])} variantes disponíveis. {row['match_scope']}; distância {row['match_distance']:.3f}."
        keys=['Turno','Flávio','Lula','Outros nominais','Brancos','Nulos','Comparecimento','Aptos']
        tbl=pd.DataFrame(values,columns=keys).to_html(index=False,escape=True)
        blocks.append(f'<article class="case" data-uf="{esc(row["uf"])}" data-group="{esc(row["group"])}"><h3>{esc(title)}</h3><p>{esc(identification)}</p><div class="scroll">{tbl}</div><p>{esc(detail)}</p><p><strong>{esc(status)}</strong>. Assinatura e eventos do log não verificados.</p></article>')
        cards.append((title,identification,keys,values,detail,status))
    options=''.join(f'<option>{esc(uf)}</option>' for uf in sorted(sample.uf.unique()))
    groups_html=pd.DataFrame(group_rows,columns=headers).to_html(index=False,escape=True)
    kinds_html=pd.DataFrame(kind_rows,columns=['Documento','Unidades','Conferência realizada / limite']).to_html(index=False,escape=True)
    page=f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Conferência amostral de documentos — 2026</title>
<style>body{{font:17px/1.65 system-ui;color:#183447;background:#f1f5f7;margin:0}}main{{max-width:1100px;margin:auto;background:white;padding:2rem}}h1{{line-height:1.2}}h2{{margin-top:2.5rem;color:#12677a}}.finding{{border-left:5px solid #12677a;background:#edf4f7;padding:1rem}}.limit{{border-left:5px solid #bd7427;background:#fff8e9;padding:1rem}}table{{border-collapse:collapse;width:100%;font-size:.88rem}}td,th{{padding:.55rem;text-align:left;border-bottom:1px solid #ccd9df}}th{{background:#edf4f7}}.scroll{{overflow:auto}}.case{{margin:1.2rem 0;border:1px solid #cbd8df;padding:1rem;border-radius:8px}}select{{padding:.5rem;font:inherit}}a{{color:#075f8a}}article[hidden]{{display:none}}@media(max-width:650px){{main{{padding:1rem}}}}@media print{{select,label{{display:none}}.case{{break-inside:avoid}}}}</style>
<main><p>Etapa 5 · conferência ampliada · versão inicial com limites documentados</p><h1>Os totais da amostra concordam; assinaturas e logs continuam pendentes</h1>
<p>{esc(lead)}</p><div class="finding"><strong>{esc(outcome)}</strong><p>São linhas de votação por candidato/categoria, não pessoas ou urnas distintas. Comparecimento e aptos coincidiram em {summary['denominators_reconciled']}/{summary['section_turns']} unidades.</p></div>
<p class="limit">{esc(LIMIT)}</p><p>{esc(INTERPRET)}</p>
<nav><a href="relatorio.pdf">PDF</a> · <a href="#metodo">Método e cobertura</a> · <a href="#casos">24 seções</a> · <a href="#dados">Tabelas e reprodução</a> · <a href="../../relatorio.html">Relatório de referência preservado</a></nav>
<h2>Resultado por grupo e território</h2><div class="scroll">{groups_html}</div><p>Os grupos são dirigidos e pequenos. A tabela descreve somente a amostra; não compara taxas nacionais de irregularidade.</p>
<h2 id="metodo">O que foi feito e o que permanece aberto</h2><p>{esc(METHOD)}</p><p>{esc(COUNT)}</p><div class="scroll">{kinds_html}</div><p>{esc(ORIGIN)}</p><p>{esc(SCHEMAS)}</p>
<h2 id="casos">Seções conferidas</h2><p>Valores abaixo recontados no RDV presidencial. “Outros nominais” são candidatos diferentes dos finalistas; brancos e nulos têm colunas próprias. Margens usam apenas os dois finalistas e não são percentuais de todos os votos.</p>
<label>UF <select id="uf"><option value="all">Todas</option>{options}</select></label> <label>Grupo <select id="group"><option value="all">Todos</option><option value="prioritario">Prioritário</option><option value="comparacao">Comparação</option></select></label><p id="count" aria-live="polite">24 seções exibidas</p>{''.join(blocks)}
<h2 id="dados">Tabelas, fontes e reprodução</h2><ul><li><a href="../amostra/secoes.csv">Seleção e pareamento</a> · <a href="../amostra/protocolo.json">Protocolo anterior aos documentos</a></li><li><a href="../documentos/inventario.csv">240 documentos, URLs e hashes</a> · <a href="../documentos/arquivos_remotos.json">Versões e intervalos dos ZIPs</a></li><li><a href="../conferencia/votacao.csv">265 comparações por candidato/categoria</a> · <a href="../conferencia/unidades.csv">48 unidades e denominadores</a> · <a href="../conferencia/documentos.csv">Situação de cada documento e erros de leitura</a></li><li><a href="resumo.json">Síntese desta edição</a> · <a href="../../../../docs/AUDITORIA.md">Método e comandos</a></li><li><a href="{OFFICIAL}">Catálogo oficial de arquivos da urna</a> · <a href="{AUDIT}">Procedimentos de auditoria do TSE</a></li></ul>
<h2>Próximo incremento</h2><p>Obter a especificação compatível das assinaturas, validar os vínculos arquivo–assinatura e a cadeia com âncoras oficiais; analisar os eventos dos logs com critérios próprios. A conferência com BU em papel ou imagem recolhida independentemente permanece aberta. A pesquisa do ato individual sobre os nulos técnicos também continua pendente.</p>
</main><script>const selects=[document.querySelector('#uf'),document.querySelector('#group')];function filter(){{let total=0;document.querySelectorAll('.case').forEach(e=>{{e.hidden=!selects.every(s=>s.value==='all'||e.dataset[s.id]===s.value);if(!e.hidden)total++}});document.querySelector('#count').textContent=total+' seções exibidas'}}selects.forEach(s=>s.addEventListener('change',filter));filter();</script></html>'''
    (destination/'relatorio.html').write_text(page,encoding='utf8')
    story=[heading('Conferência amostral de documentos — 2026','inicio',styles),p(lead,styles,'Deck'),p(outcome,styles),p('Comparecimento e aptos coincidiram em '+str(summary['denominators_reconciled'])+'/'+str(summary['section_turns'])+' unidades. As 265 linhas são por candidato/categoria, não pessoas ou urnas distintas.',styles),heading('O alcance desta conclusão','alcance',styles,level=1),p(INTERPRET,styles),table(headers,group_rows,[WIDTH*x for x in (.15,.18,.16,.24,.27)],styles,small=True),p(LIMIT,styles),PageBreak(),heading('Método, fontes e cobertura','metodo',styles),p(METHOD,styles),p(COUNT,styles),table(['Documento','Unidades','Conferência / limite'],kind_rows,[WIDTH*.23,WIDTH*.12,WIDTH*.65],styles,small=True),p(ORIGIN,styles),p(SCHEMAS,styles),p('Fontes oficiais: catálogo de arquivos transmitidos para totalização e página Como realizar auditoria, vinculados no HTML. Tabelas completas e comandos em docs/AUDITORIA.md.',styles,'Small')]
    for offset in range(0,len(cards),4):
        story.extend([PageBreak(),heading(f'Seções conferidas · {offset+1}–{min(offset+4,len(cards))}','casos-'+str(offset),styles),p('Votos presidenciais recontados no RDV. Outros = outros candidatos nominais. Comparação com as demais quatro leituras consta das tabelas. Assinaturas e eventos dos logs não verificados.',styles,'Small')])
        for title,ident,keys,values,detail,status in cards[offset:offset+4]:
            shortkeys=['Turno','Flávio','Lula','Outros','Brancos','Nulos','Comp.','Aptos']
            story.append(KeepTogether([p(title,styles,'Subhead'),p(ident,styles,'Small'),table(shortkeys,values,[WIDTH/8]*8,styles,small=True),p(detail,styles,'Small'),p(status,styles,'Small'),Spacer(1,8)]))
    story.extend([PageBreak(),heading('Pendências e reprodução','pendencias',styles),p(LIMIT,styles),p('Próximo incremento: confirmar a especificação compatível dos arquivos de assinatura e verificar sua cadeia de confiança com referências oficiais. A análise de eventos dos logs e a comparação com papel independente continuam abertas. A causa jurídica individual dos nulos técnicos da frente 3 também permanece pendente.',styles),p('Nenhuma conclusão de fraude ou de inexistência de irregularidades foi extraída desta concordância amostral.',styles),p('Os CSV e Parquets, protocolo, fontes, hashes e resumo estão disponíveis no HTML e no pacote de resultados desta etapa. Os documentos brutos ficam preservados localmente; o inventário fornece os endereços oficiais para reprodução. Não são publicados registros de votos individuais ou conteúdo dos logs.',styles),p('Comandos: auditoria --etapa amostra; auditoria --etapa documentos; preparar_especificacao_auditoria.py; auditoria --etapa conferencia; auditoria --etapa relatorio. Usar pastas novas para preservar as versões anteriores.',styles)])
    AnalysisPDF(destination/'relatorio.pdf',title='Conferência amostral de documentos — 2026',styles=styles).build(story)


def run_report(source,destination=None):
    source=Path(source).resolve();destination=Path(destination).resolve() if destination else source/'auditoria/relatorio'
    names=['auditoria/amostra/secoes.parquet','auditoria/conferencia/unidades.parquet','auditoria/conferencia/votacao.parquet',
           'auditoria/conferencia/documentos.parquet','auditoria/documentos/resumo.json']
    source,destination,state=begin(source,destination,names);con=duckdb.connect()
    try:
        sample,units,votes,documents=[con.execute('SELECT * FROM read_parquet(?)',[str(source/name)]).df() for name in names[:4]]
        acquisition=json.loads((source/names[4]).read_text(encoding='utf8'))
        summary=synthesize(sample,units,votes,documents,acquisition)
        summary['environment']=dict(python=platform.python_version(),packages={name:version(name) for name in ('duckdb','pandas','numpy','requests','asn1tools','reportlab')})
        summary['sources']=dict(documents=OFFICIAL,audit_procedures=AUDIT,
            schemas_mirror='https://github.com/doccaz/urnas-br/tree/main/docv2',
            schemas_archive_sha256='1e423054f32b8ba056960c58ada167d702c2618cc4d1dfd5de88f5090c84a235',
            schemas_origin='Espelho de terceiros; não constitui âncora oficial de confiança')
        render(destination,summary,sample,units,votes,documents)
        return finish(source,destination,state,summary,[Path(__file__),Path(__file__).with_name('pdf_layout.py')])
    except Exception as exc:failed(destination,state,exc);raise
    finally:con.close()
