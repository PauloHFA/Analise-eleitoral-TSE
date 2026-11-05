import pytest
from eleicoes.audit_atas import key,evaluate,case_id,request_text,official_source


def case(**changes):
    return dict(year=2026,turn=2,uf='BA',municipality='34193',zone='53',section='274',municipality_name_1='CAMPO FORMOSO',**changes)


def document():
    return dict(url='https://www.tre-ba.jus.br/synthetic-test',kind='ata_mrv',identity=case())


def evidence(**changes):
    base=dict(indicator='nested_payloads',review_status='revisao_documental_registrada',locator='página 2, anotação controlada',justification='Fixture exclusivamente sintética',finding='corrobora_registro')
    base.update(changes);return base


def test_normalized_geographic_identity_includes_turn():
    item=case();other=case();other.update(zone='0053',section='0274',uf='ba')
    assert key(item)==key(other) and case_id(item)=='2026-2-BA-34193-53-274'
    other['turn']=1;assert key(item)!=key(other)


@pytest.mark.parametrize('kind',['noticia_agregada','norma_geral','ata_julgamento','canal_de_acesso','contexto_geral'])
def test_general_source_cannot_confirm_case_even_with_matching_numbers(kind):
    source=document();source['kind']=kind
    assert evaluate(case(),'nested_payloads',source,evidence())=='fonte_geral_sem_confronto'


def test_exact_specific_document_can_corrobate_only_record_not_cause():
    assert evaluate(case(),'nested_payloads',document(),evidence())=='registro_corrobora_no_escopo'
    assert 'causa' not in evaluate(case(),'nested_payloads',document(),evidence())


@pytest.mark.parametrize('field,value',[('turn',1),('year',2022),('section','231'),('zone','54'),('municipality','1'),('uf','AC')])
def test_other_territory_or_turn_is_never_accepted(field,value):
    source=document();source['identity'][field]=value
    assert evaluate(case(),'nested_payloads',source,evidence())=='documento_de_outra_unidade_ou_turno'


def test_incomplete_identity_or_review_and_wrong_indicator_stay_unconfirmed():
    source=document();del source['identity']['section']
    assert evaluate(case(),'nested_payloads',source,evidence())=='identificacao_documental_insuficiente'
    assert evaluate(case(),'nested_payloads',document(),evidence(locator=''))=='revisao_incompleta'
    assert evaluate(case(),'target_error_records',document(),evidence())=='apontamento_diferente'


def test_disagreement_is_for_review_without_automatic_persistence():
    assert evaluate(case(),'nested_payloads',document(),evidence(finding='contradiz_registro'))=='divergencia_documental_a_revisar'
    assert evaluate(case(),'nested_payloads',document(),evidence(finding='unsupported'))=='evidencia_inconclusiva'


def test_official_origin_validation_rejects_lookalike_and_non_https():
    for url in ('https://tre-ba.jus.br.attacker.test/doc','http://www.tre-ba.jus.br/doc','https://user@www.tre-ba.jus.br/doc'):
        assert not official_source(url)
    source=document();source['url']='https://example.org/ata'
    assert evaluate(case(),'nested_payloads',source,evidence())=='origem_nao_verificada'


def test_draft_is_local_and_contains_identifiers_without_voter_data():
    draft=request_text(case(),['nested_payloads','target_hardware_identifiers'])
    for text in ('NÃO ENVIADA','CAMPO FORMOSO','53','274','2º turno','2026','origem do log','troca ou composição'):assert text in draft
    assert 'Nenhum pedido foi enviado' in draft and 'não são solicitados dados pessoais' in draft.lower()
