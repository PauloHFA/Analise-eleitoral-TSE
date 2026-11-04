"""Metadados reprodutíveis da referência de teste, sem consulta de rede na análise."""
from pathlib import Path
import json
from .sources import sha256


def reference_metadata():
    root=Path(__file__).resolve().parents[2]
    vectors=root/'tests/fixtures/ed521_noble_vectors.json'
    generator=root/'scripts/ed521_reference/reference.mjs'
    lock=root/'scripts/ed521_reference/package-lock.json'
    data=json.loads(vectors.read_text(encoding='utf8'))
    if sha256(generator)!=data['generator_script_sha256']:raise ValueError('Gerador difere da versão dos vetores revisados')
    return dict(profile=data['profile'],authority=data['authority'],generator=data['generator'],vectors=len(data['vectors']),
        vectors_sha256=sha256(vectors),generator_sha256=sha256(generator),package_lock_sha256=sha256(lock),
        source_url=data['source_url'],source_pdf_sha256=data['source_pdf_sha256'],source_page=12,
        strict_policy='Pontos canônicos, chave não neutra, A/R no subgrupo primo. Mais restritivo que uma equação apenas cofatada.',
        scope='Verificador de dados públicos; não gera chaves ou assinaturas em produção. Referência Noble é usada somente para testes e conferência independente.')
