"""Relatórios estáticos portáveis, tabelas completas e fichas rastreáveis."""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak

from .sources import write_json
from .documentary import review_exported_issues
from .investigation_report import load_investigation, pdf_investigation
from .map_report import load_map, pdf_map
from .synthesis import build_synthesis, executive_html, executive_pdf

NOTICE = ("Análise exploratória de dados agregados. Uma mudança observada, um alerta estatístico "
          "e uma divergência documental são categorias distintas. Nenhuma delas, isoladamente, "
          "demonstra fraude nem identifica como uma pessoa votou.")


def fmt(value):
    if value is None or pd.isna(value):
        return "indisponível"
    if isinstance(value, (float, np.floating)):
        return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return str(value)


def dictionary(columns):
    quantities = {"aptos": "Eleitorado apto publicado pelo TSE, sem redistribuir a correção nacional de 39 registros.",
        "attendance": "Quantidade de eleitores comparecentes no turno.", "abstention": "Quantidade de abstenções no turno.",
        "valid": "Soma de votos dos candidatos presidenciais (números de 1 a 94), anterior a eventual tratamento jurídico na totalização.",
        "blank": "Votos brancos, código 95.", "null_votes": "Votos nulos, código 96.",
        "other_votes": "Votos com outros códigos, preservados separadamente, sem presumir sua destinação.",
        "municipality": "Código TSE do município, distinto do código IBGE.", "zone": "Número da zona eleitoral.",
        "section": "Número da seção eleitoral; identifica-se em conjunto com UF, município e zona.",
        "local": "Número do local de votação na zona e município.", "local_name": "Nome do local publicado no arquivo oficial.",
        "local_address": "Endereço do local publicado no arquivo oficial; não foi geocodificado.",
        "turnout": "Taxa de comparecimento / aptos (fração de 0 a 1).",
        "blank_share": "Fração de brancos / comparecentes.", "null_share": "Fração de nulos / comparecentes.",
        "generation": "Data e hora de geração publicadas no arquivo; não é o momento de obtenção.",
        "membership": "Conjunto ordenado de zonas/seções na unidade territorial; usado para validar a composição entre turnos."}
    exact = {
        "comparable": "Mesma composição de seções e aptos; fontes completas e sem conflito aritmético; não estabelece identidade dos votantes.",
        "statistical_alert": "Elegível e mudança >=10 pp, passagem a zero ou desvio robusto >3,5; critério exploratório.",
        "robust_max": "Maior |mudança - mediana dos 30 pares| / (1,4826 * MAD). MAD zero implica indicador inconclusivo.",
        "peer_ids": "Identificadores UF/município/zona/seção dos 30 pares, separados por |; o próprio alvo é excluído.",
        "max_change_pp": "Maior mudança absoluta em pp: participação dos finalistas, comparecimento, brancos e nulos.",
        "small": "Menos de 50 comparecentes em algum turno: somente descrição, sem alerta estatístico de seção.",
        "non_finalist_pool_1": "Votos dos eliminados + brancos + nulos no primeiro turno; não estima transferências de pessoas.",
        "observed_extreme": "Mudança bruta >=10 pp ou candidato que passa a zero, inclusive unidades não comparáveis; não constitui alerta validado.",
        "coverage": "both: existe nos dois turnos; left_only: só primeiro; right_only: só segundo.",
        "priority": "Ordem de revisão: maior desvio robusto, maior mudança em pp e chave geográfica como desempate.",
    }
    rows = []
    for c in columns:
        if c in exact:
            text = exact[c]
        elif c in quantities or (c.endswith(("_1", "_2")) and c[:-2] in quantities):
            text = quantities.get(c, quantities.get(c[:-2], "")) + (f" Turno {c[-1]}." if c.endswith(("_1", "_2")) else "")
        elif c.startswith("delta_share_"):
            text = "Participação do candidato nos votos válidos do segundo turno menos a do primeiro, em pontos percentuais."
        elif c == "delta_turnout_pp":
            text = "100 * (comparecimento_2 / aptos_2 - comparecimento_1 / aptos_1)."
        elif c.startswith("delta_") and c.endswith("_pp"):
            text = "Mudança em pontos percentuais; brancos e nulos têm comparecimento como denominador."
        elif c.startswith("pct_"):
            text = "100 * (quantidade_2 - quantidade_1) / quantidade_1; ausente se base zero."
        elif c.startswith("delta_"):
            text = "Quantidade do segundo turno menos quantidade do primeiro turno."
        elif c.startswith("votes_"):
            text = "Quantidade de votos do candidato indicado no nome; sufixo 1/2 indica turno."
        elif c.startswith("share_"):
            text = "Participação do candidato nos votos válidos (fração de 0 a 1)."
        elif c.startswith("peer_median_"):
            text = "Mediana da mudança do indicador nos pares."
        elif c.startswith("peer_mad_"):
            text = "Mediana dos desvios absolutos à mediana nos pares (pp)."
        elif c.startswith("z_"):
            text = "Desvio robusto absoluto para o indicador; ausente se MAD insuficiente. Não é p-valor."
        elif c.startswith("zero_"):
            text = "Candidato teve votos positivos no primeiro turno e zero no segundo."
        elif c.startswith("flag_"):
            text = "Triagem para unidade comparável e >=50 comparecentes: limite de pp indicado ou passagem a zero."
        else:
            text = "Campo descritivo ou contagem; sufixo _1/_2 indica turno. Ver metodologia e fonte original."
        rows.append({"campo": c, "definicao": text})
    return pd.DataFrame(rows)


def build_report(output, current, history, summary, finalists, bu_issues, manifest, demo=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    charts = output / "graficos"
    charts.mkdir(exist_ok=True)
    stamp = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")
    label = "DEMONSTRAÇÃO COM DADOS SIMULADOS" if demo else "Análise presidencial — dados oficiais do TSE"
    domestic = current.loc[~current.is_exterior]
    name_path = output / "candidatos.csv"
    candidate_names = {}
    if name_path.exists():
        name_frame = pd.read_csv(name_path)
        candidate_names = dict(zip(name_frame.loc[name_frame.turn.eq(2), "candidate"], name_frame.loc[name_frame.turn.eq(2), "candidate_name"]))
    figures = []
    fig, ax = plt.subplots(figsize=(10, 4.5), layout="constrained")
    values = domestic.loc[domestic.comparable, "delta_turnout_pp"].dropna()
    ax.hist(values, bins=80, color="#165e83")
    ax.set(xlabel="Mudança no comparecimento (pontos percentuais)", ylabel="Seções",
           title="Distribuição das mudanças entre turnos — Brasil")
    for x in (-10, 10):
        ax.axvline(x, color="#b94932", linestyle="--")
    file = charts / "comparecimento.png"
    fig.savefig(file, dpi=160)
    plt.close(fig)
    figures.append((file, "Mudança na taxa de comparecimento; apenas seções comparáveis."))
    fig, ax = plt.subplots(figsize=(10, 4.5), layout="constrained")
    plot_columns = ["uf", "municipality", "zone", "section"] + [f"share_{c}_{t}" for c in finalists for t in (1, 2)]
    sample = domestic.loc[domestic.comparable, plot_columns].sort_values(["uf", "municipality", "zone", "section"], kind="stable")
    if len(sample) > 40000:
        sample = sample.sample(40000, random_state=2026)
    for c in finalists:
        ax.scatter(100 * sample[f"share_{c}_1"], 100 * sample[f"share_{c}_2"], s=3, alpha=.25, label=f"{c} — {candidate_names.get(c, 'candidato')}", rasterized=True)
    ax.plot([0, 100], [0, 100], color="#555", linestyle="--")
    ax.set(xlabel="Participação nos votos válidos — 1º turno (%)", ylabel="Participação — 2º turno (%)",
           title="Votação dos finalistas nas mesmas seções")
    ax.legend()
    file = charts / "votacao.png"
    fig.savefig(file, dpi=160)
    plt.close(fig)
    figures.append((file, "Gráfico amostrado até 40 mil seções; tabelas contêm o universo processado."))
    priority = current.loc[current.statistical_alert].sort_values("priority", kind="stable").head(100)
    cols = ["priority", "uf", "municipality_name_1", "municipality", "zone", "section", "max_change_pp", "robust_max", "reason", "review_status"]
    labels = {"priority": "Prioridade", "uf": "UF", "municipality_name_1": "Município", "municipality": "Código TSE",
        "zone": "Zona", "section": "Seção", "max_change_pp": "Maior mudança (pp)", "robust_max": "Desvio robusto",
        "reason": "Motivo da triagem", "review_status": "Situação"}
    def case_table(rows):
        if rows.empty:
            return "<p>Nenhum caso deste grupo entre as 100 primeiras prioridades.</p>"
        return rows[cols].rename(columns=labels).to_html(index=False, escape=True, float_format=lambda x: f"{x:.2f}", na_rep="—")
    table = "<h3>Brasil</h3>" + case_table(priority.loc[~priority.is_exterior]) + "<h3>Exterior</h3>" + case_table(priority.loc[priority.is_exterior])
    cards = []
    case_dir = output / "fichas"
    case_dir.mkdir(exist_ok=True)
    for _, row in priority.sort_values(["is_exterior", "priority"], kind="stable").iterrows():
        key = f"{row.uf}-{row.municipality}-{row.zone}-{row.section}"
        case = row.to_dict()
        case["interpretacao"] = "Mudança agregada que merece revisão; os dados não identificam transferências individuais de voto."
        case["referencia_historica"] = history
        case["fontes"] = manifest
        write_json(case_dir / f"{key}.json", _safe(case))
        display = [("Comparecentes", "attendance"), ("Aptos", "aptos"), ("Votos válidos", "valid"),
                   ("Brancos", "blank"), ("Nulos", "null_votes")] + [(f"Votos — candidato {c}", f"votes_{c}") for c in finalists]
        lines = "".join(f"<tr><td>{html.escape(title)}</td><td>{fmt(row.get(m+'_1'))}</td><td>{fmt(row.get(m+'_2'))}</td></tr>" for title, m in display)
        cards.append(f"<details><summary>{html.escape(key)} — {html.escape(str(row.reason))}</summary>"
            f"<p>{html.escape(str(row.get('municipality_name_1', '')))} — {html.escape(str(row.review_status))}</p>"
            f"<table><tr><th>Indicador</th><th>1º turno</th><th>2º turno</th></tr>{lines}</table>"
            f"<p>Conferência de BU: {html.escape(str(row.get('bu_check', 'não disponível')))}. "
            f"Pares: {int(row.get('peer_count', 0))}; {html.escape(str(row.peer_status))}.</p>"
            f"<p>Esclarecimentos possíveis a verificar: alterações no comparecimento, votos dos eliminados, "
            f"agregações, mudanças de local e versões das fontes.</p><a href='fichas/{key}.json'>Ficha completa e pares</a></details>")
    # Todos os problemas documentais permanecem separados dos 100 casos estatísticos.
    documents = []
    document_status = {}
    reviewed = review_exported_issues(output, bu_issues)
    if not reviewed.empty:
        for section_key, issue in reviewed.groupby(["uf", "municipality", "zone", "section"], dropna=False):
            name = "documental-" + "-".join(map(str, section_key))
            status = "explicado quanto ao alerta aritmético" if issue.review_status.eq("explicado quanto ao alerta aritmético").all() else "pendente de esclarecimento"
            document_status[name] = status
            write_json(case_dir / f"{name}.json", _safe({"status": status,
                "observacoes": issue.to_dict("records"), "fontes": manifest,
                "nota": "O status se refere ao motivo documentado nesta ficha; não estabelece o destino de eleitores ou uma auditoria integral da eleição."}))
            documents.append(name)
    explained_count = sum(v == "explicado quanto ao alerta aritmético" for v in document_status.values())
    pending_count = len(documents) - explained_count
    summary = dict(summary, secoes_documentais_explicadas=explained_count, secoes_documentais_pendentes=pending_count)
    documentary_notes = [
        f"Revisão das {len(documents)} seções com apontamentos: {explained_count} explicadas quanto ao alerta aritmético e {pending_count} pendentes de esclarecimento.",
        "A conferência usa o campo oficial ST_SECAO_INSTALADA, a presença de registros de votação e os valores de comparecimento e abstenções. Quando a seção está declarada não instalada, sem votação e com ambos os valores zerados, a igualdade comparecimento + abstenções = aptos não é usada para concluir inconsistência da votação. A seção continua fora da comparação entre turnos.",
        "A revisão explica o apontamento de soma; não determina por que a seção não foi instalada nem onde seus eleitores puderam votar. A tabela de apontamentos originais foi preservada; a classificação revisada está em revisao_documental.csv e nas fichas.",
    ]
    totalization_notes = []
    reconciliation_path = output / "reconciliacao_municipio_zona.csv"
    if reconciliation_path.exists():
        reconciliation = pd.read_csv(reconciliation_path)
        pending = reconciliation.loc[reconciliation.status.ne("concordante")]
        numeric = pending.loc[pending.difference.notna() & pending.difference.ne(0)]
        missing = pending.loc[pending.status.eq("cobertura divergente")]
        totalization_notes.append(
            f"Conferência de totalização: {len(pending)} linhas município/zona/candidato com apontamentos brutos, "
            f"incluindo {len(numeric)} diferenças numéricas e {len(missing)} ausências nominais (ver síntese e revisão). "
            "Essas contagens são linhas da conferência, não seções ou ocorrências de fraude.")
        for (turn, candidate), rows in numeric.groupby(["turn", "candidate"]):
            totalization_notes.append(
                f"Turno {int(turn)}, candidato {int(candidate)}: diferença somada seção menos totalização "
                f"de {fmt(rows.difference.sum())} votos em {len(rows)} linhas. "
                f"Geração dos resultados por seção: {', '.join(sorted(rows.section_generation.dropna().unique()))}; "
                f"geração da totalização: {', '.join(sorted(rows.official_generation.dropna().unique()))}.")
        categories_path = output / "reconciliacao_categorias.csv"
        if categories_path.exists():
            categories = pd.read_csv(categories_path)
            matched = categories.loc[categories.technical_category_match.eq(True)]
            if len(matched):
                linked = numeric.merge(matched[["year", "turn", "uf", "municipality", "zone"]],
                    on=["year", "turn", "uf", "municipality", "zone"], how="inner")
                totalization_notes.append(
                    f"Conferência por categoria: em {len(matched)} unidades município/zona/turno, {fmt(matched.official_null_technical.sum())} "
                    f"votos correspondem exatamente aos nulos técnicos oficiais. Nessas mesmas zonas, a diferença "
                    "nos votos nominais é compensada pela diferença nos nulos, com brancos e total de votos iguais. "
                    f"Essa correspondência abrange {len(linked)} linhas de diferença nominal. Trata-se de uma "
                    "explicação aritmética compatível com reclassificação; a razão jurídica ou operacional não foi "
                    "estabelecida. Os valores e diferenças originais permanecem preservados.")
        if len(pending):
            totalization_notes.append(
                "Os totais municipais, estaduais e nacionais não estão integralmente reconciliados com uma "
                "mesma versão oficial. Diferenças entre datas de geração e tratamento dos votos precisam "
                "ser esclarecidas antes de concluir persistência. Lacunas não são preenchidas com zero. "
                "A concordância entre boletins e votação por seção não resolve essas pendências.")
        else:
            totalization_notes.append("As somas conferidas concordam com o arquivo de totalização obtido.")
    write_json(output / "resumo.json", _safe(dict(summary, generated=stamp, demo=demo, historical=history)))
    dictionary(current.columns).to_csv(output / "dicionario.csv", index=False, encoding="utf-8-sig")
    methods = [
        "A população de comparação exige composição de seções e aptos iguais nos dois turnos, fontes completas e ausência de conflito aritmético. Unidades excluídas continuam nas tabelas de cobertura.",
        "Seções com agregações declaradas ficam fora da comparação de pares individuais. Nas tabelas por local, município e UF, a composição inclui os membros declarados nos boletins quando disponíveis. Mudanças na lista de agregação tornam a comparação indisponível, mesmo se o total de aptos for igual.",
        "Votos dos candidatos são divididos por votos válidos; comparecimento por aptos; brancos e nulos por comparecentes. Percentuais com base zero são ausentes.",
        "Pares: 30 seções do mesmo município, completando na UF, próximas em ln(1 + aptos), comparecimento e participação de todos os candidatos no primeiro turno. Centralização pela mediana e escala pelo desvio padrão na UF; o próprio alvo é excluído. Escalas menores ou iguais a 1e-12 são substituídas por 1.",
        "Desvio robusto = |mudança - mediana dos pares| / (1,4826 × MAD). MAD zero resulta em indicador inconclusivo. Limite 3,5 é exploratório; não se calculam p-valores ou probabilidades de fraude.",
        "Limites de 5, 10 e 15 pp são apresentados como sensibilidade. Passagem de votos positivos para zero é triada separadamente. Seções com menos de 50 comparecentes são apenas descritivas.",
        "2018 e 2022 fornecem referências de frequência por eleição, sem identificar as mesmas seções ou presumir continuidade dos candidatos. Comparações múltiplas podem gerar muitos alertas; a lista é uma triagem.",
        "A nota do TSE de 2026 informa 39 registros de aptos duplicados por transferência temporária. Não houve desconto arbitrário nas seções; taxas locais preservam o denominador publicado e esta limitação.",
        "Mudanças de local: esta execução compara códigos, endereços e agregações publicados nos arquivos oficiais. Não incorpora uma exportação completa do painel Capilaridade do SIG-TSE, que retornou HTTP 403 na consulta automatizada. Códigos iguais não descartam mudança física de endereço; casos prioritários exigem confirmação com o TRE.",
        "Votação por seção e BU não constituem auditorias independentes do equipamento: são representações do resultado da urna. A conferência verifica consistência entre arquivos. Diferenças na totalização exigem revisão do tratamento jurídico e da versão.",
    ]
    links = "".join(f"<li><a href='{html.escape(x.name)}'>{html.escape(x.name)}</a></li>" for x in sorted(output.glob("*.csv")))
    sources = "".join(f"<li><a href='{html.escape(m['url'])}'>{html.escape(Path(m['path']).name)}</a> — SHA256 {html.escape(m['sha256'])}; obtido {html.escape(m['retrieved_utc'])}</li>" for m in manifest)
    summary_labels = {"alertas_estatisticos": "seções na triagem combinada", "alertas_brasil": "triagem combinada — Brasil", "alertas_exterior": "triagem combinada — exterior",
        "secoes_documentais_explicadas": "seções do grupo documental original explicadas quanto ao apontamento",
        "secoes_documentais_pendentes": "seções ainda pendentes no grupo documental original (não inclui revisão jurídica da totalização)",
        "linhas_com_incompatibilidade_aritmetica": "registros com diferença na igualdade aritmética bruta (ver revisão documental)"}
    displayed_summary = [(summary_labels.get(k, k.replace('_', ' ')), v) for k, v in summary.items()
                         if k != "divergencias_persistentes_confirmadas"]
    displayed_summary.append(("confirmação de persistência de divergências", "não realizada; zero legado não é conclusão"))
    displayed_summary += [("desvio robusto >3,5 — Brasil", int((domestic.robust_flag).sum())),
        ("limite de 10 pp ou passagem a zero — Brasil", int(domestic.flag_10pp.sum()))]
    summary_table = pd.DataFrame(displayed_summary, columns=["Indicador", "Resultado"]).to_html(index=False, escape=True)
    history_table = pd.DataFrame(history).rename(columns=lambda c: c.replace("alertas_", "triagem_").replace("_", " ")).to_html(index=False, escape=True) if history else "<p>Histórico não processado.</p>"
    doc_links = "".join(f"<li><a href='fichas/{html.escape(n)}.json'>{html.escape(n)}</a> — {html.escape(document_status[n])}</li>" for n in documents)
    investigation = load_investigation(output)
    electoral_map = load_map(output)
    synthesis = build_synthesis(output) if investigation and electoral_map and not demo else None
    body = f"""<!doctype html><html lang='pt-BR'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>{label}</title><style>body{{font:16px/1.6 system-ui;margin:0;background:#f1f5f8;color:#172c3d}}main{{max-width:1200px;margin:auto;padding:32px}}h1,h2{{line-height:1.2}}section,details{{background:white;padding:20px;margin:18px 0;border-radius:8px}}.notice{{border-left:5px solid #b94932;padding:16px;background:#fff4e7}}table{{border-collapse:collapse;font-size:13px;width:100%}}td,th{{text-align:left;border-bottom:1px solid #dce2e8;padding:7px}}.scroll{{overflow:auto}}img{{max-width:100%}}li{{margin-bottom:8px}}a{{color:#165e83}}summary{{cursor:pointer;font-weight:bold}}.sources{{overflow-wrap:anywhere;font-size:12px}}</style>
    <main><h1>{label}</h1><p>Gerado em {stamp} (America/Sao_Paulo).</p><p class='notice'>{NOTICE}</p>
    <nav>{"<a href='#mapa-eleitoral'>Mapa azul/vermelho</a> · " if electoral_map else ''}{"<a href='#investigacao-dirigida'>Passagens a zero, viradas e fichas</a>" if investigation else ''}</nav>
    {executive_html(synthesis) if synthesis else ''}
    {electoral_map['html'] if electoral_map else ''}
    <section><h2>Cobertura e resultados da triagem</h2><div class='scroll'>{summary_table}</div>
    <p>A triagem combinada reúne limites de variação e desvio robusto. Mudanças de 10 pp podem ser comuns quando os votos passam a se concentrar em dois finalistas. O desvio robusto mede o afastamento em relação aos pares; as frequências históricas ajudam a contextualizar ambos. O universo processado e as exclusões estão nas tabelas, incluindo o exterior separadamente.</p></section>
    <section><h2>Gráficos</h2>{''.join(f'<figure><img src="graficos/{p.name}" alt="{html.escape(c)}"><figcaption>{c}</figcaption></figure>' for p,c in figures)}</section>
    <section><h2>Referências históricas e sensibilidade</h2><div class='scroll'>{history_table}</div></section>
    {investigation['html'] if investigation else ''}
    <section><h2>Até 100 casos prioritários para revisão</h2><div class='scroll'>{table}</div></section>
    <section><h2>Fichas dos casos</h2>{''.join(cards)}</section>
    <section><h2>Revisão documental e aritmética</h2>{''.join('<p>'+html.escape(t)+'</p>' for t in documentary_notes)}<p><a href='revisao_documental.csv'>Revisão completa por seção e turno</a></p><ul>{doc_links}</ul></section>
    <section><h2>Conferência com a totalização</h2>{''.join('<p>'+html.escape(t)+'</p>' for t in totalization_notes)}<p><a href='reconciliacao_municipio_zona.csv'>Todas as linhas por município e zona</a>; <a href='reconciliacao_totais.csv'>totais municipais, estaduais e nacionais</a>; <a href='reconciliacao_comparecimento.csv'>aptos e comparecimento</a>.</p></section>
    <section><h2>Metodologia e limites</h2><ul>{''.join('<li>'+html.escape(t)+'</li>' for t in methods)}</ul></section>
    <section><h2>Tabelas completas</h2><ul>{links}<li><a href='dicionario.csv'>Dicionário</a></li><li><a href='resumo.json'>Resumo e estado da execução</a></li></ul><p>CSV em UTF-8; versões Parquet acompanham as tabelas analíticas.</p></section>
    <section class='sources'><h2>Fontes e versões</h2><p>Tribunal Superior Eleitoral — dados abertos, atribuição CC-BY. Os hashes identificam os arquivos obtidos; não equivalem a verificação de assinatura digital.</p><ul>{sources}</ul></section></main></html>"""
    (output / "relatorio.html").write_text(body, encoding="utf-8")
    fonts = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    pdfmetrics.registerFont(TTFont("DejaVu", str(fonts / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(fonts / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu", boldItalic="DejaVu-Bold")
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "DejaVu-Bold" if style.name in ("Title", "Heading1", "Heading2") else "DejaVu"
    story = [Paragraph(html.escape(label), styles["Title"]), Spacer(1, 12), Paragraph(NOTICE, styles["BodyText"])]
    if synthesis:
        story += executive_pdf(synthesis, styles)
    story.append(Paragraph("A triagem combinada reúne mudanças absolutas e desvio em relação aos pares. A concentração em dois finalistas pode produzir mudanças grandes e comuns; consulte as frequências históricas e o desvio robusto separadamente.", styles["BodyText"]))
    for key, value in displayed_summary:
        story.append(Paragraph(f"<b>{html.escape(str(key))}:</b> {html.escape(fmt(value))}", styles["BodyText"]))
    for file, caption in figures:
        story += [Spacer(1, 10), Image(str(file), width=440, height=198), Paragraph(caption, styles["BodyText"])]
    story += [PageBreak(), Paragraph("Metodologia e limitações", styles["Heading1"])]
    for text in methods:
        story += [Paragraph(text, styles["BodyText"]), Spacer(1, 8)]
    story += [Paragraph("Revisão documental e aritmética", styles["Heading1"])]
    for text in documentary_notes:
        story += [Paragraph(html.escape(text), styles["BodyText"]), Spacer(1, 8)]
    story += [Paragraph("Conferência com a totalização", styles["Heading1"])]
    for text in totalization_notes:
        story += [Paragraph(html.escape(text), styles["BodyText"]), Spacer(1, 8)]
    story += [Paragraph("Referências históricas", styles["Heading1"])]
    for hist in history:
        story += [Paragraph(html.escape(json.dumps(hist, ensure_ascii=False)), styles["BodyText"]), Spacer(1, 8)]
    story += pdf_map(electoral_map, styles)
    story += pdf_investigation(investigation, styles)
    for _, row in priority.sort_values(["is_exterior", "priority"], kind="stable").iterrows():
        region = "Exterior" if row.is_exterior else "Brasil"
        story += [PageBreak(), Paragraph(f"{region} — caso {row.uf}/{row.municipality}/{row.zone}/{row.section}", styles["Heading1"]),
                  Paragraph(html.escape(str(row.get("municipality_name_1", ""))), styles["BodyText"]),
                  Paragraph(html.escape(str(row.reason)), styles["BodyText"])]
        for title, m in [("Aptos", "aptos"), ("Comparecentes", "attendance"), ("Brancos", "blank"), ("Nulos", "null_votes")] + [(f"Candidato {c}", f"votes_{c}") for c in finalists]:
            story.append(Paragraph(f"{title}: {fmt(row.get(m+'_1'))} → {fmt(row.get(m+'_2'))}", styles["BodyText"]))
        story += [Paragraph(f"Situação: {html.escape(str(row.review_status))}. BU: {html.escape(str(row.get('bu_check', 'não disponível')))}.", styles["BodyText"]),
                  Paragraph(f"Maior desvio robusto: {fmt(row.robust_max)}; maior mudança: {fmt(row.max_change_pp)} pp. Pares e fontes na ficha JSON e no HTML.", styles["BodyText"])]
    SimpleDocTemplate(str(output / "relatorio.pdf"), pagesize=A4, title=label, author="Análise reproduzível — fonte TSE").build(story)


def _safe(obj):
    if isinstance(obj, dict):
        return {str(k): _safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe(x) for x in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (float, np.floating)):
        return float(obj) if np.isfinite(obj) else None
    if obj is pd.NA or obj is pd.NaT:
        return None
    return obj
