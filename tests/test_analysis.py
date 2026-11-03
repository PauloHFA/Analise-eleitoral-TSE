import numpy as np
import pandas as pd
import pytest

from eleicoes.analysis import paired, peers, rank, ratio, section_base, reconcile_bu, reconciliation_totals, export_frame
from eleicoes.cli import ingest_files, save_analysis_cache, cached_analysis
from eleicoes.demo import create_demo
from eleicoes.ingest import clean, connect, normalize, has_table
from eleicoes.reconciliation import reconcile_totals


@pytest.fixture(scope="module")
def database(tmp_path_factory):
    root = tmp_path_factory.mktemp("demo")
    paths = create_demo(root)
    c = connect(root / "test.duckdb")
    ingest_files(c, {k: [v] for k, v in paths.items()}, 2026)
    yield c
    c.close()


@pytest.fixture(scope="module")
def analysis(database):
    base, finalists, candidates = section_base(database, 2026)
    frame = paired(base, finalists, candidates)
    return base, finalists, candidates, peers(frame, finalists, candidates)


def test_ratio_zero_is_missing():
    r = ratio(pd.Series([1, 0, 5]), pd.Series([0, 0, 10]))
    assert r.isna().iloc[:2].all()
    assert r.iloc[2] == .5


def test_extreme_2000_2000_to_4000_zero(analysis):
    _, _, _, f = analysis
    row = f.loc[f.section.eq("1")].iloc[0]
    assert row.votes_13_1 == row.votes_22_1 == 2000
    assert row.votes_13_2 == 4000 and row.votes_22_2 == 0
    assert row.delta_share_13_pp == 50
    assert row.delta_share_22_pp == -50
    assert row.zero_22 and row.flag_10pp


def test_large_turnout_increase(analysis):
    row = analysis[3].loc[analysis[3].section.eq("2")].iloc[0]
    assert row.delta_attendance == 150
    assert row.delta_turnout_pp == 37.5
    assert row.flag_10pp


def test_composition_change_excluded(analysis):
    row = analysis[3].loc[analysis[3].section.eq("88")].iloc[0]
    assert not row.comparable
    assert not row.flag_10pp
    assert not row.robust_flag


def test_aggregated_section_excluded(analysis):
    row = analysis[3].loc[analysis[3].section.eq("87")].iloc[0]
    assert not row.comparable
    assert not row.flag_10pp


def test_missing_turn_not_zero_filled(analysis):
    row = analysis[3].loc[analysis[3].section.eq("89")].iloc[0]
    assert row.coverage == "left_only"
    assert pd.isna(row.attendance_2)
    assert not row.comparable


def test_missing_attendance_excluded(analysis):
    base, final, candidates, _ = analysis
    b = base.copy()
    b.loc[b.section.eq("1") & b.turn.eq(1), "attendance"] = pd.NA
    row = paired(b, final, candidates).loc[lambda f: f.section.eq("1")].iloc[0]
    assert not row.comparable and not row.flag_10pp


def test_large_exports_leave_connection_reusable(tmp_path):
    con = connect(tmp_path / "export.duckdb")
    frame = pd.DataFrame({"section": np.arange(100000), "value": np.arange(100000) / 3, "label": "dado público"})
    frame["peer_ids"] = [str(i) + "|SP/71072/1/100" * 60 for i in range(len(frame))]
    export_frame(con, frame, tmp_path / "first")
    assert not has_table(con, "inexistente")
    export_frame(con, frame.iloc[:3], tmp_path / "second")
    assert con.execute("SELECT count(*) FROM read_parquet(?)", [str(tmp_path / "first.parquet")]).fetchone()[0] == 100000
    assert con.execute("SELECT count(*) FROM read_csv(?)", [str(tmp_path / "second.csv")]).fetchone()[0] == 3
    assert con.execute("SELECT max(row_group_num_rows) FROM parquet_metadata(?)", [str(tmp_path / "first.parquet")]).fetchall()[0][0] <= 16384
    con.close()


def test_history_cache_rejects_changed_artifact(database, tmp_path):
    output = tmp_path / "cache"
    output.mkdir()
    artifact = output / "dados.csv"
    artifact.write_text("valor\n1\n", encoding="utf-8")
    save_analysis_cache(database, 2026, output, {"ano": 2026}, {}, [13, 22])
    assert cached_analysis(database, 2026, output)["history"]["ano"] == 2026
    artifact.write_text("valor\n2\n", encoding="utf-8")
    assert cached_analysis(database, 2026, output) is None


def test_exterior_separate(analysis):
    row = analysis[3].loc[analysis[3].section.eq("90")].iloc[0]
    assert row.is_exterior
    assert row.peer_count == 0  # não completar com pares de uma UF brasileira


def test_thirty_peers_never_include_target(analysis):
    f = analysis[3]
    for _, row in f.loc[f.peer_count.eq(30)].iterrows():
        own = f"{row.uf}/{row.municipality}/{row.zone}/{row.section}"
        ids = row.peer_ids.split("|")
        assert len(ids) == len(set(ids)) == 30
        assert own not in ids


def test_municipal_peers_prioritized(analysis):
    f = analysis[3]
    row = f.loc[f.section.eq("1")].iloc[0]
    assert row.peer_scope == "município"
    assert all(x.split("/")[1] == row.municipality for x in row.peer_ids.split("|"))


def test_insufficient_dispersion_is_not_infinite(analysis):
    base, final, cand, f = analysis
    constant = paired(base, final, cand)
    metrics = ["delta_turnout_pp", "delta_blank_pp", "delta_null_pp"] + [f"delta_share_{c}_pp" for c in final]
    constant[metrics] = 0.
    r = peers(constant, final, cand)
    assert not r.robust_flag.any()
    assert not np.isinf(r.robust_max.to_numpy(float)).any()
    assert r.loc[r.peer_count.eq(30), "robust_max"].isna().all()


def test_small_sections_description_only(analysis):
    b, final, candidates, _ = analysis
    b = b.copy()
    b.loc[b.section.eq("1"), "attendance"] = 30
    f = paired(b, final, candidates)
    row = f.loc[f.section.eq("1")].iloc[0]
    assert row.small and not row.flag_5pp


def test_identical_duplicate_recorded_not_double_counted(database):
    count = database.execute("SELECT sum(n-1) FROM duplicates_votes_2026 WHERE versions=1").fetchone()[0]
    assert count == 1
    assert database.execute("SELECT sum(votes) FROM votes_2026 WHERE section='1' AND turn=1 AND candidate=13").fetchone()[0] == 2000


def test_conflicting_duplicate_quarantined(database):
    database.execute("CREATE TABLE raw_votes_2022 AS SELECT * REPLACE (2022 AS year) FROM raw_votes_2026")
    database.execute("INSERT INTO raw_votes_2022 SELECT * REPLACE (votes+1 AS votes) FROM raw_votes_2022 WHERE section='1' AND turn=1 AND candidate=13 LIMIT 1")
    clean(database, "votes", 2022)
    assert database.execute("SELECT count(*) FROM votes_2022 WHERE section='1' AND turn=1 AND candidate=13").fetchone()[0] == 0


def test_bu_difference_detected(database):
    checks = reconcile_bu(database, 2026)
    row = checks.loc[checks.section.eq("3") & checks.turn.eq(2) & checks.candidate.eq(13)].iloc[0]
    assert row.difference == 3
    assert "pendente" in row.status
    assert not checks.status.str.contains("persistente").any()


def test_sparse_zero_not_reported_as_missing_bu(database):
    database.execute("BEGIN")
    try:
        database.execute("DELETE FROM raw_bu_2026 WHERE section='1' AND turn=2 AND candidate=22 AND votes=0")
        checks = reconcile_bu(database, 2026)
        row = checks.loc[checks.section.eq("1") & checks.turn.eq(2) & checks.candidate.eq(22)].iloc[0]
        assert row.status == "concordante" and row.votes_bu == 0
    finally:
        database.execute("ROLLBACK")


def test_official_totals_reconcile_after_duplicate_removed(database):
    zones, totals = reconciliation_totals(database, 2026)
    assert zones.difference.eq(0).all()
    assert totals.difference.eq(0).all()


def test_official_sparse_zero_and_missing_zone_are_distinct(database):
    database.execute("BEGIN")
    try:
        database.execute("INSERT INTO raw_official_votes_2026 SELECT * REPLACE (77 AS candidate,0 AS votes) FROM raw_official_votes_2026 WHERE turn=2 AND uf='SP' AND municipality='71072' AND candidate=13 LIMIT 1")
        database.execute("INSERT INTO raw_official_votes_2026 SELECT * REPLACE (78 AS candidate,0 AS votes,'999999' AS zone) FROM raw_official_votes_2026 WHERE turn=2 AND uf='SP' AND municipality='71072' AND candidate=13 LIMIT 1")
        zones, totals = reconcile_totals(database, 2026)
        zero = zones.loc[zones.candidate.eq(77)].iloc[0]
        missing = zones.loc[zones.candidate.eq(78)].iloc[0]
        assert zero.status == "concordante" and zero.section_votes == 0 and zero.zero_imputed
        assert missing.status == "cobertura divergente" and pd.isna(missing.section_votes)
        assert totals.loc[totals.candidate.eq(78), "status"].ne("concordante").all()
    finally:
        database.execute("ROLLBACK")


def test_aggregation_sums_whole_universe(analysis):
    b, final, cand, _ = analysis
    a = paired(b, final, cand, "municipio")
    row = a.loc[a.municipality.eq("71072") & a.uf.eq("SP")].iloc[0]
    expected = b.loc[b.turn.eq(1) & b.municipality.eq("71072") & b.uf.eq("SP"), "attendance"].sum()
    assert row.attendance_1 == expected


def test_membership_change_blocks_local_alert(analysis):
    b, final, cand, _ = analysis
    b = b.copy()
    b.loc[b.section.eq("1") & b.turn.eq(2), "local"] = "OUTRO"
    a = paired(b, final, cand, "local")
    affected = a.loc[a.local.eq("OUTRO")]
    assert not affected.comparable.any()
    assert not affected.flag_10pp.any()


def test_changed_aggregation_members_block_local_comparison(analysis):
    base, final, candidates, _ = analysis
    b = base.loc[base.section.eq("87")].copy()
    b.loc[b.turn.eq(1), "aggregation"] = "88"
    b.loc[b.turn.eq(2), "aggregation"] = "88 / 87"
    assert paired(b, final, candidates, "local").comparable.all()
    b.loc[b.turn.eq(2), "aggregation"] = "9999"
    changed = paired(b, final, candidates, "local")
    assert not changed.comparable.any()
    assert not changed.flag_10pp.any()


def test_sensitivity_monotonic(analysis):
    f = analysis[3]
    assert f.flag_15pp.sum() <= f.flag_10pp.sum() <= f.flag_5pp.sum()


def test_ranking_no_assertion_of_fraud(analysis):
    f = rank(analysis[3])
    assert f.loc[f.statistical_alert, "priority"].notna().all()
    assert not f.review_status.str.contains("fraude|persistente", case=False).any()


def test_unknown_layout_rejected():
    with pytest.raises(ValueError, match="Cargo ausente"):
        normalize(pd.DataFrame({"_SOURCE": ["desconhecido.csv"]}), "votes", 2026)


def test_wrong_year_rejected():
    df = pd.DataFrame({"_SOURCE": ["x.csv"], "CD_CARGO": [1], "ANO_ELEICAO": [2022], "NR_TURNO": [1],
        "SG_UF": ["SP"], "CD_MUNICIPIO": [1], "NR_ZONA": [1], "NR_SECAO": [1], "NR_VOTAVEL": [13], "QT_VOTOS": [1]})
    with pytest.raises(ValueError, match="Ano/turno"):
        normalize(df, "votes", 2026)
