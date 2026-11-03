import pandas as pd
import pytest

from eleicoes.documentary import review_issues


@pytest.mark.parametrize("installed,has_votes,has_detail,attendance,abstention,valid,explained", [
    ("Não", False, True, 0, 0, None, True),
    ("Sim", False, True, 0, 0, None, False),
    (None, False, True, 0, 0, None, False),
    ("Não", True, True, 0, 0, 0, False),
    ("Não", False, True, 1, 0, None, False),
    ("Não", False, True, 0, 1, None, False),
    ("Não", False, False, 0, 0, None, False),
    ("Não", False, True, 0, 0, 5, False),
])
def test_uninstalled_section_explanation_requires_consistent_evidence(installed, has_votes, has_detail, attendance, abstention, valid, explained):
    key = dict(year=2026, turn=1, uf="ZZ", municipality="29424", zone="1", section="54")
    original_status = "pendente: incompatibilidade aritmética nos dados por seção"
    issues = pd.DataFrame([dict(key, aptos=22, attendance=attendance, abstention=abstention,
        valid=valid, blank=None, null_votes=None, other_votes=None, status=original_status)])
    metadata = pd.DataFrame([dict(key, installed=installed, has_votes=has_votes, has_detail=has_detail)])
    reviewed = review_issues(issues, metadata)
    assert reviewed.loc[0, "review_status"].startswith("explicado") == explained
    assert reviewed.loc[0, "status"] == original_status
    assert reviewed.loc[0, "aptos"] == 22
