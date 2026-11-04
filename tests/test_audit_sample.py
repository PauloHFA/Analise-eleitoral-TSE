import pandas as pd
import pytest

from eleicoes.audit_sample import choose,GEO


def population():
    rows=[]
    for uf in ('AC','BA','GO','SP','RS','ZZ'):
        for section in range(1,5):
            priority=section<=2;available=2 if uf=='ZZ' else 3
            rows.append(dict(year=2026,uf=uf,municipality='1',zone='1',section=str(section),eligible=True,
                reference_alert=priority,selected_pattern=priority,available_configurations=available,
                alert_configurations=available if priority else 0,robust_max_15=10 if priority else 1,
                robust_max_30=8 if priority else 1,robust_max_50=None if uf=='ZZ' else 9 if priority else 1,
                mad_below_one_unit_15=False,mad_below_one_unit_30=False,mad_below_one_unit_50=None if uf=='ZZ' else False,
                aptos_1=200+section,turnout_1=.8,share_13_1=.4,share_22_1=.5,
                margin_change_pp=30 if section==1 else -30 if section==2 else 0,absolute_margin_change_pp=30 if priority else 0))
    return pd.DataFrame(rows)


def test_strata_stability_and_controls_are_deterministic_and_disjoint():
    frame=population()
    sample,gaps=choose(frame)
    shuffled,_=choose(frame.sample(frac=1,random_state=7))
    assert sample[GEO+['group','pair_id']].equals(shuffled[GEO+['group','pair_id']])
    assert len(sample)==24 and not gaps and not sample.duplicated(GEO).any()
    assert sample.group.eq('prioritario').sum()==12
    assert sample.region.nunique()==6
    for _,pair in sample.groupby('pair_id'):
        assert len(pair)==2 and pair.uf.nunique()==1
        assert pair.loc[pair.group.eq('prioritario'),'reference_alert'].all()
        assert not pair.loc[pair.group.eq('comparacao'),'reference_alert'].any()
        assert not pair.loc[pair.group.eq('comparacao'),'selected_pattern'].any()
    assert sample.loc[sample.uf.eq('ZZ'),'available_configurations'].eq(2).all()


def test_matching_does_not_use_second_turn_features():
    frame=population()
    first,_=choose(frame)
    frame['votes_22_2']=range(len(frame));frame['attendance_2']=100000
    other,_=choose(frame)
    assert first[GEO+['pair_id']].equals(other[GEO+['pair_id']])


def test_missing_stratum_and_missing_control_remain_explicit():
    frame=population()
    frame=frame.loc[~frame.uf.eq('ZZ') & ~(frame.uf.eq('AC') & ~frame.reference_alert)]
    sample,gaps=choose(frame)
    assert gaps
    assert any(g.get('region')=='Exterior' for g in gaps)
    assert any('controle' in g['reason'] for g in gaps)
    assert sample.loc[sample.group.eq('comparacao')].uf.eq('AC').sum()==0


def test_duplicate_keys_are_rejected():
    frame=population()
    with pytest.raises(ValueError,match='Chave repetida'):choose(pd.concat([frame,frame.iloc[[0]]]))
