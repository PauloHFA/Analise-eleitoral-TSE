import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from eleicoes.analysis import GEO, export_frame, peers, rank
from eleicoes.stability import nested_neighbors, run_stability, score_variant, top_overlap


def reference(n=65):
    rng = np.random.default_rng(731)
    frame = pd.DataFrame(dict(year=2026,uf="SP",municipality=["1"]*(n//2)+["2"]*(n-n//2),
        zone="1",section=[str(i+1) for i in range(n)],municipality_name_1="SIMULADO",
        comparable=True,small=False,aptos_1=400,aptos_2=400,
        attendance_1=rng.integers(250,340,n),attendance_2=rng.integers(250,340,n),
        blank_1=rng.integers(0,10,n),blank_2=rng.integers(0,10,n),
        null_votes_1=rng.integers(0,10,n),null_votes_2=rng.integers(0,10,n)))
    for t in (1,2):
        frame[f"valid_{t}"] = frame[f"attendance_{t}"]-frame[f"blank_{t}"]-frame[f"null_votes_{t}"]
        frame[f"votes_55_{t}"] = (frame[f"valid_{t}"]*.1).astype(int) if t==1 else 0
        frame[f"votes_13_{t}"] = (frame[f"valid_{t}"]*rng.uniform(.2,.7,n)).astype(int)
        frame[f"votes_22_{t}"] = frame[f"valid_{t}"]-frame[f"votes_55_{t}"]-frame[f"votes_13_{t}"]
        frame[f"turnout_{t}"] = frame[f"attendance_{t}"]/frame[f"aptos_{t}"]
    frame["delta_turnout_pp"] = 100*(frame.turnout_2-frame.turnout_1)
    for code,num,den in (("blank","blank","attendance"),("null","null_votes","attendance"),("share_13","votes_13","valid"),("share_22","votes_22","valid")):
        frame[f"delta_{code}_pp"] = 100*(frame[f"{num}_2"]/frame[f"{den}_2"]-frame[f"{num}_1"]/frame[f"{den}_1"])
    metrics = [c for c in frame if c.startswith("delta_")]
    frame["max_change_pp"] = frame[metrics].abs().max(axis=1)
    frame["any_zero"] = False
    frame["flag_10pp"] = frame.max_change_pp.ge(10)
    return rank(peers(frame,[13,22],[13,22,55])).sort_values(GEO,kind="stable").reset_index(drop=True)


def test_anchor_reproduces_reference_and_preserves_nested_membership():
    frame = reference()
    neighbors,keys = nested_neighbors(frame,[13,22],[13,22,55],[15,30,50])
    replay = score_variant(frame,neighbors[30],keys,[13,22],30)
    assert np.allclose(replay.robust_max,frame.robust_max,equal_nan=True)
    assert replay.statistical_alert.tolist() == frame.statistical_alert.tolist()
    for i in range(len(frame)):
        assert neighbors[15][i].tolist() == neighbors[30][i,:15].tolist()
        assert neighbors[50][i,:30].tolist() == neighbors[30][i].tolist()
        assert i not in neighbors[50][i] and len(set(neighbors[50][i])) == 50


def test_insufficient_state_is_unknown_not_zero_or_false():
    frame = reference(40)
    neighbors,keys = nested_neighbors(frame,[13,22],[13,22,55],[15,30,50])
    assert neighbors[50] is None
    result = score_variant(frame,None,keys,[13,22],50)
    assert not result.available.any()
    assert result.robust_flag.isna().all() and result.statistical_alert.isna().all()
    assert result.robust_max.isna().all()


def test_corrupt_baseline_is_rejected():
    frame = reference()
    frame.loc[0,"peer_ids"] = frame.loc[0,"peer_ids"].split("|")[0]+"|"+frame.loc[0,"peer_ids"]
    with pytest.raises(ValueError,match="Referência de 30"):
        nested_neighbors(frame,[13,22],[13,22,55],[15,30,50])


def test_mad_zero_is_inconclusive_and_small_mad_is_only_diagnostic():
    frame = reference()
    for metric in [c for c in frame if c.startswith("delta_")]:
        frame[metric] = 0.
    neighbors,keys = nested_neighbors(frame,[13,22],[13,22,55],[15,30])
    result = score_variant(frame,neighbors[15],keys,[13,22],15)
    assert result.robust_max.isna().all() and not result.robust_flag.any()
    assert result.mad_below_one_unit.isna().all()
    frame["delta_blank_pp"] = np.arange(len(frame))*1e-5
    result = score_variant(frame,neighbors[15],keys,[13,22],15)
    assert result.mad_below_one_unit.all()
    assert result.statistical_alert.tolist() == (result.absolute_flag | result.robust_flag).tolist()


def test_empty_top_lists_do_not_claim_perfect_agreement():
    assert top_overlap([],[],100)["jaccard"] is None
    result = top_overlap([1,2],[2,3],25)
    assert result["intersection"] == 1 and result["jaccard"] == 1/3
    assert result["left_size"] == 2 and result["retention_left"] == .5


@pytest.mark.parametrize("size",[65,40])
def test_run_uses_common_universe_and_keeps_source_unchanged(tmp_path,size):
    source = tmp_path/"source"
    source.mkdir()
    frame = reference(size)
    writer = duckdb.connect()
    export_frame(writer,frame,source/"indicadores_secoes")
    export_frame(writer,pd.DataFrame([dict(turn=t,candidate=c) for t in (1,2) for c in ([13,22,55] if t==1 else [13,22])]),source/"candidatos")
    writer.close()
    before = (source/"indicadores_secoes.parquet").read_bytes()
    result = run_stability(source)
    assert result["eligible_units"] == size
    assert result["common_units"] == (size if size>=51 else 0)
    assert (source/"indicadores_secoes.parquet").read_bytes() == before
    con = duckdb.connect()
    for name in ("variantes","rankings","comparacao","top100"):
        path = source/"estabilidade"/name
        assert con.execute("SELECT count(*) FROM read_parquet(?)",[str(path.with_suffix('.parquet'))]).fetchone() == con.execute("SELECT count(*) FROM read_csv(?,header=true)",[str(path.with_suffix('.csv'))]).fetchone()
    assert con.execute("SELECT count(*) FROM read_parquet(?)",[str(source/"estabilidade/variantes.parquet")]).fetchone()[0] == size*3
    if size<51:
        parquet=source/"estabilidade/variantes.parquet"
        schema={r[0]:r[1] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)",[str(parquet)]).fetchall()}
        parsed=con.read_csv(str(parquet.with_suffix('.csv')),columns=schema,header=True,quotechar='"',escapechar='"',allow_quoted_nulls=False).df()
        unavailable=parsed.loc[parsed.k.eq(50)]
        assert unavailable.peer_ids.eq("").all() and unavailable.driver_metric.isna().all()
    con.close()
    with pytest.raises(FileExistsError):
        run_stability(source)


@pytest.mark.parametrize("k",[0,-1,True,1.5])
def test_invalid_peer_count_is_rejected(k):
    with pytest.raises(ValueError):
        peers(reference(),[13,22],[13,22,55],k=k)
