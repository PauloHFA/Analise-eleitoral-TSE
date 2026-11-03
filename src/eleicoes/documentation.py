"""README a partir de texto revisável e dos mesmos números usados no relatório."""
from __future__ import annotations

import json
from pathlib import Path

from .synthesis import number, metric_table


def table(headers, rows):
    def cell(v):
        return str(v).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows])


def render_readme(synthesis, template, validation=None, tests=None, pdf_edition=None):
    def results(ids):
        return table(["Resultado", "Valor", "Unidade", "Fonte"], [
            [m["label"], number(m["value"]), m["unit"],
             " + ".join(f"[{p}](outputs/2026/{p})" for p in m["source"].split(" + "))]
            for m in metric_table(synthesis, ids)])
    blocks = {
        "pdf_edition": (f"A edição explicativa tem **{number(pdf_edition['pages'])} páginas**, com **{number(pdf_edition['sections']['anexo-zeros']-1)} páginas até o início dos anexos**, sumário clicável, marcadores, tabelas por tema e fontes/contexto junto dos resultados. As **{number(pdf_edition['statistical_cases'])} fichas estatísticas** permanecem completas, em quadros comparativos que explicam o motivo da triagem. Contagens e hash da edição: [pdf_edicao.json](outputs/2026/pdf_edicao.json)." if pdf_edition else "Gere o PDF para registrar a edição, a paginação e o hash em `pdf_edicao.json`."),
        "overview": results({"observed", "comparable", "eligible", "excluded", "combined", "bu_matching", "noninstalled", "technical_votes", "coverage_geographic_units", "coverage_turn_units", "coverage_candidate_rows", "zero_flavio", "positive_zero", "flips_RJ", "flips_MG", "map_units"}),
        "sources": results({"sources", "bu_files"}),
        "comparability": results({"observed", "comparable", "eligible", "excluded", "small", "comparable_small"}),
        "screening": results({"combined", "robust", "cutoff5", "cutoff10", "cutoff15", "overlap", "cutoff_only", "robust_only"}),
        "documentary": results({"bu_matching", "noninstalled", "documentary_rows", "technical_votes", "technical_units", "coverage_geographic_units", "coverage_turn_units", "coverage_candidate_rows", "coverage_compatible_zero_attendance_rows"}),
        "zeros": results({"zero_flavio", "positive_zero", "already_zero", "previous_votes", "previous_max", "previous_lead", "zero_comparable", "zero_limited", "zero_lula", "all_ballots"}),
        "cases": results({"stat_cases", "doc_cases", "directed_cases"}),
        "states": table(["UF", "Flávio — 1º", "Lula — 1º", "Flávio — 2º", "Lula — 2º"],
                        [[r["uf"]] + [number(r[f"votes_{c}_{t}"]) for t in (1,2) for c in (22,13)] for r in synthesis["states"]]),
        "matrix": table(["Pergunta", "Situação", "Evidência e limite"], [[r["question"], r["status"], r["evidence"]] for r in synthesis["coverage_matrix"]]),
        "regional": table(["Universo", "Observadas", "Comparáveis", "Elegíveis", "Triagem combinada"],
                          [["Exterior" if r["is_exterior"] else "Brasil"] + [number(r[k]) for k in ("observed", "comparable", "eligible", "combined")] for r in synthesis["regional"]]),
        "exclusions": table(["Universo", "Motivo principal", "Unidades"], [["Exterior" if r["is_exterior"] else "Brasil", r["comparison_reason"], number(r["sections"])] for r in synthesis["exclusions"]]),
        "historical": table(["Ano — somente Brasil", "Observadas", "Elegíveis", "5 pp/zero", "10 pp/zero", "15 pp/zero", "Robusto", "% 10 pp/zero", "% robusto"],
                            [[r["ano"]] + [number(r[k]) for k in ("secoes_observadas", "comparaveis_ge50", "alertas_5pp", "alertas_10pp", "alertas_15pp", "alertas_robustos", "frequencia_10pp_pct", "frequencia_robusta_pct")] for r in synthesis["historical"]]),
        "directed_sensitivity": table(["UF", "Nível", "Observadas", "Perda ≥5 pp", "≥10 pp", "≥15 pp", "Flávio → Lula", "Lula → Flávio"],
                                      [[r["uf"], r["level"]] + [number(r[k]) for k in ("observed", "loss5", "loss10", "loss15", "flip_to_lula", "flip_to_flavio")] for r in synthesis["directed_sensitivity"]]),
        "news": table(["Fonte", "Afirmação", "Relatado", "Observado", "Conferência"], [[f"[{r['source']}]({r['url']})", r["claim"], number(r["reported"]), number(r["observed"]), r["status"]] for r in synthesis["news"]]),
        "duplicates": table(["Tabela de duplicidades", "Grupos registrados"], [[f"[{k}](outputs/2026/{k}.parquet)", number(v)] for k, v in synthesis["duplicate_groups"].items()]),
        "recommendations": "\n".join(f"{i}. {r}" for i, r in enumerate(synthesis["recommendations"], 1)),
        "dates": f"Anos dos arquivos eleitorais: {', '.join(map(str,synthesis['source_versions']['years']))}. Obtenção: de `{synthesis['source_versions']['retrieved_utc_min']}` a `{synthesis['source_versions']['retrieved_utc_max']}` (UTC). Datas de geração são campos dos arquivos, distintos da obtenção:",
        "generations": table(["Geração: votação por seção", "Geração: totalização nominal"], [[r["section_generation"], r["official_generation"]] for r in synthesis["source_versions"]["generations"]]),
        "geography": table(["Fonte geográfica", "Obtenção UTC", "SHA256"], [[f"[{r['source']}]({r['url']})", r["retrieved_utc"], f"`{r['sha256']}`"] for r in synthesis["source_versions"]["geography"]]),
    }
    rio = synthesis["rio_de_janeiro"]
    blocks["rio"] = table(["Rio de Janeiro, município", "1º turno", "2º turno"], [
        ["Flávio: votos totais", number(int(rio["votes_22_1"])), number(int(rio["votes_22_2"]))],
        ["Lula: votos totais", number(int(rio["votes_13_1"])), number(int(rio["votes_13_2"]))],
        ["Cobertura do comparecimento pela coorte (%)", number(rio["cohort_coverage_attendance_1_pct"]), number(rio["cohort_coverage_attendance_2_pct"])],
        ["Saldo Flávio − Lula na coorte", number(int(rio["cohort_margin_1_votes"])), number(int(rio["cohort_margin_2_votes"]))]])
    if validation and tests:
        inv, mapa = validation["investigacao_dirigida"], validation["mapa"]
        blocks["validation"] = f"Validação final registrada: **{tests}**. HTML: **{number(validation['links'])} referências de links/imagens inventariadas**, com os destinos locais verificados. PDF: **{number(validation['paginas_pdf'])} páginas**, estrutura e fonte Unicode incorporada verificadas. **{number(len(validation['tabelas']))} pares CSV/Parquet** conferidos por quantidade de linhas. JSONs lidos em modo estrito; fichas, fontes e controles verificados.\n\n" + \
            "Resultados completos: [validação da entrega](outputs/logs/validacao-entrega.log), [testes](outputs/logs/testes-documentacao.log), [coerência da síntese](outputs/logs/validacao-sintese.log) e [preservação SHA256](outputs/logs/preservacao-documentacao-conferencia.log). A contagem de links inclui referências repetidas e externas; URLs externas não foram testadas por rede nesta revisão. O validador confere correspondência analítica e provas documentais dos casos dirigidos; igualdade de contagens CSV/Parquet, isoladamente, não é igualdade de conteúdo de todas as células.\n\n" + \
            "```json\n" + json.dumps({"investigacao_dirigida": inv, "mapa": mapa}, ensure_ascii=False, indent=2) + "\n```"
    else:
        blocks["validation"] = "Validação desta revisão ainda não concluída. Consulte os registros em `outputs/logs/`; nenhum número de execução anterior é apresentado como validação desta revisão."
    for key, value in blocks.items():
        template = template.replace("{{" + key + "}}", value)
    if "{{" in template:
        raise ValueError("Marcador de documentação não preenchido")
    return template


def write_readme(root, synthesis, validation=None, tests=None):
    root = Path(root)
    template = (root / "docs/README.template.md").read_text(encoding="utf-8")
    pdf_path = root / "outputs/2026/pdf_edicao.json"
    edition = json.loads(pdf_path.read_text(encoding="utf-8")) if pdf_path.exists() else None
    (root / "README.md").write_text(render_readme(synthesis, template, validation, tests, edition), encoding="utf-8")
