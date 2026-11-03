"""Síntese de artefatos locais: unidades explícitas, sem nova ingestão ou inferência causal."""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb

from .sources import write_json


def number(value):
    if value is None:
        return "não avaliada"
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{value:,}".replace(",", ".") if isinstance(value, int) else str(value)


def coverage_counts(nominal, attendance):
    """Não transforma ausências em zero: exige valores publicados nas duas fontes."""
    keys = ["year", "turn", "uf", "municipality", "zone"]
    missing = nominal.loc[nominal.status.eq("cobertura divergente")]
    joined = missing.merge(attendance, on=keys, how="left", validate="many_to_one")
    compatible = (joined.attendance_sections.eq(0) & joined.attendance_official.eq(0)
                  & joined.official_votes.eq(0))
    return {"geographic_units": len(missing[["uf", "municipality", "zone"]].drop_duplicates()),
            "turn_units": len(missing[keys].drop_duplicates()), "candidate_rows": len(missing),
            "compatible_zero_attendance_rows": int(compatible.sum()),
            "unresolved_rows": int((~compatible).sum())}


def persistence_status(raw_value):
    return {"value": None, "unit": "divergências persistentes confirmadas",
            "status": "não investigado", "raw_compatibility_value": raw_value,
            "interpretation": "A confirmação de persistência não foi realizada. O zero do resumo legado não demonstra ausência de irregularidades."}


def build_synthesis(output, *, write=True):
    output = Path(output)
    saved = json.loads((output / "resumo.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "fontes_utilizadas.json").read_text(encoding="utf-8"))
    con = duckdb.connect(config={"threads": 2, "memory_limit": "1GB"})
    con.execute("SET enable_progress_bar = false")
    def frame(name, query="SELECT * FROM read_parquet(?)"):
        return con.execute(query, [str(output / f"{name}.parquet")]).df()
    metrics = []
    def add(key, label, value, unit, source, status="realizado", interpretation=""):
        metrics.append(dict(id=key, label=label, value=int(value) if value is not None else None,
                            unit=unit, source=source, status=status, interpretation=interpretation))
    try:
        counts = frame("indicadores_secoes", """SELECT count(*) observed,
            count(*) FILTER(WHERE comparable) comparable,
            count(*) FILTER(WHERE comparable AND NOT small) eligible,
            count(*) FILTER(WHERE NOT comparable) excluded,
            count(*) FILTER(WHERE small) small,
            count(*) FILTER(WHERE comparable AND small) comparable_small,
            count(*) FILTER(WHERE statistical_alert) combined,
            count(*) FILTER(WHERE robust_flag) robust,
            count(*) FILTER(WHERE flag_5pp) cutoff5,
            count(*) FILTER(WHERE flag_10pp) cutoff10,
            count(*) FILTER(WHERE flag_15pp) cutoff15,
            count(*) FILTER(WHERE flag_10pp AND robust_flag) overlap
            FROM read_parquet(?)""").iloc[0].to_dict()
        descriptions = {
            "observed": ("Universo observado", "unidades de seção, Brasil + exterior"),
            "comparable": ("Comparação territorial válida", "unidades de seção"),
            "eligible": ("Elegíveis para triagem estatística", "unidades de seção comparáveis e não pequenas"),
            "excluded": ("Sem comparação territorial válida", "unidades de seção"),
            "small": ("Menos de 50 comparecentes em algum turno", "unidades de seção, categoria sobreposta"),
            "comparable_small": ("Comparáveis, mas pequenas", "unidades de seção fora da triagem estatística"),
            "combined": ("Triagem combinada: união dos critérios", "unidades de seção"),
            "robust": ("Desvio robusto acima de 3,5", "unidades de seção"),
            "cutoff5": ("Limite de 5 pp ou passagem a zero", "unidades de seção elegíveis"),
            "cutoff10": ("Limite de 10 pp ou passagem a zero", "unidades de seção elegíveis"),
            "cutoff15": ("Limite de 15 pp ou passagem a zero", "unidades de seção elegíveis"),
            "overlap": ("Sobreposição: 10 pp/zero e desvio robusto", "unidades de seção"),
        }
        for key, (label, unit) in descriptions.items():
            add(key, label, counts[key], unit, "indicadores_secoes.parquet")
        for key, label, value in [("cutoff_only", "Somente limite de 10 pp/zero", counts["cutoff10"]-counts["overlap"]),
                                  ("robust_only", "Somente desvio robusto", counts["robust"]-counts["overlap"])]:
            add(key, label, value, "unidades de seção", "indicadores_secoes.parquet")
        regional = frame("indicadores_secoes", """SELECT is_exterior, count(*) observed,
            count(*) FILTER(WHERE comparable) comparable,
            count(*) FILTER(WHERE comparable AND NOT small) eligible,
            count(*) FILTER(WHERE statistical_alert) combined FROM read_parquet(?) GROUP BY is_exterior ORDER BY is_exterior""").to_dict("records")
        exclusions = frame("cobertura_por_motivo").to_dict("records")
        bu = frame("conferencia_bu", "SELECT status,count(*) records FROM read_parquet(?) GROUP BY status").to_dict("records")
        add("bu_matching", "Concordância BU × resultado por seção", sum(r["records"] for r in bu if r["status"] == "concordante"),
            "linhas de votação por seção/código/turno; não pessoas nem urnas distintas", "conferencia_bu.parquet",
            interpretation="Concordância de arquivos não explica o comportamento dos eleitores nem audita o equipamento de forma independente.")
        review = frame("revisao_documental")
        explained = review.loc[review.review_status.eq("explicado quanto ao alerta aritmético")]
        add("documentary_rows", "Apontamentos aritméticos originais", len(review), "linhas seção/turno", "revisao_documental.parquet")
        add("noninstalled", "Seções não instaladas: regra aritmética fora de contexto", len(explained[["uf", "municipality", "zone", "section"]].drop_duplicates()),
            "seções distintas", "revisao_documental.parquet", "explicado quanto ao apontamento",
            "Sem votação, comparecimento e abstenções zerados. Não foi estabelecido o motivo da não instalação ou o destino dos eleitores.")
        nominal = frame("reconciliacao_municipio_zona")
        attendance = frame("reconciliacao_comparecimento")
        coverage = coverage_counts(nominal, attendance)
        for key, label, unit in [("geographic_units", "Cobertura nominal: unidades geográficas", "combinações UF/município/zona"),
                                 ("turn_units", "Cobertura nominal: unidades por turno", "combinações ano/turno/UF/município/zona"),
                                 ("candidate_rows", "Cobertura nominal: linhas por candidato", "linhas de votação nominal"),
                                 ("compatible_zero_attendance_rows", "Linhas compatíveis com comparecimento zero", "linhas de votação nominal")]:
            add("coverage_"+key, label, coverage[key], unit, "reconciliacao_municipio_zona.parquet + reconciliacao_comparecimento.parquet",
                "explicado quanto ao apontamento" if coverage["unresolved_rows"] == 0 else "comparação limitada",
                "Ausência nominal compatível com comparecimento publicado zero nas duas fontes e votos oficiais zero; apontamentos brutos preservados.")
        categories = frame("reconciliacao_categorias")
        matched = categories.loc[categories.technical_category_match.eq(True)]
        add("technical_units", "Correspondência com nulos técnicos", len(matched), "unidades município/zona/turno", "reconciliacao_categorias.parquet", "explicado quanto ao apontamento")
        add("technical_votes", "Diferença nominal compensada em nulos técnicos", matched.official_null_technical.sum(), "votos, primeiro turno", "reconciliacao_categorias.parquet", "explicado quanto ao apontamento", "Correspondência aritmética; razão jurídica e operacional não estabelecida. Versões diferem.")
        zeros = frame("investigacao_zeros")
        f = zeros.loc[zeros.zero_candidate.eq(22)]
        positive = f.loc[f.positive_to_zero]
        zero_results = [("zero_flavio", "Flávio zerado no segundo turno", len(f), "seções com válidos exclusivos para Lula"),
            ("positive_zero", "Flávio: positivo para zero", len(positive), "seções"),
            ("already_zero", "Flávio já zerado no primeiro turno", int(f.already_zero.sum()), "seções"),
            ("previous_votes", "Votos anteriores nas passagens a zero", positive.previous_zero_candidate_votes.sum(), "votos no primeiro turno"),
            ("previous_max", "Máximo anterior por seção nas passagens a zero", positive.previous_zero_candidate_votes.max(), "votos no primeiro turno"),
            ("previous_lead", "Liderança anterior de Flávio nas passagens a zero", positive.margin_1_votes.gt(0).sum(), "seções"),
            ("zero_comparable", "Passagens a zero territorialmente comparáveis", positive.comparable.sum(), "seções"),
            ("zero_limited", "Passagens a zero com comparação limitada", (~positive.comparable).sum(), "seções"),
            ("zero_lula", "Lula zerado no segundo turno", zeros.zero_candidate.eq(13).sum(), "seções com válidos exclusivos para Flávio"),
            ("all_ballots", "Lula: unanimidade em todos os votos depositados", f.unanimity_all_ballots.sum(), "seções, subconjunto dos válidos exclusivos")]
        for key, label, value, unit in zero_results:
            add(key, label, value, unit, "investigacao_zeros.parquet", "comparação limitada" if key == "zero_limited" else "realizado")
        viradas = frame("investigacao_viradas", """SELECT uf,level,municipality_name_1,
            flip_to_13,flip_to_22,loss_22_5pp,loss_22_10pp,loss_22_15pp,
            votes_13_1,votes_13_2,votes_22_1,votes_22_2,
            cohort_coverage_attendance_1_pct,cohort_coverage_attendance_2_pct,
            cohort_margin_1_votes,cohort_margin_2_votes FROM read_parquet(?)""")
        for uf in ("RJ", "MG"):
            add("flips_"+uf, "Inversões municipais Flávio → Lula — "+uf, ((viradas.uf == uf) & (viradas.level == "municipio") & viradas.flip_to_13).sum(), "municípios", "investigacao_viradas.parquet")
        sensitivity = []
        for (uf, level), group in viradas.groupby(["uf", "level"], sort=True):
            sensitivity.append({"uf": uf, "level": level, "observed": len(group), **{f"loss{t}": int(group[f"loss_22_{t}pp"].sum()) for t in (5,10,15)},
                                "flip_to_lula": int(group.flip_to_13.sum()), "flip_to_flavio": int(group.flip_to_22.sum())})
        news = frame("investigacao_noticias").to_dict("records")
        rio = viradas.loc[(viradas.uf == "RJ") & (viradas.level == "municipio") & (viradas.municipality_name_1 == "RIO DE JANEIRO")]
        rio_cols = [f"votes_{c}_{t}" for c in (13,22) for t in (1,2)] + [f"cohort_coverage_attendance_{t}_pct" for t in (1,2)] + [f"cohort_margin_{t}_votes" for t in (1,2)]
        rio_values = {k: float(rio.iloc[0][k]) for k in rio_cols} if len(rio) else {}
        states = [{"uf": row.uf, **{f"votes_{c}_{t}": int(getattr(row, f"votes_{c}_{t}")) for c in (13,22) for t in (1,2)}}
                  for row in viradas.loc[viradas.level.eq("uf")].sort_values("uf").itertuples()]
        duplicate_counts = {p.stem: int(con.execute("SELECT count(*) FROM read_parquet(?)", [str(p)]).fetchone()[0]) for p in sorted(output.glob("duplicidades_*.parquet"))}
        case_paths = list((output / "fichas").glob("*.json"))
        for key, label, value, source in [("stat_cases", "Fichas estatísticas originais", sum(not p.name.startswith("documental-") for p in case_paths), "fichas/"),
                ("doc_cases", "Fichas documentais", sum(p.name.startswith("documental-") for p in case_paths), "fichas/"),
                ("directed_cases", "Fichas da investigação dirigida", len(list((output / "investigacao_fichas").glob("*.json"))), "investigacao_fichas/")]:
            add(key, label, value, "arquivos JSON; grupos podem tratar a mesma ocorrência", source,
                interpretation="Geração automática de fichas não equivale a investigação individual das causas.")
        map_summary = json.loads((output / "mapa_dados.json").read_text(encoding="utf-8"))["summary"]
        add("map_units", "Vínculo TSE–IBGE no mapa", map_summary["mapped"], "unidades municipais brasileiras", "mapa_dados.json")
        add("sources", "Arquivos eleitorais preservados", len(manifest), "arquivos TSE", "fontes_utilizadas.json")
        add("bu_files", "Arquivos de boletins de urna", sum(m["kind"] == "bu" for m in manifest), "arquivos ZIP, incluídos no total", "fontes_utilizadas.json")
        generations = nominal[["section_generation", "official_generation"]].drop_duplicates().fillna("ausente").to_dict("records")
        result = {"schema_version": 1, "year": saved["ano"], "generated": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"),
            "scope": "Síntese derivada dos artefatos locais existentes; sem nova ingestão nacional.",
            "metrics": metrics, "regional": regional, "exclusions": exclusions, "bu_status": bu,
            "nominal_coverage": coverage, "persistence": persistence_status(saved.get("divergencias_persistentes_confirmadas")),
            "historical": saved["historical"], "directed_sensitivity": sensitivity, "news": news,
            "rio_de_janeiro": rio_values, "states": states, "duplicate_groups": duplicate_counts,
            "source_versions": {"years": sorted({m["year"] for m in manifest}),
                "retrieved_utc_min": min(m["retrieved_utc"] for m in manifest), "retrieved_utc_max": max(m["retrieved_utc"] for m in manifest),
                "generations": generations, "geography": map_summary["sources"]},
            "coverage_matrix": [
                {"question": "Mudanças, zeros, viradas, participação, brancos/nulos", "status": "realizado", "evidence": "Indicadores nacionais, investigação dirigida e fichas; causas individuais não inferidas."},
                {"question": "Duplicidades e consistência BU × resultado", "status": "realizado", "evidence": "Tabelas de duplicidades e conferência linha a linha; não é auditoria independente da urna."},
                {"question": "Soma das seções não instaladas e cobertura nominal com comparecimento zero", "status": "explicado quanto ao apontamento", "evidence": "Situação oficial e zeros publicados contextualizam os apontamentos; motivos administrativos não estabelecidos."},
                {"question": "Diferença nominal e nulos técnicos", "status": "explicado quanto ao apontamento", "evidence": "Compensação aritmética nas mesmas unidades; razão jurídica e alinhamento de versões pendentes."},
                {"question": "Remanejamentos, excluídas e representatividade das coortes", "status": "comparação limitada", "evidence": "Sem correspondência oficial completa; coortes informam cobertura, sem substituir o resultado territorial."},
                {"question": "Causas jurídicas/administrativas e confirmação de persistência", "status": "não investigado", "evidence": "Não foi concluída investigação de causas ou de persistência; o zero legado não é conclusão."},
                {"question": "RDV, assinaturas digitais, logs e BU impresso/imagem", "status": "não investigado", "evidence": "Arquivos da urna e documentos físicos não foram auditados nesta execução."}],
            "recommendations": [
                "Esclarecer versões, motivo da classificação dos nulos técnicos e situação das seções sem comparecimento.",
                "Obter correspondências oficiais de remanejamentos e comparar perfis incluídos/excluídos para avaliar a representatividade das coortes.",
                "Ampliar a conferência nos casos prioritários: recontagem de RDV, assinaturas, logs e comparação com BU impresso ou imagem.",
                "Variar a quantidade de pares e examinar rankings sensíveis a MAD muito pequeno. A sensibilidade de 5/10/15 pp já foi realizada."],
            "recommendations_status": "propostas ainda não executadas"}
        if write:
            write_json(output / "sintese_analise.json", result)
        return result
    finally:
        con.close()


def metric_table(synthesis, ids=None):
    rows = synthesis["metrics"]
    return [r for r in rows if ids is None or r["id"] in ids]


EXECUTIVE_IDS = {"observed", "comparable", "eligible", "excluded", "combined", "cutoff10", "robust", "overlap", "bu_matching", "noninstalled", "technical_votes", "technical_units", "coverage_geographic_units", "coverage_turn_units", "coverage_candidate_rows", "positive_zero", "zero_flavio", "already_zero", "previous_votes", "previous_max", "previous_lead", "zero_lula", "all_ballots", "zero_comparable", "zero_limited", "flips_RJ", "flips_MG", "directed_cases", "stat_cases", "doc_cases", "map_units"}


def executive_html(synthesis):
    esc = html.escape
    rows = []
    for m in metric_table(synthesis, EXECUTIVE_IDS):
        source = m["source"].split(" + ")[0]
        status = esc(m["status"]) if source.endswith("/") else f"<a href='{esc(source)}'>{esc(m['status'])}</a>"
        rows.append(f"<tr><td>{esc(m['label'])}</td><td>{number(m['value'])}</td><td>{esc(m['unit'])}</td><td>{status}</td></tr>")
    rows = "".join(rows)
    matrix = "".join(f"<tr><td>{esc(r['question'])}</td><td>{esc(r['status'])}</td><td>{esc(r['evidence'])}</td></tr>" for r in synthesis["coverage_matrix"])
    return f"""<section id='sintese-analise'><h2>Resumo executivo: achados e cobertura</h2>
    <p>Os padrões solicitados foram pesquisados: mudanças entre turnos, passagens a zero, grandes viradas, comparecimento, brancos/nulos, duplicidades e consistência com os boletins. A investigação de todas as incongruências não está encerrada.</p>
    <div class='scroll'><table><tr><th>Resultado</th><th>Valor</th><th>Unidade</th><th>Situação e fonte</th></tr>{rows}</table></div>
    <p>As passagens de positivo para zero eram votações anteriores pequenas, sem liderança anterior de Flávio. Perder vantagem pode ocorrer mesmo ganhando votos absolutos. Concordância entre arquivos confirma os valores observados, sem explicar escolhas individuais.</p>
    <p>As ausências nominais são compatíveis com comparecimento zero nas duas fontes e votos oficiais zero. Os apontamentos originais foram preservados. A compensação em nulos técnicos é aritmética; a razão jurídica não foi estabelecida.</p>
    <p><b>Persistência: não investigada.</b> {esc(synthesis['persistence']['interpretation'])} Fichas automáticas, contagens conferidas e investigação das causas são etapas distintas; arquivos de fichas podem se sobrepor em ocorrências.</p>
    <h3>Matriz de cobertura</h3><div class='scroll'><table><tr><th>Pergunta</th><th>Situação</th><th>Evidência e limite</th></tr>{matrix}</table></div>
    <h3>Próximas análises — propostas ainda não executadas</h3><ul>{''.join('<li>'+esc(r)+'</li>' for r in synthesis['recommendations'])}</ul>
    <p><a href='sintese_analise.json'>Síntese estruturada, unidades e fontes</a>. Possibilidades de <a href='https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/como-realizar-auditoria'>auditoria descritas pelo TSE</a>.</p></section>"""


def executive_pdf(synthesis, styles):
    from reportlab.platypus import Paragraph, Spacer, PageBreak
    story = [Paragraph("Resumo executivo: achados e cobertura", styles["Heading1"])]
    story.append(Paragraph("Os padrões solicitados foram pesquisados. A investigação de todas as incongruências não está encerrada; confirmação dos valores não explica escolhas individuais.", styles["BodyText"]))
    for m in metric_table(synthesis, EXECUTIVE_IDS):
        story.append(Paragraph(html.escape(f"{m['label']}: {number(m['value'])} {m['unit']}. Fonte: {m['source']}."), styles["BodyText"]))
    story += [Spacer(1, 10), Paragraph(html.escape(synthesis["persistence"]["interpretation"]), styles["BodyText"]),
              Paragraph("Ausências nominais: compatíveis com comparecimento zero publicado nas duas fontes e zero votos oficiais. Os apontamentos originais são preservados. Fichas automáticas não equivalem a investigação das causas; a quantidade de arquivos não é quantidade de ocorrências únicas.", styles["BodyText"])]
    for r in synthesis["coverage_matrix"]:
        story += [Spacer(1, 7), Paragraph(html.escape(f"{r['question']} — {r['status']}: {r['evidence']}"), styles["BodyText"])]
    story.append(Paragraph("Propostas ainda não executadas", styles["Heading2"]))
    for r in synthesis["recommendations"]:
        story.append(Paragraph(html.escape(r), styles["BodyText"]))
    story.append(Paragraph("Referência: https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/como-realizar-auditoria. Valores, unidades e fontes: sintese_analise.json.", styles["BodyText"]))
    return story + [PageBreak()]
