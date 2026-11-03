import copy
import json
from pathlib import Path

import pytest

from eleicoes.research import assess,project_candidate

ROOT=Path(__file__).resolve().parents[1]


def inputs():
    return (json.loads((ROOT/'docs/pesquisa_categorias_2026.json').read_text(encoding='utf-8')),
            json.loads((ROOT/'docs/candidatura28_evidencia.json').read_text(encoding='utf-8'))['candidate'])


@pytest.mark.parametrize('update',['2026-09-30 12:00','2026-10-05 12:51',None])
def test_cadastro_update_and_news_are_never_effective_date(update):
    evidence,candidate=inputs()
    candidate['dataUltimaAtualizacao']=update
    result=assess(evidence,candidate)
    assert result['normative_rule_status']=='identificada em fonte oficial'
    assert not result['cause_confirmed'] and not result['registration_update_is_act_date']
    assert result['primary_act_status']=='não obtido nesta pesquisa'
    assert result['persistence_status']=='não avaliada nesta pesquisa'


@pytest.mark.parametrize('candidate_id,cargo',[(280002553883,2),(280002553884,1)])
def test_same_number_does_not_link_vice_or_previous_candidate(candidate_id,cargo):
    evidence,candidate=inputs()
    candidate['id']=candidate_id
    candidate['cargo']['codigo']=cargo
    with pytest.raises(ValueError,match='Candidatura não corresponde'):assess(evidence,candidate)


def test_secondary_report_cannot_replace_official_rule():
    evidence,candidate=inputs()
    evidence['sources']=[s for s in evidence['sources'] if s['kind']!='norma_majoritaria']
    with pytest.raises(ValueError,match='Fonte oficial ausente'):assess(evidence,candidate)


def test_new_individual_act_requires_own_review_not_automatic_promotion():
    evidence,candidate=inputs()
    evidence['primary_act_obtained']=True
    evidence['primary_act_effective_date']='2026-09-30'
    with pytest.raises(ValueError,match='revisão documental própria'):assess(evidence,candidate)


def test_projection_excludes_unnecessary_personal_fields_and_nested_extras():
    _,candidate=inputs()
    raw=copy.deepcopy(candidate)
    raw.update(cpf='SIMULADO',tituloEleitor='SIMULADO',bens=[{'descricao':'SIMULADO'}],emails=['SIMULADO'])
    raw['cargo']['extra']='SIMULADO'
    result=project_candidate(raw)
    assert 'SIMULADO' not in json.dumps(result)
    assert result['id']==280002554479 and result['descricaoSituacao']=='Renúncia'


def test_official_marker_requires_official_domain():
    evidence,candidate=inputs()
    evidence['sources'][0]['url']='https://example.invalid/guia'
    with pytest.raises(ValueError,match='fora do domínio'):assess(evidence,candidate)
