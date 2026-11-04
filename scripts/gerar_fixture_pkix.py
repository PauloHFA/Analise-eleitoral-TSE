"""Gera certificados/LCR públicos sintéticos com emissor Ed521 e raiz ECDSA.

Chaves fixas e públicas são exclusivamente de teste, sem relação com as urnas.
"""
from pathlib import Path
from datetime import datetime,timezone
import json,subprocess,hashlib
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from asn1crypto import x509 as ax,keys,algos,crl as ac

root=Path(__file__).resolve().parents[1];UTC=timezone.utc;OID='1.3.6.1.4.1.44588.2.1'
rk=ec.derive_private_key(1,ec.SECP521R1());placeholder=ec.derive_private_key(2,ec.SECP521R1());lk=ec.derive_private_key(3,ec.SECP521R1())
name=lambda s:x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME,s)])
def cert(subject,issuer,key,signer,serial,ca,ski,aki):
    return x509.CertificateBuilder().subject_name(name(subject)).issuer_name(name(issuer)).public_key(key.public_key()).serial_number(serial).not_valid_before(datetime(2025,1,1,tzinfo=UTC)).not_valid_after(datetime(2028,1,1,tzinfo=UTC)).add_extension(x509.BasicConstraints(ca,0 if ca and serial==2 else None),True).add_extension(x509.KeyUsage(not ca,False,False,False,False,ca,ca,False,False),True).add_extension(x509.SubjectKeyIdentifier(ski),False).add_extension(x509.AuthorityKeyIdentifier(aki,None,None),False).add_extension(x509.CRLDistributionPoints([x509.DistributionPoint([x509.UniformResourceIdentifier('https://example.invalid/test.crl')],None,None,None)]),False).sign(signer,hashes.SHA512(),ecdsa_deterministic=True)
node=['node',str(root/'scripts/ed521_reference/sign_test_pkix.mjs')]
def sign(messages):return json.loads(subprocess.run(node,input=json.dumps(messages),encoding='utf8',capture_output=True,check=True).stdout)
pub=bytes.fromhex(sign([])['public_key']);ski_root=x509.SubjectKeyIdentifier.from_public_key(rk.public_key()).digest;ski_ed=hashlib.sha1(pub).digest();ski_leaf=x509.SubjectKeyIdentifier.from_public_key(lk.public_key()).digest
root_cert=cert('Synthetic root','Synthetic root',rk,rk,1,True,ski_root,ski_root)
issuer_template=cert('Synthetic Ed issuer','Synthetic root',placeholder,rk,2,True,ski_ed,ski_root)
leaf_template=cert('Synthetic leaf','Synthetic Ed issuer',lk,placeholder,3,False,ski_leaf,ski_ed)
def tlv(tag,b):
    n=len(b);length=bytes([n]) if n<128 else b'\x82'+n.to_bytes(2,'big')
    return bytes([tag])+length+b
spki=tlv(0x30,algos.AlgorithmIdentifier({'algorithm':OID}).dump()+tlv(3,b'\x00'+pub))
issuer=ax.Certificate.load(issuer_template.public_bytes(serialization.Encoding.DER));issuer['tbs_certificate']['subject_public_key_info']=keys.PublicKeyInfo.load(spki)
issuer['signature_value']=rk.sign(issuer['tbs_certificate'].dump(),ec.ECDSA(hashes.SHA512(),deterministic_signing=True))
leaf=ax.Certificate.load(leaf_template.public_bytes(serialization.Encoding.DER));leaf['tbs_certificate']['signature']={'algorithm':OID};leaf['signature_algorithm']={'algorithm':OID}
def crl_template(ca,signer,aki):
    return x509.CertificateRevocationListBuilder().issuer_name(ca.subject).last_update(datetime(2026,10,1,tzinfo=UTC)).next_update(datetime(2026,11,1,tzinfo=UTC)).add_extension(x509.AuthorityKeyIdentifier(aki,None,None),False).add_extension(x509.CRLNumber(1),False).sign(signer,hashes.SHA512(),ecdsa_deterministic=True)
root_crl=crl_template(root_cert,rk,ski_root)
issuer_crypto=x509.load_der_x509_certificate(issuer.dump());ed_crl=ac.CertificateList.load(crl_template(issuer_crypto,placeholder,ski_ed).public_bytes(serialization.Encoding.DER));ed_crl['tbs_cert_list']['signature']={'algorithm':OID};ed_crl['signature_algorithm']={'algorithm':OID}
signed=sign([leaf['tbs_certificate'].dump().hex(),ed_crl['tbs_cert_list'].dump().hex()])['signatures'];leaf['signature_value']=bytes.fromhex(signed[0]);ed_crl['signature']=bytes.fromhex(signed[1])
fixture=dict(authority='Certificados e LCR sintéticos para testes; chaves e sementes públicas, sem relação com as urnas',root_der=root_cert.public_bytes(serialization.Encoding.DER).hex(),issuer_der=issuer.dump().hex(),leaf_der=leaf.dump().hex(),root_crl_der=root_crl.public_bytes(serialization.Encoding.DER).hex(),issuer_crl_der=ed_crl.dump().hex(),node_generator_sha256=hashlib.sha256((root/'scripts/ed521_reference/sign_test_pkix.mjs').read_bytes()).hexdigest())
(root/'tests/fixtures/pkix_ed521.json').write_text(json.dumps(fixture,indent=2)+'\n',encoding='utf8',newline='\n')
print('Fixture pública sintética Ed521 gerada; não é cadeia oficial nem material de urna.')
