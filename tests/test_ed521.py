import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from eleicoes import ed521 as ed

VECTORS=json.loads((Path(__file__).parent/'fixtures/ed521_noble_vectors.json').read_text(encoding='utf8'))['vectors']


@pytest.mark.parametrize('vector',VECTORS,ids=lambda v:v['id'])
def test_independently_generated_noble_vectors(vector):
    key,msg,sig,ctx=(bytes.fromhex(vector[k]) for k in ('public_key','message','signature','context'))
    assert ed.verify(key,msg,sig,ctx)
    assert not ed.verify(key,msg+b'changed',sig,ctx)
    changed=bytearray(sig);changed[70]^=1
    assert not ed.verify(key,msg,bytes(changed),ctx)
    assert not ed.verify(key,msg,sig,ctx+b'x')
    scalar=int.from_bytes(sig[66:],'little')+ed.L
    assert not ed.verify(key,msg,sig[:66]+scalar.to_bytes(66,'little'),ctx)


def encode(point):
    x,y,z,_=point;inv=pow(z,ed.P-2,ed.P);x=x*inv%ed.P;y=y*inv%ed.P
    return (y|((x&1)<<527)).to_bytes(66,'little')


def test_group_order_and_strict_key_policy():
    assert ed.equal(ed.multiply(ed.L,ed.BASE),ed.IDENTITY)
    assert ed.equal(ed.add(ed.BASE,ed.IDENTITY),ed.BASE)
    assert not ed.equal(ed.multiply(ed.L-1,ed.BASE),ed.IDENTITY)
    with pytest.raises(ValueError,match='neutra'):ed.public_point(encode(ed.IDENTITY))
    torsion=(0,ed.P-1,1,0)
    for point in (torsion,ed.add(ed.BASE,torsion)):
        with pytest.raises(ValueError,match='subgrupo'):ed.public_point(encode(point))


def test_rejects_noncanonical_encodings_and_wrong_lengths():
    for value in (ed.P,ed.P+1,(1<<526)|12,1|(1<<527)):
        with pytest.raises(ValueError):ed.decode_point(value.to_bytes(66,'little'))
    assert not ed.verify(b'\x00'*65,b'',b'\x00'*132)
    assert not ed.verify(b'\x00'*66,b'',b'\x00'*131)
    with pytest.raises(ValueError):ed.verify(b'\x00'*66,b'',b'\x00'*132,b'x'*256)
    with pytest.raises(TypeError):ed.verify('key',b'',b'')


def test_identity_key_forgery_is_rejected_but_identity_nonce_is_allowed():
    base=encode(ed.BASE);identity=encode(ed.IDENTITY);msg=b'controlled boundary'
    # Uma equação ingênua aceitaria R=B,S=1 para qualquer mensagem com A=neutro.
    assert not ed.verify(identity,msg,base+(1).to_bytes(66,'little'))
    k=int.from_bytes(hashlib.shake_256(b'SigEd521\x00\x00'+identity+base+msg).digest(132),'little')%ed.L
    assert ed.verify(base,msg,identity+k.to_bytes(66,'little'))


def tlv(tag,body):
    size=len(body);length=bytes([size]) if size<128 else b'\x82'+size.to_bytes(2,'big')
    return bytes([tag])+length+body


def synthetic_certificate(key):
    # Certificado sintético apenas para exercitar a navegação DER/SPKI.
    spki=tlv(0x30,tlv(0x30,b'')+tlv(0x03,b'\x00'+key))
    tbs=tlv(0x30,tlv(0xa0,tlv(2,b'\x02'))+tlv(2,b'\x01')+tlv(0x30,b'')*4+spki)
    data=tlv(0x30,tbs+tlv(0x30,b'')+tlv(3,b'\x00'))
    return SimpleNamespace(public_key_algorithm_oid=SimpleNamespace(dotted_string='1.3.6.1.4.1.44588.2.1'),public_bytes=lambda _:data)


def test_certificate_key_extraction_has_exact_oid_and_size():
    key=bytes.fromhex(VECTORS[0]['public_key']);cert=synthetic_certificate(key)
    assert ed.public_key_from_certificate(cert)==key
    cert.public_key_algorithm_oid.dotted_string='1.3.101.113'
    with pytest.raises(ValueError,match='OID'):ed.public_key_from_certificate(cert)
    with pytest.raises(ValueError):ed.public_key_from_certificate(synthetic_certificate(key[:-1]))
