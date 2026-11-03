"""Leitura em blocos, seleção explícita do cargo e quarentena de conflitos."""
from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import duckdb
import pandas as pd

LOG = logging.getLogger(__name__)
KEY = ["year", "turn", "uf", "municipality", "zone", "section"]


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute("SET memory_limit='1GB'")
    con.execute("SET threads=2")
    con.execute("SET preserve_insertion_order=false")
    return con


def csv_chunks(path, chunksize=60000):
    """Prefere BR quando existe, evitando somar BR e UFs em duplicidade."""
    path = Path(path)
    if path.suffix.lower() != ".zip":
        yield from _read_csv(path, path.name, chunksize)
        return
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if n.lower().endswith(".csv") and not n.startswith("__MACOSX"))
        br = [n for n in names if Path(n).stem.upper().endswith("_BR")]
        if br:
            names = br
        if not names:
            raise ValueError(f"Nenhum CSV em {path}")
        for name in names:
            with z.open(name) as f:
                yield from _read_csv(f, f"{path.parent.name}/{path.name}:{name}", chunksize)


def _read_csv(stream, name, chunksize):
    needed = {"DT_GERACAO", "HH_GERACAO", "ANO_ELEICAO", "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO",
        "NR_ZONA", "NR_SECAO", "NR_LOCAL_VOTACAO", "CD_CARGO", "CD_CARGO_PERGUNTA", "DT_ELEICAO", "DT_PLEITO", "CD_ELEICAO",
        "NM_LOCAL_VOTACAO", "DS_LOCAL_VOTACAO_ENDERECO", "NR_VOTAVEL", "NR_CANDIDATO", "NM_VOTAVEL", "NM_URNA_CANDIDATO",
        "NM_CANDIDATO", "QT_VOTOS", "QT_VOTOS_NOMINAIS", "QT_APTOS", "QT_COMPARECIMENTO", "QT_COMPARECENTES", "QT_ABSTENCOES",
        "QT_VOTOS_VALIDOS", "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS", "DS_SITUACAO_SECAO", "DS_SIT_TOTALIZACAO", "DS_TIPO_URNA",
        "DS_SECOES_AGREGADAS", "NR_SECAO_PRINCIPAL", "NR_SECAO_AGREGADORA", "NR_SECAO_AGREGADA", "ST_SECAO_INSTALADA",
        "ST_SECAO_ANULADA", "QT_VOTOS_ANULADOS_APU_SEP", "ST_VOTO_EM_TRANSITO", "NM_TIPO_DESTINACAO_VOTOS"}
    for chunk in pd.read_csv(stream, sep=";", encoding="latin-1", dtype=str,
                             keep_default_na=False, chunksize=chunksize, usecols=lambda c: c.strip().upper() in needed):
        chunk.columns = [c.strip().lstrip("\ufeff").upper() for c in chunk.columns]
        chunk["_SOURCE"] = name
        yield chunk


def column(df, *names, default=None):
    for name in names:
        if name in df:
            return df[name].replace({"": None, "#NULO#": None, "#NULO": None, "#NE#": None, "#NE": None})
    return pd.Series(default, index=df.index, dtype=object)


def number(df, *names, default=None):
    s = pd.to_numeric(column(df, *names, default=default), errors="coerce")
    return s.where(s >= 0).astype("Int64")


def normalize(df, kind, year):
    cargo = number(df, "CD_CARGO", "CD_CARGO_PERGUNTA")
    if cargo.isna().all():
        raise ValueError(f"Cargo ausente em {df['_SOURCE'].iloc[0]}; não inferir Presidente")
    df = df.loc[cargo.eq(1).fillna(False)].copy()
    if df.empty:
        return pd.DataFrame()
    out = pd.DataFrame(index=df.index)
    out["year"] = number(df, "ANO_ELEICAO", default=year)
    out["turn"] = number(df, "NR_TURNO")
    out["uf"] = column(df, "SG_UF")
    out["municipality"] = column(df, "CD_MUNICIPIO")
    out["municipality_name"] = column(df, "NM_MUNICIPIO")
    out["zone"] = column(df, "NR_ZONA")
    out["section"] = column(df, "NR_SECAO")
    out["local"] = column(df, "NR_LOCAL_VOTACAO")
    out["generation"] = column(df, "DT_GERACAO").fillna("") + " " + column(df, "HH_GERACAO").fillna("")
    out["election_date"] = column(df, "DT_ELEICAO", "DT_PLEITO")
    out["election_id"] = column(df, "CD_ELEICAO")
    out["source_file"] = column(df, "_SOURCE")
    out["local_name"] = column(df, "NM_LOCAL_VOTACAO")
    out["local_address"] = column(df, "DS_LOCAL_VOTACAO_ENDERECO")
    if kind in ("votes", "bu", "official_votes"):
        out["candidate"] = number(df, "NR_VOTAVEL", "NR_CANDIDATO")
        out["candidate_name"] = column(df, "NM_VOTAVEL", "NM_URNA_CANDIDATO", "NM_CANDIDATO")
        out["votes"] = number(df, "QT_VOTOS", "QT_VOTOS_NOMINAIS")
        if out["candidate"].isna().any() or out["votes"].isna().any():
            raise ValueError("Candidato/votos ausentes: conferir o leiaute oficial")
    if kind in ("detail", "official_detail", "bu"):
        out["aptos"] = number(df, "QT_APTOS")
        out["attendance"] = number(df, "QT_COMPARECIMENTO", "QT_COMPARECENTES")
        out["abstention"] = number(df, "QT_ABSTENCOES")
        out["detail_valid"] = number(df, "QT_VOTOS_VALIDOS", "QT_VOTOS_NOMINAIS")
        out["detail_blank"] = number(df, "QT_VOTOS_BRANCOS")
        out["detail_null"] = number(df, "QT_VOTOS_NULOS")
        out["status"] = column(df, "DS_SITUACAO_SECAO", "DS_SIT_TOTALIZACAO", "DS_TIPO_URNA")
        out["aggregation"] = column(df, "DS_SECOES_AGREGADAS", "NR_SECAO_PRINCIPAL", "NR_SECAO_AGREGADORA", "NR_SECAO_AGREGADA")
        out["installed"] = column(df, "ST_SECAO_INSTALADA")
        out["annulled"] = column(df, "ST_SECAO_ANULADA")
        out["separately_annulled"] = number(df, "QT_VOTOS_ANULADOS_APU_SEP", default=0)
    if kind.startswith("official"):
        out = out.drop(columns=["section", "local"])
        out["vote_type"] = column(df, "ST_VOTO_EM_TRANSITO", default="N")
        if kind == "official_votes":
            out["destination"] = column(df, "NM_TIPO_DESTINACAO_VOTOS", default="não informado")
    required = ["year", "turn", "uf", "municipality", "zone"]
    if not kind.startswith("official"):
        required.append("section")
    if out[required].isna().any().any():
        raise ValueError(f"Chave incompleta em {kind}")
    if not out["year"].eq(year).all() or not out["turn"].isin([1, 2]).all():
        raise ValueError("Ano/turno inesperado; arquivo recusado")
    # Normalizar representações numéricas (001 == 1) sem alterar códigos de município.
    for c in ("zone", "section", "local", "municipality"):
        if c in out:
            out[c] = out[c].map(lambda x: str(int(x)) if x is not None and str(x).isdigit() else x)
    return out.reset_index(drop=True)


def load(con, path, kind, year, resume=False):
    table = f"raw_{kind}_{year}"
    path = Path(path)
    if resume and path.suffix.lower() == ".zip" and has_table(con, table):
        prefix = f"{path.parent.name}/{path.name}:"
        # A tabela só aparece completa após COMMIT; a origem inclui o hash do ZIP.
        if len(path.parent.name) == 16 and sha256_prefix(path) == path.parent.name:
            same = con.execute(f"SELECT count(*),bool_and(starts_with(source_file,?)) FROM {table}", [prefix]).fetchall()[0]
            if same[0] and same[1]:
                LOG.info("Retomando tabela confirmada do mesmo arquivo: %s", table)
                return table
    # Cada recurso é substituído como unidade numa transação, inclusive em reexecuções.
    con.execute("BEGIN")
    try:
        con.execute(f"DROP TABLE IF EXISTS {table}")
        first = True
        total = 0
        chunks = 0
        for chunk in csv_chunks(path):
            frame = normalize(chunk, kind, year)
            if frame.empty:
                continue
            con.register("incoming", frame)
            if first:
                con.execute(f"CREATE TABLE {table} AS SELECT * FROM incoming")
                first = False
            else:
                con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM incoming")
            con.unregister("incoming")
            total += len(frame)
            chunks += 1
            if chunks % 10 == 0:
                LOG.info("%s: %s linhas processadas", table, f"{total:,}")
        if first:
            raise ValueError(f"Arquivo sem linhas presidenciais: {path}")
        con.execute("COMMIT")
        LOG.info("%s: %s registros presidenciais", table, f"{total:,}")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return table


def sha256_prefix(path):
    from .sources import sha256
    return sha256(path)[:16]


def load_bu(con, paths, year):
    table = f"raw_bu_{year}"
    con.execute("BEGIN")
    try:
        con.execute(f"DROP TABLE IF EXISTS {table}")
        first = True
        for path in paths:
            for chunk in csv_chunks(path):
                frame = normalize(chunk, "bu", year)
                if frame.empty:
                    continue
                con.register("incoming", frame)
                if first:
                    con.execute(f"CREATE TABLE {table} AS SELECT * FROM incoming")
                    first = False
                else:
                    con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM incoming")
                con.unregister("incoming")
        if first:
            raise ValueError("Nenhum boletim presidencial")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


def clean(con, kind, year):
    """Duplicata idêntica é registrada; conflitos de medidas vão à quarentena."""
    raw, target = f"raw_{kind}_{year}", f"{kind}_{year}"
    keys = [x for x in KEY if not (kind.startswith("official") and x == "section")]
    if kind in ("votes", "bu", "official_votes"):
        keys += ["candidate"]
    if kind.startswith("official"):
        keys += ["vote_type"]
    if kind == "official_votes":
        keys += ["destination"]
    key_sql = ",".join(keys)
    measures = ["votes"] if kind in ("votes", "official_votes") else (
        ["votes", "aptos", "attendance"] if kind == "bu" else
        ["aptos", "attendance", "abstention", "detail_valid", "detail_blank", "detail_null"])
    # Medidas + local/agrupamento: versões incompatíveis não podem ser colapsadas.
    cols = [c[0] for c in con.execute(f"DESCRIBE {raw}").fetchall()]
    measure_sql = ",".join(f"coalesce(cast({c} as varchar),'NULL')" for c in measures +
                           (["local"] if "local" in cols else []) +
                           (["aggregation"] if "aggregation" in cols else []))
    con.execute(f"""CREATE OR REPLACE TEMP TABLE duplicate_keys AS
        SELECT {key_sql},count(*) n FROM {raw} GROUP BY {key_sql} HAVING count(*)>1""")
    con.execute(f"""CREATE OR REPLACE TABLE duplicates_{kind}_{year} AS
        SELECT {key_sql},max(d.n) n,count(DISTINCT row({measure_sql})) versions
        FROM {raw} r JOIN duplicate_keys d USING({key_sql}) GROUP BY {key_sql}""")
    old_rows = con.execute("SELECT table_type FROM information_schema.tables WHERE table_name=?", [target]).fetchall()
    old = old_rows[0] if old_rows else None
    if old:
        con.execute(f"DROP {'VIEW' if old[0]=='VIEW' else 'TABLE'} {target}")
    if con.execute(f"SELECT count(*) FROM duplicates_{kind}_{year}").fetchall()[0][0] == 0:
        con.execute(f"CREATE VIEW {target} AS SELECT * FROM {raw}")
        return target
    con.execute(f"""CREATE OR REPLACE TABLE {target} AS
        SELECT r.* EXCLUDE(rn) FROM
        (SELECT *, row_number() OVER(PARTITION BY {key_sql} ORDER BY generation DESC, source_file) rn FROM {raw}) r
        WHERE rn=1 AND NOT EXISTS
        (SELECT 1 FROM duplicates_{kind}_{year} d WHERE d.versions>1 AND
         {' AND '.join('r.'+k+'=d.'+k for k in keys)})""")
    return target


def has_table(con, name):
    return con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name=?", [name]).fetchall()[0][0] > 0
