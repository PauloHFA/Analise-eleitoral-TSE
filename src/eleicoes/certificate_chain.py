"""Conferência de um vínculo X.509 e de LCR completa, sem promover âncoras.

Verifica apenas o alcance descrito nas funções; não implementa validação integral
de caminhos RFC 5280. Ausência de evidência de revogação permanece inconclusiva.
"""
from cryptography import x509
from cryptography.exceptions import InvalidSignature,UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
import asn1tools
from .audit_signature import canonical_ecdsa,temporal_status
from .ed521 import public_key_from_certificate,verify


def extension(cert,kind):
    try:return cert.extensions.get_extension_for_class(kind).value
    except x509.ExtensionNotFound:return None


def verify_signed_object(obj,issuer):
    """Certificado/LCR: assina os bytes TBS diretamente, sem o wrapper do VSC."""
    message=getattr(obj,'tbs_certificate_bytes',None)
    if message is None:message=obj.tbs_certlist_bytes
    oid=obj.signature_algorithm_oid.dotted_string
    try:
        if oid=='1.3.6.1.4.1.44588.2.1':
            key=public_key_from_certificate(issuer)
            return 'confere_com_candidato' if verify(key,message,obj.signature) else 'nao_confere_com_candidato'
        if oid=='1.2.840.10045.4.3.4':
            key=issuer.public_key()
            if not isinstance(key,ec.EllipticCurvePublicKey) or key.curve.name!='secp521r1':return 'algoritmo_nao_suportado'
            key.verify(canonical_ecdsa(obj.signature),message,ec.ECDSA(hashes.SHA512()))
            return 'confere_com_candidato'
        return 'algoritmo_nao_suportado'
    except InvalidSignature:return 'nao_confere_com_candidato'
    except (ValueError,IndexError,UnsupportedAlgorithm,asn1tools.DecodeError):return 'objeto_ou_chave_nao_suportados'


def issuer_binding(cert,issuer,stamp):
    """Nome/AKI/SKI e assinatura de um vínculo; confiança/tempo são separados."""
    result=dict(issuer_name_match=cert.issuer==issuer.subject,aki_ski_match=None,
        ca_basic_constraint=False,ca_key_cert_sign=False,signature_status='nao_verificada',
        issuer_time_status=temporal_status(issuer,stamp),leaf_time_status=temporal_status(cert,stamp),
        path_status='incompleto_sem_ancora',revocation_status='indeterminado_sem_lcr_verificada')
    aki=extension(cert,x509.AuthorityKeyIdentifier);ski=extension(issuer,x509.SubjectKeyIdentifier)
    if aki and aki.key_identifier and ski:result['aki_ski_match']=aki.key_identifier==ski.digest
    basic=extension(issuer,x509.BasicConstraints);usage=extension(issuer,x509.KeyUsage)
    result['ca_basic_constraint']=bool(basic and basic.ca)
    result['ca_key_cert_sign']=bool(usage and usage.key_cert_sign)
    if not result['issuer_name_match']:result['signature_status']='nome_emissor_incompativel';return result
    if result['aki_ski_match'] is not True:result['signature_status']='identificador_emissor_incompativel_ou_ausente';return result
    if not result['ca_basic_constraint'] or not result['ca_key_cert_sign']:
        result['signature_status']='restricao_de_ca_incompativel';return result
    result['signature_status']=verify_signed_object(cert,issuer)
    # Não interpretar demais extensões/políticas como validação de caminho completo.
    result['unsupported_critical_extensions']=';'.join(e.oid.dotted_string for e in issuer.extensions if e.critical and not isinstance(e.value,(x509.BasicConstraints,x509.KeyUsage,x509.SubjectKeyIdentifier,x509.AuthorityKeyIdentifier)))
    return result


def assess_crl(cert,issuer,crl,moment):
    """Somente LCR completa/direta, assinada e cujo período cubra o instante.

Não fornece status histórico a partir de LCR posterior nem consulta OCSP.
"""
    if crl is None:return 'indeterminado_lcr_nao_obtida'
    if cert.issuer!=issuer.subject:return 'indeterminado_emissor_certificado_diferente'
    if crl.issuer!=issuer.subject:return 'indeterminado_emissor_lcr_diferente'
    usage=extension(issuer,x509.KeyUsage)
    if not usage or not usage.crl_sign:return 'indeterminado_ca_sem_crl_sign'
    basic=extension(issuer,x509.BasicConstraints)
    if not basic or not basic.ca:return 'indeterminado_signatario_nao_ca'
    if not issuer.not_valid_before_utc<=moment<=issuer.not_valid_after_utc:return 'indeterminado_validade_signatario_lcr'
    aki=extension(crl,x509.AuthorityKeyIdentifier);ski=extension(issuer,x509.SubjectKeyIdentifier)
    if aki and aki.key_identifier and (not ski or aki.key_identifier!=ski.digest):return 'indeterminado_aki_lcr'
    if extension(crl,x509.DeltaCRLIndicator) is not None or extension(crl,x509.IssuingDistributionPoint) is not None:return 'indeterminado_escopo_lcr_nao_suportado'
    if any(e.critical and not isinstance(e.value,(x509.AuthorityKeyIdentifier,x509.CRLNumber)) for e in crl.extensions):return 'indeterminado_extensao_lcr'
    if verify_signed_object(crl,issuer)!='confere_com_candidato':return 'indeterminado_assinatura_lcr'
    if crl.next_update_utc is None or not crl.last_update_utc<=moment<crl.next_update_utc:return 'indeterminado_periodo_lcr'
    revoked=crl.get_revoked_certificate_by_serial_number(cert.serial_number)
    if revoked is not None:
        if any(e.critical for e in revoked.extensions):return 'indeterminado_extensao_registro'
        reason=extension(revoked,x509.CRLReason)
        if reason and reason.reason==x509.ReasonFlags.remove_from_crl:return 'indeterminado_remove_from_crl'
        if revoked.revocation_date_utc>moment:return 'indeterminado_data_registro'
        return 'serial_presente_em_lcr_verificada'
    return 'serial_ausente_em_lcr_verificada_no_periodo'
