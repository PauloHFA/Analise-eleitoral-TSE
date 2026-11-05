"""Fichas de pendências e minutas locais; fontes gerais nunca explicam um caso."""
import html
from reportlab.platypus import PageBreak
from .pdf_layout import AnalysisPDF,pdf_styles,p,heading,table,WIDTH

METHOD='As 33 linhas de apontamento dos logs foram relacionadas a 28 unidades seção/turno. Seis unidades com eventos adicionais ao nível ERRO receberam busca individual por município, zona, seção, data e ano. As demais 22 permanecem no inventário, sem busca individual nesta rodada. Seleção dirigida, sem estimativa de frequência nacional.'
GATE='Um confronto específico exige documento de seção ou atendimento, identidade territorial/ano/turno compatíveis, apontamento definido, localização no documento e revisão registrada. Notícia agregada, norma, diretório e ata de julgamento não satisfazem esse critério. Metadados e URL declarados não autenticam sozinhos um documento.'
LIMIT='Nenhuma ata de mesa receptora ou registro individualizado de atendimento/substituição dos casos foi obtido nesta rodada. As causas continuam pendentes. Não localizar um documento em uma busca não demonstra sua inexistência nem regularidade ou irregularidade da votação.'
NEXT='Há 28 minutas locais, uma por unidade, e 56 necessidades documentais de dois tipos: ata da mesa receptora e registro de atendimento/contingência/substituição. São documentos a procurar, não documentos existentes ou pedidos enviados. Nenhum contato externo foi realizado.'


def render(dest,summary,cases,issues,sources,searches):
    esc=lambda v:html.escape(str(v))
    limit=LIMIT if summary['specific_evidence_entries']==0 else 'Há evidências específicas registradas nesta versão. O alcance de cada confronto consta da ficha; causas e persistência não são confirmadas automaticamente.'
    issue_names=dict(target_error_records='Mensagens de nível ERRO',reinicio_solicitado='Solicitação de reinício',
        impressora_erro_desconhecido='Erro desconhecido da impressora',nested_payloads='Log aninhado',
        target_hardware_identifiers='Identificadores de hardware',target_clock_regressions='Retrocesso na ordem temporal',
        boots_between_markers='Ligações entre marcos',impressora_falha='Mensagem de falha da impressora')
    status_names=dict(sem_documento_especifico='Documento específico não obtido',
        sem_confronto_especifico_concluido='Sem confronto específico concluído',
        registro_corrobora_no_escopo='Registro corroborado no escopo',
        divergencia_documental_a_revisar='Divergência documental a revisar',evidencia_insuficiente='Evidência insuficiente',
        confronto_com_evidencia_especifica='Confronto com evidência específica')
    def tbl(headers,rows):return '<table><thead><tr>'+''.join('<th>'+esc(v)+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'
    (dest/'fichas').mkdir(exist_ok=True)
    rows=[];initial=[];all_rows=[]
    for case in cases.sort_values(['priority','uf','municipality','zone','section','turn']).to_dict('records'):
        selected=issues.loc[issues.case_id.eq(case['case_id'])];query=searches
        for name in ('year','turn','uf','municipality','zone','section'):
            query=query.loc[query[name].astype(str).eq(str(case[name]))]
        # Chaves dos CSV locais podem ser strings; comparação por valor canônico.
        if case['individual_searches'] and query.empty:
            from .audit_atas import key
            query=searches.loc[searches.apply(lambda r:key(r)==key(case),axis=1)]
        ident=f"{case['uf']} · {case['municipality_name_1']} · zona {case['zone']} · seção {case['section']} · {case['turn']}º turno"
        search_label='Realizada' if case['individual_searches'] else 'Não realizada'
        issue_values=[
            [issue_names.get(r['indicator'],r['indicator']),r['count'],r['reason'],status_names.get(r['document_status'],r['document_status'])] for r in selected.to_dict('records')]
        search_text=''.join('<li>'+esc(r['query'])+'</li>' for r in query.to_dict('records')) or '<li>Busca individual ainda não realizada.</li>'
        card=f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(ident)}</title><style>body{{max-width:1050px;margin:2rem auto;padding:1rem;font:17px/1.65 system-ui;color:#183447}}table{{border-collapse:collapse;width:100%;font-size:.86rem}}td,th{{padding:.5rem;border-bottom:1px solid #ccd9df;text-align:left}}.scroll{{overflow:auto}}.limit{{padding:1rem;background:#fff8e9}}a{{color:#075f8a}}</style><h1>{esc(ident)}</h1><p>Município TSE {esc(case['municipality'])}; grupo {esc(case['group'])}; prioridade documental {esc(case['priority'])}.</p><p class="limit">{esc(LIMIT)}</p><p>Busca individual: {esc(search_label)}. Situação do confronto: {esc(case['document_status'])}. A confirmação causal não é automatizada.</p><div class="scroll">{tbl(['Indicador local','Contagem','Evidência necessária / limite','Confronto'],issue_values)}</div><h2>Buscas registradas</h2><ul>{search_text}</ul><h2>Documentos e questões</h2><p>Procurar ata da mesa receptora e registro de atendimento/substituição com a identificação exata acima. Os tipos são necessidades, não comprovação de existência.</p><p><a href="../{case['request_draft']}">Minuta local, não enviada</a> · <a href="../relatorio.html">Inventário completo</a> · <a href="../confronto.csv">Confrontos por apontamento</a></p><p>{esc(GATE)}</p></html>'''
        card=card.replace(esc(LIMIT),esc(limit)).replace(esc(case['document_status']),esc(status_names.get(case['document_status'],case['document_status'])))
        (dest/case['card']).write_text(card,encoding='utf8')
        values=[case['uf'],case['municipality_name_1'],f"{case['zone']}/{case['section']}",case['turn'],case['issues'],search_label]
        all_rows.append(values)
        if case['priority']=='inicial':initial.append(values)
        rows.append('<tr class="case" data-uf="'+esc(case['uf'])+'" data-priority="'+esc(case['priority'])+'" data-research="'+('sim' if case['individual_searches'] else 'nao')+'">'+''.join('<td>'+esc(v)+'</td>' for v in values)+'<td><a href="'+case['card']+'">Ficha</a></td></tr>')
    headers=['UF','Município','Zona/seção','Turno','Apontamentos','Busca individual']
    kind_names={'noticia_agregada':'Notícia agregada','contexto_geral':'Contexto geral','orientacao_geral':'Orientação geral','norma_geral':'Norma geral','canal_de_acesso':'Canal de acesso','ata_julgamento':'Ata de julgamento'}
    source_rows=[[r.source_id,kind_names.get(r.kind,r.kind),r.scope] for r in sources.itertuples(index=False)]
    lead=f"Dossiê de {summary['section_turns']} unidades seção/turno, com {summary['issue_rows']} apontamentos preservados. Foram registradas {summary['individual_searches']} buscas individuais e {summary['reviewed_context_sources']} fontes de contexto revisadas; nenhuma evidência específica dos casos foi obtida."
    if summary['specific_evidence_entries']:
        lead=lead.replace('nenhuma evidência específica dos casos foi obtida',f"{summary['specific_evidence_entries']} evidências específicas registradas, com alcance indicado nas fichas")
    overview=[['Inventário',summary['section_turns'],'Unidades seção/turno com apontamentos'],['Busca individual realizada',summary['units_with_individual_search'],'Sem ata ou atendimento específico obtido'],['Busca individual ainda não realizada',summary['units_without_individual_search'],'Não tratadas como buscas sem resultado'],['Evidências específicas registradas',summary['specific_evidence_entries'],'Ausência de obtenção, não prova de inexistência']]
    options=''.join('<option>'+esc(uf)+'</option>' for uf in sorted(cases.uf.unique()))
    source_links=''.join('<li>'+esc(r.source_id)+' — <a href="'+esc(r.url)+'">'+esc(r.title)+'</a>: '+esc(r.scope)+'</li>' for r in sources.itertuples(index=False))
    links=[('casos.csv','28 unidades e cobertura da pesquisa'),('confronto.csv','33 apontamentos e situação documental'),('buscas.csv','Seis consultas individuais e hashes'),('resultados_busca.csv','Resultados examinados e decisão de uso'),('fontes.csv','Fontes de contexto e proveniência'),('documentos_necessarios.csv','Necessidades documentais, sem pedidos enviados'),('evidencias_registradas.json','Registro de evidências específicas'),('resumo.json','Síntese e preservação'),('relatorio.pdf','PDF'),('../logs/relatorio.html','Análise anterior dos logs'),('../../../../docs/ATAS.md','Método e reprodução')]
    page=f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Atas e registros operacionais — dossiê 2026</title><style>body{{font:17px/1.65 system-ui;color:#183447;background:#f1f5f7;margin:0}}main{{max-width:1100px;margin:auto;background:white;padding:2rem}}h1{{line-height:1.2}}h2{{color:#12677a}}table{{border-collapse:collapse;width:100%;font-size:.86rem}}td,th{{padding:.5rem;text-align:left;border-bottom:1px solid #ccd9df}}th{{background:#edf4f7}}.limit{{padding:1rem;border-left:5px solid #bd7427;background:#fff8e9}}.scroll{{overflow:auto}}a{{color:#075f8a}}select{{font:inherit;padding:.4rem}}[hidden]{{display:none}}</style><main><p>Etapa 5 · pesquisa e confronto documental</p><h1>Pesquisa registrada; causas dependem de documentos específicos</h1><p>{esc(lead)}</p><p class="limit">{esc(LIMIT)}</p>{tbl(['Frente','Unidades / registros','Interpretação'],overview)}
<h2>O que foi feito</h2><p>{esc(METHOD)}</p><p>{esc(GATE)}</p><p>Uma busca do segundo turno retornou o boletim do TRE-BA sobre 60 substituições no primeiro turno, sem identificação da seção selecionada. Ele foi mantido como notícia agregada; não confirma substituição em Campo Formoso nem explica a composição dos logs.</p><h2>Seis unidades da pesquisa inicial</h2><div class="scroll">{tbl(headers,initial)}</div>
<h2>Inventário e fichas</h2><label>UF <select id="uf"><option value="all">Todas</option>{options}</select></label> <label>Prioridade <select id="priority"><option value="all">Todas</option><option value="inicial">Inicial</option><option value="acompanhamento">Acompanhamento</option></select></label> <label>Busca individual <select id="research"><option value="all">Todas</option><option value="sim">Realizada</option><option value="nao">Não realizada</option></select></label><p id="count" aria-live="polite">28 unidades exibidas</p><div class="scroll"><table><thead><tr>{''.join('<th>'+esc(v)+'</th>' for v in headers)}<th>Detalhe</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Fontes e limites</h2><ul>{source_links}</ul><p>Os hashes identificam capturas textuais, não os bytes HTTP originais nem autenticação independente. Documentos gerais foram consultados, mas não contam como atas/atendimentos de uma unidade.</p><h2>Próximo passo executável</h2><p>{esc(NEXT)}</p><p>Obter os documentos específicos pelos canais públicos ou por solicitações expressamente autorizadas, registrar arquivo original, origem e hash, e revisar o vínculo com cada apontamento. Corroboração de um registro não é explicação automática de sua causa; discordância permanece a revisar, sem classificação de persistência.</p><h2>Tabelas e reprodução</h2><ul>{''.join('<li><a href="'+url+'">'+esc(label)+'</a></li>' for url,label in links)}</ul></main><script>const selects=[document.querySelector('#uf'),document.querySelector('#priority'),document.querySelector('#research')];function filter(){{let total=0;document.querySelectorAll('.case').forEach(e=>{{e.hidden=!selects.every(s=>s.value==='all'||e.dataset[s.id]===s.value);if(!e.hidden)total++}});document.querySelector('#count').textContent=total+' unidades exibidas'}}selects.forEach(s=>s.addEventListener('change',filter));filter();</script></html>'''
    (dest/'relatorio.html').write_text(page.replace(esc(LIMIT),esc(limit)),encoding='utf8')
    pdf_headers=['UF','Município','Zona/seção','Tº','Apontamentos','Busca individual']
    styles=pdf_styles();story=[heading('Atas e registros operacionais — 2026','inicio',styles),p(lead,styles,'Deck'),p(limit,styles),
        table(['Frente','Unidades / registros','Interpretação'],overview,[WIDTH*.36,WIDTH*.16,WIDTH*.48],styles,small=True),
        heading('Seis unidades pesquisadas individualmente','prioridades',styles,level=1),table(pdf_headers,initial,[WIDTH*x for x in (.06,.28,.15,.08,.17,.26)],styles,small=True),
        PageBreak(),heading('Método e fontes de contexto','metodo',styles),p(METHOD,styles),p(GATE,styles),
        table(['Fonte','Tipo','Alcance'],source_rows,[WIDTH*.09,WIDTH*.22,WIDTH*.69],styles,small=True)]
    for offset in range(0,len(all_rows),14):
        story.extend([PageBreak(),heading(f'Inventário {offset+1}–{min(offset+14,len(all_rows))}','inventario-'+str(offset),styles),
            p('São unidades seção/turno, com motivos potencialmente sobrepostos. “Não realizada” distingue ausência de busca individual de busca sem documento obtido. Todas possuem ficha e minuta local não enviada.',styles,'Small'),
            table(pdf_headers,all_rows[offset:offset+14],[WIDTH*x for x in (.06,.28,.15,.08,.17,.26)],styles,small=True)])
    story.extend([PageBreak(),heading('O que falta para o confronto','pendencias',styles),p(NEXT,styles),p(limit,styles),
        p('A notícia do TRE-BA sobre 60 substituições refere-se ao primeiro turno e ao estado, sem identificação da seção selecionada. Não foi usada para explicar o caso de Campo Formoso. As atas de julgamento encontradas também não substituem atas da mesa receptora.',styles),
        p('As minutas pedem identificação exata de ano, turno, município, zona/seção e localização da anotação. Questões específicas tratam de log aninhado, identificadores, OpenSession, impressora, ligações e cronologia; nenhum dado pessoal ou escolha individual é solicitado.',styles),
        p('Registre os originais e seus hashes em uma nova versão. Fontes específicas poderão corroborar ou contradizer um registro dentro do escopo revisado; esta rotina não confirma causalidade ou persistência automaticamente. Demais pendências PKIX, CEPESC, layout oficial e BU independente continuam separadas.',styles),
        p('Comando local: eleicoes auditoria --output outputs/2026 --data data --etapa atas. Tabelas, 28 fichas e 28 minutas no HTML; método e fontes em docs/ATAS.md. Os resultados anteriores permanecem preservados.',styles)])
    AnalysisPDF(dest/'relatorio.pdf',title='Atas e registros operacionais — 2026',styles=styles).build(story)
