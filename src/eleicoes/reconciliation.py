"""Conferência de totais com cobertura explícita e zeros esparsos documentados."""
import pandas as pd
import csv
import io
import zipfile
from pathlib import Path


def reconcile_totals(con, year):
    keys = ["year", "turn", "uf", "municipality", "zone", "candidate"]
    group = keys[:-1]
    ks, gs = ",".join(keys), ",".join(group)
    aliases = ",".join(f'coalesce(s.{k},o.{k}) AS "{k}"' for k in keys)
    frame = con.execute(f"""WITH
      s AS (SELECT {ks},sum(votes)::BIGINT section_votes,max(generation) section_generation
            FROM votes_{year} WHERE candidate BETWEEN 1 AND 94 GROUP BY {ks}),
      o AS (SELECT {ks},sum(votes)::BIGINT official_votes,max(generation) official_generation
            FROM official_votes_{year} GROUP BY {ks}),
      vp AS (SELECT {gs},true has_sections,max(generation) zone_section_generation
             FROM votes_{year} GROUP BY {gs}),
      op AS (SELECT {gs},true has_official,max(generation) zone_official_generation
             FROM official_votes_{year} GROUP BY {gs}),
      bad AS (SELECT {ks},true conflict FROM duplicates_votes_{year} WHERE versions>1
              UNION SELECT {ks},true conflict FROM duplicates_official_votes_{year} WHERE versions>1),
      j AS (SELECT {aliases},s.section_votes raw_section_votes,o.official_votes raw_official_votes,
             s.section_generation,o.official_generation FROM s FULL OUTER JOIN o USING({ks}))
      SELECT j.* EXCLUDE(raw_section_votes,raw_official_votes,section_generation,official_generation),
        CASE WHEN has_sections AND NOT coalesce(conflict,false) THEN coalesce(raw_section_votes,0) ELSE raw_section_votes END section_votes,
        CASE WHEN has_official AND NOT coalesce(conflict,false) THEN coalesce(raw_official_votes,0) ELSE raw_official_votes END official_votes,
        CASE WHEN has_sections AND has_official AND NOT coalesce(conflict,false)
             THEN coalesce(raw_section_votes,0)-coalesce(raw_official_votes,0) END difference,
        coalesce(j.section_generation,zone_section_generation) section_generation,
        coalesce(j.official_generation,zone_official_generation) official_generation,
        coalesce(has_sections AND has_official AND NOT coalesce(conflict,false) AND
             (raw_section_votes IS NULL OR raw_official_votes IS NULL),false) zero_imputed,
        CASE WHEN coalesce(conflict,false) THEN 'conflito em fonte: não imputar zero'
             WHEN NOT coalesce(has_sections,false) OR NOT coalesce(has_official,false) THEN 'cobertura divergente'
             WHEN coalesce(raw_section_votes,0)=coalesce(raw_official_votes,0) THEN 'concordante'
             ELSE 'pendente: conferir versão e tratamento na totalização' END status
      FROM j LEFT JOIN vp USING({gs}) LEFT JOIN op USING({gs}) LEFT JOIN bad USING({ks})""").df()
    totals = []
    for label, grouping in [("municipio", ["year", "turn", "uf", "municipality", "candidate"]),
                            ("uf", ["year", "turn", "uf", "candidate"]),
                            ("brasil", ["year", "turn", "candidate"])]:
        g = frame.groupby(grouping, dropna=False, observed=True)[["section_votes", "official_votes"]].sum(min_count=1)
        pending = frame.assign(pending=frame.status.ne("concordante")).groupby(grouping, dropna=False, observed=True).pending.sum()
        g["pending_zone_rows"] = pending
        g["difference"] = g.section_votes - g.official_votes
        g["status"] = "pendente: conferir zonas e cobertura"
        g.loc[g.difference.eq(0) & g.pending_zone_rows.eq(0), "status"] = "concordante"
        g["level"] = label
        totals.append(g.reset_index())
    return frame, pd.concat(totals, ignore_index=True)


def _category_rows(source):
    if source.suffix.lower() != ".zip":
        with source.open(encoding="latin-1", newline="") as stream:
            yield from csv.DictReader(stream, delimiter=";")
        return
    with zipfile.ZipFile(source) as archive:
        names = sorted(n for n in archive.namelist() if n.lower().endswith(".csv"))
        names = [n for n in names if Path(n).stem.upper().endswith("_BR")] or names
        for name in names:
            with archive.open(name) as stream:
                yield from csv.DictReader(io.TextIOWrapper(stream, encoding="latin-1"), delimiter=";")


def reconcile_categories(con, year, nominal):
    """Confronta contagens da urna com categorias de destinação da totalização.

    Preserva a diferença nominal: equivalência aritmética não comprova a razão
    jurídica da reclassificação de uma candidatura.
    """
    source = Path(con.execute(f"SELECT path FROM inputs_{year} WHERE kind='official_detail'").fetchall()[0][0])
    quantities = {
        "official_valid": ("QT_TOTAL_VOTOS_VALIDOS", "QT_VOTOS_NOMINAIS_VALIDOS", "QT_VOTOS_VALIDOS", "QT_VOTOS_NOMINAIS"),
        "official_blank": ("QT_VOTOS_BRANCOS",),
        "official_null_total": ("QT_TOTAL_VOTOS_NULOS", "QT_VOTOS_NULOS"),
        "official_null_regular": ("QT_VOTOS_NULOS",),
        "official_null_technical": ("QT_VOTOS_NULOS_TECNICOS",),
        "official_attendance": ("QT_COMPARECIMENTO",),
    }
    records = []
    for row in _category_rows(source):
        if row.get("CD_CARGO") != "1":
            continue
        record = {"year": year, "turn": int(row["NR_TURNO"]), "uf": row["SG_UF"],
            "municipality": str(int(row["CD_MUNICIPIO"])), "zone": str(int(row["NR_ZONA"]))}
        for target, alternatives in quantities.items():
            field = next((f for f in alternatives if f in row), None)
            value = pd.to_numeric(row[field], errors="coerce") if field else None
            record[target] = int(value) if value is not None and pd.notna(value) and value >= 0 else None
        records.append(record)
    keys = ["year", "turn", "uf", "municipality", "zone"]
    official = pd.DataFrame(records).groupby(keys, dropna=False)[list(quantities)].sum(min_count=1).reset_index()
    section = con.execute(f"""SELECT year,turn,uf,municipality,zone,
        sum(CASE WHEN candidate BETWEEN 1 AND 94 THEN votes ELSE 0 END) section_valid,
        sum(CASE WHEN candidate=95 THEN votes ELSE 0 END) section_blank,
        sum(CASE WHEN candidate=96 THEN votes ELSE 0 END) section_null,
        sum(votes) section_total FROM votes_{year} GROUP BY year,turn,uf,municipality,zone""").df()
    frame = section.merge(official, on=keys, how="outer", validate="one_to_one")
    for column in quantities:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")
    coverage = nominal.assign(nominal_coverage_pending=nominal.status.eq("cobertura divergente"))
    coverage = coverage.groupby(keys, dropna=False).nominal_coverage_pending.any().reset_index()
    frame = frame.merge(coverage, on=keys, how="left", validate="one_to_one")
    frame["valid_difference"] = frame.section_valid - frame.official_valid
    frame["null_total_difference"] = frame.section_null - frame.official_null_total
    frame["blank_difference"] = frame.section_blank - frame.official_blank
    frame["attendance_difference"] = frame.section_total - frame.official_attendance
    frame["technical_category_match"] = (
        frame.official_null_technical.gt(0) &
        frame.valid_difference.eq(frame.official_null_technical) &
        frame.null_total_difference.eq(-frame.official_null_technical) &
        frame.section_null.eq(frame.official_null_regular) &
        frame.blank_difference.eq(0) & frame.attendance_difference.eq(0) &
        ~frame.nominal_coverage_pending.fillna(True).astype(bool)).fillna(False).astype(bool)
    frame["status"] = "pendente: conferir categorias e cobertura"
    unchanged = frame.valid_difference.eq(0) & frame.null_total_difference.eq(0) & frame.blank_difference.eq(0) & frame.attendance_difference.eq(0)
    frame.loc[unchanged & ~frame.nominal_coverage_pending.fillna(True).astype(bool), "status"] = "concordante por categorias"
    frame.loc[frame.technical_category_match, "status"] = "compatível aritmeticamente com reclassificação para nulos técnicos"
    frame["source_file"] = str(source)
    return frame
