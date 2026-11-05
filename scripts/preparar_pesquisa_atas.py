"""Preserva buscas/capturas já obtidas; não envia pedidos nem acessa cartórios."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from eleicoes.sources import sha256, write_json

QUERIES = [
    ('B01','atas-ind-ac2.json','AC',1139,7,47,2,'Feijó 7 47 25 outubro 2026 ata atendimento urna'),
    ('B02','atas-ind-ba1.json','BA',34193,53,274,1,'Campo Formoso 53 274 4 outubro 2026 ata urna'),
    ('B03','atas-ind-ba2.json','BA',34193,53,274,2,'Campo Formoso 53 274 25 outubro 2026 substituição urna'),
    ('B04','atas-ind-mt1.json','MT',90352,9,369,1,'Barra do Garças 9 369 4 outubro 2026 impressora urna'),
    ('B05','atas-ind-pr1.json','PR',75833,43,384,1,'Guarapuava 43 384 4 outubro 2026 ata urna'),
    ('B06','atas-ind-zz1.json','ZZ',29416,1,920,1,'Boston 1 920 4 outubro 2026 ata urna'),
]


def official(url):
    u=urlsplit(url);h=u.hostname or ''
    return u.scheme=='https' and not u.username and bool(re.fullmatch(r'(?:[a-z0-9-]+\.)*(?:tse|tre-[a-z]{2})\.jus\.br',h) or h=='www.justicaeleitoral.jus.br')


def prepare(captures, data):
    captures=Path(captures).resolve();data=Path(data).resolve();dest=data/'auditoria/atas/v1'
    if dest.exists() and any(dest.iterdir()):raise FileExistsError('Captura preenchida; usar outra árvore --data')
    dest.mkdir(parents=True,exist_ok=True)
    queries=[];results=[];sources=[];by_url={}

    def add_source(url,title,content,kind,scope,*,turn=None,uf=None):
        if url in by_url:return by_url[url]
        if not official(url):raise ValueError('Fonte não é portal eleitoral oficial declarado')
        sid=f'S{len(sources)+1:02d}';name=sid+'.md';encoded=content.encode('utf8');(dest/name).write_bytes(encoded)
        sources.append(dict(source_id=sid,url=url,title=title,capture_file=name,capture_sha256=sha256(dest/name),
            kind=kind,scope=scope,year=2026 if '/2026/' in url else None,turn=turn,uf=uf,
            method='Extração textual Firecrawl; hash da captura, não dos bytes originais HTTP',
            specific_document=False))
        by_url[url]=sid;return sid

    for bid,filename,uf,municipality,zone,section,turn,query in QUERIES:
        p=captures/filename;obj=json.loads(p.read_text(encoding='utf8'));web=obj['data']['web']
        (dest/filename).write_bytes(p.read_bytes())
        queries.append(dict(search_id=bid,year=2026,turn=turn,uf=uf,municipality=municipality,zone=zone,section=section,
            query=query,capture_file=filename,capture_sha256=sha256(p),saved_at=datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),
            results=len(web),method='Firecrawl search --limit 3 --scrape',specific_documents_obtained=0,
            interpretation='Busca individual realizada, sem documento específico obtido; não comprova inexistência'))
        for row in web:
            sid=None
            if official(row['url']):
                kind='noticia_agregada' if '2deg-boletim' in row['url'] else 'contexto_geral'
                sid=add_source(row['url'],row.get('title',''),row.get('markdown',''),kind,
                    'Boletim estadual de 60 substituições no primeiro turno, sem vínculo com a seção selecionada' if kind=='noticia_agregada' else 'Resultado consultado sem ata ou atendimento individualizado da seção',
                    turn=1 if kind=='noticia_agregada' else None,uf='BA' if kind=='noticia_agregada' else None)
            results.append(dict(result_id=f'R{len(results)+1:02d}',search_id=bid,url=row['url'],title=row.get('title',''),source_id=sid,
                electoral_official_host=official(row['url']),decision='contexto_sem_evidencia_especifica' if sid else 'fora_das_fontes_eleitorais_oficiais',
                reason='Não foi obtida ata ou registro de atendimento com vínculo exato à seção/turno; notícia agregada não confirma ocorrência individual' if sid else 'Resultado não utilizado como evidência institucional do caso'))

    extras=[('atas-tse.json','entenda-o-que','orientacao_geral','Explicação geral sobre mesas receptoras; não é ata do caso'),
            ('atas-tse.json','23-751','norma_geral','Regulamentação geral; não documenta ocorrência da seção'),
            ('atas-boston.json','como-a-justica','orientacao_geral','Organização do exterior; não comprova evento em Boston'),
            ('atas-tse.json','/servicos-judiciais/atas-das-sessoes','ata_julgamento','Atas de julgamento, distintas de atas de mesa receptora')]
    for filename,needle,kind,scope in extras:
        p=captures/filename;obj=json.loads(p.read_text(encoding='utf8'));r=next(r for r in obj['data']['web'] if needle in r['url'])
        add_source(r['url'],r.get('title',''),r.get('markdown',''),kind,scope)
    for filename,url,title in (
        ('atas-rota-df.md','https://www.tre-df.jus.br/servicos-eleitorais/zonas-eleitorais/zz-zona-exterior-endereco-e-telefones','Zona do Exterior — diretório oficial'),
        ('atas-rota-ac.md','https://www.tre-ac.jus.br/institucional/cartorios-eleitorais','Zonas eleitorais do Acre — diretório oficial')):
        add_source(url,title,(captures/filename).read_text(encoding='utf8'),'canal_de_acesso','Rota oficial de acesso; nenhuma solicitação enviada')
    prior=data/'auditoria/documentacao/logs/v1/auditoria.md'
    add_source('https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/como-realizar-auditoria','Como realizar auditoria',prior.read_text(encoding='utf8'),
        'orientacao_geral','Referência sobre comparação de atas e documentos digitais; não é evidência de ocorrência individual')
    write_json(dest/'pesquisa.json',dict(version=1,captured_at=datetime.now(timezone.utc).isoformat(),queries=queries,results=results,sources=sources,
        scope='Seis buscas individuais dos casos prioritários. Outras buscas exploratórias não são contabilizadas como buscas individuais. Nenhum documento específico obtido ou contato enviado.'))
    write_json(dest/'evidencias.json',dict(version=1,evidence=[],scope='Registros futuros exigem documento específico, identidade exata, apontamento e localização da evidência; não classificam causa automaticamente.'))
    write_json(dest/'manifesto.json',{p.name:sha256(p) for p in sorted(dest.iterdir()) if p.is_file() and p.name!='manifesto.json'})
    print(json.dumps(dict(individual_searches=len(queries),search_results=len(results),reviewed_context_sources=len(sources),specific_documents_obtained=0),ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capturas',default='.firecrawl');p.add_argument('--data',default='data');a=p.parse_args();prepare(a.capturas,a.data)
