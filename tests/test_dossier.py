import csv
import io
import json
import zipfile

import duckdb
import pandas as pd
import pytest

from eleicoes.analysis import export_frame
from eleicoes.dossier import KEY, aggregate_raw, build_dossier, read_raw_categories, run_dossier
from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv


def fixtures():
    nominal, categories, attendance, context, raw = [], [], [], [], []
    for zone, turn in (("1",1),("1",2),("2",1),("2",2),("3",1)):
        key=dict(year=2026,turn=turn,uf="SP",municipality="1",zone=zone)
        technical, absent = (zone, turn)==("1",1), zone=="2"
        valid, regular, tech = (0,0,0) if absent else (90,10,5) if technical else (100,5,0)
        total = valid+regular+tech
        section_valid = None if absent else valid+tech
        section_null = None if absent else regular
        categories.append(dict(**key,section_valid=section_valid,section_blank=None if absent else 0,
            section_null=section_null,section_total=None if absent else total,official_valid=valid,
            official_blank=0,official_null_total=regular+tech,official_null_regular=regular,
            official_null_technical=tech,official_attendance=total,nominal_coverage_pending=absent,
            valid_difference=None if absent else tech,null_total_difference=None if absent else -tech,
            blank_difference=None if absent else 0,attendance_difference=None if absent else 0,
            technical_category_match=technical,status="compatível" if technical else "concordante",source_file="simulado.csv"))
        attendance.append(dict(**key,aptos_sections=200,aptos_official=200,attendance_sections=total,attendance_official=total))
        context.append(dict(**key,municipality_name="SIMULADO <teste>",detail_generations="26/10/2026 10:00:00"))
        raw.append(dict(**key,DT_GERACAO="01/11/2026",HH_GERACAO="19:00:00",ANO_ELEICAO="2026",NR_TURNO=str(turn),
            SG_UF="SP",CD_MUNICIPIO="1",NR_ZONA=zone,CD_CARGO="1",CD_ELEICAO=str(100+turn),
            ST_VOTO_EM_TRANSITO="N",QT_TOTAL_VOTOS_VALIDOS=str(valid),QT_VOTOS_BRANCOS="0",
            QT_TOTAL_VOTOS_NULOS=str(regular+tech),QT_VOTOS_NULOS=str(regular),QT_VOTOS_NULOS_TECNICOS=str(tech),QT_COMPARECIMENTO=str(total)))
        values = [(13,90,90),(28,5,0)] if technical else [(13,None,0),(28,None,0)] if absent else [(13,65,60),(28,35,40)] if zone=="3" else [(13,50,50),(28,50,50)]
        for candidate, section, official in values:
            diff=None if absent else section-official
            nominal.append(dict(**key,candidate=candidate,section_votes=section,official_votes=official,difference=diff,
                section_generation="26/10/2026 12:07:25",official_generation="02/11/2026 19:31:33",zero_imputed=False,
                status="cobertura divergente" if absent else "pendente" if diff else "concordante"))
    return tuple(pd.DataFrame(f) for f in (nominal,categories,attendance,context,raw))


def test_local_matching_cannot_be_hidden_by_canceling_differences():
    units, nominal = build_dossier(*fixtures())
    technical=units.loc[units.zone.eq("1") & units.turn.eq(1)].iloc[0]
    assert technical.technical_arithmetic_match and technical.official_null_technical==5
    assert technical.published_match_reproduced
    cancellation=units.loc[units.zone.eq("3")].iloc[0]
    assert cancellation.nominal_difference==0 and cancellation.nominal_gap_rows==2
    assert cancellation.selected and not cancellation.technical_arithmetic_match
    assert cancellation.finding=="pendência de conferência"
    assert units.documentary_cause_status.eq("não investigada neste incremento").all()
    assert units.persistence_status.eq("não investigada neste incremento").all()
    assert nominal.generation_relation.eq("seção gerada antes do nominal oficial").all()


def test_zero_coverage_has_three_distinct_units_and_does_not_impute():
    units, nominal = build_dossier(*fixtures())
    covered=units.loc[units.zero_attendance_coverage]
    assert len(covered)==2
    assert len(covered[["uf","municipality","zone"]].drop_duplicates())==1
    lines=nominal.merge(covered[KEY],on=KEY)
    assert len(lines)==4 and lines.coverage_gap.all()
    assert lines.section_votes.isna().all() and lines.difference.isna().all()
    assert covered.nominal_difference.isna().all()
    assert covered.finding.eq("lacuna nominal com comparecimento zero").all()


@pytest.mark.parametrize("change",["missing","duplicate","changed","bad_difference"])
def test_missing_conflicting_or_changed_raw_categories_block_confirmation(change):
    nominal,categories,attendance,context,raw=fixtures()
    if change=="missing":raw.loc[0,"QT_VOTOS_NULOS_TECNICOS"]="-1"
    elif change=="duplicate":raw=pd.concat([raw,raw.iloc[[0]]],ignore_index=True)
    elif change=="changed":raw.loc[0,"QT_VOTOS_NULOS_TECNICOS"]="6"
    else:categories.loc[0,"valid_difference"]=0
    units,_=build_dossier(nominal,categories,attendance,context,raw)
    unit=units.loc[units.zone.eq("1") & units.turn.eq(1)].iloc[0]
    assert not unit.technical_arithmetic_match and not unit.published_match_reproduced
    assert unit.selected
    if change=="duplicate":assert unit.raw_partition_conflict and pd.isna(unit.raw_official_null_technical)
    if change=="changed":assert unit.raw_categories_disagree


def test_vote_in_transit_partitions_require_complete_quantities():
    raw=fixtures()[-1].iloc[[0]].copy()
    raw=pd.concat([raw,raw],ignore_index=True)
    raw.loc[1,"ST_VOTO_EM_TRANSITO"]="S"
    combined=aggregate_raw(raw).iloc[0]
    assert not combined.raw_partition_conflict and combined.raw_official_null_technical==10
    raw.loc[1,"QT_VOTOS_NULOS_TECNICOS"]=""
    assert pd.isna(aggregate_raw(raw).iloc[0].raw_official_null_technical)


def test_nominal_duplicates_and_inconsistent_arithmetic_are_rejected():
    nominal,*rest=fixtures()
    with pytest.raises(ValueError,match="duplicada"):
        build_dossier(pd.concat([nominal,nominal.iloc[[0]]]),*rest)
    nominal.loc[0,"difference"]=1
    with pytest.raises(ValueError,match="não fecha"):
        build_dossier(nominal,*rest)


def test_raw_zip_prefers_national_and_preserves_generations_and_line_numbers(tmp_path):
    raw=fixtures()[-1].drop(columns=KEY).copy()
    raw["NM_MUNICIPIO"]="SIMULADO\nCONTINUAÇÃO"
    text=io.StringIO(newline="")
    writer=csv.DictWriter(text,fieldnames=raw.columns,delimiter=";")
    writer.writeheader();writer.writerows(raw.to_dict("records"))
    path=tmp_path/"raw.zip"
    with zipfile.ZipFile(path,"w") as archive:
        archive.writestr("detalhe_BR.csv",text.getvalue().encode("latin-1"))
        archive.writestr("detalhe_SP.csv",text.getvalue().encode("latin-1"))
    actual=read_raw_categories(path,2026)
    assert len(actual)==len(raw)
    assert actual.member.eq("detalhe_BR.csv").all()
    assert actual.source_line.iloc[0]==3
    assert actual.DT_GERACAO.eq("01/11/2026").all()


def create_inputs(tmp_path):
    source=tmp_path/"reference";source.mkdir()
    data=tmp_path/"data";data.mkdir()
    nominal,categories,attendance,context,raw=fixtures()
    con=duckdb.connect()
    for name,frame in (("reconciliacao_municipio_zona",nominal),("reconciliacao_categorias",categories),("reconciliacao_comparecimento",attendance)):
        export_frame(con,frame,source/name)
    sections=context.drop(columns="detail_generations").assign(section="1",generation="26/10/2026 10:00:00",
        source_file="simulado.csv",has_detail=True,has_votes=True)
    export_frame(con,sections,source/"secoes_por_turno")
    con.close()
    entries=[]
    for kind in ("votes","detail","official_votes","official_detail"):
        path=data/(kind+".csv")
        if kind=="official_detail":raw.drop(columns=KEY).to_csv(path,index=False,sep=";",encoding="latin-1")
        else:path.write_text("SIMULADO",encoding="utf-8")
        entries.append(dict(year=2026,kind=kind,path=path.name,sha256=sha256(path),url="https://example.invalid/"+path.name))
    (source/"fontes_utilizadas.json").write_text(json.dumps(entries),encoding="utf-8")
    (source/"relatorio.pdf").write_bytes(b"PDF SIMULADO PRESERVADO")
    return source,data


def test_end_to_end_exports_preserve_sources_and_refuse_overwrite(tmp_path):
    source,data=create_inputs(tmp_path)
    before={p:sha256(p) for folder in (source,data) for p in folder.iterdir() if p.is_file()}
    summary=run_dossier(source,data)
    assert summary["technical_units"]==1 and summary["technical_votes"]==5
    assert summary["coverage_turn_units"]==2 and summary["coverage_geographic_units"]==1 and summary["coverage_candidate_rows"]==4
    assert summary["selected_unit_turns"]==4 and summary["preservation_verified"]
    assert all(sha256(p)==digest for p,digest in before.items())
    out=source/"dossie_categorias"
    page=(out/"relatorio.html").read_text(encoding="utf-8")
    assert "SIMULADO &lt;teste&gt;" in page and "<teste>" not in page
    assert page.count('data-finding="')==4
    con=duckdb.connect()
    for parquet in out.glob("*.parquet"):
        expected=con.read_parquet(str(parquet))
        columns=dict(zip(expected.columns,expected.types))
        actual=read_export_csv(con,parquet.with_suffix(".csv"),columns={k:str(v) for k,v in columns.items()})
        assert actual.fetchall()==expected.fetchall()
    con.close()
    with pytest.raises(FileExistsError):run_dossier(source,data)
    with pytest.raises(ValueError):run_dossier(source,data,source)
    with pytest.raises(ValueError):run_dossier(source,data,data/"child")

    # Exercita também o validador independente contra os arquivos produzidos.
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location("validate_dossier",Path(__file__).resolve().parents[1]/"scripts/validar_dossie.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checked=module.validate(source,data)
    assert checked['technical_votes']==5 and checked['html_case_anchors']==4


def test_wrong_original_hash_fails_without_classifying_causes(tmp_path):
    source,data=create_inputs(tmp_path)
    (data/"official_detail.csv").write_text("ALTERADO",encoding="utf-8")
    with pytest.raises(ValueError,match="SHA256"):
        run_dossier(source,data)
    state=json.loads((source/"dossie_categorias/estado_execucao.json").read_text(encoding="utf-8"))
    assert state["status"]=="incompleto"


def test_invalid_generation_is_not_assumed_same_version():
    nominal,*rest=fixtures()
    nominal.loc[0,"section_generation"]="desconhecida"
    _,result=build_dossier(nominal,*rest)
    assert result.iloc[0].generation_relation=="data ausente ou inválida"
