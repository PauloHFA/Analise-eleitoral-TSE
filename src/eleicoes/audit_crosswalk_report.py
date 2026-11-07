"""Relatórios do cruzamento local entre logs, votação, indicadores e assinaturas."""
import html

from .pdf_layout import AnalysisPDF, WIDTH, callout, heading, p, pdf_styles, table


def render(destination, summary, units, issues, candidates, unmatched, contingency):
    esc = lambda value: html.escape("—" if value is None else str(value), quote=True)
    evidence_rows = [
        ["Unidades seção/turno com logs", summary["section_turns"], "Âncora do cruzamento"],
        ["Indicadores correspondentes", f'{summary["indicator_matches"]}/{summary["section_turns"]}',
         "Chave territorial exata; 2026"],
        ["Hashes de log correspondentes", f'{summary["signature_hash_matches"]}/{summary["section_turns"]}',
         "SHA256 do arquivo local"],
        ["Assinaturas verificadas", f'{summary["signature_crypto_valid_with_embedded_key"]}/{summary["section_turns"]}',
         "Chave embutida; sem validação de cadeia"],
        ["Linhas de votação na conferência amostral", summary["sample_vote_candidate_rows"],
         "RDV, BU binário, imagem e arquivos de resultados/BU"],
        ["Linhas amostrais discordantes", summary["sample_vote_discordant_rows"],
         "Comparação dos valores disponíveis"],
        ["Linhas da comparação nacional", summary["national_vote_candidate_rows"],
         "Correspondência por unidade e candidato"],
        ["Diferenças não nulas na comparação nacional",
         summary["national_vote_nonzero_difference_rows"], "Sem imputar ausências"],
        ["Chaves candidato sem linha nacional",
         summary["candidate_rows_without_national_match"], "Registradas como lacuna de correspondência"],
    ]
    summary_html = "".join(
        "<tr><td>" + "</td><td>".join(esc(value) for value in row) + "</td></tr>"
        for row in evidence_rows)
    gap_html = "".join(
        "<tr><td>" + "</td><td>".join(esc(row[name]) for name in (
            "year", "turn", "uf", "municipality", "zone", "section", "candidate",
            "detail")) + "</td></tr>"
        for row in unmatched.to_dict("records"))
    unit_gap_html = "".join(
        "<tr><td>" + "</td><td>".join(esc(row[name]) for name in (
            "source", "relation", "year", "turn", "uf", "municipality", "zone",
            "section", "indicator", "detail")) + "</td></tr>"
        for row in unmatched.loc[
            unmatched.relation.ne("chave candidato sem correspondência entre tabelas")
        ].to_dict("records"))
    candidate_gaps = unmatched.loc[
        unmatched.relation.eq("chave candidato sem correspondência entre tabelas")]
    pattern_html = "".join(
        "<tr><td>" + "</td><td>".join(esc(value) for value in row) + "</td></tr>"
        for row in contingency[[
            "group", "region", "has_target_error_message", "sample_vote_status",
            "national_vote_status", "section_turns",
        ]].itertuples(index=False, name=None))
    issue_rows = "".join(
        "<tr><td>" + "</td><td>".join(esc(row[name]) for name in (
            "uf", "municipality", "zone", "section", "indicator", "count",
            "sample_vote_status", "national_vote_status")) + "</td></tr>"
        for row in issues.to_dict("records"))
    report = f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cruzamento integrado — logs e votação 2026</title>
<style>body{{max-width:1180px;margin:2rem auto;padding:1rem;font:16px/1.6 system-ui;color:#183447}}
h1,h2{{color:#12677a}}table{{border-collapse:collapse;width:100%;font-size:.84rem}}
td,th{{padding:.45rem;border-bottom:1px solid #ccd9df;text-align:left;vertical-align:top}}
th{{background:#edf4f7}}.scroll{{overflow:auto}}.limit{{padding:1rem;background:#fff8e9}}
a{{color:#075f8a}}</style><main><p>Etapa local · cruzamento integrado</p>
<h1>Logs, conferência de votação, indicadores e assinaturas</h1>
<p>{summary["section_turns"]} unidades seção/turno · {summary["log_issue_rows"]} apontamentos
em {summary["log_issue_section_turns"]} unidades · {summary["sample_vote_candidate_rows"]}
linhas de votação da amostra.</p>
<p class="limit">Este cruzamento é descritivo e limitado à amostra dirigida e aos arquivos locais.
Uma chave que não encontra linha permanece ausente, nunca é convertida em zero. Concordância entre
arquivos não prova causa, independência da fonte ou regularidade integral; nenhuma causa foi confirmada.</p>
<h2>Cobertura e correspondências</h2><table><thead><tr><th>Medida</th><th>Resultado</th>
<th>Interpretação</th></tr></thead><tbody>{summary_html}</tbody></table>
<h2>Relação entre mensagem ERRO e comparação de votos</h2><p>{summary["error_units_sample_vote_concordant"]}
unidades com mensagem ERRO têm linhas amostrais concordantes; {summary["error_units_sample_vote_discordant"]}
unidades têm discordância de valor na comparação amostral; {summary["error_units_national_nonzero_difference"]}
apresentam diferença não nula na comparação nacional. Isso descreve coexistência, não causalidade.</p>
<h2>Correspondências de candidato não encontradas</h2><p>São chaves da conferência amostral sem linha correspondente
na tabela nacional por candidato. Não foram interpretadas como votos iguais a zero.</p>
<div class="scroll"><table><thead><tr><th>Ano</th><th>Turno</th><th>UF</th><th>Município</th>
<th>Zona</th><th>Seção</th><th>Candidato</th><th>Relação</th></tr></thead><tbody>{gap_html}</tbody></table></div>
<h3>Outras lacunas de unidade</h3><div class="scroll"><table><thead><tr><th>Fonte</th>
<th>Relação</th><th>Ano</th><th>Turno</th><th>UF</th><th>Município</th><th>Zona</th>
<th>Seção</th><th>Indicador</th><th>Detalhe</th></tr></thead><tbody>{unit_gap_html}</tbody></table></div>
<h2>Contingência descritiva</h2><div class="scroll"><table><thead><tr><th>Grupo amostral</th>
<th>Território</th><th>Mensagem ERRO</th><th>Conferência amostral</th>
<th>Comparação nacional</th><th>Unidades</th></tr></thead><tbody>{pattern_html}</tbody></table></div>
<h2>Apontamentos de log e estado do cruzamento</h2><div class="scroll"><table><thead><tr>
<th>UF</th><th>Município TSE</th><th>Zona</th><th>Seção</th><th>Indicador</th>
<th>Contagem</th><th>Conferência amostral</th><th>Comparação nacional</th></tr></thead>
<tbody>{issue_rows}</tbody></table></div>
<h2>Reprodução e dados completos</h2><ul><li><a href="unidades.csv">Cruzamento por unidade</a> /
<a href="unidades.parquet">Parquet</a></li><li><a href="apontamentos.csv">Apontamentos integrados</a> /
<a href="apontamentos.parquet">Parquet</a></li><li><a href="conferencia_candidatos.csv">Detalhe por candidato</a> /
<a href="conferencia_candidatos.parquet">Parquet</a></li><li><a href="sem_correspondencia.csv">Lacunas de correspondência</a> /
<a href="sem_correspondencia.parquet">Parquet</a></li><li><a href="contingencias.csv">Contingência descritiva</a> /
<a href="contingencias.parquet">Parquet</a></li><li><a href="resumo.json">Resumo e hashes</a></li>
<li><a href="relatorio.pdf">PDF</a></li></ul></main></html>'''
    (destination / "relatorio.html").write_text(report, encoding="utf-8")

    styles = pdf_styles()
    story = [
        heading("Cruzamento integrado — 2026", "inicio", styles),
        p(f"{summary['section_turns']} unidades seção/turno; {summary['log_issue_rows']} apontamentos "
          f"em {summary['log_issue_section_turns']} unidades.", styles, "Deck"),
        callout("Leitura estrita",
                "Chaves sem correspondência são lacunas, não zeros. Concordância mede somente os valores "
                "presentes nas fontes locais. O cruzamento não identifica causa nem valida independência "
                "ou confiança institucional.", styles),
        table(["Medida", "Resultado", "Alcance"], evidence_rows,
              [WIDTH * .34, WIDTH * .17, WIDTH * .49], styles, small=True),
        heading("ERRO nos logs e valores de votação", "associacao", styles, level=1),
        p(f'{summary["error_units_sample_vote_concordant"]} unidades com mensagem ERRO têm comparação '
          f'amostral concordante; {summary["error_units_sample_vote_discordant"]} têm divergência de valor; '
          f'{summary["error_units_national_nonzero_difference"]} têm diferença nacional não nula. '
          "Não se infere relação causal.", styles),
        heading("Linhas de candidato sem correspondência", "lacunas", styles, level=1),
        table(["Ano", "Turno", "UF", "Município", "Zona", "Seção", "Candidato", "Relação"],
              [[row.get(name) for name in (
                  "year", "turn", "uf", "municipality", "zone", "section", "candidate", "detail")]
               for row in candidate_gaps.to_dict("records")],
              [WIDTH * value for value in (.07, .07, .06, .16, .08, .08, .1, .38)],
              styles, small=True),
        heading("Limites e reprodução", "limites", styles, level=1),
        p("A assinatura anotada usa chave embutida; cadeia institucional e revogação não são validadas "
          "nesta etapa. A conferência amostral reúne RDV, BU binário, imagem e arquivos de resultado/BU, "
          "não um BU independente em papel. A seleção é dirigida e não estima frequências nacionais. "
          "Resumos, detalhes por candidato e valores completos estão nos CSV/Parquet acompanhados de hashes.", styles),
    ]
    AnalysisPDF(destination / "relatorio.pdf",
                title="Cruzamento integrado — logs e votação 2026", styles=styles).build(story)
