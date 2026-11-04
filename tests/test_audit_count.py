from collections import Counter
import copy
import asn1tools
import pytest
from eleicoes.audit_count import decode_strict,rdv_counts,bu_counts,image_counts,compare_values

EXPECTED=dict(municipality='1',zone='2',section='3',election_id='6257')
IDENT=dict(municipioZona=dict(municipio=1,zona=2),secao=3)


def rdv(votes):
    return dict(rdv=dict(fase=2,identificacao=copy.deepcopy(IDENT),eleicoes=('eleicoesVota',[
        dict(idEleicao=6257,votosCargos=[dict(idCargo=('cargoConstitucional',1),quantidadeEscolhas=1,votos=votes)])])))


def test_rdv_counts_nominals_and_suspended_categories_without_exporting_order():
    votes=[dict(tipoVoto=2,digitacao='13')]*4+[dict(tipoVoto=2,digitacao='22')]*2
    votes += [dict(tipoVoto=n) for n in (3,5,4,6,7,8,9)]
    assert rdv_counts(rdv(votes),EXPECTED)==Counter({13:4,22:2,95:2,96:5})
    assert rdv_counts(rdv(list(reversed(votes))),EXPECTED)==rdv_counts(rdv(votes),EXPECTED)


def test_rdv_absence_is_not_zero_and_unrecognized_categories_fail_closed():
    obj=rdv([]);obj['rdv']['eleicoes'][1][0]['votosCargos']=[]
    with pytest.raises(ValueError,match='Cargo'):rdv_counts(obj,EXPECTED)
    with pytest.raises(ValueError,match='Tipo'):rdv_counts(rdv([dict(tipoVoto=1,digitacao='13')]),EXPECTED)
    obj=rdv([]);obj['rdv']['identificacao']['secao']=4
    with pytest.raises(ValueError,match='territorial'):rdv_counts(obj,EXPECTED)


def test_duplicate_election_and_nonofficial_rdv_are_rejected():
    obj=rdv([]);obj['rdv']['eleicoes'][1].append(copy.deepcopy(obj['rdv']['eleicoes'][1][0]))
    with pytest.raises(ValueError,match='duplicada'):rdv_counts(obj,EXPECTED)
    obj=rdv([]);obj['rdv']['fase']=1
    with pytest.raises(ValueError,match='oficial'):rdv_counts(obj,EXPECTED)


def bu(rows):
    return dict(identificacaoSecao=copy.deepcopy(IDENT),fase=2,cabecalho=dict(dataGeracao='20261004T170000'),
        urna=dict(versaoVotacao='test'),resultadosVotacaoPorEleicao=[dict(idEleicao=6257,qtdEleitoresAptos=300,
        resultadosVotacao=[dict(qtdComparecimento=200,totaisVotosCargo=[dict(codigoCargo=('cargoConstitucional',1),votosVotaveis=rows)])])])


def test_bu_preserves_denominators_and_detects_duplicates():
    row=dict(tipoVoto=1,quantidadeVotos=195,identificacaoVotavel=dict(codigo=13))
    values,meta=bu_counts(bu([row,dict(tipoVoto=2,quantidadeVotos=5)]),EXPECTED)
    assert values=={13:195,95:5} and meta['aptos']==300 and meta['attendance']==200
    with pytest.raises(ValueError,match='repetido'):bu_counts(bu([row,row]),EXPECTED)


IMAGE='''Município                        00001
Zona Eleitoral                    0002
Seção Eleitoral                   0003
--------------PRESIDENTE--------------
Nome do candidato       Num cand Votos
  CANDIDATO A                 13  0195
--------------------------------------
Eleitores aptos                   0300
Total de votos Nominais           0195
Brancos                           0003
Nulos                             0002
Total Apurado                     0200
============= BU DIGITAL =============
'''.encode('latin1')


def test_image_compares_aggregate_text_and_rejects_incomplete_extraction():
    values,meta=image_counts(IMAGE,EXPECTED)
    assert values=={13:195,95:3,96:2} and meta==dict(aptos=300,attendance=200)
    with pytest.raises(ValueError,match='reconcilia'):image_counts(IMAGE.replace(b'0195',b'0194',1),EXPECTED)
    with pytest.raises(ValueError,match='Seção'):image_counts(IMAGE.replace(b'0003\n---',b'0004\n---'),EXPECTED)


def test_strict_asn1_rejects_truncation_and_trailing_bytes():
    codec=asn1tools.compile_string('T DEFINITIONS ::= BEGIN A ::= SEQUENCE { n INTEGER } END',codec='ber')
    data=codec.encode('A',dict(n=5))
    assert decode_strict(codec,'A',data)==dict(n=5)
    with pytest.raises(ValueError,match='adicionais'):decode_strict(codec,'A',data+b'\x00')
    with pytest.raises(Exception):decode_strict(codec,'A',data[:-1])


def test_missing_document_does_not_hide_known_disagreement_or_become_zero():
    assert compare_values([10,11,None])==('divergencia_de_valores',False)
    assert compare_values([10,10,None])==('comparacao_limitada',False)
    assert compare_values([0,0,0])==('concordante',True)
