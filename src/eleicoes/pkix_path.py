"""Adapta o validador PKIX mantido por pyHanko ao perfil criptográfico das urnas.

Âncoras são sempre explícitas; não há fallback para a lista TLS do sistema.
O êxito sem revogação nunca é promovido a êxito de revogação.
"""
import asyncio
from functools import lru_cache
import asn1tools
from datetime import timedelta
from cryptography.exceptions import InvalidSignature
from asn1crypto import x509 as ax509,crl as acrl
from cryptography.hazmat.primitives import serialization
from urllib.parse import urlsplit
from pathlib import Path
import json
from pyhanko_certvalidator import CertificateValidator,ValidationContext
from pyhanko_certvalidator.sig_validate import DefaultSignatureValidator
from pyhanko_certvalidator.policy_decl import CertRevTrustPolicy,RevocationCheckingPolicy,RevocationCheckingRule
from pyhanko_certvalidator.errors import PathBuildingError,ValidationError,RevokedError,AlgorithmNotSupported
from .ed521 import verify,public_point
from .audit_signature import canonical_ecdsa

ED521_OID='1.3.6.1.4.1.44588.2.1'


@lru_cache(maxsize=1)
def spki_codec():
    return asn1tools.compile_string('Keys DEFINITIONS ::= BEGIN SPKI ::= SEQUENCE { algorithm SEQUENCE { id OBJECT IDENTIFIER, parameters ANY OPTIONAL }, key BIT STRING } END',codec='der')


def ed521_spki(encoded):
    obj,used=spki_codec().decode_with_length('SPKI',encoded)
    if used!=len(encoded) or spki_codec().encode('SPKI',obj)!=encoded:raise InvalidSignature('SPKI não canônico')
    if obj['algorithm']['id']!=ED521_OID or 'parameters' in obj['algorithm']:raise InvalidSignature('Algoritmo SPKI incompatível')
    key,bits=obj['key']
    if len(key)!=66 or bits!=528:raise InvalidSignature('Tamanho da chave Ed521 incompatível')
    try:public_point(key)
    except ValueError as exc:raise InvalidSignature(str(exc)) from exc
    return key


class UrnaSignatureValidator(DefaultSignatureValidator):
    def validate_signature(self,signature,signed_data,public_key_info,signature_algorithm,context=None):
        oid=signature_algorithm['algorithm'].dotted
        if oid==ED521_OID:
            if context is not None and context.prehashed:raise AlgorithmNotSupported('Ed521ph não suportado')
            if public_key_info['algorithm']['algorithm'].dotted!=ED521_OID:raise InvalidSignature('OID de chave incompatível')
            if signature_algorithm['parameters'].native is not None or public_key_info['algorithm']['parameters'].native is not None:raise AlgorithmNotSupported('Parâmetros Ed521 inesperados')
            key=ed521_spki(public_key_info.dump())
            if not verify(key,signed_data,signature):raise InvalidSignature('Ed521 não confere')
            return
        if oid=='1.2.840.10045.4.3.4':signature=canonical_ecdsa(signature)
        if context is None:super().validate_signature(signature,signed_data,public_key_info,signature_algorithm)
        else:super().validate_signature(signature,signed_data,public_key_info,signature_algorithm,context)


def asn1_certificate(cert):
    return ax509.Certificate.load(cert.public_bytes(serialization.Encoding.DER),strict=True)


def asn1_crl(crl):
    return acrl.CertificateList.load(crl.public_bytes(serialization.Encoding.DER),strict=True)


def load_explicit_anchors(directory):
    """Manifesto de seleção é entrada da análise, não prova automática de origem."""
    from .audit_signature import certificate
    directory=Path(directory).resolve()
    manifest=json.loads((directory/'confianca.json').read_text(encoding='utf8'))
    if manifest.get('version')!=1:raise ValueError('Versão de manifesto não suportada')
    result=[];seen=set()
    for record in manifest['anchors']:
        path=(directory/record['file']).resolve()
        if not path.is_relative_to(directory):raise ValueError('Âncora fora da pasta de fontes')
        parsed,info=certificate(path.read_bytes())
        if info['sha256']!=record['der_sha256'] or info['sha256'] in seen:raise ValueError('Impressão digital diferente ou repetida')
        url=urlsplit(record.get('publication_url',''))
        if url.scheme!='https' or not url.hostname or not url.hostname.endswith('.tse.jus.br') or not record.get('selection_reason'):
            raise ValueError('Seleção sem proveniência declarada e justificativa')
        seen.add(info['sha256']);result.append(parsed)
    return result,manifest


async def _validate(leaf,intermediates,anchors,moment,crls,require_revocation):
    rule=RevocationCheckingRule.CRL_REQUIRED if require_revocation else RevocationCheckingRule.NO_CHECK
    context=ValidationContext(trust_roots=[asn1_certificate(c) for c in anchors],
        other_certs=[asn1_certificate(c) for c in intermediates],moment=moment,allow_fetching=False,
        crls=[asn1_crl(c) for c in crls],ocsps=[],retroactive_revinfo=False,time_tolerance=timedelta(0),
        revinfo_policy=CertRevTrustPolicy(RevocationCheckingPolicy(rule,rule),retroactive_revinfo=False),
        signature_validator=UrnaSignatureValidator())
    validator=CertificateValidator(asn1_certificate(leaf),validation_context=context)
    path=await validator.async_validate_usage({'digital_signature'})
    # Material de auditoria sem exportar os certificados completos.
    return len(path)


def validate_path(leaf,intermediates,anchors,moment,crls=()):
    if moment.tzinfo is None:raise ValueError('Instante deve incluir fuso horário')
    result=dict(path_status='nao_avaliado',revocation_status='nao_avaliada_sem_caminho',
                anchors_supplied=len(anchors),moment=moment.isoformat(),backend='pyhanko-certvalidator',error_type=None,reason=None)
    try:
        result['path_length']=asyncio.run(_validate(leaf,intermediates,anchors,moment,crls,False))
        result['path_status']='confere_no_instante_com_ancora_explicita'
    except PathBuildingError as exc:
        result.update(path_status='inconclusivo_sem_ancora' if not anchors else 'inconclusivo_caminho_nao_encontrado',error_type=type(exc).__name__,reason=str(exc));return result
    except ValidationError as exc:
        result.update(path_status='nao_confere_no_perfil' if anchors else 'inconclusivo_sem_ancora',error_type=type(exc).__name__,reason=str(exc));return result
    except (ValueError,KeyError,NotImplementedError,AlgorithmNotSupported) as exc:
        result.update(path_status='nao_suportado',error_type=type(exc).__name__,reason=str(exc));return result
    try:
        asyncio.run(_validate(leaf,intermediates,anchors,moment,crls,True))
        result['revocation_status']='conferida_por_lcr_no_instante'
    except RevokedError as exc:result.update(revocation_status='revogado_segundo_lcr_validada',error_type=type(exc).__name__,reason=str(exc))
    except ValidationError as exc:result.update(revocation_status='inconclusiva_evidencia_lcr',error_type=type(exc).__name__,reason=str(exc))
    except (ValueError,KeyError,NotImplementedError,AlgorithmNotSupported) as exc:result.update(revocation_status='nao_suportada',error_type=type(exc).__name__,reason=str(exc))
    return result
