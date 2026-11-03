"""Indicadores simétricos entre candidatos; escores exploratórios, sem p-valores."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from .ingest import KEY, has_table

LOG = logging.getLogger(__name__)
GEO = ["uf", "municipality", "zone", "section"]
PARQUET_OPTIONS = "FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 1, ROW_GROUP_SIZE 8192, STRING_DICTIONARY_PAGE_SIZE_LIMIT 1048576"


def aggregation_identity(municipality, zone, section, aggregation):
    """Identifica a seção principal e os membros declarados, sem depender da ordem textual."""
    principal = f"{municipality}:{zone}:{section}"
    if pd.isna(aggregation) or not str(aggregation).strip():
        return principal, True
    text = str(aggregation).strip()
    numbers = re.findall(r"\d+", text)
    if not numbers or re.search(r"[^\d\s,;/|]", text) or any(int(n) <= 0 for n in numbers):
        return principal, False
    members = sorted({str(int(n)) for n in numbers} - {str(section)})
    return principal + ("[" + ",".join(members) + "]" if members else ""), True


def ratio(a, b):
    """Denominador zero/ausente produz ausência, nunca infinito ou zero artificial."""
    a = pd.to_numeric(a, errors="coerce").astype(float)
    b = pd.to_numeric(b, errors="coerce").astype(float)
    return a.div(b.where(b > 0))


def export_frame(con, frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con.register("export_frame", frame)
    try:
        for suffix, options in [(".csv", "FORMAT CSV, HEADER TRUE"), (".parquet", PARQUET_OPTIONS)]:
            p = str(path.with_suffix(suffix)).replace("'", "''")
            con.execute(f"COPY export_frame TO '{p}' ({options})").fetchall()
    finally:
        con.unregister("export_frame")


def export_table(con, table, path):
    """Exporta tabelas grandes sem materializar milhões de registros em pandas."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for suffix, options in [(".csv", "FORMAT CSV, HEADER TRUE"), (".parquet", PARQUET_OPTIONS)]:
        target = str(path.with_suffix(suffix)).replace("'", "''")
        con.execute(f"COPY {table} TO '{target}' ({options})").fetchall()


def section_base(con, year, use_bu=True):
    table = f"votes_{year}"
    finalists = [int(r[0]) for r in con.execute(f"""SELECT candidate FROM {table}
        WHERE turn=2 AND candidate BETWEEN 1 AND 94 GROUP BY candidate
        HAVING sum(votes)>0 ORDER BY candidate""").fetchall()]
    if len(finalists) != 2:
        raise ValueError(f"Esperados dois finalistas em {year}, encontrados {finalists}; verificar cobertura")
    candidates = [int(r[0]) for r in con.execute(f"SELECT DISTINCT candidate FROM {table} WHERE candidate BETWEEN 1 AND 94 ORDER BY 1").fetchall()]
    key = ",".join(KEY)
    pivots = ",".join(f"sum(CASE WHEN candidate={c} THEN votes ELSE 0 END)::BIGINT votes_{c}" for c in candidates)
    con.execute(f"""CREATE OR REPLACE TEMP VIEW vote_summary AS SELECT {key},
        max(municipality_name) municipality_name, max(local) vote_local,
        max(generation) vote_generation, max(election_id) vote_election_id,
        sum(CASE WHEN candidate BETWEEN 1 AND 94 THEN votes ELSE 0 END)::BIGINT valid,
        sum(CASE WHEN candidate=95 THEN votes ELSE 0 END)::BIGINT blank,
        sum(CASE WHEN candidate=96 THEN votes ELSE 0 END)::BIGINT null_votes,
        sum(CASE WHEN candidate NOT BETWEEN 1 AND 96 THEN votes ELSE 0 END)::BIGINT other_votes,
        {pivots}, count(*) vote_rows FROM {table} GROUP BY {key}""")
    coalesced = ",".join(f'coalesce(v.{k},d.{k}) AS "{k}"' for k in KEY)
    frame = con.execute(f"""SELECT {coalesced}, coalesce(d.municipality_name,v.municipality_name) municipality_name,
        coalesce(d.local,v.vote_local) local, v.* EXCLUDE({key},municipality_name),
        d.* EXCLUDE({key},municipality_name,local),
        v.vote_rows IS NOT NULL has_votes, d.year IS NOT NULL has_detail
        FROM vote_summary v FULL OUTER JOIN detail_{year} d USING({key})""").df()
    # Um candidato conflitante compromete o denominador e toda a seção, não só aquela linha.
    bad = con.execute(f"SELECT DISTINCT {key} FROM duplicates_votes_{year} WHERE versions>1").df()
    bad["vote_conflict"] = True
    frame = frame.merge(bad, on=KEY, how="left", validate="one_to_one")
    frame["vote_conflict"] = frame["vote_conflict"].fillna(False).astype(bool)
    if use_bu and has_table(con, f"bu_{year}"):
        meta = con.execute(f"""SELECT {key},max(aggregation) bu_aggregation, max(aptos) bu_aptos,
            max(attendance) bu_attendance FROM bu_{year} GROUP BY {key}""").df()
        frame = frame.merge(meta, on=KEY, how="left", validate="one_to_one")
        frame["aggregation"] = frame["aggregation"].fillna(frame.bu_aggregation)
    frame["structural_issue"] = (
        (frame["attendance"] > frame["aptos"]).fillna(False) |
        ((frame["attendance"] + frame["abstention"]) != frame["aptos"]).fillna(False) |
        ((frame["valid"] + frame["blank"] + frame["null_votes"] + frame["other_votes"]) != frame["attendance"]).fillna(False)
    )
    frame["eligible_source"] = frame["has_votes"] & frame["has_detail"] & ~frame["vote_conflict"] & ~frame["structural_issue"] & frame.valid.gt(0)
    frame.loc[frame.installed.fillna("").str.upper().isin(["NÃO", "NAO", "N"]), "eligible_source"] = False
    frame.loc[frame.annulled.fillna("").str.upper().isin(["SIM", "S"]), "eligible_source"] = False
    return frame, finalists, candidates


def paired(base, finalists, candidates, level="secao"):
    """Totais por local/município usam o universo inteiro, não só seções pareadas."""
    keys_by_level = {"secao": GEO, "local": ["uf", "municipality", "zone", "local"],
                     "municipio": ["uf", "municipality"], "uf": ["uf"]}
    keys = keys_by_level[level]
    measures = ["aptos", "attendance", "abstention", "valid", "blank", "null_votes", "other_votes"] + [f"votes_{c}" for c in candidates]
    context = ["year", "turn"] + GEO + ["municipality_name", "local", "local_name", "local_address", "generation", "vote_generation", "aggregation", "eligible_source"]
    b = base[list(dict.fromkeys(context + measures))].copy()
    b["_member"] = b["zone"].astype(str) + ":" + b["section"].astype(str)
    if level == "secao":
        b["membership"] = b["_member"]
        b["n_sections"] = 1
    else:
        signatures = [aggregation_identity(m, z, s, a) for m, z, s, a in
            zip(b.municipality, b.zone, b.section, b.aggregation)]
        b["_member"] = [item[0] for item in signatures]
        b["eligible_source"] = b.eligible_source & np.asarray([item[1] for item in signatures], dtype=bool)
        aggs = {m: (lambda s: s.sum(min_count=len(s))) for m in measures}
        aggs.update({"membership": ("_member", lambda s: "|".join(sorted(s.astype(str)))),
                     "n_sections": ("_member", "size"), "eligible_source": ("eligible_source", "all")})
        # Named aggregation to preserve missing values instead of quietly undercounting.
        named = {m: (m, fun) for m, fun in aggs.items() if m in measures}
        named.update({k: v for k, v in aggs.items() if k not in measures})
        if "municipality" in keys:
            named["municipality_name"] = ("municipality_name", "first")
        b = b.groupby(["year", "turn"] + keys, dropna=False, observed=True).agg(**named).reset_index()
    one = b.loc[b.turn.eq(1)].drop(columns="turn")
    two = b.loc[b.turn.eq(2)].drop(columns="turn")
    out = one.merge(two, on=["year"] + keys, how="outer", suffixes=("_1", "_2"), indicator="coverage", validate="one_to_one")
    out["level"] = level
    out["is_exterior"] = out["uf"].eq("ZZ")
    out["comparable"] = (out.coverage.eq("both") & out["eligible_source_1"].fillna(False) &
        out["eligible_source_2"].fillna(False) & out["membership_1"].eq(out["membership_2"]) &
        out["aptos_1"].eq(out["aptos_2"]) & out["aptos_1"].gt(0) & out["attendance_1"].notna() & out["attendance_2"].notna())
    out["comparison_reason"] = "comparável"
    out.loc[~out["eligible_source_1"].fillna(False).astype(bool) | ~out["eligible_source_2"].fillna(False).astype(bool), "comparison_reason"] = "fonte ausente, votos válidos zero ou inconsistência de origem"
    out.loc[out["attendance_1"].isna() | out["attendance_2"].isna(), "comparison_reason"] = "comparecimento ausente"
    out.loc[out["aptos_1"].ne(out["aptos_2"]), "comparison_reason"] = "quantidade de aptos diferente ou ausente"
    out.loc[out["membership_1"].ne(out["membership_2"]), "comparison_reason"] = "composição de seções diferente ou ausente"
    out.loc[~out.coverage.eq("both"), "comparison_reason"] = "registro presente em um único turno"
    # Presença de campo de agregação exige revisão antes de alertar em nível seção.
    if level == "secao":
        aggregation = out["aggregation_1"].notna() | out["aggregation_2"].notna()
        out.loc[aggregation, "comparable"] = False
        out.loc[aggregation, "comparison_reason"] = "seção agregada: conferir em unidade territorial compatível"
        out["local_changed"] = out["local_1"].ne(out["local_2"]) & out["local_1"].notna() & out["local_2"].notna()
    out["small"] = (out["attendance_1"].lt(50) | out["attendance_2"].lt(50)).fillna(False).astype(bool)
    changes = [m for m in measures if not m.startswith("votes_") or int(m.split("_")[1]) in finalists]
    for m in changes:
        out[f"delta_{m}"] = out[f"{m}_2"] - out[f"{m}_1"]
        out[f"pct_{m}"] = 100 * ratio(out[f"delta_{m}"], out[f"{m}_1"])
    out["turnout_1"] = ratio(out.attendance_1, out.aptos_1)
    out["turnout_2"] = ratio(out.attendance_2, out.aptos_2)
    out["delta_turnout_pp"] = 100 * (out.turnout_2 - out.turnout_1)
    for name, numerator, denominator in [("blank", "blank", "attendance"), ("null", "null_votes", "attendance")]:
        for t in (1, 2):
            out[f"{name}_share_{t}"] = ratio(out[f"{numerator}_{t}"], out[f"{denominator}_{t}"])
        out[f"delta_{name}_pp"] = 100 * (out[f"{name}_share_2"] - out[f"{name}_share_1"])
    for c in finalists:
        for t in (1, 2):
            out[f"share_{c}_{t}"] = ratio(out[f"votes_{c}_{t}"], out[f"valid_{t}"])
        out[f"delta_share_{c}_pp"] = 100 * (out[f"share_{c}_2"] - out[f"share_{c}_1"])
        out[f"zero_{c}"] = out[f"votes_{c}_1"].gt(0) & out[f"votes_{c}_2"].eq(0)
    out["eliminated_votes_1"] = out.valid_1 - sum(out[f"votes_{c}_1"] for c in finalists)
    # Espaço aritmético para ganhos sem perda do rival: não é estimativa de transferência individual.
    out["non_finalist_pool_1"] = out.eliminated_votes_1 + out.blank_1 + out.null_votes_1
    metrics = ["delta_turnout_pp", "delta_blank_pp", "delta_null_pp"] + [f"delta_share_{c}_pp" for c in finalists]
    out["max_change_pp"] = out[metrics].abs().max(axis=1)
    out["any_zero"] = out[[f"zero_{c}" for c in finalists]].any(axis=1)
    eligible = out.comparable & ~out.small
    for threshold in (5, 10, 15):
        out[f"flag_{threshold}pp"] = eligible & (out.max_change_pp.ge(threshold) | out.any_zero)
    out["observed_extreme"] = out.max_change_pp.ge(10) | out.any_zero
    out["robust_max"] = np.nan
    out["robust_flag"] = False
    out["peer_status"] = "não calculado neste nível"
    return out


def peers(frame, finalists, candidates, k=30):
    """k vizinhos: município primeiro; completar na mesma UF. Alvo sempre excluído."""
    if isinstance(k, bool) or not isinstance(k, (int, np.integer)) or k < 1:
        raise ValueError("A quantidade de pares deve ser um inteiro positivo")
    frame = frame.copy()
    metrics = ["delta_turnout_pp", "delta_blank_pp", "delta_null_pp"] + [f"delta_share_{c}_pp" for c in finalists]
    frame["peer_count"] = 0
    frame["peer_scope"] = ""
    frame["peer_status"] = "não comparável ou menos de 50 comparecentes"
    for metric in metrics:
        frame[f"peer_median_{metric}"] = np.nan
        frame[f"peer_mad_{metric}"] = np.nan
        frame[f"z_{metric}"] = np.nan
    frame["peer_ids"] = ""
    valid = frame.comparable & ~frame.small
    for uf, ids in frame.loc[valid].groupby("uf", sort=True).groups.items():
        ids = np.asarray(sorted(ids))
        f = frame.loc[ids]
        if len(f) < k + 1:
            frame.loc[ids, "peer_status"] = f"menos de {k} pares elegíveis na UF"
            continue
        features = [np.log1p(f.aptos_1.to_numpy(float)), f.turnout_1.to_numpy(float)]
        features.extend(ratio(f[f"votes_{c}_1"], f.valid_1).to_numpy(float) for c in candidates)
        x = np.column_stack(features)
        if not np.isfinite(x).all():
            raise ValueError("Características dos pares têm valores ausentes")
        center = np.median(x, axis=0)
        scale = np.std(x, axis=0)
        x = (x - center) / np.where(scale > 1e-12, scale, 1)
        # Consulta em lotes: arrays O(n*k), sem matriz de distâncias n*n.
        neighbors = np.empty((len(f), k), dtype=np.int32)
        municipalities = f.municipality.to_numpy()
        local_positions = pd.Series(np.arange(len(f))).groupby(municipalities).apply(list)
        # Uma seção com 30 pares no município não precisa de uma busca na UF inteira.
        fallback = np.concatenate([np.asarray(p, dtype=int) for p in local_positions if len(p) <= k]) if any(len(p) <= k for p in local_positions) else np.array([], dtype=int)
        state_neighbors = np.full((len(f), k + 1), -1, dtype=np.int32)
        if len(fallback):
            state_neighbors[fallback] = cKDTree(x).query(x[fallback], k=k + 1, workers=2)[1]
        scope = np.full(len(f), "município + UF", dtype=object)
        for positions in local_positions:
            pos = np.asarray(positions, dtype=int)
            if len(pos) > 1:
                local_tree = cKDTree(x[pos])
                local_idx = local_tree.query(x[pos], k=min(k + 1, len(pos)), workers=2)[1]
                local_idx = np.asarray(local_idx).reshape(len(pos), -1)
            else:
                local_idx = np.array([[0]])
            for row, p in enumerate(pos):
                local = [int(pos[j]) for j in local_idx[row] if pos[j] != p][:k]
                chosen = set(local)
                for q in state_neighbors[p]:
                    if len(local) == k:
                        break
                    if q != p and int(q) not in chosen:
                        local.append(int(q))
                        chosen.add(int(q))
                neighbors[p] = local
                if len(pos) >= k + 1:
                    scope[p] = "município"
        max_z = np.full(len(f), np.nan)
        informative = np.zeros(len(f), dtype=int)
        for metric in metrics:
            y = f[metric].to_numpy(float)
            peer_values = y[neighbors]
            median = np.median(peer_values, axis=1)
            mad = np.median(np.abs(peer_values - median[:, None]), axis=1)
            z = np.divide(np.abs(y - median), 1.4826 * mad,
                out=np.full(len(f), np.nan), where=mad > 1e-9)
            frame.loc[ids, f"peer_median_{metric}"] = median
            frame.loc[ids, f"peer_mad_{metric}"] = mad
            frame.loc[ids, f"z_{metric}"] = z
            max_z = np.fmax(max_z, z)
            informative += np.isfinite(z)
        labels = (f.uf.astype(str) + "/" + f.municipality.astype(str) + "/" + f.zone.astype(str) + "/" + f.section.astype(str)).to_numpy()
        frame.loc[ids, "peer_ids"] = ["|".join(labels[n]) for n in neighbors]
        frame.loc[ids, "peer_count"] = k
        frame.loc[ids, "peer_scope"] = scope
        frame.loc[ids, "robust_max"] = max_z
        frame.loc[ids, "robust_flag"] = max_z > 3.5
        frame.loc[ids, "peer_status"] = np.where(informative == len(metrics), "calculado", "dispersão insuficiente em um ou mais indicadores")
        LOG.info("Pares %s: %s seções", uf, len(f))
    return frame


def reconcile_bu(con, year):
    """Ausência de registro/candidato não é convertida em zero sem BU presente."""
    if not has_table(con, f"bu_{year}"):
        return pd.DataFrame(columns=KEY + ["candidate", "votes_result", "votes_bu", "difference", "status"])
    table = create_bu_reconciliation(con, year)
    return con.execute(f"SELECT * FROM {table}").df()


def create_bu_reconciliation(con, year):
    keys = KEY + ["candidate"]
    sqlkey = ",".join(keys)
    table = f"bu_reconciliation_{year}"
    section_key = ','.join(KEY)
    con.execute(f"""CREATE OR REPLACE TABLE {table} AS
        WITH vk AS (SELECT DISTINCT {section_key},true present_v FROM votes_{year}),
             bk AS (SELECT DISTINCT {section_key},true present_b FROM bu_{year}),
             joined AS (SELECT {','.join(f'coalesce(v.{k},b.{k}) AS "{k}"' for k in keys)},
                v.votes raw_votes_result, b.votes raw_votes_bu,
                v.generation result_generation,b.generation bu_generation,
                v.election_id result_election,b.election_id bu_election,
                v.source_file result_source,b.source_file bu_source
                FROM votes_{year} v FULL OUTER JOIN bu_{year} b USING({sqlkey}))
        SELECT j.*,CASE WHEN present_v THEN coalesce(raw_votes_result,0) END votes_result,
            CASE WHEN present_b THEN coalesce(raw_votes_bu,0) END votes_bu,
            CASE WHEN present_v AND present_b THEN coalesce(raw_votes_result,0)-coalesce(raw_votes_bu,0) END difference,
        CASE WHEN NOT coalesce(present_v,false) OR NOT coalesce(present_b,false) THEN 'seção ausente em uma fonte'
             WHEN EXISTS(SELECT 1 FROM duplicates_votes_{year} d WHERE d.versions>1 AND
                  {' AND '.join('j.'+k+'=d.'+k for k in keys)}) OR
                  EXISTS(SELECT 1 FROM duplicates_bu_{year} d WHERE d.versions>1 AND
                  {' AND '.join('j.'+k+'=d.'+k for k in keys)}) THEN 'registro conflitante: não imputar zero'
             WHEN coalesce(raw_votes_result,0)=coalesce(raw_votes_bu,0) THEN 'concordante'
             ELSE 'pendente de esclarecimento: diferença entre fontes' END status
        FROM joined j LEFT JOIN vk USING({section_key}) LEFT JOIN bk USING({section_key})""")
    return table


def reconciliation_totals(con, year):
    from .reconciliation import reconcile_totals
    return reconcile_totals(con, year)


def rank(frame):
    out = frame.copy()
    out["statistical_alert"] = out.flag_10pp | out.robust_flag
    out["review_status"] = np.where(out.statistical_alert, "pendente de esclarecimento", "sem alerta pelos critérios")
    # Não comparáveis continuam visíveis no inventário, mas não recebem ranking.
    out["review_status"] = np.where(~out.comparable, "comparação indisponível: composição ou cobertura", out.review_status)
    out["reason"] = ["; ".join(filter(None, [
        "mudança >=10 pp" if a else "", "candidato passou a zero" if z else "",
        "desvio robusto >3,5" if r else ""])) for a, z, r in
        zip(out.flag_10pp & out.max_change_pp.ge(10), out.any_zero & out.comparable & ~out.small, out.robust_flag)]
    out["_score"] = out.robust_max.fillna(-1)
    out = out.sort_values(["statistical_alert", "_score", "max_change_pp", "uf", "municipality", "zone", "section"],
                          ascending=[False, False, False, True, True, True, True], kind="stable")
    out["priority"] = pd.Series(np.arange(1, len(out) + 1), index=out.index).where(out.statistical_alert)
    return out.drop(columns="_score")
