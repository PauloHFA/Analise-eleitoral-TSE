"""Relatórios v3 para confronto documental sem inferência causal automática."""
import html

from .audit_atas import GEO, key
from .pdf_layout import AnalysisPDF, WIDTH, callout, heading, p, pdf_styles, table

STATUS = {
    "sem_documento_especifico": "Documento específico não obtido",
    "evidencia_insuficiente": "Evidência inconclusiva ou insuficiente",
    "registro_corrobora_no_escopo": "Registro corroborado no escopo",
    "divergencia_documental_a_revisar": "Divergência documental a revisar",
}
FINDINGS = {
    "corrobora_registro": "Corrobora o registro no escopo",
    "contradiz_registro": "Contradiz o registro; requer revisão",
    "inconclusivo": "Inconclusivo",
}


def render(destination, summary, cases, issues, sources, searches, evidence, source_map):
    escape = lambda value: html.escape("—" if value is None else str(value), quote=True)
    issue_rows = []
    for row in issues.to_dict("records"):
        issue_rows.append([
            row["uf"], row["municipality"], f"{row['zone']}/{row['section']}", row["turn"],
            row["indicator"], row["count"], STATUS.get(row["document_status"], row["document_status"]),
            row["evidence_ids"], "Não confirmada",
        ])
    evidence_rows = []
    evidence_html = []
    evidence_card_rows = {}
    for item in evidence:
        source = source_map[item["source_id"]]
        identity = item["case"]
        location = (f"{identity['uf']} · município {identity['municipality']} · "
                    f"zona {identity['zone']} · seção {identity['section']} · "
                    f"{identity['turn']}º turno")
        kind = source["kind"]
        outcome = ("Escopo da consulta registrado; inconclusivo" if kind == "resposta_oficial"
                   else FINDINGS.get(item["finding"], "Inconclusivo"))
        evidence_rows.append([
            item["evidence_id"], source["source_id"], kind, location, item["indicator"],
            item["locator"], outcome,
        ])
        evidence_card_rows.setdefault(key(identity), []).append(
            [item["evidence_id"], source["title"], kind, item["indicator"],
             item["locator"], outcome, source["url"]])
        evidence_html.append(
            '<article><h3>' + escape(item["evidence_id"]) + ' · ' + escape(source["title"]) +
            '</h3><p><strong>Tipo:</strong> ' + escape(kind) +
            ' · <strong>Unidade:</strong> ' + escape(location) +
            ' · <strong>Apontamento:</strong> ' + escape(item["indicator"]) +
            '</p><p><strong>Localização:</strong> ' + escape(item["locator"]) +
            '</p><p><strong>Revisão:</strong> ' + escape(outcome) +
            ' · ' + escape(item["justification"]) +
            '</p><p><a href="' + escape(source["url"]) + '">' + escape(source["url"]) +
            '</a> · SHA256 local: <code>' + escape(source["capture_sha256"]) +
            '</code></p></article>')

    source_links = ''.join(
        '<li>' + escape(row.source_id) + ' · ' + escape(row.kind) + ' · <a href="' +
        escape(row.url) + '">' + escape(row.title or row.url) + '</a></li>'
        for row in sources.itertuples(index=False))
    (destination / "fichas").mkdir(exist_ok=True)
    case_rows = []
    for case in cases.to_dict("records"):
        identity = {name: case[name] for name in GEO}
        case_issues = []
        for issue in issues.to_dict("records"):
            if key(issue) == key(identity):
                case_issues.append(
                    "<tr><td>" + "</td><td>".join(escape(issue[name]) for name in (
                        "indicator", "count", "document_status", "evidence_ids",
                        "cause_status")) + "</td></tr>")
        case_evidence = []
        for item in evidence_card_rows.get(key(identity), []):
            case_evidence.append(
                '<tr><td>' + '</td><td>'.join(escape(value) for value in item[:-1]) +
                '</td><td><a href="' + escape(item[-1]) + '">Fonte oficial declarada</a></td></tr>')
        location = (f"{case['uf']} · município {case['municipality_name_1']} · "
                    f"zona {case['zone']} · seção {case['section']} · {case['turn']}º turno")
        card = f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>Ficha documental — {escape(case['case_id'])}</title><main>
<p><a href="../relatorio.html">Voltar ao relatório</a></p>
<h1>{escape(case['case_id'])}</h1><p>{escape(location)}</p>
<p>Buscas individuais registradas: {escape(case['individual_searches'])}. Causa: não confirmada.</p>
<h2>Apontamentos</h2><table><thead><tr><th>Indicador</th><th>Contagem</th>
<th>Confronto</th><th>Evidências</th><th>Causa</th></tr></thead><tbody>
{''.join(case_issues)}</tbody></table>
<h2>Documentos registrados</h2><table><thead><tr><th>ID</th><th>Fonte</th><th>Tipo</th>
<th>Indicador</th><th>Localização</th><th>Revisão</th><th>Link</th></tr></thead><tbody>
{''.join(case_evidence)}</tbody></table>
<p>Vínculo de fonte, localização e revisão não autentica automaticamente proveniência,
assinatura nem causa. Respostas oficiais registram apenas escopo consultado.</p>
</main></html>'''
        (destination / case["card"]).write_text(card, encoding="utf-8")
        research = "sim" if case["individual_searches"] else "nao"
        case_rows.append(
            '<tr class="case" data-uf="' + escape(case["uf"]) +
            '" data-priority="' + escape(case["priority"]) +
            '" data-research="' + research + '"><td>' + escape(case["uf"]) +
            '</td><td>' + escape(case["municipality_name_1"]) +
            '</td><td>' + escape(f"{case['zone']}/{case['section']}") +
            '</td><td>' + escape(case["turn"]) + '</td><td>' +
            escape(case["issues"]) + '</td><td>' +
            escape(case["individual_searches"]) + '</td><td><a href="' +
            escape(case["card"]) + '">Ficha</a></td></tr>')
    uf_options = ''.join(
        '<option>' + escape(uf) + '</option>' for uf in sorted(cases.uf.unique()))
    html_rows = ''.join(
        '<tr><td>' + '</td><td>'.join(escape(value) for value in row) + '</td></tr>'
        for row in issue_rows)
    units_label = "unidade seção/turno" if summary["section_turns"] == 1 else "unidades seção/turno"
    page = f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Confronto documental — logs eleitorais 2026</title>
<style>body{{max-width:1180px;margin:2rem auto;padding:1rem;font:16px/1.6 system-ui;color:#183447}}
h1,h2{{color:#12677a}}table{{border-collapse:collapse;width:100%;font-size:.84rem}}
td,th{{padding:.45rem;border-bottom:1px solid #ccd9df;text-align:left;vertical-align:top}}
th{{background:#edf4f7}}.scroll{{overflow:auto}}.limit{{padding:1rem;background:#fff8e9}}
article{{border-top:1px solid #ccd9df;padding:1rem 0}}code{{overflow-wrap:anywhere}}
a{{color:#075f8a}}</style><main><p>Etapa documental · versão v3</p>
<h1>Confronto por apontamento, sem confirmação automática de causa</h1>
<p>{summary['section_turns']} {units_label} · {summary['individual_searches']} buscas individuais ·
{summary['issue_rows']} apontamentos ·
{summary['registered_evidence_entries']} registros revisados ·
{summary['specific_evidence_entries']} documentos de evento específicos ·
{summary['official_response_entries']} respostas oficiais.</p>
<p class="limit">Os arquivos originais ficam preservados localmente e não são distribuídos neste relatório.
Hashes e URLs declarados não autenticam sozinhos proveniência, assinatura ou integridade jurídica.
Corroboração ou divergência limita-se ao registro e localização revisados. Causa e persistência não são
confirmadas automaticamente. Nenhum pedido foi enviado.</p>
<h2>Evidências recebidas e revisão registrada</h2>{''.join(evidence_html)}
<h2>Situação dos apontamentos</h2><div class="scroll"><table><thead><tr>
<th>UF</th><th>Município TSE</th><th>Zona/seção</th><th>Turno</th><th>Indicador</th>
<th>Contagem</th><th>Confronto documental</th><th>Evidências</th><th>Causa</th>
</tr></thead><tbody>{html_rows}</tbody></table></div>
<h2>Fontes registradas</h2><ul>{source_links}</ul>
<h2>Inventário e fichas</h2><label>UF <select id="uf"><option value="all">Todas</option>
{uf_options}</select></label> <label>Prioridade <select id="priority">
<option value="all">Todas</option><option value="inicial">Inicial</option>
<option value="acompanhamento">Acompanhamento</option></select></label>
<label>Busca individual <select id="research"><option value="all">Todas</option>
<option value="sim">Realizada</option><option value="nao">Não realizada</option></select></label>
<p id="count" aria-live="polite">{len(cases)} unidades exibidas</p>
<div class="scroll"><table><thead><tr><th>UF</th><th>Município</th><th>Zona/seção</th>
<th>Turno</th><th>Apontamentos</th><th>Buscas individuais</th><th>Ficha</th></tr></thead>
<tbody>{''.join(case_rows)}</tbody></table></div>
<h2>Reprodução e artefatos</h2><ul><li><a href="casos.csv">Inventário de unidades</a></li>
<li><a href="confronto.csv">Confronto por apontamento</a></li>
<li><a href="evidencias_registradas.json">Registro de evidências</a></li>
<li><a href="resumo.json">Síntese e hashes</a></li>
<li><a href="relatorio.pdf">Relatório PDF</a></li></ul></main>
<script>const selects=[document.querySelector('#uf'),document.querySelector('#priority'),
document.querySelector('#research')];function filter(){{let total=0;
document.querySelectorAll('.case').forEach(e=>{{e.hidden=!selects.every(s=>
s.value==='all'||e.dataset[s.id]===s.value);if(!e.hidden)total++}});
document.querySelector('#count').textContent=total+' unidades exibidas'}}
selects.forEach(s=>s.addEventListener('change',filter));filter();</script></html>'''
    (destination / "relatorio.html").write_text(page, encoding="utf-8")

    styles = pdf_styles()
    summary_rows = [
        ["Unidades seção/turno", summary["section_turns"], "Apontamentos preservados"],
        ["Registros documentais revisados", summary["registered_evidence_entries"], "Originais preservados sob data/"],
        ["Documentos de evento específicos", summary["specific_evidence_entries"], "Ata ou registro operacional"],
        ["Respostas oficiais", summary["official_response_entries"], "Escopo consultado; sempre inconclusivo"],
        ["Causas confirmadas", "Não", "A rotina não automatiza causalidade"],
    ]
    story = [
        heading("Confronto documental — 2026", "inicio", styles),
        p(f"{summary['section_turns']} unidades seção/turno e {summary['issue_rows']} apontamentos.", styles, "Deck"),
        callout("Limite de interpretação",
            "Registro corroborado não explica automaticamente a causa. Resposta oficial delimita consulta, "
            "não prova ocorrência ou inexistência. Divergência permanece para revisão.", styles),
        table(["Medida", "Valor", "Alcance"], summary_rows,
              [WIDTH * .34, WIDTH * .14, WIDTH * .52], styles, small=True),
        heading("Evidências e localização", "evidencias", styles, level=1),
        table(["ID", "Fonte", "Tipo", "Unidade", "Indicador", "Localização", "Revisão"],
              evidence_rows, [WIDTH * value for value in (.07, .08, .14, .21, .14, .18, .18)],
              styles, small=True),
        heading("Apontamentos", "apontamentos", styles, level=1),
        table(["UF", "Município", "Zona/seção", "Turno", "Indicador", "N", "Confronto", "IDs", "Causa"],
              issue_rows, [WIDTH * value for value in (.05, .14, .12, .06, .15, .05, .19, .1, .14)],
              styles, small=True),
        heading("Proveniência e pendências", "limites", styles, level=1),
        p("A versão v3 preserva a captura v2 e os novos arquivos originais por SHA256. A URL e a revisão "
          "são declarações; não houve autenticação automática de assinatura ou da origem do arquivo. "
          "Pedidos não foram enviados. As demais frentes PKIX/LCR, CEPESC, layout oficial e BU independente "
          "permanecem separadas.", styles),
        p("As 28 fichas e minutas permanecem locais. A ausência de documento obtido em buscas anteriores "
          "não foi convertida em evidência de ausência de ocorrência.", styles),
    ]
    AnalysisPDF(destination / "relatorio.pdf",
                title="Confronto documental — 2026", styles=styles).build(story)
