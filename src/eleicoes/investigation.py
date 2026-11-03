"""Investigação dirigida, reproduzível sobre os Parquets já conferidos."""
from __future__ import annotations

import gc
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import numpy as np
import pandas as pd

from .analysis import export_frame
from .ingest import KEY
from .sources import sha256, write_json

LOG = logging.getLogger(__name__)
GEO = ["year", "uf", "municipality", "zone", "section"]
VALUES = ["aptos", "attendance", "abstention", "valid", "blank", "null_votes", "other_votes", "votes_13", "votes_22"]
KEEP = GEO + ["local", "municipality_name_1", "municipality_name_2", "local_1", "local_2",
    "local_name_1", "local_name_2", "local_address_1", "local_address_2", "aggregation_1", "aggregation_2",
    "generation_1", "generation_2", "vote_generation_1", "vote_generation_2", "coverage", "comparable",
    "comparison_reason", "small", "level", "is_exterior", "bu_check", "peer_count"] + [f"{m}_{t}" for m in VALUES for t in (1, 2)]


def ratio(a, b):
    a = pd.to_numeric(a, errors="coerce").astype(float)
    b = pd.to_numeric(b, errors="coerce").astype(float)
    return a / b.where(b > 0)


def metrics(frame):
    f = frame.copy()
    for t in (1, 2):
        total = f[f"votes_22_{t}"] + f[f"votes_13_{t}"]
        f[f"margin_{t}_pp"] = 100 * ratio(f[f"votes_22_{t}"] - f[f"votes_13_{t}"], total)
        f[f"margin_{t}_votes"] = f[f"votes_22_{t}"] - f[f"votes_13_{t}"]
        f[f"turnout_{t}"] = ratio(f[f"attendance_{t}"], f[f"aptos_{t}"])
        for c in (13, 22):
            f[f"share_{c}_{t}"] = ratio(f[f"votes_{c}_{t}"], f[f"valid_{t}"])
    f["margin_loss_22_pp"] = f.margin_1_pp - f.margin_2_pp
    f["margin_loss_22_votes"] = f.margin_1_votes - f.margin_2_votes
    for m in VALUES:
        f[f"delta_{m}"] = f[f"{m}_2"] - f[f"{m}_1"]
    f["eliminated_votes_1"] = f.valid_1 - f.votes_13_1 - f.votes_22_1
    f["ballot_balance_residual"] = f.delta_votes_13 + f.delta_votes_22 - f.eliminated_votes_1 - f.delta_valid
    f["turnout_change_pp"] = 100 * (f.turnout_2 - f.turnout_1)
    f["flip_to_13"] = (f.margin_1_pp.gt(0) & f.margin_2_pp.lt(0)).fillna(False)
    f["flip_to_22"] = (f.margin_1_pp.lt(0) & f.margin_2_pp.gt(0)).fillna(False)
    f["tie_1"] = (f.votes_13_1.eq(f.votes_22_1) & (f.votes_13_1 + f.votes_22_1).gt(0)).fillna(False).astype(bool)
    f["tie_2"] = (f.votes_13_2.eq(f.votes_22_2) & (f.votes_13_2 + f.votes_22_2).gt(0)).fillna(False).astype(bool)
    for threshold in (5, 10, 15):
        f[f"loss_22_{threshold}pp"] = (f.margin_1_pp.gt(0) & f.margin_loss_22_pp.ge(threshold - 1e-10)).fillna(False).astype(bool)
        f[f"loss_13_{threshold}pp"] = (f.margin_1_pp.lt(0) & f.margin_loss_22_pp.le(-threshold + 1e-10)).fillna(False).astype(bool)
    f["pattern"] = np.select([f.flip_to_13, f.flip_to_22, f.tie_1 | f.tie_2, f.loss_22_10pp, f.loss_13_10pp],
        ["Flávio → Lula", "Lula → Flávio", "empate", "vantagem de Flávio reduzida", "vantagem de Lula reduzida"], default="sem padrão selecionado")
    f["selected_pattern"] = f.flip_to_13 | f.flip_to_22 | f.loss_22_10pp | f.loss_13_10pp | (f.tie_1 ^ f.tie_2)
    return f


def zeros(frame):
    exclusive_13 = frame.votes_22_2.eq(0) & frame.votes_13_2.gt(0) & frame.valid_2.eq(frame.votes_13_2)
    exclusive_22 = frame.votes_13_2.eq(0) & frame.votes_22_2.gt(0) & frame.valid_2.eq(frame.votes_22_2)
    z = frame.loc[(exclusive_13 | exclusive_22).fillna(False)].copy()
    z["zero_candidate"] = np.where(exclusive_13.loc[z.index], 22, 13)
    z["winner_candidate"] = np.where(z.zero_candidate.eq(22), 13, 22)
    z["previous_zero_candidate_votes"] = np.where(z.zero_candidate.eq(22), z.votes_22_1, z.votes_13_1)
    z["positive_to_zero"] = z.previous_zero_candidate_votes.gt(0).fillna(False)
    z["already_zero"] = z.previous_zero_candidate_votes.eq(0).fillna(False)
    z["first_turn_available"] = z.previous_zero_candidate_votes.notna()
    z["unanimity_all_ballots"] = (z.blank_2.eq(0) & z.null_votes_2.eq(0) & z.other_votes_2.eq(0) & z.valid_2.eq(z.attendance_2)).fillna(False)
    z["pattern"] = np.select([z.positive_to_zero, z.already_zero], ["positivo → zero", "já zerado no primeiro turno"], default="primeiro turno indisponível")
    return z


def peer_margin_scores(frame, neighbors):
    """Reutiliza os IDs dos 30 pares, sem selecionar vizinhos pelo segundo turno."""
    ids = frame.uf.astype(str) + "/" + frame.municipality.astype(str) + "/" + frame.zone.astype(str) + "/" + frame.section.astype(str)
    lookup = dict(zip(ids, frame.margin_loss_22_pp))
    result = neighbors[GEO].copy()
    result["peer_ids"] = neighbors.peer_ids
    result["margin_peer_median"] = np.nan
    result["margin_peer_mad"] = np.nan
    result["margin_robust_z"] = np.nan
    result["margin_peer_status"] = "não elegível ou sem 30 pares"
    for index, row in neighbors.iterrows():
        if not row.comparable or row.small or row.peer_count != 30 or not isinstance(row.peer_ids, str):
            continue
        own = "/".join(str(row[k]) for k in ("uf", "municipality", "zone", "section"))
        peers = row.peer_ids.split("|")
        if len(peers) != 30 or len(set(peers)) != 30 or own in peers:
            raise ValueError(f"Lista inválida de pares: {own}")
        values = np.array([lookup.get(k, np.nan) for k in peers], dtype=float)
        value = lookup.get(own, np.nan)
        if not np.isfinite(values).all() or not np.isfinite(value):
            result.loc[index, "margin_peer_status"] = "indicadores dos pares indisponíveis"
            continue
        median = np.median(values)
        mad = np.median(np.abs(values - median))
        result.loc[index, ["margin_peer_median", "margin_peer_mad"]] = [median, mad]
        if mad <= 1e-9:
            result.loc[index, "margin_peer_status"] = "dispersão insuficiente"
        else:
            result.loc[index, "margin_robust_z"] = abs(value - median) / (1.4826 * mad)
            result.loc[index, "margin_peer_status"] = "calculado com os mesmos 30 pares"
    result["margin_robust_flag"] = result.margin_robust_z.gt(3.5)
    return result


def classify(frame):
    f = frame.copy()
    for name in ("document_differences", "document_missing", "duplicate_conflicts", "election_mismatches"):
        if name not in f:
            f[name] = 0 if name == "duplicate_conflicts" else np.nan
    complete = f.document_missing.eq(0) & f.election_mismatches.eq(0)
    clean = complete & f.document_differences.eq(0) & f.duplicate_conflicts.eq(0)
    f["investigation_status"] = "comparação territorial limitada"
    f["investigation_reason"] = "Contagens e/ou composição exigem ressalva: " + f.comparison_reason.fillna("cobertura não demonstrada").astype(str)
    confirmed = clean & f.comparable.fillna(False).astype(bool)
    f.loc[confirmed, "investigation_status"] = "mudança confirmada nos arquivos"
    f.loc[confirmed, "investigation_reason"] = "Composição e aptos compatíveis; registros dos dois turnos presentes e concordantes com os BU, sem conflito de duplicidade. Não identifica transferências individuais."
    if "already_zero" in f:
        f.loc[confirmed & f.already_zero, "investigation_status"] = "observação confirmada nos arquivos"
    difference = complete & (f.document_differences.gt(0) | f.duplicate_conflicts.gt(0))
    f.loc[difference, "investigation_status"] = "divergência documental"
    f.loc[difference, "investigation_reason"] = "Diferença ou conflito entre registros; gerações e situação devem ser examinadas. Persistência não confirmada automaticamente."
    return f


def _read(con, folder, name, where="", parameters=None):
    path = folder / (name + ".parquet")
    columns = [r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()]
    selected = [c for c in KEEP if c in columns]
    sql = "SELECT " + ",".join(dict.fromkeys(selected)) + " FROM read_parquet(?) " + where
    return con.execute(sql, [str(path)] + (parameters or [])).df()


def document_checks(con, output, target_keys):
    """Prova por seção/turno, sem confundir ausência de candidato com ausência de urna."""
    con.register("investigation_keys", target_keys[GEO].drop_duplicates())
    key = ",".join(KEY)
    con.execute("""CREATE OR REPLACE TEMP TABLE investigation_bu AS
        SELECT b.* FROM read_parquet(?) b SEMI JOIN investigation_keys k USING(year,uf,municipality,zone,section)""",
        [str(output / "conferencia_bu.parquet")])
    counts = con.execute(f"""SELECT {key},count(*) records_checked,
        count(*) FILTER(WHERE difference<>0 OR contains(status,'conflitante')) document_differences,
        bool_or(raw_votes_result IS NOT NULL) has_result,
        bool_or(raw_votes_bu IS NOT NULL) has_bu,
        count(*) FILTER(WHERE result_election IS NOT NULL AND bu_election IS NOT NULL AND result_election<>bu_election) election_mismatches,
        count(*) FILTER(WHERE raw_votes_result IS NULL AND votes_result=0) implicit_zero_result,
        count(*) FILTER(WHERE raw_votes_bu IS NULL AND votes_bu=0) implicit_zero_bu,
        max(result_generation) result_generation,max(bu_generation) bu_generation,
        max(result_source) result_source,max(bu_source) bu_source,
        max(result_election) result_election,max(bu_election) bu_election
        FROM investigation_bu GROUP BY {key}""").df()
    meta = con.execute(f"""SELECT b.* EXCLUDE(vote_local,local_name,local_address),b.local_name,b.local_address
        FROM read_parquet(?) b SEMI JOIN investigation_keys k USING(year,uf,municipality,zone,section)""",
        [str(output / "secoes_por_turno.parquet")]).df()
    checks = meta.merge(counts, on=KEY, how="outer", validate="one_to_one")
    expected_empty = checks.installed.fillna("").str.upper().isin(["NÃO", "NAO", "N"]) & checks.has_votes.eq(False)
    checks["document_missing"] = (~checks.has_result.fillna(False).astype(bool) | ~checks.has_bu.fillna(False).astype(bool)).astype(int)
    checks.loc[expected_empty, "document_missing"] = 0
    for name in ("document_differences", "election_mismatches", "records_checked", "implicit_zero_result", "implicit_zero_bu"):
        checks[name] = checks[name].fillna(0).astype(int)
    checks["duplicate_conflicts"] = 0
    checks["duplicate_groups"] = 0
    for kind in ("votes", "bu", "detail"):
        path = output / f"duplicidades_{kind}.parquet"
        if not path.exists():
            checks["document_missing"] += 1
            continue
        # Arquivos vazios podem ter chaves do tipo NULL; pular só após contar.
        if con.execute("SELECT count(*) FROM read_parquet(?)", [str(path)]).fetchall()[0][0] == 0:
            continue
        dup = con.execute(f"""SELECT {key},count(*) groups_found,count(*) FILTER(WHERE versions>1) conflicts
            FROM read_parquet(?) SEMI JOIN investigation_keys USING(year,uf,municipality,zone,section) GROUP BY {key}""", [str(path)]).df()
        checks = checks.merge(dup, on=KEY, how="left", validate="one_to_one")
        checks["duplicate_conflicts"] += checks.conflicts.fillna(0).astype(int)
        checks["duplicate_groups"] += checks.groups_found.fillna(0).astype(int)
        checks = checks.drop(columns=["conflicts", "groups_found"])
    return checks


def add_checks(frame, checks, level):
    f = frame.copy()
    keys = {"secao": GEO, "local": ["year", "uf", "municipality", "zone", "local"],
            "municipio": ["year", "uf", "municipality"], "uf": ["year", "uf"]}[level]
    fields = ["document_differences", "document_missing", "duplicate_conflicts", "duplicate_groups", "election_mismatches", "records_checked", "implicit_zero_result", "implicit_zero_bu"]
    grouped = checks.groupby(keys, dropna=False, observed=True)[fields].sum().reset_index()
    turns = checks.groupby(keys, dropna=False, observed=True).turn.nunique().reset_index(name="checked_turns")
    grouped = grouped.merge(turns, on=keys, validate="one_to_one")
    f = f.merge(grouped, on=keys, how="left", validate="one_to_one")
    # Ausência de um turno inteiro não aparece como linha no groupby.
    f["document_missing"] = f.document_missing.fillna(1) + f.checked_turns.fillna(0).ne(2).astype(int)
    return classify(f)


def cohort_totals(sections, municipalities):
    keys = ["year", "uf", "municipality"]
    quantities = [f"{m}_{t}" for m in VALUES for t in (1, 2)]
    eligible = sections.loc[sections.comparable.fillna(False)].copy()
    cohort = eligible.groupby(keys, observed=True)[quantities].sum(min_count=1).reset_index()
    counts = eligible.groupby(keys, observed=True).size().reset_index(name="cohort_sections")
    cohort = cohort.merge(counts, on=keys, validate="one_to_one")
    cohort = metrics(cohort)
    columns = [c for c in cohort if c not in keys and c != "cohort_sections"]
    cohort = cohort.rename(columns={c: "cohort_" + c for c in columns})
    result = municipalities.merge(cohort, on=keys, how="left", validate="one_to_one")
    for t in (1, 2):
        for name in ("aptos", "attendance", "valid"):
            result[f"cohort_coverage_{name}_{t}_pct"] = 100 * ratio(result[f"cohort_{name}_{t}"], result[f"{name}_{t}"])
    return result


def _safe(value):
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    return value


def _case_key(row):
    keys = {"secao": ["uf", "municipality", "zone", "section"], "local": ["uf", "municipality", "zone", "local"],
            "municipio": ["uf", "municipality"], "uf": ["uf"]}[row["level"]]
    return row["level"] + "-" + "-".join(str(row[k]) for k in keys)


def _news_claims(z, municipalities, ufs):
    tse = "https://www.justicaeleitoral.jus.br/fato-ou-boato/checagens/2026/e-falso-que-124-mil-urnas-tenham-registrado-votos-apenas-para-lula-no-2o-turno-das-eleicoes-2026"
    folha = "https://www1.folha.uol.com.br/colunas/painel/2026/10/flavio-teve-zero-voto-em-106-urnas-nas-quais-somou-quase-15-mil.shtml"
    claims = [
        ("TSE", tse, "2026-10-29", "Seções com válidos exclusivamente para Lula", 106, len(z.loc[z.zero_candidate.eq(22)])),
        ("TSE", tse, "2026-10-29", "Seções com válidos exclusivamente para Flávio", 4, len(z.loc[z.zero_candidate.eq(13)])),
        ("TSE", tse, "2026-10-29", "Votos de Lula nas seções em que Flávio zerou", 14860, z.loc[z.zero_candidate.eq(22), "votes_13_2"].sum()),
        ("Folha", folha, "2026-10-28", "Municípios brasileiros que viraram de Flávio para Lula", 211, int((municipalities.flip_to_13 & ~municipalities.is_exterior).sum())),
        ("O TEMPO", "https://www.otempo.com.br/politica/2026/10/28/em-minas-76-cidades-viraram-para-lula-na-eleicao-veja-quais", "2026-10-28", "Municípios de MG que viraram de Flávio para Lula", 76, int((municipalities.flip_to_13 & municipalities.uf.eq("MG")).sum())),
    ]
    rio = municipalities.loc[municipalities.uf.eq("RJ") & municipalities.municipality.eq("60011")]
    if len(rio):
        row = rio.iloc[0]
        claims += [("Folha", folha, "2026-10-28", "Vantagem de Lula na cidade do Rio: reportagem cita aproximadamente 644 mil", 644000, -row.margin_2_votes),
            ("CNN Brasil", "https://www.cnnbrasil.com.br/eleicoes/veja-a-votacao-nas-cidades-que-lula-e-flavio-fizeram-campanha-no-2o-turno/", "2026-10-26", "Votos de Lula na cidade do Rio no segundo turno", 1898391, row.votes_13_2)]
    return pd.DataFrame([dict(source=s, url=url, published=date, claim=claim, reported=int(expected), observed=int(actual),
        status="confirmado na cópia analisada" if expected == actual else "relato não confirmado",
        reviewed_on="2026-11-03", note="Afirmações registradas na consulta de 03/11/2026 e reproduzidas offline. Comparação com a versão local; divergência da notícia não é divergência da votação.") for s, url, date, claim, expected, actual in claims])


def investigate(output="outputs/2026", ufs=("RJ", "MG"), regenerate=True):
    output = Path(output)
    ufs = list(dict.fromkeys(uf.upper() for uf in ufs))
    required = ["indicadores_secoes", "indicadores_local", "indicadores_municipio", "indicadores_uf", "secoes_por_turno", "conferencia_bu", "candidatos"]
    missing = [name for name in required if not (output / (name + ".parquet")).is_file()]
    if missing:
        raise FileNotFoundError("Investigação exige tabelas locais completas; faltam: " + ", ".join(missing))
    report_summary = json.loads((output / "resumo.json").read_text(encoding="utf-8"))
    demo = bool(report_summary.get("demo", False))
    if not demo and not (output / "fontes_utilizadas.json").exists():
        raise FileNotFoundError("Manifesto de fontes ausente; não confirmar uma investigação sem proveniência")
    original_cases = {p.name: sha256(p) for p in (output / "fichas").glob("*.json") if not p.name.startswith("documental-")}
    con = duckdb.connect()
    con.execute("SET memory_limit='1GB'")
    con.execute("SET threads=2")
    con.execute("SET enable_progress_bar=false")
    try:
        finals = con.execute("SELECT DISTINCT candidate FROM read_parquet(?) WHERE turn=2 AND candidate BETWEEN 1 AND 94 AND votes>0 ORDER BY 1", [str(output / "candidatos.parquet")]).fetchall()
        if finals != [(13,), (22,)]:
            raise ValueError("Esta investigação exige os finalistas 13 e 22; não inferir nomes em outra eleição")
        LOG.info("Lendo indicadores nacionais e distinguindo os padrões")
        sections = metrics(_read(con, output, "indicadores_secoes"))
        if set(sections.year.dropna()) != {2026}:
            raise ValueError("A investigação dirigida é específica de 2026")
        unknown_ufs = set(ufs) - set(sections.uf.unique())
        if unknown_ufs:
            raise ValueError("UFs ausentes da base: " + ", ".join(sorted(unknown_ufs)))
        z = zeros(sections)
        regional = sections.loc[sections.uf.isin(ufs)].copy()
        zero_municipalities = z[["uf", "municipality"]].drop_duplicates()
        context_sections = sections.merge(zero_municipalities, on=["uf", "municipality"], how="inner", validate="many_to_one")
        targets = pd.concat([regional[GEO], context_sections[GEO]], ignore_index=True).drop_duplicates()
        del context_sections
        con.register("target_peer_keys", targets)
        neighbor_ids = con.execute("""SELECT b.year,b.uf,b.municipality,b.zone,b.section,b.peer_ids,b.peer_count,b.comparable,b.small
            FROM read_parquet(?) b SEMI JOIN target_peer_keys USING(year,uf,municipality,zone,section)""", [str(output / "indicadores_secoes.parquet")]).df()
        LOG.info("Calculando a margem com os mesmos 30 pares: %s alvos", len(neighbor_ids))
        scores = peer_margin_scores(sections, neighbor_ids)
        regional = regional.merge(scores, on=GEO, how="left", validate="one_to_one")
        z = z.merge(scores, on=GEO, how="left", validate="one_to_one")
        LOG.info("Conferindo BU, situação e duplicidades nos dois turnos")
        checks = document_checks(con, output, targets)
        z = add_checks(z, checks, "secao")
        regional = add_checks(regional, checks, "secao")
        municipalities = metrics(_read(con, output, "indicadores_municipio"))
        selected_municipalities = municipalities.loc[municipalities.uf.isin(ufs)].copy()
        selected_municipalities = cohort_totals(regional, selected_municipalities)
        selected_municipalities = add_checks(selected_municipalities, checks, "municipio")
        all_locals = metrics(_read(con, output, "indicadores_local"))
        locals_selected = add_checks(all_locals.loc[all_locals.uf.isin(ufs)], checks, "local")
        states = metrics(_read(con, output, "indicadores_uf"))
        states = add_checks(states.loc[states.uf.isin(ufs)], checks, "uf")
        # Para os zeros fora das UFs priorizadas, verificar também unidades territoriais compatíveis.
        z["compatible_context"] = "não localizado nos níveis local/município"
        z["compatible_context_key"] = ""
        contexts = {}
        for idx, row in z.loc[~z.comparable].iterrows():
            candidates = all_locals.loc[all_locals.uf.eq(row.uf) & all_locals.municipality.eq(row.municipality) & all_locals.zone.eq(row.zone)]
            if row.get("local_1") == row.get("local_2") and pd.notna(row.get("local_1")):
                candidates = candidates.loc[candidates.local.eq(row.local_1) & candidates.comparable]
            else:
                candidates = candidates.iloc[:0]
            if candidates.empty:
                candidates = municipalities.loc[municipalities.uf.eq(row.uf) & municipalities.municipality.eq(row.municipality) & municipalities.comparable]
            if not candidates.empty:
                candidate_level = candidates.iloc[0].level
                verified = add_checks(candidates.head(1), checks, candidate_level)
                context = verified.iloc[0]
                z.loc[idx, "compatible_context"] = "nível " + context.level + ": " + context.investigation_status + "; contexto não substitui a seção"
                z.loc[idx, "compatible_context_key"] = _case_key(context)
                contexts[tuple(row[k] for k in GEO)] = context.to_dict()
        z.loc[z.comparable, "compatible_context"] = "seção comparável"
        inventory = pd.concat([regional, locals_selected, selected_municipalities, states], ignore_index=True, sort=False)
        inventory["case_file"] = ""
        z["case_file"] = ""
        fichas = output / "investigacao_fichas"
        fichas.mkdir(exist_ok=True)
        selected_sections = []
        for uf in ufs:
            subset = inventory.loc[inventory.level.eq("secao") & inventory.uf.eq(uf) & inventory.comparable & ~inventory.small & inventory.selected_pattern]
            selected_sections.extend(subset.sort_values(["margin_robust_z", "margin_loss_22_pp", "uf", "municipality", "zone", "section"],
                ascending=[False, False, True, True, True, True], na_position="last", kind="stable").head(50).index.tolist())
        selected_cities = inventory.index[inventory.level.eq("municipio") & (inventory.flip_to_13 | inventory.flip_to_22)].tolist()
        selected_states = inventory.index[inventory.level.eq("uf")].tolist()
        sources = json.loads((output / "fontes_utilizadas.json").read_text(encoding="utf-8")) if (output / "fontes_utilizadas.json").exists() else []
        # Provas completas só para as fichas; os demais casos têm a conferência resumida na tabela.
        case_rows = [dict(row, kind="zero") for _, row in z.iterrows()] + [dict(inventory.loc[i], kind="virada") for i in selected_cities + selected_sections + selected_states]
        case_keys = pd.DataFrame([r for r in case_rows if r["level"] == "secao"])[GEO].drop_duplicates()
        con.register("detailed_case_keys", case_keys)
        proofs = con.execute("""SELECT b.* FROM investigation_bu b SEMI JOIN detailed_case_keys USING(year,uf,municipality,zone,section)
            ORDER BY year,uf,municipality,zone,section,turn,candidate""").df()
        proof_groups = {key: rows.to_dict("records") for key, rows in proofs.groupby(GEO, dropna=False, observed=True)}
        case_metadata = checks.merge(case_keys, on=GEO, how="inner", validate="many_to_one")
        check_groups = {key: rows.to_dict("records") for key, rows in case_metadata.groupby(GEO, dropna=False, observed=True)}
        official = con.execute("SELECT * FROM read_parquet(?) WHERE candidate IN (13,22)", [str(output / "reconciliacao_municipio_zona.parquet")]).df()
        names = set()
        for record in case_rows:
            case_name = record["kind"] + "-" + _case_key(record)
            link = "investigacao_fichas/" + case_name + ".json"
            names.add(case_name + ".json")
            if record["kind"] == "zero":
                match = pd.Series(True, index=z.index)
                for k in GEO:
                    match &= z[k].eq(record[k])
                z.loc[match, "case_file"] = link
            else:
                match = inventory.level.eq(record["level"]) & inventory.uf.eq(record["uf"])
                for k in {"secao": GEO[2:], "municipio": ["municipality"], "uf": []}[record["level"]]:
                    match &= inventory[k].eq(record[k])
                inventory.loc[match, "case_file"] = link
            key = tuple(record.get(k) for k in GEO)
            evidence = checks.loc[checks.uf.eq(record["uf"])]
            totals = official.loc[official.uf.eq(record["uf"])]
            if record["level"] != "uf":
                evidence = evidence.loc[evidence.municipality.eq(record["municipality"])]
                totals = totals.loc[totals.municipality.eq(record["municipality"])]
            if record["level"] == "secao":
                section_evidence = check_groups.get(key, [])
                bu_evidence = proof_groups.get(key, [])
                totals = totals.loc[totals.zone.eq(record["zone"])]
            else:
                section_evidence = []
                bu_evidence = []
            write_json(fichas / (case_name + ".json"), _safe(dict(
                identification={k: record.get(k) for k in ["year", "level", "uf", "municipality", "municipality_name_1", "zone", "section"]},
                indicators=record, section_metadata=section_evidence, bu_records=bu_evidence,
                territorial_documentary_summary=evidence.groupby("turn")["document_missing"].agg(["size", "sum"]).reset_index().to_dict("records"),
                official_finalist_totals=totals.to_dict("records"), sources=sources,
                compatible_territorial_context=contexts.get(key),
                explanation="Conferência das contagens e da composição. Os dados agregados não identificam quem mudou de voto; concordância dos arquivos não estabelece a causa da mudança.")))
        # Arquivos de rodadas anteriores são preservados fora do conjunto corrente.
        stale = [p for p in fichas.glob("*.json") if p.name not in names]
        if stale:
            archived = output / "investigacao_anteriores" / datetime.now().strftime("%Y%m%dT%H%M%S")
            archived.mkdir(parents=True, exist_ok=True)
            for p in stale:
                p.rename(archived / p.name)
        news = _news_claims(z, municipalities, ufs)
        if demo:
            news["status"] = "SIMULADO: não comparar com notícia real"
        LOG.info("Exportando inventário, conferências e fichas")
        export_frame(con, z, output / "investigacao_zeros")
        export_frame(con, inventory, output / "investigacao_viradas")
        export_frame(con, checks, output / "investigacao_conferencia_bu")
        export_frame(con, news, output / "investigacao_noticias")
        definitions = {
            "margin_1_pp": "100 × (Flávio − Lula) / (Flávio + Lula), primeiro turno. Não usa os eliminados no denominador.",
            "margin_2_pp": "Mesma margem entre os finalistas no segundo turno.",
            "margin_loss_22_pp": "Margem do primeiro menos segundo turno: positivo indica redução relativa da vantagem de Flávio.",
            "margin_loss_22_votes": "Saldo de votos Flávio − Lula no primeiro menos o saldo no segundo turno.",
            "delta_votes_22": "Votos de Flávio no segundo menos no primeiro turno; pode ser positivo mesmo quando sua vantagem diminui.",
            "margin_robust_z": "|mudança de margem − mediana dos 30 pares| / (1,4826 × MAD). Não é probabilidade; MAD insuficiente resulta em ausência.",
            "unanimity_all_ballots": "Todos os votos depositados foram para o finalista vencedor, com brancos/nulos/outros zerados e comparecimento igual aos seus votos.",
            "ballot_balance_residual": "ΔLula + ΔFlávio − votos dos eliminados no primeiro turno − Δválidos. Zero demonstra identidade contábil, sem identificar transferências pessoais.",
            "investigation_status": "Classificação da comparação: mudança/observação confirmada nos arquivos, comparação territorial limitada ou divergência documental sem persistência presumida.",
        }
        pd.DataFrame([dict(campo=k, definicao=v) for k,v in definitions.items()]).to_csv(output / "investigacao_dicionario.csv", index=False, encoding="utf-8-sig")
        primary = z.loc[z.zero_candidate.eq(22)]
        changed = primary.loc[primary.positive_to_zero]
        inputs = [output / (n + ".parquet") for n in required]
        summary = dict(generated=datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"), year=2026, ufs=ufs, demo=demo,
            zero_22_second=len(primary), positive_to_zero_22=len(changed), already_zero_22=int(primary.already_zero.sum()),
            max_previous_22=int(changed.previous_zero_candidate_votes.max()) if len(changed) else None,
            total_previous_22=int(changed.previous_zero_candidate_votes.sum()), comparable_positive_to_zero_22=int(changed.comparable.sum()),
            led_first_positive_to_zero_22=int(changed.margin_1_pp.gt(0).sum()), zero_13_second=int(z.zero_candidate.eq(13).sum()),
            all_ballots_unanimous_13=int(primary.unanimity_all_ballots.sum()), fichas=len(names),
            cities_flipped_to_13={uf: int((municipalities.uf.eq(uf) & municipalities.flip_to_13).sum()) for uf in ufs},
            classification=z.investigation_status.value_counts().to_dict(),
            baseline_expected=dict(zero_22_second=106, positive_to_zero_22=56, already_zero_22=50, comparable_positive_to_zero_22=44,
                max_previous_22=16, total_previous_22=118, led_first_positive_to_zero_22=0, zero_13_second=4),
            preservation="As tabelas de origem e as 100 fichas estatísticas originais não são alteradas.",
            input_hashes={p.name: sha256(p) for p in inputs},
            input_fingerprints={p.name: [p.stat().st_size,p.stat().st_mtime_ns] for p in inputs},
            original_statistical_case_hashes=original_cases,
            code_hash=sha256(Path(__file__)))
        summary["baseline_differences"] = {k: dict(expected=v, observed=summary[k]) for k, v in summary["baseline_expected"].items() if summary[k] != v} if not demo else {}
        write_json(output / "investigacao_resumo.json", _safe(summary))
        del sections, regional, inventory, z, checks, proofs, neighbor_ids, scores, all_locals, municipalities
        gc.collect()
    finally:
        con.close()
    if regenerate:
        regenerate_report(output)
        changed_cases = [name for name,digest in original_cases.items() if sha256(output / "fichas" / name) != digest]
        if changed_cases:
            raise RuntimeError("Fichas estatísticas originais mudaram: " + ", ".join(changed_cases))
    return summary


def regenerate_report(output):
    from .report import build_report
    output = Path(output)
    saved = json.loads((output / "resumo.json").read_text(encoding="utf-8"))
    con = duckdb.connect()
    con.execute("SET threads=2")
    try:
        current = con.execute("SELECT * FROM read_parquet(?)", [str(output / "indicadores_secoes.parquet")]).df()
        issues = con.execute("SELECT * FROM read_parquet(?)", [str(output / "pendencias_documentais.parquet")]).df()
        sources = json.loads((output / "fontes_utilizadas.json").read_text(encoding="utf-8")) if (output / "fontes_utilizadas.json").exists() else []
        summary = {k: v for k, v in saved.items() if k not in ("generated", "demo", "historical")}
        build_report(output, current, saved.get("historical", []), summary, [13, 22], issues, sources, demo=saved.get("demo", False))
    finally:
        con.close()
