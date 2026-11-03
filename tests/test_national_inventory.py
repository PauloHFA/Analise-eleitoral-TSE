import numpy as np
import pandas as pd
import pytest

from eleicoes.investigation import peer_margin_scores
from eleicoes.national_inventory import add_patterns,margin_scores,run_inventory


def sample(f1=60,l1=40,f2=45,l2=70):
    row=dict(year=2026,uf='SP',municipality='1',zone='1',section='1',level='secao',comparable=True,small=False,
             comparison_reason='comparável',peer_count=0,peer_ids=None)
    for t,f,l in ((1,f1,l1),(2,f2,l2)):
        row.update({f'votes_22_{t}':f,f'votes_13_{t}':l,f'valid_{t}':f+l,f'attendance_{t}':f+l,
                    f'aptos_{t}':400,f'abstention_{t}':400-f-l,f'blank_{t}':0,f'null_votes_{t}':0,f'other_votes_{t}':0})
    return pd.DataFrame([row])


def test_candidate_swap_reverses_margin_and_patterns_symmetrically():
    frame=sample(150,100,160,240)
    a=add_patterns(frame).iloc[0]
    other=frame.copy()
    for t in (1,2):other[f'votes_22_{t}'],other[f'votes_13_{t}']=frame[f'votes_13_{t}'],frame[f'votes_22_{t}']
    b=add_patterns(other).iloc[0]
    assert a.flip_to_13 and b.flip_to_22
    assert a.margin_change_pp==-b.margin_change_pp
    assert a.loss_22_10pp==b.loss_13_10pp
    assert a.delta_votes_22>0 and a.margin_change_pp<0


def peers_fixture():
    frame=pd.concat([sample()]*31,ignore_index=True)
    frame['section']=[str(i) for i in range(31)]
    frame['peer_count']=0
    frame['peer_ids']=None
    frame.loc[0,'peer_count']=30
    frame.loc[0,'peer_ids']='|'.join(f'SP/1/1/{i}' for i in range(1,31))
    frame=add_patterns(frame)
    frame['margin_loss_22_pp']=np.arange(31,dtype=float)
    frame.loc[0,'margin_loss_22_pp']=90
    return frame


def test_vectorized_scores_reproduce_existing_method_without_reselecting():
    frame=peers_fixture()
    neighbors=frame.iloc[[0]][['year','uf','municipality','zone','section','comparable','small','peer_count','peer_ids']]
    expected=peer_margin_scores(frame,neighbors).iloc[0]
    actual=margin_scores(frame).iloc[0]
    assert actual.margin_peer_median==expected.margin_peer_median
    assert actual.margin_peer_mad==expected.margin_peer_mad
    assert actual.margin_robust_z==pytest.approx(expected.margin_robust_z)


@pytest.mark.parametrize('kind',['self','duplicate','missing','ineligible'])
def test_invalid_neighbors_are_rejected(kind):
    frame=peers_fixture()
    if kind=='ineligible':frame.loc[1,'small']=True
    else:
        ids=frame.loc[0,'peer_ids'].split('|')
        ids[0]={'self':'SP/1/1/0','duplicate':ids[1],'missing':'MG/1/1/1'}[kind]
        frame.loc[0,'peer_ids']='|'.join(ids)
    with pytest.raises(ValueError):margin_scores(frame)


def test_zero_mad_missing_indicator_and_insufficient_pairs_remain_unknown():
    frame=peers_fixture()
    frame['margin_loss_22_pp']=0.
    actual=margin_scores(frame)
    assert actual.iloc[0].margin_peer_status=='dispersão insuficiente'
    assert pd.isna(actual.iloc[0].margin_robust_flag)
    assert pd.isna(actual.iloc[1].margin_robust_flag)
    frame.loc[1,'margin_loss_22_pp']=np.nan
    assert margin_scores(frame).iloc[0].margin_peer_status=='indicadores dos pares indisponíveis'


def test_zero_pair_denominator_is_not_a_tie_or_a_flip():
    row=add_patterns(sample(0,0,0,0)).iloc[0]
    assert pd.isna(row.margin_1_pp) and not row.tie_1 and not row.flip_to_13 and not row.flip_to_22


def test_inventory_runs_offline_and_preserves_reference(tmp_path):
    from eleicoes.demo import create_demo
    from eleicoes.cli import ingest_files,analyze_year
    from eleicoes.ingest import connect
    from eleicoes.sources import write_json,sha256
    source=tmp_path/'source';source.mkdir()
    paths=create_demo(tmp_path/'raw')
    con=connect(tmp_path/'demo.duckdb')
    ingest_files(con,{k:[v] for k,v in paths.items()},2026)
    analyze_year(con,2026,source)
    con.close()
    write_json(source/'fontes_utilizadas.json',[])
    digest=sha256(source/'indicadores_secoes.parquet')
    result=run_inventory(source)
    assert result['tables']['secoes']>0 and result['preservation_verified']
    assert sha256(source/'indicadores_secoes.parquet')==digest
    assert (source/'nacional/inventario/secoes.parquet').exists()
    with pytest.raises(FileExistsError):run_inventory(source)
    with pytest.raises(ValueError):run_inventory(source,source)
