import json

import numpy as np
import pandas as pd
import pytest

from eleicoes.investigation import metrics, zeros, classify, peer_margin_scores, cohort_totals, investigate


def sample(f1=2000, l1=2000, f2=0, l2=4000, third=0, blank2=0, null2=0):
    row = dict(year=2026, uf="SP", municipality="1", zone="1", section="1", level="secao",
        comparable=True, comparison_reason="comparável", small=False, is_exterior=False)
    for t,f,l,b,n,other in ((1,f1,l1,0,0,third),(2,f2,l2,blank2,null2,0)):
        total = f+l+other if f is not None and l is not None else np.nan
        row.update({f"votes_22_{t}":f, f"votes_13_{t}":l, f"valid_{t}":total,
            f"attendance_{t}":total+b+n, f"aptos_{t}":6000, f"abstention_{t}":6000-total-b-n,
            f"blank_{t}":b, f"null_votes_{t}":n, f"other_votes_{t}":0})
    return pd.DataFrame([row])


def test_2000_each_to_4000_and_zero():
    row = zeros(metrics(sample())).iloc[0]
    assert row.positive_to_zero and row.unanimity_all_ballots
    assert row.margin_loss_22_pp == 100
    assert row.previous_zero_candidate_votes == 2000
    assert row.ballot_balance_residual == 0


def test_already_zero_is_not_new_disappearance():
    row = zeros(metrics(sample(0,100,0,120))).iloc[0]
    assert row.already_zero and not row.positive_to_zero


def test_valid_unanimity_preserves_blank_and_null_denominator():
    row = zeros(metrics(sample(3,100,0,110,blank2=2,null2=1))).iloc[0]
    assert not row.unanimity_all_ballots
    assert row.valid_2 == 110 and row.attendance_2 == 113


def test_missing_second_turn_is_not_zero():
    assert zeros(metrics(sample(f2=None))).empty


def test_missing_first_turn_does_not_claim_positive_to_zero():
    row = zeros(metrics(sample(f1=None))).iloc[0]
    assert not row.first_turn_available and not row.positive_to_zero and not row.already_zero


def test_advantage_can_fall_while_absolute_votes_increase():
    row = metrics(sample(150,100,160,240,third=100)).iloc[0]
    assert row.flip_to_13 and row.loss_22_10pp
    assert row.delta_votes_22 == 10 and row.margin_loss_22_pp == 40
    assert row.ballot_balance_residual == 0


def test_eliminated_candidates_do_not_change_the_pairwise_denominator():
    row = metrics(sample(150,100,150,100,third=500)).iloc[0]
    assert row.margin_loss_22_pp == 0 and not row.loss_22_5pp
    assert row.share_22_1 != row.share_22_2


@pytest.mark.parametrize("comparable,missing,difference,expected", [
    (True,0,0,"mudança confirmada nos arquivos"),
    (False,0,0,"comparação territorial limitada"),
    (True,1,0,"comparação territorial limitada"),
    (True,0,1,"divergência documental"),
])
def test_classification_preserves_coverage_and_composition(comparable,missing,difference,expected):
    f = metrics(sample())
    f["comparable"] = comparable
    f["document_missing"] = missing
    f["document_differences"] = difference
    f["election_mismatches"] = 0
    assert classify(f).iloc[0].investigation_status == expected


def test_reused_peers_and_zero_mad():
    f = pd.concat([sample(10,10,10,10)]*31,ignore_index=True)
    f["section"] = [str(i) for i in range(31)]
    f = metrics(f)
    ids = [f"SP/1/1/{i}" for i in range(1,31)]
    neighbors = f.iloc[[0]][["year","uf","municipality","zone","section","comparable","small"]].copy()
    neighbors["peer_ids"] = "|".join(ids)
    neighbors["peer_count"] = 30
    result = peer_margin_scores(f, neighbors).iloc[0]
    assert result.margin_peer_status == "dispersão insuficiente" and pd.isna(result.margin_robust_z)
    f.loc[0,"margin_loss_22_pp"] = 100
    f.loc[1:,"margin_loss_22_pp"] = np.arange(30)
    result = peer_margin_scores(f, neighbors).iloc[0]
    assert result.margin_robust_z > 3.5 and np.isfinite(result.margin_robust_z)
    neighbors.loc[0,"peer_ids"] = "SP/1/1/0|" + "|".join(ids[1:])
    with pytest.raises(ValueError):
        peer_margin_scores(f, neighbors)


def test_cohort_is_a_subset_with_explicit_coverage():
    f = pd.concat([sample(60,40,65,35),sample(50,40,40,80)],ignore_index=True)
    f["section"] = ["1","2"]
    f.loc[1,"comparable"] = False
    full = f.groupby(["year","uf","municipality"])[[f"{m}_{t}" for m in ("aptos","attendance","abstention","valid","blank","null_votes","other_votes","votes_13","votes_22") for t in (1,2)]].sum().reset_index()
    result = cohort_totals(f, metrics(full)).iloc[0]
    assert result.cohort_sections == 1
    assert result.cohort_votes_22_1 == 60 and result.votes_22_1 == 110
    assert 0 < result.cohort_coverage_attendance_1_pct < 100


def test_local_pipeline_exports_case_proofs_without_redownloading(tmp_path):
    from eleicoes.demo import create_demo
    from eleicoes.cli import ingest_files, analyze_year
    from eleicoes.ingest import connect
    from eleicoes.sources import write_json
    paths = create_demo(tmp_path / "raw")
    con = connect(tmp_path / "test.duckdb")
    ingest_files(con, {k:[v] for k,v in paths.items()}, 2026)
    frame,hist,summary,finalists,issues = analyze_year(con,2026,tmp_path)
    con.close()
    write_json(tmp_path / "resumo.json", dict(summary,demo=True,historical=[hist]))
    original = (tmp_path / "indicadores_secoes.parquet").read_bytes()
    result = investigate(tmp_path,ufs=("SP",),regenerate=False)
    assert result["positive_to_zero_22"] == 1
    assert result["demo"] and not result["baseline_differences"]
    assert (tmp_path / "indicadores_secoes.parquet").read_bytes() == original
    case = json.loads((tmp_path / "investigacao_fichas/zero-secao-SP-71072-1-1.json").read_text(encoding="utf-8"))
    assert case["bu_records"] and len(case["section_metadata"]) == 2
    assert case["indicators"]["investigation_status"] == "mudança confirmada nos arquivos"
    assert (tmp_path / "investigacao_viradas.csv").exists()
    from eleicoes.investigation_report import load_investigation, pdf_investigation
    from reportlab.lib.styles import getSampleStyleSheet
    bundle = load_investigation(tmp_path)
    assert not bundle["stale"] and len(bundle["zeros"]) == 1
    assert "DEMONSTRAÇÃO COM DADOS SIMULADOS" in bundle["html"]
    assert pdf_investigation(bundle,getSampleStyleSheet())
