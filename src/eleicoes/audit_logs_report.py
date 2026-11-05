"""Relatório de contagens operacionais; nunca imprime mensagens dos logs."""
import html
from collections import Counter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.platypus import PageBreak
from .pdf_layout import AnalysisPDF, pdf_styles, p, heading, table, picture, WIDTH

OFFICIAL = 'https://www.justicaeleitoral.jus.br/fato-ou-boato/checagens/2022/logs-das-urnas-eletronicas-sao-dados-publicos-e-nao-revelam-votos-de-eleitores'
LIMIT = 'São contagens de mensagens, não pessoas, votos afetados ou interrupções físicas medidas. O nível ERRO é atribuído pelo software que gerou o log. A seleção é dirigida e não permite estimar frequências nacionais. Não se atribuem causas ou fraude aos eventos.'
METHOD = 'Os 48 ZIPs originais são conferidos por SHA256 e tamanho. Todos os membros logd.dat, inclusive o aninhado, são lidos em memória com CRC e limites. O layout observado tem seis campos separados por tabulação e texto Latin-1; o token hexadecimal final é conferido apenas na sintaxe. Não se verifica o algoritmo desse token nem se afirma homologação do layout.'
TIME = 'As datas-alvo configuradas são 04/10/2026 e 25/10/2026. Registros anteriores e posteriores ficam em categorias separadas; os arquivos do segundo turno podem carregar histórico do primeiro. Os horários são os declarados no próprio log, sem fuso autenticado. Retrocessos são medidos na ordem física do mesmo membro; relógios de membros distintos não são unidos. Não se deduplicam linhas automaticamente.'
MARKERS = 'Presença de urna pronta, início de encerramento e geração do BU não demonstra cobertura contínua. Falta de uma mensagem não demonstra ausência da operação. Ligações entre marcos são contadas apenas dentro do mesmo membro e quando a ordem temporal permite; não se mede duração de paralisação nem se presume troca de equipamento por identificadores distintos.'
TRUST = 'A conferência anterior das assinaturas de hardware e hashes do ZIP é vinculada por SHA256. Confiança até raiz oficial e revogação continuam pendentes na etapa PKIX. A leitura de um log não supre essa evidência. Também permanecem abertos CEPESC, layout oficial, BU de origem independente e esclarecimentos operacionais/documentais.'
CONTEXT = 'A posição dos erros é calculada apenas quando o mesmo membro tem marcos compatíveis, relógio sem retrocesso na data-alvo e um único identificador de hardware. “Após o início do encerramento” não comprova que a operação terminou ou que não houve efeito. Sem essas condições, o contexto fica não classificável. Nenhuma mensagem é declarada normal ou explicada sem documento operacional.'


def chart(destination, counts):
    labels = ['anterior', 'data_alvo', 'posterior']
    values = [int(counts.loc[counts.window.eq(w) & counts.level.eq('ERRO'), 'count'].sum()) for w in labels]
    fig, ax = plt.subplots(figsize=(8.4, 2.4), layout='constrained')
    bars = ax.bar(['Antes da data-alvo', 'Na data-alvo', 'Depois da data-alvo'], values, color=['#758b99', '#12677a', '#b7762c'])
    ax.bar_label(bars, padding=3)
    ax.set_ylabel('Registros de nível ERRO')
    ax.set_title('Histórico e dia do turno são universos distintos', fontsize=11)
    ax.set_ylim(0, max(values + [1]) * 1.25)
    ax.spines[['top', 'right']].set_visible(False)
    fig.savefig(destination / 'erros_por_janela.png', dpi=160)
    plt.close(fig)


def render(destination, summary, units, counts, issues):
    esc = lambda value: html.escape(str(value))
    chart(destination, counts)
    number = lambda value: f'{value:,}'.replace(',', '.')
    lead = f"Foram analisados {summary['section_turns']} arquivos de {summary['sections']} seções nos dois turnos: {summary['payloads']} membros textuais, incluindo {summary['nested_payloads']} aninhado. Há {number(summary['records'])} registros válidos, dos quais {number(summary['target_records'])} nas datas-alvo."
    finding = f"Nas datas-alvo: {summary['target_error_records']} registros de nível ERRO em {summary['units_with_target_errors']} unidades seção/turno; {summary['target_alert_records']} registros de nível ALERTA. Há {summary['review_rows']} apontamentos em {summary['review_units']} unidades, com possível sobreposição entre motivos."
    overview = [
        ['Leitura', number(summary['records']), f"{summary['invalid_rows']} linhas não interpretadas; {summary['payloads']} membros incluídos"],
        ['Antes da data-alvo', number(summary['earlier_records']), 'Preparação e histórico; não somar aos eventos do dia'],
        ['Na data-alvo', number(summary['target_records']), '04/10 no 1º; 25/10 no 2º; conforme relógio declarado'],
        ['Depois da data-alvo', str(summary['later_records']), 'Janela própria, sem classificação automática'],
        ['Cronologia', str(summary['target_clock_regressions']), 'Retrocessos na data-alvo, dentro do mesmo membro'],
        ['Marcos incompletos', str(summary['units_with_incomplete_markers']), 'Unidades com ausência de pelo menos um dos três marcos'],
        ['Mais de um identificador', str(summary['units_multiple_target_hardware']), 'Unidades na data-alvo; não inferir substituição sem documento'],
    ]
    issue_counts = issues.groupby('indicator', as_index=False).agg(rows=('section', 'size'))
    issue_names = dict(boots_between_markers='Ligação entre marcos', impressora_erro_desconhecido='Erro desconhecido da impressora',
        impressora_falha='Mensagem de falha da impressora', nested_payloads='Membro de log aninhado',
        reinicio_solicitado='Solicitação de reinício', target_clock_regressions='Ordem temporal não monotônica',
        target_error_records='Mensagens de nível ERRO', target_hardware_identifiers='Mais de um identificador de hardware',
        invalid_rows='Linhas não interpretadas', overlap_previous_members='Sobreposição entre membros',
        marker_status='Marcos incompletos', target_records='Sem registros na data-alvo')
    issue_table = [[issue_names.get(r.indicator,r.indicator), r.rows] for r in issue_counts.itertuples(index=False)]
    error_names = {'mr_desmontagem_erro':'Desmontagem de MR', 'opensession_erro':'OpenSession', 'impressora_erro_desconhecido':'Erro da impressora'}
    context_names = {'apos_ultimo_inicio_encerramento':'Após o último início de encerramento', 'antes_da_primeira_prontidao':'Antes da primeira prontidão', 'entre_prontidao_e_inicio_encerramento':'Entre prontidão e início de encerramento', 'nao_classificavel_por_marcos':'Contexto não classificável pelos marcos'}
    error_table = [[error_names.get(r['event'],r['event']),context_names.get(r['context'],r['context']),r['count']] for r in summary['target_errors_by_type_context']]
    html_rows, pdf_rows = [], []
    issue_keys = {tuple(r[k] for k in ('year', 'turn', 'uf', 'municipality', 'zone', 'section')) for r in issues.to_dict('records')}
    for row in units.sort_values(['uf', 'municipality', 'zone', 'section', 'turn']).to_dict('records'):
        flagged = tuple(row[k] for k in ('year', 'turn', 'uf', 'municipality', 'zone', 'section')) in issue_keys
        values = [row['uf'], row['municipality'], f"{row['zone']}/{row['section']}", row['turn'], row['target_error_records'], row['target_alert_records'], row['urna_ligada'], row['energia_bateria'], 'Incompletos' if row['marker_status'].startswith('marcos_incompletos') else 'Presentes']
        pdf_rows.append(values)
        html_rows.append('<tr class="unit" data-uf="'+esc(row['uf'])+'" data-group="'+esc(row['group'])+'" data-review="'+('sim' if flagged else 'nao')+'">'+''.join('<td>'+esc(v)+'</td>' for v in values)+'</tr>')
    def tbl(headers, rows):
        return '<table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
    headers = ['UF', 'Mun. TSE', 'Zona/seção', 'Turno', 'ERRO', 'ALERTA', 'Ligação', 'Bateria', 'Marcos']
    links = [('relatorio.pdf', 'PDF'), ('unidades.csv', 'Unidades, marcos, hashes e grupos'), ('membros.csv', 'Membros internos e cobertura'), ('contagens.csv', 'Todas as contagens por janela, módulo, nível e regra'), ('erros_contexto.csv', 'Erros por tipo e posição em relação aos marcos'), ('pendencias.csv', 'Todos os apontamentos e justificativas'), ('comparacao_turnos.csv', 'Comparação descritiva dos dois turnos'), ('regras.csv', 'Regras locais e expressões exatas'), ('protocolo.json', 'Política de leitura e privacidade'), ('resumo.json', 'Síntese e versões'), ('../caminho_pkix/relatorio.html', 'Confiança criptográfica: etapa preservada'), ('../../../../docs/LOGS.md', 'Método, limites e reprodução')]
    options = ''.join('<option>'+esc(uf)+'</option>' for uf in sorted(units.uf.unique()))
    page = f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Eventos dos logs — amostra 2026</title><style>body{{font:17px/1.65 system-ui;color:#183447;background:#f1f5f7;margin:0}}main{{max-width:1100px;margin:auto;background:white;padding:2rem}}h1{{line-height:1.2}}h2{{color:#12677a;margin-top:2rem}}table{{border-collapse:collapse;width:100%;font-size:.88rem}}td,th{{padding:.5rem;text-align:left;border-bottom:1px solid #ccd9df}}th{{background:#edf4f7}}.scroll{{overflow:auto}}.limit{{background:#fff8e9;border-left:5px solid #bd7427;padding:1rem}}.finding{{background:#edf4f7;padding:1rem}}img{{max-width:100%}}a{{color:#075f8a}}select{{font:inherit;padding:.4rem}}[hidden]{{display:none}}@media(max-width:650px){{main{{padding:1rem}}}}</style><main>
<p>Etapa 5 · eventos operacionais · amostra dirigida</p><h1>O que os logs registram e o que ainda precisa de esclarecimento</h1><p>{esc(lead)}</p><p class="finding">{esc(finding)}</p><p class="limit">{esc(LIMIT)}</p><div class="scroll">{tbl(['Indicador','Registros / unidades','Leitura correta'],overview)}</div><img src="erros_por_janela.png" alt="Contagens de registros ERRO separadas entre antes, na data-alvo e depois"><p>As janelas são definidas separadamente para cada turno. A mesma linha histórica pode estar em arquivos de ambos os turnos; estes não são somados como eventos únicos da eleição.</p>
<h2>Método e limites</h2><p>{esc(METHOD)}</p><p>{esc(TIME)}</p><p>{esc(MARKERS)}</p><p>{esc(TRUST)}</p><p>Os eventos são classificados por mensagens fixas locais. Não se publicam mensagens brutas, nomes, identificações pessoais, teclas, biometria ou sequência/horário de votação individual. A explicação oficial da Justiça Eleitoral sobre logs e sigilo é de <a href="{OFFICIAL}">2022</a>; não é um dicionário de eventos de 2026.</p>
<h2>Que tipos de erro foram registrados?</h2><div class="scroll">{tbl(['Tipo local','Posição em relação aos marcos','Registros'],error_table)}</div><p>{esc(CONTEXT)}</p><h2>Apontamentos para revisão</h2><div class="scroll">{tbl(['Indicador','Unidades seção/turno'],issue_table)}</div><p>Motivos podem se sobrepor. Erro registrado não demonstra divergência nos totais. Contagens antes/depois, regras e evidência por unidade estão nas tabelas completas.</p>
<h2>Unidades nas datas-alvo</h2><p>Ligação e bateria são mensagens, não quantidades comprovadas de reinícios ou falhas. “Presentes” indica os três marcos, sem provar continuidade. A comparação entre turnos é descritiva e não presume o mesmo equipamento.</p><label>UF <select id="uf"><option value="all">Todas</option>{options}</select></label> <label>Grupo <select id="group"><option value="all">Todos</option><option value="prioritario">Prioritário</option><option value="comparacao">Comparação</option></select></label> <label>Revisão <select id="review"><option value="all">Todas</option><option value="sim">Com apontamento</option><option value="nao">Sem os apontamentos selecionados</option></select></label><p id="count" aria-live="polite">48 unidades exibidas</p><div class="scroll"><table><thead><tr>{''.join('<th>'+esc(x)+'</th>' for x in headers)}</tr></thead><tbody>{''.join(html_rows)}</tbody></table></div>
<h2>Tabelas, fontes e reprodução</h2><ul>{''.join('<li><a href="'+url+'">'+esc(label)+'</a></li>' for url,label in links)}</ul><h2>Próximo passo documental</h2><p>Confrontar os apontamentos com atas de seção e registros de atendimento/substituição, especialmente onde há conteúdo aninhado, identificadores distintos ou mensagens de erro. Nenhuma causa foi confirmada apenas pelo log; nenhum contato externo foi enviado.</p></main><script>const selects=[document.querySelector('#uf'),document.querySelector('#group'),document.querySelector('#review')];function filter(){{let total=0;document.querySelectorAll('.unit').forEach(e=>{{e.hidden=!selects.every(s=>s.value==='all'||e.dataset[s.id]===s.value);if(!e.hidden)total++}});document.querySelector('#count').textContent=total+' unidades exibidas'}}selects.forEach(s=>s.addEventListener('change',filter));filter();</script></html>'''
    (destination / 'relatorio.html').write_text(page, encoding='utf8')
    styles = pdf_styles()
    story = [heading('Eventos dos logs — amostra 2026', 'inicio', styles), p(lead, styles, 'Deck'), p(finding, styles), p(LIMIT, styles),
             table(['Indicador', 'Registros / unidades', 'Leitura correta'], overview, [WIDTH*x for x in (.27,.16,.57)], styles, small=True),
             picture(destination/'erros_por_janela.png', max_height=150), PageBreak(), heading('Tipos de erro e contexto', 'erros', styles),
             table(['Tipo local','Posição em relação aos marcos','Registros'],error_table,[WIDTH*.27,WIDTH*.57,WIDTH*.16],styles,small=True),
             p(CONTEXT,styles),p('As expressões técnicas são classificadas por regras fixas e não revelam pessoas ou escolhas. Desmontagem de MR, OpenSession e erro da impressora são mensagens distintas; sua contagem não determina causa, duração nem impacto nos totais.',styles),
             p('Consulte erros_contexto.csv para o vínculo entre tipo, membro e seção/turno. Os apontamentos completos estão em pendencias.csv. A classificação é exploratória e continua dependente de documentação operacional.',styles),
             PageBreak(), heading('Método, fontes e interpretação', 'metodo', styles),
             p(METHOD, styles), p(TIME, styles), p(MARKERS, styles), p(TRUST, styles),
             p('Mensagens e dados pessoais não são exportados. As regras locais não constituem um dicionário oficial; a publicação da Justiça Eleitoral de 2022 explica o alcance dos logs e está vinculada no HTML. Os arquivos digitais não são uma observação independente do equipamento.', styles)]
    for offset in range(0, len(pdf_rows), 16):
        story.extend([PageBreak(), heading(f'Unidades {offset+1}–{min(offset+16,len(pdf_rows))}', 'unidades-'+str(offset), styles),
            p('Contagens somente na data-alvo do respectivo turno. Ligação/bateria são mensagens. Marcos presentes não provam cobertura contínua. Mun. = código TSE; Z/S = zona/seção.', styles, 'Small'),
            table(['UF','Mun.','Z/S','Tº','Erro','Alerta','Liga','Bat.','Marcos'], pdf_rows[offset:offset+16], [WIDTH*x for x in (.06,.11,.12,.06,.08,.09,.08,.08,.32)], styles, small=True)])
    story.extend([PageBreak(), heading('Pendências e reprodução', 'pendencias', styles),
        table(['Indicador','Unidades seção/turno'], issue_table, [WIDTH*.7,WIDTH*.3], styles, small=True),
        p('Os apontamentos completos, com identificação territorial, motivo e valores, estão em pendencias.csv. Não há classificação automática de fraude, persistência ou impacto nos votos.', styles),
        p('Próxima conferência: atas e registros operacionais de atendimento/substituição. Conteúdo aninhado e identificadores diferentes precisam de contexto documental. A concordância anterior RDV/BU não é explicação causal para esses eventos.', styles),
        p('Reprodução: eleicoes auditoria --output outputs/2026 --data data --etapa logs. Usar uma pasta nova com --dest para preservar versões. Método, fontes e tabelas completas em docs/LOGS.md e no HTML.', styles)])
    AnalysisPDF(destination/'relatorio.pdf', title='Eventos dos logs — amostra 2026', styles=styles).build(story)
