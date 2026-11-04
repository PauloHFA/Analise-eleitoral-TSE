from datetime import datetime,timezone
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID,ObjectIdentifier
from eleicoes.pkix_path import validate_path
import json
from pathlib import Path
import hashlib
import pytest
from cryptography.hazmat.primitives import serialization
from eleicoes.pkix_path import load_explicit_anchors

UTC=timezone.utc;MOMENT=datetime(2026,10,4,12,tzinfo=UTC)


def make_cert(name,*,issuer=None,issuer_key=None,key=None,ca=False,path_length=None,expired=False,extra=None):
    key=key or ec.generate_private_key(ec.SECP521R1());subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,name)])
    issuer_name=issuer.subject if issuer else subject;issuer_key=issuer_key or key
    ski=x509.SubjectKeyIdentifier.from_public_key(key.public_key())
    issuer_ski=issuer.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value if issuer else ski
    builder=x509.CertificateBuilder().subject_name(subject).issuer_name(issuer_name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime(2025,1,1,tzinfo=UTC)).not_valid_after(datetime(2026,7,18,tzinfo=UTC) if expired else datetime(2028,1,1,tzinfo=UTC)).add_extension(x509.BasicConstraints(ca,path_length),True).add_extension(x509.KeyUsage(digital_signature=not ca,content_commitment=False,key_encipherment=False,data_encipherment=False,key_agreement=False,key_cert_sign=ca,crl_sign=ca,encipher_only=False,decipher_only=False),True).add_extension(ski,False).add_extension(x509.AuthorityKeyIdentifier(issuer_ski.digest,None,None),False)
    if issuer:builder=builder.add_extension(x509.CRLDistributionPoints([x509.DistributionPoint(full_name=[x509.UniformResourceIdentifier('https://example.invalid/crl')],relative_name=None,reasons=None,crl_issuer=None)]),False)
    if extra:
        for extension,critical in extra:builder=builder.add_extension(extension,critical)
    return key,builder.sign(issuer_key,hashes.SHA512())


def chain(*,expired=False,extra=None):
    rk,root=make_cert('Controlled root',ca=True)
    ik,issuer=make_cert('Controlled issuer',issuer=root,issuer_key=rk,ca=True,path_length=0,expired=expired,extra=extra)
    _,leaf=make_cert('Controlled leaf',issuer=issuer,issuer_key=ik)
    return rk,root,ik,issuer,leaf


def make_crl(cert,key,*,revoked=None,stale=False):
    ski=cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest
    builder=x509.CertificateRevocationListBuilder().issuer_name(cert.subject).last_update(datetime(2026,10,1,tzinfo=UTC)).next_update(datetime(2026,10,2,tzinfo=UTC) if stale else datetime(2026,11,1,tzinfo=UTC)).add_extension(x509.AuthorityKeyIdentifier(ski,None,None),False).add_extension(x509.CRLNumber(1),False)
    if revoked:builder=builder.add_revoked_certificate(x509.RevokedCertificateBuilder().serial_number(revoked.serial_number).revocation_date(datetime(2026,10,3,tzinfo=UTC)).build())
    return builder.sign(key,hashes.SHA512())


def test_no_implicit_root_and_no_revocation_success_from_missing_data():
    _,root,_,issuer,leaf=chain()
    missing=validate_path(leaf,[issuer,root],[],MOMENT)
    assert missing['path_status']=='inconclusivo_sem_ancora'
    result=validate_path(leaf,[issuer],[root],MOMENT)
    assert result['path_status']=='confere_no_instante_com_ancora_explicita',result
    assert result['revocation_status']=='inconclusiva_evidencia_lcr',result


def test_complete_path_and_crls_pass_then_revocation_and_staleness_fail_closed():
    rk,root,ik,issuer,leaf=chain();root_crl=make_crl(root,rk)
    result=validate_path(leaf,[issuer],[root],MOMENT,[root_crl,make_crl(issuer,ik)])
    assert result['revocation_status']=='conferida_por_lcr_no_instante',result
    revoked=validate_path(leaf,[issuer],[root],MOMENT,[root_crl,make_crl(issuer,ik,revoked=leaf)])
    assert revoked['revocation_status']=='revogado_segundo_lcr_validada',revoked
    stale=validate_path(leaf,[issuer],[root],MOMENT,[root_crl,make_crl(issuer,ik,stale=True)])
    assert stale['revocation_status']=='inconclusiva_evidencia_lcr',stale


def test_expired_issuer_and_unknown_critical_extension_are_not_accepted():
    _,root,_,issuer,leaf=chain(expired=True)
    assert validate_path(leaf,[issuer],[root],MOMENT)['path_status']=='nao_confere_no_perfil'
    _,root,_,issuer,leaf=chain(extra=[(x509.UnrecognizedExtension(ObjectIdentifier('1.2.3.999'),b'\x05\x00'),True)])
    assert validate_path(leaf,[issuer],[root],MOMENT)['path_status']=='nao_confere_no_perfil'


def test_path_length_constraint_is_enforced():
    rk,root=make_cert('Root',ca=True)
    ak,a=make_cert('CA A',issuer=root,issuer_key=rk,ca=True,path_length=0)
    bk,b=make_cert('CA B',issuer=a,issuer_key=ak,ca=True)
    _,leaf=make_cert('Leaf',issuer=b,issuer_key=bk)
    result=validate_path(leaf,[a,b],[root],MOMENT)
    assert result['path_status']=='nao_confere_no_perfil',result


def test_name_constraints_are_enforced():
    _,root,ik,issuer,_=chain(extra=[(x509.NameConstraints([x509.DNSName('allowed.example')],None),True)])
    _,leaf=make_cert('Leaf',issuer=issuer,issuer_key=ik,extra=[(x509.SubjectAlternativeName([x509.DNSName('outside.example')]),False)])
    result=validate_path(leaf,[issuer],[root],MOMENT)
    assert result['path_status']=='nao_confere_no_perfil',result


def test_complete_synthetic_ed521_path_and_ed521_crl_use_the_adapter():
    data=json.loads((Path(__file__).parent/'fixtures/pkix_ed521.json').read_text(encoding='utf8'))
    root,issuer,leaf=(x509.load_der_x509_certificate(bytes.fromhex(data[n])) for n in ('root_der','issuer_der','leaf_der'))
    crls=[x509.load_der_x509_crl(bytes.fromhex(data[n])) for n in ('root_crl_der','issuer_crl_der')]
    result=validate_path(leaf,[issuer],[root],MOMENT,crls)
    assert result['path_status']=='confere_no_instante_com_ancora_explicita',result
    assert result['revocation_status']=='conferida_por_lcr_no_instante',result


def test_valid_name_and_aki_do_not_make_a_bad_signature_valid():
    _,root,_,issuer,_=chain()
    wrong_key=ec.generate_private_key(ec.SECP521R1())
    _,leaf=make_cert('Wrong signature',issuer=issuer,issuer_key=wrong_key)
    result=validate_path(leaf,[issuer],[root],MOMENT)
    assert result['path_status']=='nao_confere_no_perfil',result


def test_os_trust_store_is_never_loaded(monkeypatch):
    import pyhanko_certvalidator.registry as registry
    def forbidden():raise AssertionError('Lista TLS do sistema não pode ser usada')
    monkeypatch.setattr(registry,'_system_trust_roots',forbidden)
    _,root,_,issuer,leaf=chain()
    assert validate_path(leaf,[issuer,root],[],MOMENT)['path_status']=='inconclusivo_sem_ancora'


def test_anchor_manifest_is_explicit_and_pinned(tmp_path):
    _,root,_,_,_=chain();der=root.public_bytes(serialization.Encoding.DER);(tmp_path/'root.der').write_bytes(der)
    policy=dict(version=1,anchors=[]);file=tmp_path/'confianca.json';file.write_text(json.dumps(policy))
    assert load_explicit_anchors(tmp_path)[0]==[]
    entry=dict(file='root.der',der_sha256=hashlib.sha256(der).hexdigest(),publication_url='https://www.tse.jus.br/synthetic-test-only',selection_reason='Fixture sintética controlada, não publicação real')
    policy['anchors']=[entry];file.write_text(json.dumps(policy))
    assert len(load_explicit_anchors(tmp_path)[0])==1
    entry['der_sha256']='0'*64;file.write_text(json.dumps(policy))
    with pytest.raises(ValueError,match='digital'):load_explicit_anchors(tmp_path)
    entry['file']='../outside.der';file.write_text(json.dumps(policy))
    with pytest.raises(ValueError,match='fora'):load_explicit_anchors(tmp_path)
