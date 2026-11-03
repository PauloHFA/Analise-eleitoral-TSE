import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from eleicoes.analysis import export_frame
from eleicoes.coverage import run_coverage


def inputs(folder):
    folder.mkdir()
    frame = pd.DataFrame(dict(year=2026,uf=["SP","SP","SP","ZZ"],municipality=["1","1","1","2"],
        municipality_name_1=["SIMULADO"]*4,zone=["1"]*4,section=["1","2","3","4"],
        comparable=[True,True,False,False],small=[False,True,False,False],
        comparison_reason=["comparável","comparável","aptos diferentes","fonte ausente"],
        aptos_1=[400.,50.,np.nan,30.],attendance_1=[300.,30.,np.nan,0.],
        turnout_1=[.75,.6,np.nan,0.],blank_share_1=[.01,.02,np.inf,np.nan],
        null_share_1=[.01,.02,1.1,np.nan],share_13_1=[.6,.7,.8,np.nan],share_22_1=[.4,.3,.2,np.nan]))
    con = duckdb.connect()
    export_frame(con,frame,folder/"indicadores_secoes")
    export_frame(con,pd.DataFrame(dict(turn=[2,2],candidate=[13,22])),folder/"candidatos")
    con.close()
    return frame


def test_groups_close_and_missing_is_not_zero(tmp_path):
    source = tmp_path/"source"
    inputs(source)
    original = (source/"indicadores_secoes.parquet").read_bytes()
    result = run_coverage(source)
    assert result["observed_units"] == 4
    assert result["comparable_units"] == 2 and result["eligible_units"] == 1
    assert result["comparable_small_units"] == 1 and result["excluded_units"] == 2
    profile = next(r for r in result["regional_profiles"] if r["scope"]=="Brasil" and r["analysis_group"]=="not_comparable" and r["metric"]=="Eleitorado apto")
    assert profile["missing"] == 1 and profile["used"] == 0 and profile["median"] is None
    zero = next(r for r in result["regional_profiles"] if r["scope"]=="Exterior" and r["analysis_group"]=="not_comparable" and r["metric"]=="Comparecimento")
    assert zero["used"] == 1 and zero["median"] == 0
    absent = next(r for r in result["regional_profiles"] if r["scope"]=="Exterior" and r["analysis_group"]=="eligible" and r["metric"]=="Comparecimento")
    assert absent["units"] == 0 and absent["median"] is None
    assert (source/"indicadores_secoes.parquet").read_bytes() == original
    with pytest.raises(FileExistsError):
        run_coverage(source)


def test_quality_categories_and_percentage_point_difference(tmp_path):
    source = tmp_path/"source"
    inputs(source)
    result = run_coverage(source)
    profiles = result["regional_profiles"]
    infinite = next(r for r in profiles if r["scope"]=="Brasil" and r["analysis_group"]=="not_comparable" and r["metric"]=="Brancos/comparecentes")
    assert infinite["nonfinite"] == 1 and infinite["used"] == 0
    outside = next(r for r in profiles if r["scope"]=="Brasil" and r["analysis_group"]=="not_comparable" and r["metric"]=="Nulos/comparecentes")
    assert outside["out_of_range"] == 1 and outside["median"] is None
    difference = next(r for r in result["regional_differences"] if r["scope"]=="Brasil" and r["comparison_group"]=="comparable_small" and r["metric"]=="Taxa de comparecimento")
    assert difference["difference_unit"] == "pp" and difference["median_difference"] == -15
    for record in profiles:
        assert record["units"] == sum(record[k] for k in ("used","missing","nonfinite","out_of_range"))


def test_coverage_rates_and_thresholds_have_explicit_denominators(tmp_path):
    source = tmp_path/"source"
    inputs(source)
    result = run_coverage(source,thresholds=[50,80,95])
    con = duckdb.connect()
    row = con.execute("SELECT observed,comparable,eligible,comparable_pct,eligible_pct FROM read_parquet(?) WHERE uf='SP'",[str(source/"cobertura/municipios.parquet")]).fetchone()
    assert row[:3] == (3,2,1) and row[3] == pytest.approx(200/3) and row[4] == pytest.approx(100/3)
    for name in ("municipios","resumo_uf","perfis","diferencas","distribuicao_geografica","faixas","unidades"):
        path = source/"cobertura"/name
        assert con.execute("SELECT count(*) FROM read_parquet(?)",[str(path.with_suffix('.parquet'))]).fetchone() == con.execute("SELECT count(*) FROM read_csv(?,header=true)",[str(path.with_suffix('.csv'))]).fetchone()
    con.close()
    brasil = [r for r in result["thresholds"] if r["region"]=="Brasil"]
    assert [r["below_comparable"] for r in brasil] == [0,1,1]
    assert all(r["below_eligible"]==1 for r in brasil)
    json.loads((source/"cobertura/resumo.json").read_text(encoding="utf-8"),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
