"""Leitor do layout observado em VSC/2026 e verificações separadas por alcance.

O esquema abaixo é uma adaptação explícita, não uma especificação oficial do TSE.
Não utiliza heurísticas por tamanho nem ignora bytes ou campos desconhecidos.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import hashlib
import re
import asn1tools
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec,utils

LAYOUT_ID='observado-vsc-2026-sequencia-final-v1'
SCHEMA='''ObservedVSC DEFINITIONS IMPLICIT TAGS ::= BEGIN
VSC ::= SEQUENCE { sw Entity, hw Entity, platform Platform }
Platform ::= SEQUENCE { model ENUMERATED {ue2009(9),ue2010(10),ue2011(11),ue2013(13),ue2015(15),ue2020(20),ue2022(22)}, algorithm Algorithm }
Algorithm ::= ENUMERATED {rsa(1),ecdsa(2),cepesc(3),eddsa(4)}
Entity ::= SEQUENCE { created GeneralString (SIZE(15)), version INTEGER (2..2), auto Auto,
    payload OCTET STRING, keyset [0] GeneralString OPTIONAL, certificate [1] OCTET STRING OPTIONAL }
Auto ::= SEQUENCE { user User, hashAlgorithm HashAlgorithm, algorithm SignatureAlgorithm, signature Digital }
User ::= SEQUENCE { name GeneralString, serial INTEGER }
HashAlgorithm ::= SEQUENCE { algorithm ENUMERATED {sha1(1),sha256(2),sha384(3),sha512(4)} }
SignatureAlgorithm ::= SEQUENCE { algorithm Algorithm, bits INTEGER }
Digital ::= SEQUENCE { size INTEGER, hash OCTET STRING, signature OCTET STRING }
Payload ::= SEQUENCE { files SEQUENCE OF SignedFile }
SignedFile ::= SEQUENCE { name GeneralString, signature Digital }
ECDSASignature ::= SEQUENCE { r INTEGER, s INTEGER }
END'''
_CODEC=None


def codec():
    global _CODEC
    if _CODEC is None:_CODEC=asn1tools.compile_string(SCHEMA,codec='ber',numeric_enums=True)
    return _CODEC


def decode(name,data):
    obj,used=codec().decode_with_length(name,data,check_constraints=True)
    if used!=len(data):raise ValueError('Bytes adicionais após a entidade')
    # O layout observado usa comprimentos definidos e a codificação reproduzível.
    # Rejeitar campos ignorados pelo decodificador e variantes não suportadas.
    if codec().encode(name,obj)!=data:raise ValueError('Codificação ou campo fora do layout suportado')
    return obj


def parse_vsc(data):
    obj=decode('VSC',data)
    for role in ('sw','hw'):
        ent=obj[role];datetime.strptime(ent['created'],'%Y%m%dT%H%M%S')
        if ent['auto']['hashAlgorithm']['algorithm']!=4:raise ValueError('Somente SHA512 suportado nesta versão')
        files=decode('Payload',ent['payload'])['files']
        names=[r['name'] for r in files]
        if not names or len(names)!=len(set(names)):raise ValueError('Lista de arquivos vazia ou duplicada')
        if any(not re.fullmatch(r'[A-Za-z0-9_-]+\.[A-Za-z0-9]+',n) for n in names):raise ValueError('Nome de arquivo inseguro ou não suportado')
        for dig in [ent['auto']['signature']]+[r['signature'] for r in files]:
            if len(dig['hash'])!=64 or not dig['signature'] or dig['size']<1:raise ValueError('Estrutura de hash/assinatura incompleta')
        ent['files']=files
    if obj['platform']['algorithm']!=obj['hw']['auto']['algorithm']['algorithm']:raise ValueError('Algoritmo da plataforma difere do hardware')
    if set(r['name'] for r in obj['sw']['files'])!=set(r['name'] for r in obj['hw']['files']):raise ValueError('Listas SW/HW diferentes')
    return obj


def hash_status(content,expected):
    return 'concordante' if hashlib.sha512(content).digest()==expected else 'divergente'


def certificate(data):
    padding=0
    if data.startswith(b'-----BEGIN CERTIFICATE-----'):
        cert=x509.load_pem_x509_certificate(data)
        # Não aceitar outro certificado ou conteúdo não branco após o PEM.
        marker=b'-----END CERTIFICATE-----';end=data.find(marker)+len(marker)
        if end<len(marker) or data[end:].strip():raise ValueError('Conteúdo extra após certificado PEM')
    else:
        if len(data)<2 or data[0]!=0x30:raise ValueError('Certificado DER sem sequência')
        first=data[1]
        if first&128:
            length_bytes=first&127
            if length_bytes==0 or length_bytes>4 or len(data)<2+length_bytes:raise ValueError('Comprimento DER inválido')
            size=int.from_bytes(data[2:2+length_bytes],'big');end=2+length_bytes+size
        else:end=2+first
        if end>len(data) or any(data[end:]):raise ValueError('Certificado truncado ou sufixo não nulo')
        padding=len(data)-end;cert=x509.load_der_x509_certificate(data[:end])
    der=cert.public_bytes(serialization.Encoding.DER)
    return cert,dict(sha256=hashlib.sha256(der).hexdigest(),key_oid=cert.public_key_algorithm_oid.dotted_string,
        signature_oid=cert.signature_algorithm_oid.dotted_string,not_before=cert.not_valid_before_utc.isoformat(),
        not_after=cert.not_valid_after_utc.isoformat(),der_zero_padding=padding,
        issuer_cn='; '.join(x.value for x in cert.issuer.get_attributes_for_oid(x509.NameOID.COMMON_NAME)))


def temporal_status(cert,stamp):
    # O VSC não informa fuso. Exigir validade em todas as hipóteses UTC -12..+14.
    local=datetime.strptime(stamp,'%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc)
    low=local-timedelta(hours=14);high=local+timedelta(hours=12)
    if low>=cert.not_valid_before_utc and high<=cert.not_valid_after_utc:return 'compativel_em_todos_os_fusos_considerados'
    if low>cert.not_valid_after_utc:return 'fora_do_intervalo_de_validade'
    if high<cert.not_valid_before_utc:return 'anterior_ao_intervalo_de_validade'
    return 'inconclusivo_sem_fuso'


def canonical_ecdsa(signature):
    # Algumas assinaturas codificam r/s com largura fixa em BER, não DER mínimo.
    # Ler a sequência inteira e recodificar os mesmos inteiros sem aceitar lixo.
    def element(offset,tag,limit):
        if offset+2>limit or signature[offset]!=tag:raise ValueError('Tag ou comprimento ECDSA inválido')
        size=signature[offset+1];start=offset+2
        if size&128:
            count=size&127
            if count==0 or count>2 or start+count>limit:raise ValueError('Comprimento BER não suportado')
            size=int.from_bytes(signature[start:start+count],'big');start+=count
        end=start+size
        if end>limit:raise ValueError('Assinatura ECDSA truncada')
        return start,end
    start,end=element(0,0x30,len(signature))
    _,first_end=element(start,0x02,end);_,second_end=element(first_end,0x02,end)
    if end!=len(signature) or second_end!=end:raise ValueError('Campo adicional na assinatura ECDSA')
    obj,used=codec().decode_with_length('ECDSASignature',signature)
    if used!=len(signature) or obj['r']<=0 or obj['s']<=0:raise ValueError('Assinatura ECDSA malformada')
    return utils.encode_dss_signature(obj['r'],obj['s'])


def verify_signature(cert,algorithm,digest,signature):
    if algorithm!=2:return 'nao_verificado_algoritmo',('Ed521 não implementado nesta versão' if algorithm==4 else 'Algoritmo não implementado nesta versão')
    if cert is None:return 'nao_verificado_certificado','Certificado não disponível ou ilegível'
    key=cert.public_key()
    if not isinstance(key,ec.EllipticCurvePublicKey) or key.curve.name!='secp521r1':return 'nao_verificado_chave','Chave não é ECDSA P-521'
    try:
        # A mensagem assinada é o hash de 64 bytes; ECDSA aplica SHA512 a ele.
        key.verify(canonical_ecdsa(signature),digest,ec.ECDSA(hashes.SHA512()))
        return 'valida_com_chave_embutida',None
    except InvalidSignature:return 'invalida_com_chave_embutida','A equação ECDSA não confere com esta chave'
    except (ValueError,asn1tools.DecodeError) as exc:return 'assinatura_malformada',str(exc)
