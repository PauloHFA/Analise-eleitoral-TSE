import pandas as pd
import pytest

from eleicoes.audit_crosswalk import build_crosswalk


def identity(section):
    return dict(year=2026, turn=2, uf="BA", municipality="34193", zone="53", section=section)


def inputs():
    logs = pd.DataFrame([
        {**identity("274"), "group": "prioritario", "region": "Brasil",
         "target_error_records": 1, "source_sha256": "a" * 64},
        {**identity("275"), "group": "comparacao", "region": "Brasil",
         "target_error_records": 0, "source_sha256": "b" * 64},
    ])
    issues = pd.DataFrame([
        {**identity("274"), "indicator": "target_error_records", "count": 1,
         "status": "evento_para_revisao", "reason": "Revisão descritiva"},
        {**identity("999"), "indicator": "target_clock_regressions", "count": 1,
         "status": "cronologia_limitada", "reason": "Chave sem log"},
    ])
    signatures = pd.DataFrame([{
        **identity("274"), "kind": "log", "role": "hw", "member": "log.jez",
        "hash_status": "concordante", "crypto_status": "valida_com_chave_embutida",
        "crypto_reason": None, "algorithm": 2, "local_sha256": "a" * 64,
        "signed_sha512": "c" * 128,
    }])
    sample_votes = pd.DataFrame([
        {**identity("274"), "candidate": 13, "rdv_votes": 4, "binary_bu_votes": 4,
         "image_votes": 4, "result_votes": 4, "csv_bu_votes": 4,
         "comparison_complete": True, "status": "concordante",
         "result_source": "resultado", "bu_source": "BU"},
        {**identity("274"), "candidate": 22, "rdv_votes": 5, "binary_bu_votes": 5,
         "image_votes": 5, "result_votes": 5, "csv_bu_votes": 5,
         "comparison_complete": True, "status": "concordante",
         "result_source": "resultado", "bu_source": "BU"},
        {**identity("275"), "candidate": 13, "rdv_votes": 6, "binary_bu_votes": 6,
         "image_votes": 6, "result_votes": 7, "csv_bu_votes": 6,
         "comparison_complete": True, "status": "concordante",
         "result_source": "resultado", "bu_source": "BU"},
    ])
    national_votes = pd.DataFrame([
        {**identity("274"), "candidate": 13, "votes_result": 4, "votes_bu": 4,
         "difference": 0, "result_generation": "g1", "bu_generation": "g1",
         "result_source": "resultado", "bu_source": "BU", "status": "concordante"},
        {**identity("275"), "candidate": 13, "votes_result": 6, "votes_bu": 6,
         "difference": 0, "result_generation": "g1", "bu_generation": "g1",
         "result_source": "resultado", "bu_source": "BU", "status": "concordante"},
        {**identity("275"), "candidate": 95, "votes_result": 0, "votes_bu": 0,
         "difference": 0, "result_generation": "g1", "bu_generation": "g1",
         "result_source": "resultado", "bu_source": "BU", "status": "concordante"},
    ])
    indicators = pd.DataFrame([{
        "year": 2026, "uf": "BA", "municipality": "34193", "zone": "53", "section": "274",
        "coverage": "comparavel", "comparable": True, "small": False,
        "comparison_reason": None, "generation_1": "g1", "generation_2": "g2",
        "vote_generation_1": "v1", "vote_generation_2": "v2",
        "turnout_1": 0.8, "turnout_2": 0.75, "delta_turnout_pp": -5.0,
        "delta_null_pp": 0.0, "delta_share_13_pp": -3.0, "delta_share_22_pp": 3.0,
        "delta_votes_13": -2, "delta_votes_22": 2,
    }])
    return logs, issues, signatures, sample_votes, national_votes, indicators


def test_crosswalk_keeps_missing_candidate_rows_and_joins_three_levels():
    units, issues, candidates, unmatched, contingency = build_crosswalk(*inputs())

    first = units.loc[units.section.eq("274")].iloc[0]
    second = units.loc[units.section.eq("275")].iloc[0]
    assert first.indicator_join_status == "correspondente"
    assert first.signature_assessment == "hash_concordante_e_assinatura_valida_com_chave_embutida"
    assert first.sample_vote_status == "concordante_nas_fontes_amostrais"
    assert first.national_vote_status == "lacuna_de_correspondencia_candidato"
    assert second.indicator_join_status == "sem_correspondencia"
    assert second.signature_join_status == "sem_correspondencia"
    assert second.sample_vote_status == "discordante_nos_valores"
    assert candidates.candidate_match_status.value_counts().to_dict() == {
        "correspondente": 2,
        "sem_linha_correspondente_na_conferencia_nacional": 1,
        "somente_na_conferencia_nacional": 1,
    }
    missing = candidates.loc[candidates.candidate.eq(22)].iloc[0]
    assert missing.candidate_match_status == "sem_linha_correspondente_na_conferencia_nacional"
    assert pd.isna(missing.national_votes_result)
    assert pd.isna(missing.national_difference)
    assert unmatched.relation.eq("chave candidato sem correspondência entre tabelas").sum() == 2
    assert unmatched.relation.eq("apontamento sem unidade de log").sum() == 1
    assert len(issues) == 2 and len(contingency) == 2


def test_crosswalk_rejects_duplicate_unit_and_candidate_keys():
    frames = list(inputs())
    frames[0] = pd.concat([frames[0], frames[0].iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="Chave repetida em logs"):
        build_crosswalk(*frames)

    frames = list(inputs())
    frames[3] = pd.concat([frames[3], frames[3].iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="conferência amostral por candidato"):
        build_crosswalk(*frames)
