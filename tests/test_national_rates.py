import duckdb
import pandas as pd
import pytest

from eleicoes.national_rates import rates,mask_rates,cohort
from eleicoes.national_inventory import add_patterns
from test_national_inventory import sample


def test_alert_rate_uses_only_eligible_sections_not_votes_or_municipal_average():
    frame=pd.concat([sample()]*5,ignore_index=True)
    frame['eligible']=[True,True,False,False,True]
    frame['comparable']=[True,True,True,False,True]
    frame['reference_alert']=[True,False,False,False,False]
    frame['selected_pattern']=False;frame['margin_robust_z']=None
    frame['municipality']=['1','1','1','1','2']
    con=duckdb.connect();con.register('sections',frame)
    result=rates(con,['year','uf','municipality']).set_index('municipality')
    assert result.loc['1','observed_sections']==4
    assert result.loc['1','eligible_sections']==2
    assert result.loc['1','rate_per_1000']==500
    assert result.loc['1','eligible_coverage_pct']==50
    region=rates(con,['year','region']).iloc[0]
    assert region.rate_per_1000==pytest.approx(1000/3)
    assert region.rate_per_1000!=(500+0)/2
    con.close()


def test_zero_eligible_and_masked_low_coverage_are_not_colored_as_zero():
    frame=pd.DataFrame(dict(eligible_sections=[0,10,40,40],eligible_coverage_pct=[0,100,60,90],rate_per_1000=[float('nan'),0.,250.,0.]))
    result=mask_rates(frame)
    assert result.rate_map_value.iloc[:3].isna().all()
    assert result.rate_map_value.iloc[3]==0
    assert result.rate_per_1000.iloc[1]==0
    assert len(set(result.rate_map_status))==4


def test_cohort_sums_require_all_parts_and_do_not_replace_full_territory():
    frame=pd.concat([sample(),sample(),sample()],ignore_index=True)
    frame.loc[1,'attendance_1']=None
    frame.loc[2,'comparable']=False
    con=duckdb.connect();con.register('sections',frame)
    result=cohort(con).iloc[0]
    assert result.cohort_sections==2
    assert pd.isna(result.cohort_attendance_1)
    assert result.cohort_votes_22_1==120
    assert result.cohort_votes_22_1<frame.votes_22_1.sum()
    con.close()


@pytest.mark.parametrize('minimum,coverage',[(0,80),(30,101),(30,-1)])
def test_invalid_display_thresholds_are_rejected(minimum,coverage):
    with pytest.raises(ValueError):mask_rates(pd.DataFrame(),minimum,coverage)


def test_rates_pipeline_keeps_totals_and_cohorts_separate(tmp_path):
    from eleicoes.demo import create_demo
    from eleicoes.cli import ingest_files,analyze_year
    from eleicoes.ingest import connect
    from eleicoes.sources import write_json
    from eleicoes.national_inventory import run_inventory
    from eleicoes.national_rates import run_rates
    source=tmp_path/'reference';source.mkdir()
    paths=create_demo(tmp_path/'raw')
    con=connect(tmp_path/'demo.duckdb')
    ingest_files(con,{k:[v] for k,v in paths.items()},2026)
    analyze_year(con,2026,source);con.close()
    write_json(source/'fontes_utilizadas.json',[])
    run_inventory(source)
    summary=run_rates(source,minimum=1,coverage=0)
    assert summary['tables']['municipios']>0 and summary['preservation_verified']
    con=duckdb.connect()
    frame=con.read_parquet(str(source/'nacional/taxas/municipios.parquet')).df()
    assert {'votes_13_1','cohort_votes_13_1','eligible_sections','reference_alert_sections','rate_per_1000'}<=set(frame)
    assert frame.eligible_sections.le(frame.observed_sections).all()
    assert frame.rate_per_1000.dropna().between(0,1000).all()
    con.close()
