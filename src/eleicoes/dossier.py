"""Dossiê local de diferenças nominais e categorias; não infere causas jurídicas."""
from __future__ import annotations

import csv
from datetime import datetime
import html
import io
import json
from pathlib import Path
import platform
import zipfile

import duckdb
import pandas as pd

from .analysis import export_frame
from .sources import sha256, write_json

KEY = ["year", "turn", "uf", "municipality", "zone"]
QUANTITIES = {
    "official_valid": ("QT_TOTAL_VOTOS_VALIDOS", "QT_VOTOS_NOMINAIS_VALIDOS", "QT_VOTOS_VALIDOS", "QT_VOTOS_NOMINAIS"),
    "official_blank": ("QT_VOTOS_BRANCOS",),
    "official_null_total": ("QT_TOTAL_VOTOS_NULOS", "QT_VOTOS_NULOS"),
    "official_null_regular": ("QT_VOTOS_NULOS",),
    "official_null_technical": ("QT_VOTOS_NULOS_TECNICOS",),
    "official_attendance": ("QT_COMPARECIMENTO",),
}
INPUTS = ("reconciliacao_municipio_zona.parquet", "reconciliacao_categorias.parquet",
          "reconciliacao_comparecimento.parquet", "secoes_por_turno.parquet", "fontes_utilizadas.json")


def joined(values):
    return " | ".join(sorted({str(v).strip() for v in values if pd.notna(v) and str(v).strip()})) or None


def records(frame):
    """Converte ausências pandas em null JSON, nunca em NaN literal."""
    return json.loads(frame.to_json(orient="records", force_ascii=False))


def read_raw_categories(path, year):
    """Preserva as linhas presidenciais e todos os QT_ antes da agregação."""
    rows = []
    def consume(stream, member):
        reader = csv.DictReader(stream, delimiter=";")
        for row in reader:
            if row.get("CD_CARGO") != "1":
                continue
            if int(row["ANO_ELEICAO"]) != year or int(row["NR_TURNO"]) not in (1, 2):
                raise ValueError("Ano/turno inesperado no detalhe oficial")
            rows.append(dict(year=year, turn=int(row["NR_TURNO"]), uf=row["SG_UF"],
                municipality=str(int(row["CD_MUNICIPIO"])), zone=str(int(row["NR_ZONA"])),
                member=member, source_line=reader.line_num, **row))
    path = Path(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            members = sorted(n for n in archive.namelist() if n.lower().endswith(".csv") and not n.startswith("__MACOSX"))
            members = [n for n in members if Path(n).stem.upper().endswith("_BR")] or members
            for member in members:
                with archive.open(member) as stream:
                    consume(io.TextIOWrapper(stream, encoding="latin-1", newline=""), member)
    else:
        with path.open(encoding="latin-1", newline="") as stream:
            consume(stream, path.name)
    if not rows:
        raise ValueError("Nenhuma linha presidencial no detalhe oficial")
    return pd.DataFrame(rows)


def aggregate_raw(raw):
    frame = raw[KEY].copy()
    for target, alternatives in QUANTITIES.items():
        field = next((f for f in alternatives if f in raw), None)
        values = pd.to_numeric(raw[field], errors="coerce") if field else pd.Series(float("nan"), index=raw.index)
        frame["raw_" + target] = values.where(values.ge(0) & values.mod(1).eq(0)).astype("Int64")
    frame["raw_generation"] = raw.DT_GERACAO.fillna("") + " " + raw.HH_GERACAO.fillna("")
    frame["raw_last_totalization"] = raw.get("DT_ULTIMA_TOTALIZACAO", pd.Series("", index=raw.index)).fillna("") + " " + raw.get("HH_ULTIMA_TOTALIZACAO", pd.Series("", index=raw.index)).fillna("")
    frame["raw_vote_type"] = raw.get("ST_VOTO_EM_TRANSITO", pd.Series("não informado", index=raw.index)).fillna("não informado")
    # Duas linhas da mesma partição não são interpretadas como votos adicionais.
    frame["raw_partition_conflict"] = frame.duplicated(KEY + ["raw_vote_type"], keep=False)
    frame["raw_election_id"] = raw.get("CD_ELEICAO", pd.Series("", index=raw.index))
    aggregations = {"raw_" + name: (lambda s: s.sum(min_count=len(s))) for name in QUANTITIES}
    aggregations.update(raw_generation=joined, raw_last_totalization=joined, raw_vote_type=joined,
                        raw_partition_conflict="any", raw_election_id=joined)
    out = frame.groupby(KEY, dropna=False).agg(aggregations).reset_index()
    multiple_elections = frame.groupby(KEY, dropna=False).raw_election_id.nunique().gt(1).reset_index(name="multiple_elections")
    out = out.merge(multiple_elections, on=KEY, validate="one_to_one")
    out["raw_partition_conflict"] |= out.multiple_elections
    out.loc[out.raw_partition_conflict, ["raw_" + name for name in QUANTITIES]] = pd.NA
    return out


def unique(frame, keys, name):
    if frame[keys].isna().any().any() or frame.duplicated(keys).any():
        raise ValueError(f"Chave ausente ou duplicada em {name}")


def generation_relation(section, official):
    a = pd.to_datetime(section, format="%d/%m/%Y %H:%M:%S", errors="coerce")
    b = pd.to_datetime(official, format="%d/%m/%Y %H:%M:%S", errors="coerce")
    out = pd.Series("data ausente ou inválida", index=section.index)
    out.loc[a.notna() & b.notna() & a.lt(b)] = "seção gerada antes do nominal oficial"
    out.loc[a.notna() & b.notna() & a.eq(b)] = "mesma geração informada"
    out.loc[a.notna() & b.notna() & a.gt(b)] = "seção gerada depois do nominal oficial"
    return out


def build_dossier(nominal, categories, attendance, context, raw):
    """Junta as evidências, preservando lacunas e a classificação publicada."""
    for name, frame, keys in (("nominais", nominal, KEY + ["candidate"]), ("categorias", categories, KEY),
                              ("comparecimento", attendance, KEY), ("contexto", context, KEY)):
        unique(frame, keys, name)
    nominal = nominal.copy()
    nominal["generation_relation"] = generation_relation(nominal.section_generation, nominal.official_generation)
    nominal["nonzero_difference"] = nominal.difference.notna() & nominal.difference.ne(0)
    nominal["coverage_gap"] = nominal.status.eq("cobertura divergente") | nominal.section_votes.isna() | nominal.official_votes.isna()
    nominal["unresolved_nominal"] = nominal.status.ne("concordante")
    arithmetic_bad = (nominal.difference.notna() & nominal.section_votes.notna() & nominal.official_votes.notna() &
                      nominal.difference.ne(nominal.section_votes - nominal.official_votes))
    if arithmetic_bad.any():
        raise ValueError("Diferença nominal publicada não fecha com as parcelas")
    n = nominal.groupby(KEY, dropna=False).agg(
        nominal_rows=("candidate", "size"), nominal_gap_rows=("nonzero_difference", "sum"),
        nominal_coverage_rows=("coverage_gap", "sum"), nominal_pending_rows=("unresolved_nominal", "sum"),
        nominal_zero_imputed_rows=("zero_imputed", "sum"),
        nominal_difference=("difference", lambda s: s.sum(min_count=len(s))),
        official_nominal_votes=("official_votes", lambda s: s.sum(min_count=len(s))),
        section_generation=("section_generation", joined), official_nominal_generation=("official_generation", joined),
        generation_relations=("generation_relation", joined)).reset_index()
    categories = categories.rename(columns={"status": "published_category_status", "technical_category_match": "published_technical_match"})
    # Categorias comparam soma dos votos com comparecimento; o outro arquivo
    # compara comparecentes do detalhe de seção com os do detalhe municipal.
    attendance = attendance.rename(columns={"attendance_difference": "detail_attendance_difference"})
    keys = pd.concat([f[KEY] for f in (categories, n, attendance, context, raw)], ignore_index=True).drop_duplicates()
    units = keys
    for frame in (categories, n, attendance, context, aggregate_raw(raw)):
        units = units.merge(frame, on=KEY, how="left", validate="one_to_one")
    known_equal = pd.Series(True, index=units.index)
    raw_disagrees = pd.Series(False, index=units.index)
    for name in QUANTITIES:
        a, b = units[name], units["raw_" + name]
        known_equal &= (a.notna() & b.notna() & a.eq(b)).fillna(False)
        raw_disagrees |= (a.notna() & b.notna() & a.ne(b)).fillna(False)
    units["raw_categories_confirmed"] = known_equal & ~units.raw_partition_conflict.fillna(True)
    units["raw_categories_disagree"] = raw_disagrees
    consistent = pd.Series(True, index=units.index)
    for difference, a, b in (("valid_difference", "section_valid", "official_valid"),
        ("null_total_difference", "section_null", "official_null_total"),
        ("blank_difference", "section_blank", "official_blank"),
        ("attendance_difference", "section_total", "official_attendance")):
        consistent &= (units[a].notna() & units[b].notna() & units[difference].eq(units[a]-units[b])).fillna(False)
    units["published_arithmetic_consistent"] = consistent
    clean_coverage = units.nominal_coverage_rows.eq(0) & units.nominal_pending_rows.eq(units.nominal_gap_rows)
    technical = (units.official_null_technical.gt(0) &
        (units.section_valid - units.official_valid).eq(units.official_null_technical) &
        (units.section_null - units.official_null_total).eq(-units.official_null_technical) &
        units.section_null.eq(units.official_null_regular) & units.section_blank.eq(units.official_blank) &
        units.section_total.eq(units.official_attendance) & clean_coverage &
        units.nominal_difference.eq(units.official_null_technical) & units.nominal_gap_rows.gt(0))
    units["technical_arithmetic_match"] = technical.fillna(False) & units.raw_categories_confirmed & consistent
    units["published_match_reproduced"] = units.published_technical_match.eq(units.technical_arithmetic_match).fillna(False)
    units["zero_attendance_coverage"] = (units.nominal_coverage_rows.gt(0) &
        units.attendance_sections.eq(0) & units.attendance_official.eq(0) & units.official_nominal_votes.eq(0)).fillna(False)
    category_changed = pd.Series(False, index=units.index)
    for field in ("valid_difference", "null_total_difference", "blank_difference", "attendance_difference"):
        category_changed |= units[field].notna() & units[field].ne(0)
    attendance_issue = (units.attendance_sections.isna() | units.attendance_official.isna() |
                        units.attendance_sections.ne(units.attendance_official) |
                        units.aptos_sections.isna() | units.aptos_official.isna() | units.aptos_sections.ne(units.aptos_official))
    units["selected"] = (units.nominal_pending_rows.fillna(1).gt(0) | category_changed |
                          ~units.raw_categories_confirmed | ~consistent | ~units.published_match_reproduced | attendance_issue)
    units["finding"] = "concordante no escopo aritmético"
    units.loc[units.selected, "finding"] = "pendência de conferência"
    units.loc[units.zero_attendance_coverage & units.raw_categories_confirmed, "finding"] = "lacuna nominal com comparecimento zero"
    units.loc[units.technical_arithmetic_match, "finding"] = "correspondência aritmética com nulos técnicos"
    units["documentary_cause_status"] = "não investigada neste incremento"
    units["persistence_status"] = "não investigada neste incremento"
    units["is_exterior"] = units.uf.eq("ZZ")
    units["case_id"] = units[KEY].astype(str).agg("-".join, axis=1)
    return units.sort_values(KEY).reset_index(drop=True), nominal.sort_values(KEY + ["candidate"])


def provenance(source, data, year):
    manifest = json.loads((source / "fontes_utilizadas.json").read_text(encoding="utf-8"))
    sources = []
    for kind in ("votes", "detail", "official_votes", "official_detail"):
        matches = {r["sha256"]: r for r in manifest if r.get("year") == year and r.get("kind") == kind}
        if len(matches) != 1:
            raise ValueError(f"Versão ausente ou ambígua para {kind}")
        entry = dict(next(iter(matches.values())))
        relative = Path(entry["path"].replace("\\", "/"))
        path = (data / relative).resolve()
        if not path.is_relative_to(data) or sha256(path) != entry["sha256"]:
            raise ValueError(f"Caminho ou SHA256 inválido: {kind}")
        entry.update(source_id=kind, local_path=str(path), hash_verified=True)
        sources.append(entry)
    return sources


def build_html(destination, units, nominal, sources, summary):
    esc = lambda v: html.escape(str(v))
    def number(value):
        return "ausente" if pd.isna(value) else f"{int(value):,}".replace(",", ".")
    groups = {key: frame for key, frame in nominal.groupby(KEY, dropna=False)}
    rows = []
    labels = {"section_valid": "Nominais nas seções", "official_valid": "Válidos oficiais", "section_null": "Nulos nas seções",
              "official_null_regular": "Nulos regulares oficiais", "official_null_technical": "Nulos técnicos oficiais",
              "official_null_total": "Nulos oficiais totais", "section_blank": "Brancos nas seções", "official_blank": "Brancos oficiais",
              "section_total": "Total de votos nas seções", "official_attendance": "Comparecimento oficial"}
    for row in records(units.loc[units.selected]):
        key = tuple(row[k] for k in KEY)
        candidates = groups.get(key)
        selected = candidates.loc[candidates.unresolved_nominal] if candidates is not None else pd.DataFrame()
        details = "".join(f"<tr><td>{esc(v.candidate)}</td><td>{number(v.section_votes)}</td><td>{number(v.official_votes)}</td><td>{number(v.difference)}</td><td>{'Sim (referência)' if v.zero_imputed else 'Não'}</td><td>{esc(v.status)}</td></tr>" for v in selected.itertuples())
        quantities = "".join(f"<tr><th>{label}</th><td>{number(row.get(field))}</td></tr>" for field,label in labels.items())
        generations = "".join(f"<li>{label}: {esc(row.get(field) or 'ausente')}</li>" for field,label in
            (("section_generation","Votação por seção"),("official_nominal_generation","Nominais oficiais"),
             ("raw_generation","Detalhe oficial"),("detail_generations","Detalhe por seção"),("raw_last_totalization","Última totalização informada")))
        interpretation = ("A diferença nominal é compensada pelas categorias de nulos na mesma unidade. A causa jurídica ou operacional ainda não foi investigada."
            if row["technical_arithmetic_match"] else
            "Há ausência de registros nominais com comparecimento zero nas duas fontes e zero votos nominais oficiais conhecidos. Isso não determina o motivo da ausência."
            if row["zero_attendance_coverage"] else "Este caso precisa de conferência adicional; consulte as parcelas e os registros originais nas tabelas.")
        rows.append(f'''<tr id="caso-{esc(row['case_id'])}" data-uf="{esc(row['uf'])}" data-turn="{row['turn']}" data-finding="{esc(row['finding'])}">
<td>{esc(row['uf'])}</td><td>{esc(row.get('municipality_name') or '')}<br>{esc(row['municipality'])} / zona {esc(row['zone'])}</td><td>{row['turn']}</td>
<td>{number(row['nominal_difference'])}</td><td>{number(row['official_null_technical'])}</td><td>{esc(row['finding'])}
<details><summary>Valores, versões e pendências</summary><p>{interpretation}</p><table><tbody>{quantities}</tbody></table>
<p>Linhas nominais com apontamento, por número do candidato. Os zeros implícitos da reconciliação original estão identificados; as demais ausências permanecem ausentes.</p>
<table><thead><tr><th>Candidato</th><th>Seções</th><th>Oficial</th><th>Diferença</th><th>Zero implícito na referência?</th><th>Situação original</th></tr></thead><tbody>{details}</tbody></table>
<ul>{generations}</ul><p>Relação das gerações: {esc(row.get('generation_relations'))}. Datas distintas não demonstram a causa da diferença.</p>
<p>Fontes: <a href="#fontes">votes, detail, official_votes e official_detail</a>. As versões são as do manifesto local. Campos originais, partições e linhas do CSV estão em categorias_originais.</p>
<p>Explicação documental da causa: não investigada neste incremento. Persistência: não investigada neste incremento.</p></details></td></tr>''')
    source_rows = "".join(f"<tr><th>{esc(r['source_id'])}</th><td><a href=\"{esc(r['url'])}\">{esc(r['path'])}</a><br>Obtido: {esc(r.get('retrieved_utc'))}<br>Last-Modified: {esc(r.get('remote',{}).get('Last-Modified'))}<br><code>{esc(r['sha256'])}</code></td></tr>" for r in sources)
    options = lambda values: "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in sorted(set(values)))
    page = f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dossiê de categorias e versões — {summary['year']}</title><style>
body{{font:16px/1.5 system-ui,sans-serif;margin:auto;max-width:1200px;padding:24px;color:#172337}}h1,h2{{line-height:1.2}}
table{{border-collapse:collapse;width:100%;margin:16px 0}}th,td{{border:1px solid #cad3df;padding:8px;text-align:left;vertical-align:top}}
thead{{background:#e9eff6}}code{{overflow-wrap:anywhere}}details{{margin-top:10px}}summary{{cursor:pointer;color:#15538f}}
.note{{background:#f1f5fa;padding:16px;border-left:4px solid #396fa0}}label{{display:inline-block;margin:8px}}input,select{{font:inherit;max-width:100%;padding:4px}}
@media print{{.controls{{display:none}}body{{max-width:none;padding:0}}tr{{break-inside:avoid}}}}
</style><h1>Dossiê de categorias e versões — {summary['year']}</h1>
<p>Esta etapa organiza as evidências locais por município, zona e turno. Ela confere parcelas e versões; a investigação da explicação oficial da causa continua pendente.</p>
<div class="note"><strong>{number(summary['technical_units'])} unidades por turno</strong> têm correspondência aritmética com nulos técnicos, somando <strong>{number(summary['technical_votes'])} votos</strong>.
<p>Há também {number(summary['coverage_turn_units'])} combinações município/zona/turno com lacuna nominal e comparecimento zero: {number(summary['coverage_geographic_units'])} unidades geográficas e {number(summary['coverage_candidate_rows'])} linhas por candidato. Essas três contagens têm unidades diferentes.</p></div>
<h2>Como ler as evidências</h2><p>A diferença é sempre votação nominal nas seções menos votação nominal oficial. Nas categorias, a comparação é feita dentro da mesma unidade e turno: o excesso nominal precisa coincidir com os nulos técnicos e ser compensado na diferença de nulos totais, com brancos e comparecimento concordantes. O detalhe oficial original também foi confrontado com a tabela publicada.</p>
<p>As tabelas guardam o universo completo de {number(summary['unit_turns'])} unidades por turno e os dois turnos. O relatório detalha {number(summary['selected_unit_turns'])} unidades com apontamentos, em {number(summary['selected_geographic_units'])} combinações município/zona. Zeros implícitos e situações originais permanecem registrados. A soma nacional não substitui a conferência local.</p>
<p>Ausência, conflito de partição ou geração inválida continuam identificados. Partições distintas de voto em trânsito são preservadas; duplicidades da mesma partição bloqueiam a confirmação do detalhe original. Datas não têm fuso inferido e não são datas de obtenção.</p>
<h2>Inventário verificável</h2><p>Abra os detalhes de cada linha para consultar parcelas, candidatos afetados e gerações. Os filtros funcionam localmente, sem servidor.</p>
<div class="controls"><label>UF <select id="uf"><option value="">Todas</option>{options(units.loc[units.selected,'uf'])}</select></label>
<label>Turno <select id="turn"><option value="">Todos</option><option>1</option><option>2</option></select></label>
<label>Situação <select id="finding"><option value="">Todas</option>{options(units.loc[units.selected,'finding'])}</select></label>
<label>Município/zona <input id="search" type="search"></label><p id="visible" aria-live="polite"></p></div>
<table id="cases"><thead><tr><th>UF</th><th>Município / zona</th><th>Turno</th><th>Diferença nominal, votos</th><th>Nulos técnicos, votos</th><th>Conferência e evidências</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Tabelas e reprodução</h2><p>CSV e Parquet completos: <a href="unidades.csv">unidades CSV</a> / <a href="unidades.parquet">Parquet</a>;
<a href="nominais.csv">nominais CSV</a> / <a href="nominais.parquet">Parquet</a>;
<a href="categorias_originais.csv">categorias originais CSV</a> / <a href="categorias_originais.parquet">Parquet</a>;
<a href="resumo_uf.csv">resumo por UF e turno CSV</a> / <a href="resumo_uf.parquet">Parquet</a>;
<a href="dicionario.csv">dicionário</a>; <a href="resumo.json">resumo e hashes</a>; <a href="fontes.json">manifesto das fontes</a>.</p>
<p>Executar <code>eleicoes dossie --output outputs/2026 --data data</code>. Para repetir, escolher outra pasta com <code>--dest</code>; saídas preenchidas são recusadas.</p>
<h2 id="fontes">Fontes e versões preservadas</h2><p>Os quatro arquivos locais foram conferidos por SHA256 antes e depois da execução. URLs identificam a origem e podem passar a oferecer outra versão; os hashes identificam a versão efetivamente usada. Não houve nova ingestão ou consulta à rede.</p><table>{source_rows}</table>
<h2>O que permanece pendente</h2><p>Documentação jurídica/operacional das categorias, razão das diferenças de geração, versões alternativas e motivo das unidades sem comparecimento ainda não foram investigados. A correspondência aritmética não confirma a causa nem encerra a avaliação de persistência. A classificação original e as fichas anteriores foram preservadas.</p>
<script>const rows=[...document.querySelectorAll('#cases > tbody > tr')];
function filter(){{const query=document.getElementById('search').value.toLocaleLowerCase('pt-BR');let count=0;for(const row of rows){{const match=['uf','turn','finding'].every(key=>!document.getElementById(key).value||row.dataset[key]===document.getElementById(key).value)&&row.children[1].textContent.toLocaleLowerCase('pt-BR').includes(query);row.hidden=!match;count+=match;}}document.getElementById('visible').textContent=count+' de '+rows.length+' unidades por turno';}}
for(const id of ['uf','turn','finding','search'])document.getElementById(id).addEventListener('input',filter);filter();</script></html>'''
    (destination / "relatorio.html").write_text(page, encoding="utf-8")


def run_dossier(source, data="data", destination=None):
    source, data = Path(source).resolve(), Path(data).resolve()
    destination = Path(destination).resolve() if destination else source / "dossie_categorias"
    if destination == source or source.is_relative_to(destination) or destination == data or data.is_relative_to(destination) or destination.is_relative_to(data):
        raise ValueError("A saída deve ser separada da referência e dos dados originais")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("A saída já contém arquivos; escolha outra pasta com --dest")
    hashes = {name: sha256(source / name) for name in INPUTS}
    for name in ("relatorio.html", "relatorio.pdf", "sintese_analise.json"):
        if (source / name).exists():
            hashes[name] = sha256(source / name)
    destination.mkdir(parents=True, exist_ok=True)
    state = dict(status="em execução", started=datetime.now().astimezone().isoformat(), input_hashes=hashes)
    write_json(destination / "estado_execucao.json", state)
    con = duckdb.connect(config={"threads": 2, "memory_limit": "1GB"})
    try:
        nominal, categories, attendance = [con.read_parquet(str(source / name)).df() for name in INPUTS[:3]]
        years = set(nominal.year) | set(categories.year) | set(attendance.year)
        if len(years) != 1:
            raise ValueError("As tabelas devem pertencer ao mesmo ano")
        year = int(next(iter(years)))
        sources = provenance(source, data, year)
        raw = read_raw_categories(next(r['local_path'] for r in sources if r['kind'] == 'official_detail'), year)
        con.read_parquet(str(source / "secoes_por_turno.parquet")).create_view("sections")
        context = con.execute('''SELECT year,turn,uf,municipality,zone,any_value(municipality_name) municipality_name,
            count(*) section_rows,count(*) FILTER(WHERE has_detail) section_detail_rows,
            count(*) FILTER(WHERE has_votes) section_vote_rows,
            string_agg(DISTINCT generation,' | ' ORDER BY generation) detail_generations,
            string_agg(DISTINCT source_file,' | ' ORDER BY source_file) detail_source_members
            FROM sections GROUP BY year,turn,uf,municipality,zone''').df()
        if set(context.year) != {year}:
            raise ValueError("Ano inesperado nas seções")
        units, nominal = build_dossier(nominal, categories, attendance, context, raw)
        if not set(units.turn).issubset({1, 2}):
            raise ValueError("Turno inesperado nas tabelas")
        for kind in ("votes", "detail", "official_votes", "official_detail"):
            units["source_" + kind] = kind
        by_uf = units.groupby(["uf", "turn", "is_exterior"], dropna=False).agg(
            unit_turns=("zone", "size"), selected_unit_turns=("selected", "sum"),
            technical_units=("technical_arithmetic_match", "sum"), coverage_turn_units=("zero_attendance_coverage", "sum")).reset_index()
        tables = dict(unidades=units, nominais=nominal, categorias_originais=raw, resumo_uf=by_uf)
        for name, frame in tables.items():
            export_frame(con, frame, destination / name)
        selected = units.loc[units.selected]
        coverage = units.loc[units.zero_attendance_coverage]
        technical = units.loc[units.technical_arithmetic_match]
        coverage_keys = coverage[KEY]
        coverage_nominal = nominal.merge(coverage_keys, on=KEY, how="inner", validate="many_to_one")
        summary = dict(status="concluído", year=year, unit_turns=len(units),
            selected_unit_turns=len(selected), selected_geographic_units=len(selected[KEY[2:]].drop_duplicates()),
            technical_units=len(technical), technical_votes=int(technical.official_null_technical.sum()),
            technical_by_turn=records(technical.groupby("turn").agg(units=("zone", "size"), votes=("official_null_technical", "sum")).reset_index()),
            nominal_differences_by_candidate=records(nominal.loc[nominal.nonzero_difference].groupby(["turn", "candidate"]).agg(rows=("candidate", "size"), votes=("difference", "sum")).reset_index()),
            coverage_turn_units=len(coverage), coverage_geographic_units=len(coverage[KEY[2:]].drop_duplicates()),
            coverage_candidate_rows=int(coverage_nominal.coverage_gap.sum()),
            raw_category_mismatches=int(units.raw_categories_disagree.sum()),
            raw_categories_unconfirmed=int((~units.raw_categories_confirmed).sum()),
            published_match_not_reproduced=int((~units.published_match_reproduced).sum()),
            findings=records(units.groupby("finding").size().reset_index(name="unit_turns")),
            input_hashes=hashes, original_hashes={r['source_id']: r['sha256'] for r in sources},
            documentary_cause_status="não investigada neste incremento", persistence_status="não investigada neste incremento",
            code_hash=sha256(Path(__file__)), tables={name:len(frame) for name,frame in tables.items()},
            versions=dict(python=platform.python_version(),duckdb=duckdb.__version__,pandas=pd.__version__),
            limitations=["Sem pesquisa externa ou explicação jurídica da destinação por candidato", "Gerações distintas não demonstram a causa", "Não confirma persistência nem atribui irregularidade"])
        write_json(destination / "fontes.json", sources)
        write_json(destination / "resumo.json", summary)
        definitions = {
            "nominal_difference": "Soma das diferenças seção menos oficial por candidato; ausente se alguma parcela estiver ausente. Diferenças de sinais opostos não anulam a seleção por linha.",
            "zero_imputed": "Indicador preservado da reconciliação original: ausência da linha de um candidato tratada como zero esparso quando as duas fontes cobrem a unidade e não há conflito. Não é imputação nova do dossiê nem zero explicitamente publicado em uma linha original.",
            "technical_arithmetic_match": "Conferência local das parcelas nominais, brancos, nulos, comparecimento e detalhe original; não explica a causa.",
            "published_technical_match": "Classificação publicada preservada, sem substituição do artefato de referência.",
            "attendance_difference": "Soma dos votos de todas as categorias nas seções menos comparecimento oficial; provém da reconciliação de categorias.",
            "detail_attendance_difference": "Comparecimento no detalhe por seção menos comparecimento no detalhe oficial por município/zona; provém da reconciliação de comparecimento.",
            "raw_categories_confirmed": "Todas as seis categorias conhecidas e iguais ao detalhe original, sem partição duplicada ou eleições ambíguas.",
            "zero_attendance_coverage": "Lacuna nominal, comparecimento zero conhecido nas duas fontes e soma nominal oficial zero conhecida.",
            "generation_relation": "Comparação das datas informadas no formato dia/mês/ano, sem fuso inferido. Ausência/data inválida permanece identificada.",
            "selected": "Apontamento nominal, diferença em categorias/aptos/comparecimento, lacuna ou conflito de categorias originais ou referência não reproduzida.",
            "source_line": "Linha física final do registro no CSV original (cabeçalho na linha 1); identificar junto com member e hash do ZIP.",
            "documentary_cause_status": "Não investigada neste incremento. Concordância aritmética não comprova causa ou inexistência de irregularidade.",
            "persistence_status": "Não investigada neste incremento; não equivale a zero divergências existentes.",
        }
        export_frame(con, pd.DataFrame([dict(field=k, definition=v) for k,v in definitions.items()]), destination / "dicionario")
        build_html(destination, units, nominal, sources, summary)
        for name, digest in hashes.items():
            if sha256(source / name) != digest:
                raise ValueError(f"Referência alterada durante execução: {name}")
        for item in sources:
            if sha256(item['local_path']) != item['sha256']:
                raise ValueError(f"Arquivo original alterado: {item['source_id']}")
        summary['preservation_verified'] = True
        summary['finished'] = datetime.now().astimezone().isoformat()
        write_json(destination / "resumo.json", summary)
        write_json(destination / "manifesto.json", {p.name: sha256(p) for p in sorted(destination.iterdir()) if p.name not in ('estado_execucao.json','manifesto.json')})
        state.update(status="concluído", finished=summary['finished'])
        write_json(destination / "estado_execucao.json", state)
        return summary
    except Exception as exc:
        state.update(status="incompleto", error=f"{type(exc).__name__}: {exc}")
        write_json(destination / "estado_execucao.json", state)
        raise
    finally:
        con.close()
