import csv
import duckdb
import pandas as pd
import pytest

from eleicoes.reconciliation import reconcile_categories


@pytest.mark.parametrize("omit_technical", [False, True])
def test_technical_null_explanation_requires_zone_level_agreement(tmp_path, omit_technical):
    source = tmp_path / "detail.csv"
    rows = []
    for zone, regular, total_null in ((1, 10, 15), (2, 8, 13)):
        rows.append(dict(CD_CARGO=1, NR_TURNO=1, SG_UF="SP", CD_MUNICIPIO=1, NR_ZONA=zone,
            QT_TOTAL_VOTOS_VALIDOS=90, QT_VOTOS_BRANCOS=0, QT_TOTAL_VOTOS_NULOS=total_null,
            QT_VOTOS_NULOS=regular, QT_VOTOS_NULOS_TECNICOS=5, QT_COMPARECIMENTO=105))
    if omit_technical:
        for row in rows:
            row.pop("QT_VOTOS_NULOS_TECNICOS")
    with source.open("w", encoding="latin-1", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    con = duckdb.connect()
    con.execute("CREATE TABLE inputs_2026(kind VARCHAR,path VARCHAR)")
    con.execute("INSERT INTO inputs_2026 VALUES ('official_detail',?)", [str(source)])
    con.execute("CREATE TABLE votes_2026(year INTEGER,turn INTEGER,uf VARCHAR,municipality VARCHAR,zone VARCHAR,candidate INTEGER,votes INTEGER)")
    for zone in ("1", "2"):
        con.executemany("INSERT INTO votes_2026 VALUES (2026,1,'SP','1',?,?,?)",
            [(zone, 13, 90), (zone, 28, 5), (zone, 96, 10)])
    nominal = pd.DataFrame([dict(year=2026,turn=1,uf="SP",municipality="1",zone=z,status="pendente") for z in ("1", "2")])
    actual = reconcile_categories(con, 2026, nominal).set_index("zone")
    assert actual.loc["1", "technical_category_match"] == (not omit_technical)
    assert not actual.loc["2", "technical_category_match"]
    con.close()
