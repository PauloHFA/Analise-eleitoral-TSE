import math

import pandas as pd
from PIL import Image

from eleicoes.pdf_layout import picture
from eleicoes.pdf_report import _case_rows, candidate_label, case_explanation, n


def test_candidate_names_do_not_assume_continuity_between_elections():
    assert candidate_label(13, {13:"FERNANDO HADDAD"}) == "Fernando Haddad"
    assert candidate_label(22, {22:"CANDIDATO SIMULADO 22"}) == "Candidato Simulado 22"
    assert candidate_label(13, {13:"LUIZ INACIO LULA DA SILVA"}) == "Lula"


def test_case_explains_small_peer_dispersion_instead_of_claiming_fraud():
    row = pd.Series(dict(z_delta_blank_pp=582.26, delta_blank_pp=1.54,
                         peer_median_delta_blank_pp=0., peer_mad_delta_blank_pp=.0018))
    result = case_explanation(row, [13,22])
    assert "brancos sobre comparecentes" in result and "+1,54 pp" in result
    assert "MAD 0,0018 pp" in result and "escore 582,26" in result
    assert "dispersão pequena" in result


def test_uninformative_scores_stay_unavailable():
    result = case_explanation(pd.Series(dict(z_delta_blank_pp=math.nan)), [13,22])
    assert "Não há escore robusto informativo" in result


def test_case_table_separates_absolute_votes_from_percentage_points():
    row = pd.Series(dict(aptos_1=500,aptos_2=500,attendance_1=400,attendance_2=420,
        valid_1=390,valid_2=410,votes_13_1=200,votes_13_2=220,votes_22_1=190,votes_22_2=190,
        blank_1=5,blank_2=5,null_votes_1=5,null_votes_2=5,turnout_1=.8,turnout_2=.84,
        share_13_1=200/390,share_13_2=220/410,share_22_1=190/390,share_22_2=190/410,
        blank_share_1=5/400,blank_share_2=5/420,null_share_1=5/400,null_share_2=5/420))
    rows = _case_rows(row,[13,22],{13:"LULA",22:"FLAVIO"})
    turnout = next(r for r in rows if r[0] == "Comparecimento")
    flavio = next(r for r in rows if r[0] == "Flávio — votos")
    assert turnout[1:] == ["400 (80,0%)", "420 (84,0%)", "+20; +4,0 pp"]
    assert flavio[-1].startswith("0; -")  # margem/participação podem cair sem perda absoluta


def test_picture_preserves_native_aspect_ratio(tmp_path):
    path = tmp_path / "map.png"
    Image.new("RGB", (1600, 700)).save(path)
    result = picture(path,max_height=180)
    assert abs(result.drawWidth/result.drawHeight - 1600/700) < 1e-12
    assert result.drawHeight <= 180


def test_missing_numbers_are_not_printed_as_zero_or_nan():
    assert n(None) == n(math.nan) == n(math.inf) == "não disponível"
    assert n(5246) == "5.246"
