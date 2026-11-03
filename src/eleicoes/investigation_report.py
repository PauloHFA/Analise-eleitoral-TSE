"""Apresentação offline da investigação dirigida, com filtros e anexos PDF."""
from __future__ import annotations

import html
import json
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.platypus import Image, LongTable, PageBreak, Paragraph, Spacer, TableStyle

from .sources import sha256


def _number(value):
    return "—" if pd.isna(value) else f"{value:,.0f}".replace(",", ".")


def _percent(value):
    return "—" if pd.isna(value) else f"{value:.1f}%"


def load_investigation(output):
    output = Path(output)
    path = output / "investigacao_resumo.json"
    if not path.exists():
        return None
    info = json.loads(path.read_text(encoding="utf-8"))
    for name, digest in info["input_hashes"].items():
        source = output / name
        fingerprint = info.get("input_fingerprints", {}).get(name)
        unchanged = source.exists() and fingerprint == [source.stat().st_size, source.stat().st_mtime_ns]
        if not unchanged and (not source.exists() or sha256(source) != digest):
            return dict(html="<section><h2>Investigação dirigida desatualizada</h2><p>As fontes analíticas mudaram. Execute eleicoes investigar para atualizar esta investigação.</p></section>", stale=True)
    con = duckdb.connect()
    con.execute("SET threads=2")
    try:
        zeros = con.execute("SELECT * FROM read_parquet(?) ORDER BY zero_candidate DESC,previous_zero_candidate_votes DESC,uf,municipality,zone,section", [str(output / "investigacao_zeros.parquet")]).df()
        projection = "level,uf,municipality,municipality_name_1,zone,section,local,comparable,pattern,votes_22_1,votes_13_1,votes_22_2,votes_13_2,margin_loss_22_pp,margin_robust_z,investigation_status,case_file,flip_to_13,flip_to_22,margin_1_votes,margin_2_votes,cohort_sections,cohort_margin_1_votes,cohort_margin_2_votes,cohort_coverage_attendance_1_pct,cohort_coverage_attendance_2_pct"
        inventory = con.execute(f"SELECT {projection} FROM read_parquet(?) WHERE selected_pattern OR level='uf' ORDER BY margin_robust_z DESC NULLS LAST,margin_loss_22_pp DESC,uf,municipality,zone,section", [str(output / "investigacao_viradas.parquet")]).df()
        news = con.execute("SELECT * FROM read_parquet(?)", [str(output / "investigacao_noticias.parquet")]).df()
        sensitivity = con.execute("""SELECT uf,level,count(*) units,
            count(*) FILTER(WHERE loss_22_5pp) loss_5pp,
            count(*) FILTER(WHERE loss_22_10pp) loss_10pp,
            count(*) FILTER(WHERE loss_22_15pp) loss_15pp,
            count(*) FILTER(WHERE loss_22_10pp AND comparable AND NOT small) eligible_loss_10pp,
            count(*) FILTER(WHERE flip_to_13) flipped_to_lula
            FROM read_parquet(?) GROUP BY uf,level ORDER BY uf,level""", [str(output / "investigacao_viradas.parquet")]).df()
    finally:
        con.close()
    cities = inventory.loc[inventory.level.eq("municipio") & (inventory.flip_to_13 | inventory.flip_to_22)].sort_values("margin_loss_22_pp", ascending=False)
    states = inventory.loc[inventory.level.eq("uf")].copy()
    statements = [
        f"Flávio sem votos válidos em {info['zero_22_second']} seções no segundo turno: em {info['positive_to_zero_22']} ele tinha votos no primeiro; em {info['already_zero_22']} já estava zerado.",
        f"Nos casos de positivo para zero, sua votação anterior somava {info['total_previous_22']} votos, com máximo de {info['max_previous_22']} por seção. Ele liderava {info['led_first_positive_to_zero_22']} dessas seções no primeiro turno. {info['comparable_positive_to_zero_22']} são comparáveis pelos critérios definidos.",
        f"Lula recebeu todos os votos depositados em {info['all_ballots_unanimous_13']} das seções em que Flávio zerou; nas demais, a unanimidade se refere aos votos válidos. O sentido inverso também foi conferido: Lula zerado em {info['zero_13_second']} seções.",
        "Margem = 100 × (Flávio − Lula) / (Flávio + Lula). A redução da margem é primeiro menos segundo turno; uma redução de 10 pp na margem não equivale a perder 10 pp da participação do candidato. Os percentuais sobre todos os votos válidos permanecem nas tabelas.",
        "Perder vantagem não exige perder votos: o adversário pode crescer mais. As fichas mostram votos dos eliminados, comparecimento, brancos e nulos; essa identidade contábil não identifica transferências individuais nem explica a causa política da mudança.",
        "Composição, aptos ou cobertura diferentes limitam a comparação. Nos municípios, a coorte usa somente as mesmas seções comparáveis, com cobertura de comparecimento nos dois turnos; seus totais não substituem o resultado territorial completo.",
        "Desvio robusto da mudança de margem: mesmos 30 pares da análise original; MAD insuficiente não gera escore. A classificação documental descreve o que os arquivos permitem verificar e não confirma persistência de irregularidade.",
    ]
    if info.get("demo"):
        statements.insert(0, "DEMONSTRAÇÃO COM DADOS SIMULADOS: as contagens desta seção não são resultados eleitorais reais.")
    if info.get("baseline_differences"):
        statements.append("As contagens diferem da consulta preliminar; conferir baseline_differences em investigacao_resumo.json antes de interpretar o conjunto.")
    graphs = output / "graficos"
    graphs.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 3.8), layout="constrained")
    ax.bar(["Tinha votos no 1º turno", "Já estava zerado"], [info["positive_to_zero_22"], info["already_zero_22"]], color=["#165e83", "#94a9b8"])
    ax.set(title="Seções com Flávio zerado no segundo turno", ylabel="Seções")
    fig.savefig(graphs / "investigacao_zeros.png", dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 3.8), layout="constrained")
    ax.bar(list(info["cities_flipped_to_13"]), list(info["cities_flipped_to_13"].values()), color="#165e83")
    ax.set(title="Municípios que passaram de Flávio para Lula", ylabel="Municípios — observação territorial")
    fig.savefig(graphs / "investigacao_viradas.png", dpi=150)
    plt.close(fig)
    columns = ["kind", "uf", "municipality_name_1", "unit", "pattern", "comparable", "votes_22_1", "votes_13_1", "votes_22_2", "votes_13_2", "margin_loss_22_pp", "margin_robust_z", "investigation_status", "case_file", "level"]
    display = []
    for kind, rows in (("zero", zeros), ("virada", inventory)):
        for row in rows.to_dict("records"):
            level = row["level"]
            row["kind"] = kind
            row["unit"] = (f"zona {row.get('zone')}, seção {row.get('section')}" if level == "secao" else
                f"zona {row.get('zone')}, local {row.get('local')}" if level == "local" else level)
            values = []
            for column in columns:
                value = row.get(column)
                if value is None or pd.isna(value):
                    value = None
                elif isinstance(value, float):
                    value = round(value, 4)
                values.append(value)
            display.append(values)
    serialized = json.dumps(display, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c")
    options = lambda values: "".join(f"<option value='{html.escape(str(v), quote=True)}'>{html.escape(str(v))}</option>" for v in sorted(set(values)))
    news_rows = "".join(f"<tr><td><a href='{html.escape(r.url, quote=True)}'>{html.escape(r.source)}</a> ({r.published})</td><td>{html.escape(r.claim)}</td><td>{_number(r.reported)}</td><td>{_number(r.observed)}</td><td>{html.escape(r.status)}</td></tr>" for r in news.itertuples())
    city_cols = ["uf", "municipality_name_1", "votes_22_1", "votes_13_1", "votes_22_2", "votes_13_2", "comparable", "cohort_sections", "cohort_coverage_attendance_1_pct", "cohort_coverage_attendance_2_pct", "cohort_margin_1_votes", "cohort_margin_2_votes"]
    labels = {"uf": "UF", "municipality_name_1": "Município", "votes_22_1": "Flávio 1º", "votes_13_1": "Lula 1º", "votes_22_2": "Flávio 2º", "votes_13_2": "Lula 2º", "comparable": "Território comparável", "cohort_sections": "Seções da coorte", "cohort_coverage_attendance_1_pct": "Cobertura coorte 1º (%)", "cohort_coverage_attendance_2_pct": "Cobertura coorte 2º (%)", "cohort_margin_1_votes": "Saldo Flávio na coorte 1º", "cohort_margin_2_votes": "Saldo Flávio na coorte 2º"}
    city_html = cities[city_cols].rename(columns=labels).to_html(index=False, escape=True, float_format=lambda v: f"{v:.2f}", na_rep="—")
    sensitivity_html = sensitivity.rename(columns={"level":"Nível", "uf":"UF", "units":"Unidades observadas", "loss_5pp":"Redução ≥5 pp", "loss_10pp":"Redução ≥10 pp", "loss_15pp":"Redução ≥15 pp", "eligible_loss_10pp":"≥10 pp comparáveis, não pequenas", "flipped_to_lula":"Viraram para Lula"}).to_html(index=False, escape=True)
    controls = f"""<label>Grupo <select id='inv-kind'><option value=''>Todos</option><option value='zero'>Unanimidades / zeros</option><option value='virada'>Viradas e margens</option></select></label>
    <label>UF <select id='inv-uf'><option value=''>Todas</option>{options([r[1] for r in display])}</select></label>
    <label>Padrão <select id='inv-pattern'><option value=''>Todos</option>{options([r[4] for r in display])}</select></label>
    <label>Comparabilidade <select id='inv-comparable'><option value=''>Todas</option><option value='true'>Comparável</option><option value='false'>Limitada</option></select></label>
    <label>Nível <select id='inv-level'><option value=''>Todos</option>{options([r[14] for r in display])}</select></label>
    <label>Município ou seção <input id='inv-search' type='search'></label>"""
    script = """<script>
    (()=>{const all=JSON.parse(document.getElementById('inv-data').textContent);let page=0;
    const ids=['kind','uf','pattern','comparable','level','search'];const el=Object.fromEntries(ids.map(k=>[k,document.getElementById('inv-'+k)]));
    function render(){const q=el.search.value.toLocaleLowerCase('pt-BR');const rows=all.filter(r=>(!el.kind.value||r[0]===el.kind.value)&&(!el.uf.value||r[1]===el.uf.value)&&(!el.pattern.value||r[4]===el.pattern.value)&&(!el.comparable.value||String(r[5])===el.comparable.value)&&(!el.level.value||r[14]===el.level.value)&&(!q||(String(r[2])+' '+r[3]).toLocaleLowerCase('pt-BR').includes(q)));
    page=Math.max(0,Math.min(page,Math.ceil(rows.length/50)-1));const body=document.getElementById('inv-body');body.replaceChildren();
    rows.slice(page*50,page*50+50).forEach(r=>{const tr=document.createElement('tr');[r[1],r[2],r[3],r[4],r[5]?'sim':'limitada',r[6],r[7],r[8],r[9],r[10],r[11],r[12]].forEach(v=>{const td=document.createElement('td');td.textContent=v===null?'—':v;tr.append(td)});const td=document.createElement('td');if(r[13]){const a=document.createElement('a');a.href=r[13];a.textContent='Ficha';td.append(a)}tr.append(td);body.append(tr)});
    document.getElementById('inv-count').textContent=rows.length+' registros; página '+(page+1)+' de '+Math.max(1,Math.ceil(rows.length/50));document.getElementById('inv-prev').disabled=page===0;document.getElementById('inv-next').disabled=(page+1)*50>=rows.length;}
    ids.forEach(k=>el[k].addEventListener(k==='search'?'input':'change',()=>{page=0;render()}));document.getElementById('inv-prev').onclick=()=>{page--;render()};document.getElementById('inv-next').onclick=()=>{page++;render()};render();})();
    </script>"""
    fragment = f"""<section id='investigacao-dirigida'><h2>Passagens a zero e grandes viradas — 2026</h2>{''.join('<p>'+html.escape(s)+'</p>' for s in statements)}
    <p>{info['fichas']} fichas dirigidas, separadas das 100 fichas da triagem original. Exterior identificado por ZZ, quando presente.</p>
    <img src='graficos/investigacao_zeros.png' alt='Seções em que Flávio ficou zerado, separadas pela votação anterior'>
    <img src='graficos/investigacao_viradas.png' alt='Municípios que viraram de Flávio para Lula nas UFs priorizadas'>
    <h3>Sensibilidade dos limites de mudança de margem</h3><p>Reduções da vantagem de Flávio onde ele liderava o primeiro turno. Contagens observadas incluem unidades não comparáveis; a coluna de elegibilidade explicita essa diferença. As inversões são incluídas mesmo abaixo dos limites.</p><div class='scroll'>{sensitivity_html}</div>
    <h3>Confronto das notícias com a base</h3><div class='scroll'><table><thead><tr><th>Fonte e data</th><th>Afirmação</th><th>Noticiado</th><th>Base local</th><th>Conferência</th></tr></thead><tbody>{news_rows}</tbody></table></div>
    <h3>Busca nos casos observados</h3><p>Filtros funcionam offline; 50 linhas por página. As viradas e reduções estão ordenadas pelo desvio robusto da margem, redução da margem e chave geográfica. Inventário completo e provas nos arquivos abaixo.</p><div style='display:flex;flex-wrap:wrap;gap:12px'>{controls}</div>
    <p id='inv-count' aria-live='polite'></p><div class='scroll'><table><thead><tr>{''.join('<th>'+h+'</th>' for h in ['UF','Município','Unidade','Padrão','Comparável','Flávio 1º','Lula 1º','Flávio 2º','Lula 2º','Perda margem Flávio (pp)','Desvio robusto','Conferência','Ficha'])}</tr></thead><tbody id='inv-body'></tbody></table></div><button id='inv-prev' type='button'>Anterior</button> <button id='inv-next' type='button'>Próxima</button>
    <noscript>Ative JavaScript para os filtros ou consulte os CSV completos.</noscript><script id='inv-data' type='application/json'>{serialized}</script>{script}
    <h3>Municípios com inversão: total completo e coorte comparável</h3><div class='scroll'>{city_html}</div>
    <p><a href='investigacao_zeros.csv'>Todas as unanimidades</a> · <a href='investigacao_viradas.csv'>Inventário territorial completo e sensibilidade</a> · <a href='investigacao_conferencia_bu.csv'>Conferências por seção/turno</a> · <a href='investigacao_noticias.csv'>Conferência das notícias</a> · <a href='investigacao_resumo.json'>Fontes, parâmetros e hashes</a></p></section>"""
    return dict(html=fragment, statements=statements, info=info, zeros=zeros, cities=cities, states=states, news=news, sensitivity=sensitivity, graphs=graphs, stale=False)


def pdf_investigation(bundle, styles):
    if bundle is None:
        return []
    if bundle.get("stale"):
        return [Paragraph("Investigação dirigida desatualizada; executar eleicoes investigar.", styles["BodyText"])]
    story = [PageBreak(), Paragraph("Passagens a zero e grandes viradas — 2026", styles["Heading1"])]
    for text in bundle["statements"]:
        story += [Paragraph(html.escape(text), styles["BodyText"]), Spacer(1, 6)]
    for name in ("investigacao_zeros.png", "investigacao_viradas.png"):
        story += [Image(str(bundle["graphs"] / name), width=440, height=186)]
    story += [Paragraph("Sensibilidade da redução da vantagem de Flávio", styles["Heading2"])]
    for r in bundle["sensitivity"].itertuples():
        story += [Paragraph(html.escape(f"{r.uf}, {r.level}: ≥5 pp {r.loss_5pp}; ≥10 pp {r.loss_10pp}; ≥15 pp {r.loss_15pp}. Elegíveis em ≥10 pp: {r.eligible_loss_10pp}; viradas para Lula: {r.flipped_to_lula}."), styles["BodyText"])]
    story += [Paragraph("Confronto das notícias", styles["Heading2"])]
    for row in bundle["news"].itertuples():
        story += [Paragraph(html.escape(f"{row.source} ({row.published}): {row.claim}. Noticiado: {row.reported}; base: {row.observed}; {row.status}."), styles["BodyText"]), Spacer(1, 5)]
    def table(headers, rows, widths):
        data = [[Paragraph(html.escape(str(v)), styles["BodyText"]) for v in headers]]
        data.extend([[Paragraph(html.escape(str(v)), styles["BodyText"]) for v in row] for row in rows])
        result = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        result.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e5edf3")), ("GRID", (0,0), (-1,-1), .25, colors.HexColor("#cad4dd")), ("VALIGN", (0,0), (-1,-1), "TOP")]))
        return result
    story += [PageBreak(), Paragraph("Unanimidades: todas as seções", styles["Heading1"]), Paragraph("As fichas JSON contêm situação, composição, registros de BU e fontes. A identificação usa UF/município TSE/zona/seção. A coluna zero identifica o candidato sem votos no segundo turno.", styles["BodyText"]), Spacer(1, 8)]
    rows = [(f"{r.uf}/{r.municipality}/{r.zone}/{r.section}", r.zero_candidate, f"{_number(r.votes_22_1)} / {_number(r.votes_13_1)}", f"{_number(r.votes_22_2)} / {_number(r.votes_13_2)}", "sim" if r.comparable else "limitada") for r in bundle["zeros"].itertuples()]
    story.append(table(["Seção", "Zero", "1º F / L", "2º F / L", "Comparação"], rows, [154, 36, 84, 84, 72]))
    story += [PageBreak(), Paragraph("Municípios com inversão de liderança", styles["Heading1"])]
    rows = [(f"{r.uf} — {r.municipality_name_1}", f"{_number(r.votes_22_1)} / {_number(r.votes_13_1)}", f"{_number(r.votes_22_2)} / {_number(r.votes_13_2)}", f"{_percent(r.cohort_coverage_attendance_1_pct)} / {_percent(r.cohort_coverage_attendance_2_pct)}") for r in bundle["cities"].itertuples()]
    story += [Paragraph("F / L = Flávio / Lula. Cobertura é a fração do comparecimento municipal contida na coorte das mesmas seções comparáveis, no 1º e 2º turnos. O HTML e os CSV trazem os saldos da coorte e a comparação territorial completa.", styles["BodyText"]), Spacer(1, 8), table(["Município", "1º F / L", "2º F / L", "Cobertura 1º / 2º"], rows, [128, 100, 100, 102])]
    return story
