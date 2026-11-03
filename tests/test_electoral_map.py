import json
import math

import pandas as pd
import pytest

from eleicoes.electoral_map import cached_json, geometry_path, match_municipalities, normalize_name, winner_color
from eleicoes.sources import sha256


def test_tse_codes_are_not_used_as_ibge_codes():
    votes=pd.DataFrame([dict(uf="SP",municipality="71072",municipality_name_1="SÃO PAULO")])
    localities=[{"municipio-id":3550308,"municipio-nome":"São Paulo","UF-sigla":"SP"}]
    result=match_municipalities(votes,localities).iloc[0]
    assert result.municipality=="71072" and result.ibge_code=="3550308"


def test_same_name_in_other_uf_is_not_linked():
    votes=pd.DataFrame([dict(uf="SP",municipality="1",municipality_name_1="ALFA")])
    localities=[{"municipio-id":1,"municipio-nome":"Alfa","UF-sigla":"MG"}]
    assert pd.isna(match_municipalities(votes,localities).iloc[0].ibge_code)


def test_reviewed_alias_requires_uf_tse_code_and_expected_name():
    votes=pd.DataFrame([dict(uf="MG",municipality="53031",municipality_name_1="SÃO THOMÉ DAS LETRAS"),dict(uf="MG",municipality="999",municipality_name_1="SÃO THOMÉ DAS LETRAS")])
    localities=[{"municipio-id":3165206,"municipio-nome":"São Tomé das Letras","UF-sigla":"MG"}]
    result=match_municipalities(votes,localities)
    assert result.iloc[0].ibge_code=="3165206" and pd.isna(result.iloc[1].ibge_code)


def test_ambiguous_locality_is_rejected():
    votes=pd.DataFrame([dict(uf="SP",municipality="1",municipality_name_1="ALFA")])
    localities=[{"municipio-id":i,"municipio-nome":"Alfa","UF-sigla":"SP"} for i in (1,2)]
    with pytest.raises(ValueError):
        match_municipalities(votes,localities)


def test_blue_for_flavio_red_for_lula_and_neutral_for_ties():
    blue=winner_color(90,10);red=winner_color(10,90)
    assert int(blue[5:7],16)>int(blue[1:3],16)
    assert int(red[1:3],16)>int(red[5:7],16)
    assert winner_color(0,0)==winner_color(50,50)==winner_color(None,50)
    assert int(winner_color(90,10)[1:3],16)<int(winner_color(51,49)[1:3],16)


def test_geometry_keeps_holes_and_bounds():
    geometry=dict(type="Polygon",coordinates=[[[0,0],[2,0],[2,2],[0,2],[0,0]],[[.5,.5],[1,.5],[1,1],[.5,.5]]])
    path,bounds=geometry_path(geometry)
    assert path.count("M")==path.count("Z")==2
    assert bounds==pytest.approx([0,-2,2*math.cos(math.radians(15)),2])
    assert normalize_name("São Luís d'Oeste")=="SAOLUISDOESTE"


def test_offline_geography_rejects_changed_cache(tmp_path):
    file=tmp_path / "raw.json"
    file.write_text('[1]',encoding="utf-8")
    (tmp_path / "sample.json").write_text(json.dumps(dict(file=file.name,sha256=sha256(file))),encoding="utf-8")
    assert cached_json(tmp_path,"sample","https://example.invalid",offline=True)[0]==[1]
    file.write_text('[2]',encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        cached_json(tmp_path,"sample","https://example.invalid",offline=True)


def test_static_map_keeps_north_above_south(tmp_path,monkeypatch):
    from matplotlib.figure import Figure
    from eleicoes.electoral_map import static_maps,project
    observed=[]
    def inspect(figure,*args,**kwargs):
        for ax in figure.axes:
            north=ax.transData.transform(project(-45,5))[1]
            south=ax.transData.transform(project(-45,-30))[1]
            observed.append(north>south)
    monkeypatch.setattr(Figure,'savefig',inspect)
    features=[dict(ibge_code=str(i),uf=uf,votes_22_1=60,votes_13_1=40,votes_22_2=40,votes_13_2=60) for i,uf in ((1,'RJ'),(2,'MG'))]
    geometry=dict(type='Polygon',coordinates=[[[-46,-20],[-44,-20],[-44,-18],[-46,-18],[-46,-20]]])
    mesh=dict(features=[dict(properties=dict(codarea=str(i)),geometry=geometry) for i in (1,2)])
    static_maps(tmp_path,features,mesh)
    assert len(observed)==6 and all(observed)
