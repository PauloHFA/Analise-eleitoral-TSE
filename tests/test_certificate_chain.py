from datetime import datetime,timezone
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from eleicoes.certificate_chain import issuer_binding,assess_crl,verify_signed_object
from types import SimpleNamespace
from pathlib import Path
import json

UTC=timezone.utc
MOMENT=datetime(2026,10,4,12,tzinfo=UTC)


def issuer(*,ca=True,cert_sign=True,crl_sign=True,expired=False,key=None,ski=None):
    key=key or ec.generate_private_key(ec.SECP521R1());name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Controlled issuer')])
    cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1).not_valid_before(datetime(2025,1,1,tzinfo=UTC)).not_valid_after(datetime(2026,7,18,tzinfo=UTC) if expired else datetime(2028,1,1,tzinfo=UTC)).add_extension(x509.BasicConstraints(ca=ca,path_length=None),critical=True).add_extension(x509.KeyUsage(digital_signature=False,content_commitment=False,key_encipherment=False,data_encipherment=False,key_agreement=False,key_cert_sign=cert_sign,crl_sign=crl_sign,encipher_only=False,decipher_only=False),critical=True).add_extension(x509.SubjectKeyIdentifier(ski) if ski is not None else x509.SubjectKeyIdentifier.from_public_key(key.public_key()),critical=False).sign(key,hashes.SHA512())
    return key,cert


def leaf(key,ca,*,algorithm=None):
    ski=ca.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Controlled leaf')])
    return x509.CertificateBuilder().subject_name(name).issuer_name(ca.subject).public_key(ec.generate_private_key(ec.SECP521R1()).public_key()).serial_number(10).not_valid_before(datetime(2026,1,1,tzinfo=UTC)).not_valid_after(datetime(2027,1,1,tzinfo=UTC)).add_extension(x509.AuthorityKeyIdentifier(ski,None,None),critical=False).sign(key,algorithm or hashes.SHA512())


def crl(key,ca,*,revoked=False,stale=False,delta=False):
    builder=x509.CertificateRevocationListBuilder().issuer_name(ca.subject).last_update(datetime(2026,9,30,tzinfo=UTC)).next_update(datetime(2026,10,1,tzinfo=UTC) if stale else datetime(2026,11,1,tzinfo=UTC))
    ski=ca.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest
    builder=builder.add_extension(x509.AuthorityKeyIdentifier(ski,None,None),critical=False)
    if revoked:builder=builder.add_revoked_certificate(x509.RevokedCertificateBuilder().serial_number(10).revocation_date(datetime(2026,10,3,tzinfo=UTC)).build())
    if delta:builder=builder.add_extension(x509.DeltaCRLIndicator(1),critical=True)
    return builder.sign(key,hashes.SHA512())


def test_link_signature_is_distinct_from_trust_and_time():
    key,ca=issuer(expired=True);cert=leaf(key,ca)
    result=issuer_binding(cert,ca,'20261004T120000')
    assert result['signature_status']=='confere_com_candidato'
    assert result['issuer_time_status']=='fora_do_intervalo_de_validade'
    assert result['leaf_time_status']=='compativel_em_todos_os_fusos_considerados'
    assert result['path_status']=='incompleto_sem_ancora'


def test_wrong_key_even_with_same_name_and_ski_fails_signature():
    key,ca=issuer();cert=leaf(key,ca);ski=ca.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest
    _,replacement=issuer(ski=ski)
    assert issuer_binding(cert,replacement,'20261004T120000')['signature_status']=='nao_confere_com_candidato'


def test_aki_and_constraints_are_checked_before_signature():
    key,ca=issuer();cert=leaf(key,ca);_,other=issuer()
    assert issuer_binding(cert,other,'20261004T120000')['signature_status']=='identificador_emissor_incompativel_ou_ausente'
    key,ca=issuer(ca=False)
    assert issuer_binding(leaf(key,ca),ca,'20261004T120000')['signature_status']=='restricao_de_ca_incompativel'
    key,ca=issuer(cert_sign=False)
    assert issuer_binding(leaf(key,ca),ca,'20261004T120000')['signature_status']=='restricao_de_ca_incompativel'


def test_unsupported_algorithm_is_not_invalid_signature():
    key,ca=issuer()
    assert verify_signed_object(leaf(key,ca,algorithm=hashes.SHA256()),ca)=='algoritmo_nao_suportado'


def test_absence_of_crl_is_unknown_not_nonrevoked():
    key,ca=issuer();cert=leaf(key,ca)
    assert assess_crl(cert,ca,None,MOMENT)=='indeterminado_lcr_nao_obtida'


def test_verified_crl_records_membership_only_in_covered_period():
    key,ca=issuer();cert=leaf(key,ca)
    assert assess_crl(cert,ca,crl(key,ca),MOMENT)=='serial_ausente_em_lcr_verificada_no_periodo'
    assert assess_crl(cert,ca,crl(key,ca,revoked=True),MOMENT)=='serial_presente_em_lcr_verificada'
    assert assess_crl(cert,ca,crl(key,ca,stale=True),MOMENT)=='indeterminado_periodo_lcr'
    assert assess_crl(cert,ca,crl(key,ca),datetime(2026,11,1,tzinfo=UTC))=='indeterminado_periodo_lcr'


def test_crl_bad_signature_delta_and_expired_ca_are_inconclusive():
    key,ca=issuer();cert=leaf(key,ca);other=ec.generate_private_key(ec.SECP521R1())
    assert assess_crl(cert,ca,crl(other,ca),MOMENT)=='indeterminado_assinatura_lcr'
    assert assess_crl(cert,ca,crl(key,ca,delta=True),MOMENT)=='indeterminado_escopo_lcr_nao_suportado'
    key,ca=issuer(expired=True)
    assert assess_crl(leaf(key,ca),ca,crl(key,ca),MOMENT)=='indeterminado_validade_signatario_lcr'


def test_crl_sign_permission_is_not_cert_sign_permission():
    key,ca=issuer(crl_sign=False)
    assert assess_crl(leaf(key,ca),ca,crl(key,ca),MOMENT)=='indeterminado_ca_sem_crl_sign'


def test_ed521_certificate_signature_uses_raw_tbs_not_vsc_hash_wrapper(monkeypatch):
    import eleicoes.certificate_chain as module
    vector=json.loads((Path(__file__).parent/'fixtures/ed521_noble_vectors.json').read_text(encoding='utf8'))['vectors'][0]
    key=bytes.fromhex(vector['public_key']);monkeypatch.setattr(module,'public_key_from_certificate',lambda cert:key)
    obj=SimpleNamespace(tbs_certificate_bytes=bytes.fromhex(vector['message']),signature=bytes.fromhex(vector['signature']),signature_algorithm_oid=SimpleNamespace(dotted_string='1.3.6.1.4.1.44588.2.1'))
    assert verify_signed_object(obj,object())=='confere_com_candidato'
    obj.tbs_certificate_bytes+=b'changed'
    assert verify_signed_object(obj,object())=='nao_confere_com_candidato'
