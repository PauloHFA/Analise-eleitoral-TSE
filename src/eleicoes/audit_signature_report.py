"""Relatório do alcance efetivo das conferências de assinatura."""
import html
from reportlab.platypus import PageBreak
from .pdf_layout import AnalysisPDF,pdf_styles,p,heading,table,WIDTH

ALGORITHMS={2:'ECDSA P-521',3:'CEPESC',4:'Ed521'}
LIMIT='A verificação ECDSA usa a chave do certificado embutido no próprio arquivo. A cadeia até uma âncora oficial e a revogação não foram validadas. Isso comprova a equação criptográfica com essa chave, sem demonstrar por si só a autenticidade institucional do certificado.'
METHOD='O esquema local descreve explicitamente o layout observado: listas SW e HW seguidas do modelo/algoritmo, com tags de contexto para os campos opcionais. O leitor exige a versão 2, consumo integral, recodificação byte a byte, nomes seguros e únicos, listas SW/HW compatíveis e correspondência de seção/turno. É uma adaptação inferida dos arquivos; não foi localizada uma especificação oficial compatível. O esquema consultado na primeira entrega continua preservado e não foi alterado.'
CRYPTO='Para ECDSA P-521, a mensagem é o hash SHA512 de 64 bytes e a verificação aplica SHA512 a essa mensagem, conforme a rotina de exemplo do pacote técnico consultado. Os mesmos inteiros r/s são recodificados de BER para DER quando necessário. Uma mudança de bytes que preserve apenas o hash local não equivale à validação da assinatura. Ed521 e CEPESC permanecem sem verificador neste projeto; não são tratados como inválidos.'
TIME='O certificado embutido é lido em PEM ou DER; o preenchimento nulo após DER é contado e registrado. A validade temporal do certificado de ponta é comparada à data declarada no VSC sob todas as hipóteses de fuso entre UTC−12 e UTC+14. Essa data não é um carimbo de tempo autenticado; a verificação não cobre a validade dos certificados emissores nem revogação.'


def render(destination,summary,frames,sample):
    files=frames['arquivos_assinados'];selected=files.loc[files.scope.eq('documento_obtido')];env=frames['envelopes'];units=frames['unidades']
    file_ok=int(selected.hash_status.eq('concordante').sum());env_ok=int(env.hash_status.eq('concordante').sum())
    hw=env.loc[env.role.eq('hw')];valid=int(hw.crypto_status.eq('valida_com_chave_embutida').sum());unsupported=int(hw.crypto_status.eq('nao_verificado_algoritmo').sum())
    intro=f"Foram lidos {summary['read_units']}/{summary['section_turns']} arquivos de assinatura, das mesmas {summary['sections']} seções nos dois turnos. Nenhum documento da amostra foi substituído e não houve nova ingestão nacional."
    outcome=f"Conferiram {file_ok}/{len(selected)} hashes SHA512 dos documentos obtidos e {env_ok}/{len(env)} hashes das listas internas. As assinaturas ECDSA das listas de hardware conferiram em {valid} unidades com a chave embutida; {unsupported} unidades usam Ed521, ainda não verificado."
    rows=[['SHA512 de BU, RDV, imagem e log',str(len(selected)),f'{file_ok} concordantes; quatro documentos × SW/HW × seção/turno'],
          ['SHA512 do conteúdo das listas SW/HW',str(len(env)),f'{env_ok} concordantes'],
          ['Assinatura ECDSA de hardware — lista interna',str(valid),'Válida com a chave embutida; cadeia não validada'],
          ['Assinatura ECDSA de hardware — documentos obtidos',str(int(selected.crypto_status.eq('valida_com_chave_embutida').sum())),'Válida com a chave embutida; vinculada aos bytes pelo SHA512'],
          ['Hardware Ed521',str(unsupported),'Não verificado; ausência de verificador não é assinatura inválida'],
          ['Software CEPESC',str(int(env.role.eq('sw').sum())),'Não verificado neste projeto'],
          ['Cadeia e revogação','48 certificados de ponta','Não validadas; nenhum total de certificados confiáveis foi inferido']]
    details=[];table_rows=[]
    for unit in units.to_dict('records'):
        f=selected;e=env
        for key in ('year','turn','uf','municipality','zone','section'):
            f=f.loc[f[key].eq(unit[key])];e=e.loc[e[key].eq(unit[key])]
        hw_row=e.loc[e.role.eq('hw')]
        status=hw_row.crypto_status.iloc[0] if len(hw_row)==1 else 'leitura_limitada'
        alg=ALGORITHMS.get(unit.get('hardware_algorithm'),'não identificado')
        label='ECDSA confere com chave embutida' if status=='valida_com_chave_embutida' else 'Não verificado (Ed521)' if unit.get('hardware_algorithm')==4 else status
        result=[unit['uf'],unit['municipality'],f'{unit["zone"]}/{unit["section"]}',unit['turn'],alg,
                f'{int(f.hash_status.eq("concordante").sum())}/{len(f)}',label]
        table_rows.append(result)
        details.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in result)+'</tr>')
    hdr=['UF','Município TSE','Zona/seção','Turno','Hardware','Hashes dos arquivos','Assinatura da lista HW']
    esc=lambda v:html.escape(str(v));simple=lambda heads,data:'<table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in heads)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in data)+'</tbody></table>'
    links=[('arquivos_assinados.csv','Entradas dos arquivos e alcance'),('envelopes.csv','Hashes e assinaturas das listas'),('certificados.csv','Certificados, validade e limites de cadeia'),('unidades.csv','Unidades e leitura do layout'),('layout_observado.asn1','Esquema local do layout observado'),('resumo.json','Síntese e versões de dependências'),('relatorio.pdf','PDF desta conferência'),('../relatorio/relatorio.html','Primeira conferência amostral preservada'),('../../../../docs/ASSINATURAS.md','Método e reprodução')]
    page=f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Assinaturas da amostra — 2026</title><style>body{{font:17px/1.65 system-ui;color:#183447;background:#f1f5f7;margin:0}}main{{max-width:1100px;background:white;margin:auto;padding:2rem}}h1{{line-height:1.2}}h2{{color:#12677a;margin-top:2rem}}table{{border-collapse:collapse;width:100%;font-size:.85rem}}td,th{{padding:.5rem;border-bottom:1px solid #ccd9df;text-align:left}}th{{background:#edf4f7}}.scroll{{overflow:auto}}.finding,.limit{{padding:1rem;border-left:5px solid #12677a;background:#edf4f7}}.limit{{border-color:#bd7427;background:#fff8e9}}a{{color:#075f8a}}</style><main>
<p>Etapa 5 · incremento de leitura e verificação das assinaturas</p><h1>Hashes conferidos e ECDSA verificada com a chave embutida; cadeia e Ed521 permanecem abertos</h1><p>{esc(intro)}</p><p class="finding">{esc(outcome)}</p><p class="limit">{esc(LIMIT)}</p>
<h2>O que os números representam</h2><div class="scroll">{simple(['Conferência','Quantidade','Resultado e alcance'],rows)}</div><p>Os {len(selected)} registros são conferências dos mesmos 192 documentos em duas listas (SW/HW), não arquivos ou urnas distintos. As listas mencionam {summary['listed_file_entries']} entradas; {summary['outside_scope_entries']} não correspondem aos quatro tipos obtidos e ficam fora do escopo. Os arquivos de assinatura já obtidos são o quinto tipo da amostra.</p>
<h2>Formato observado e método</h2><p>{esc(METHOD)}</p><p>{esc(CRYPTO)}</p><p>{esc(TIME)}</p><p>As listas SW/HW são comparadas também entre si. Os testes controlados incluem arquivo alterado, chave errada, assinatura truncada, campos adicionais, nomes inseguros, duplicidades e algoritmo não suportado. Os documentos não obtidos não são marcados como erros de hash.</p>
<h2>As 48 unidades seção/turno</h2><div class="scroll"><table><thead><tr>{''.join('<th>'+esc(v)+'</th>' for v in hdr)}</tr></thead><tbody>{''.join(details)}</tbody></table></div>
<h2>Fontes, tabelas e reprodução</h2><ul>{''.join('<li><a href="'+link+'">'+esc(label)+'</a></li>' for link,label in links)}</ul>
<p>Fontes: <a href="https://dadosabertos.tse.jus.br/dataset/resultados-2026-arquivos-transmitidos-para-totalizacao">catálogo oficial dos documentos</a>; <a href="https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/como-realizar-auditoria">procedimentos de auditoria do TSE</a>. O código técnico de terceiros serviu como referência de estrutura; as contagens desta entrega foram calculadas sobre os originais locais, sem adotar resultados de outros projetos.</p>
<h2>Próximos procedimentos</h2><p>Confirmar o layout por documentação oficial, implementar e validar Ed521 com referência e vetores independentes, validar a cadeia e revogação com âncoras oficiais, analisar eventos dos logs e obter BU independente. O resultado não constitui auditoria integral e não explica as escolhas dos eleitores.</p></main></html>'''
    (destination/'relatorio.html').write_text(page,encoding='utf8')
    styles=pdf_styles();story=[heading('Assinaturas da amostra — 2026','inicio',styles),p(intro,styles,'Deck'),p(outcome,styles),p(LIMIT,styles),table(['Conferência','Quantidade','Alcance'],rows,[WIDTH*.36,WIDTH*.13,WIDTH*.51],styles,small=True),p('Contagens de verificações não são contagens de urnas distintas. As 384 verificações de arquivos correspondem a 192 documentos em duas listas. A amostra permanece dirigida, sem inferência nacional de irregularidades.',styles,'Small'),PageBreak(),heading('Método e limitações','metodo',styles),p(METHOD,styles),p(CRYPTO,styles),p(TIME,styles),p('Não foi buscada uma combinação de algoritmo e mensagem que simplesmente produzisse aprovação: o procedimento ECDSA segue a mensagem descrita na rotina técnica de referência e é testado com arquivos e chaves alterados. O esquema observado tem nome e hash próprios e não substitui o esquema anterior.',styles),p('Próximos procedimentos: documentação oficial compatível, Ed521 com vetores independentes, cadeia/revogação, logs e BU independente. Fontes e comandos completos no HTML e em docs/ASSINATURAS.md. A primeira conferência, seus relatórios e classificações continuam preservados.',styles)]
    for offset in range(0,len(table_rows),16):
        story.extend([PageBreak(),heading(f'Unidades {offset+1}–{min(offset+16,len(table_rows))}','unidades-'+str(offset),styles),p('Hashes: BU, RDV, imagem e log comparados em SW e HW. A coluna de assinatura se refere à lista de hardware; a cadeia permanece não validada em todos os casos.',styles,'Small'),table(hdr,table_rows[offset:offset+16],[WIDTH*x for x in (.06,.13,.12,.07,.16,.13,.33)],styles,small=True)])
    AnalysisPDF(destination/'relatorio.pdf',title='Assinaturas da amostra — 2026',styles=styles).build(story)
