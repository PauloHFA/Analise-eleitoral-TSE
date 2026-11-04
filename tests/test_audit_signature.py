import copy
import hashlib
from datetime import datetime,timezone
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from eleicoes.audit_signature import codec,parse_vsc,hash_status,certificate,temporal_status,verify_signature


def example():
    digital=dict(size=132,hash=b'a'*64,signature=b's'*132)
    payload=codec().encode('Payload',dict(files=[dict(name='o03220sp0000100020003-rdv.dat',signature=digital)]))
    ent=dict(created='20261004T170000',version=2,auto=dict(user=dict(name='UEAO',serial=1),hashAlgorithm=dict(algorithm=4),
        algorithm=dict(algorithm=4,bits=521),signature=dict(size=132,hash=hashlib.sha512(payload).digest(),signature=b's'*132)),payload=payload)
    return dict(sw=copy.deepcopy(ent),hw=copy.deepcopy(ent),platform=dict(model=22,algorithm=4))


def test_observed_layout_roundtrips_and_trailing_unknown_fields_are_rejected():
    data=codec().encode('VSC',example());parsed=parse_vsc(data)
    assert len(parsed['hw']['files'])==1 and parsed['platform']['model']==22
    with pytest.raises(ValueError,match='adicionais'):parse_vsc(data+b'\x00')
    with pytest.raises(Exception):parse_vsc(data[:-1])
    obj=example();obj['hw']['version']=3
    with pytest.raises(Exception):parse_vsc(codec().encode('VSC',obj))


@pytest.mark.parametrize('name',['../file.dat','C:\\file.dat','x/file.dat','file\x00.dat'])
def test_unsafe_names_are_rejected_without_file_lookup(name):
    obj=example();payload=codec().encode('Payload',dict(files=[dict(name=name,signature=obj['hw']['auto']['signature'])]))
    obj['hw']['payload']=payload
    with pytest.raises(ValueError,match='inseguro'):parse_vsc(codec().encode('VSC',obj))


def test_duplicate_names_unknown_hash_and_model_algorithm_mismatch_are_rejected():
    obj=example();item=codec().decode('Payload',obj['hw']['payload'])['files'][0]
    obj['hw']['payload']=codec().encode('Payload',dict(files=[item,item]))
    with pytest.raises(ValueError,match='duplicada'):parse_vsc(codec().encode('VSC',obj))
    obj=example();obj['sw']['auto']['hashAlgorithm']['algorithm']=2
    with pytest.raises(ValueError,match='SHA512'):parse_vsc(codec().encode('VSC',obj))
    obj=example();obj['platform']['algorithm']=2
    with pytest.raises(ValueError,match='difere'):parse_vsc(codec().encode('VSC',obj))


def make_cert():
    key=ec.generate_private_key(ec.SECP521R1());name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'controlled test')])
    cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1).not_valid_before(datetime(2026,1,1,tzinfo=timezone.utc)).not_valid_after(datetime(2027,1,1,tzinfo=timezone.utc)).sign(key,hashes.SHA512())
    return key,cert


def test_ecdsa_valid_corruption_wrong_key_and_unsupported_algorithm_are_distinct():
    key,cert=make_cert();digest=hashlib.sha512(b'file').digest();sig=key.sign(digest,ec.ECDSA(hashes.SHA512()))
    assert verify_signature(cert,2,digest,sig)[0]=='valida_com_chave_embutida'
    assert verify_signature(cert,2,hashlib.sha512(b'changed').digest(),sig)[0]=='invalida_com_chave_embutida'
    _,other=make_cert()
    assert verify_signature(other,2,digest,sig)[0]=='invalida_com_chave_embutida'
    assert verify_signature(cert,4,digest,sig)[0]=='nao_verificado_algoritmo'
    assert verify_signature(cert,3,digest,sig)[0]=='nao_verificado_algoritmo'
    assert verify_signature(cert,2,digest,sig+b'\x00')[0]=='assinatura_malformada'


def test_hash_mismatch_certificate_padding_and_time_are_separate_from_trust():
    _,cert=make_cert();der=cert.public_bytes(serialization.Encoding.DER)
    decoded,info=certificate(der+b'\x00'*16)
    assert info['der_zero_padding']==16 and info['sha256']==hashlib.sha256(der).hexdigest()
    with pytest.raises(ValueError,match='sufixo'):certificate(der+b'X')
    assert temporal_status(decoded,'20261004T170000')=='compativel_em_todos_os_fusos_considerados'
    assert temporal_status(decoded,'20280101T170000')=='fora_do_intervalo_de_validade'
    assert temporal_status(decoded,'20260101T000000')=='inconclusivo_sem_fuso'
    assert hash_status(b'file',hashlib.sha512(b'file').digest())=='concordante'
    assert hash_status(b'changed',hashlib.sha512(b'file').digest())=='divergente'


def test_unknown_fields_inside_sequences_are_not_silently_ignored():
    def append_field(data,field):
        first=data[1];start=2+(first&127) if first&128 else 2
        body=data[start:]+field;length=len(body)
        encoded=bytes([length]) if length<128 else bytes([0x80+(length.bit_length()+7)//8])+length.to_bytes((length.bit_length()+7)//8,'big')
        return b'\x30'+encoded+body
    raw=codec().encode('VSC',example())
    with pytest.raises(Exception):parse_vsc(append_field(raw,b'\x05\x00'))
    key,cert=make_cert();digest=hashlib.sha512(b'file').digest();sig=key.sign(digest,ec.ECDSA(hashes.SHA512()))
    assert verify_signature(cert,2,digest,append_field(sig,b'\x02\x01\x01'))[0]=='assinatura_malformada'
