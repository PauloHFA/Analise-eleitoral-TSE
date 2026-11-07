"""Ampliação versionada da pesquisa: conclusão de busca não é evidência de caso."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
from .audit_atas import key,official_source
from .sources import sha256,write_json

COMPLETED={'concluida_com_resultados','concluida_sem_resultados'}


def check_coverage(cases,jobs,latest,history):
    pending={key(r) for r in cases if r['individual_searches']==0}
    if len(jobs)!=len({r['search_id'] for r in jobs}) or len(jobs)!=len({key(r) for r in jobs}):raise ValueError('Plano de buscas repetido')
    if {key(r) for r in jobs}!=pending:raise ValueError('Plano não fecha as unidades pendentes')
    plan={r['search_id']:r for r in jobs}
    if len(latest)!=len(plan) or len({r['search_id'] for r in latest})!=len(plan):raise ValueError('Execução incompleta ou duplicada')
    last={}
    for attempt in history:
        if attempt['search_id'] not in plan or key(attempt)!=key(plan[attempt['search_id']]):raise ValueError('Tentativa fora do plano')
        last[attempt['search_id']]=attempt
    for row in latest:
        if row['search_id'] not in plan or key(row)!=key(plan[row['search_id']]):raise ValueError('Execução fora do plano')
        if row['status'] not in COMPLETED:raise ValueError('Falha não pode ser contada como busca concluída')
        if row['query']!=plan[row['search_id']]['query']:raise ValueError('Consulta diferente do plano')
        if row['search_id'] not in last or last[row['search_id']]['status']!=row['status']:raise ValueError('Histórico não fecha o resultado final')


def check_payload(row,payload):
    web=payload.get('data',{}).get('web')
    if payload.get('success') is False or not isinstance(web,list):raise ValueError('Resposta de busca inválida')
    if len(web)!=row['results'] or (row['status']=='concluida_sem_resultados')!=(not bool(web)):raise ValueError('Estado/quantidade de resultados incompatíveis')
    return web


def prepare_expansion(source,captures,data):
    import duckdb
    source,captures,data=Path(source).resolve(),Path(captures).resolve(),Path(data).resolve()
    previous=data/'auditoria/atas/v1';dest=data/'auditoria/atas/v2'
    if dest.exists() and any(dest.iterdir()):raise FileExistsError('Captura v2 já preenchida; usar outra árvore --data')
    old_manifest=json.loads((previous/'manifesto.json').read_text(encoding='utf8'))
    for name,digest in old_manifest.items():
        path=(previous/name).resolve()
        if not path.is_relative_to(previous) or sha256(path)!=digest:raise ValueError('Captura inicial alterada')
    plan=json.loads((captures/'plano.json').read_text(encoding='utf8'))
    if plan['reference_sha256']!=sha256(source/'auditoria/atas/casos.parquet'):raise ValueError('Plano pertence a outra referência')
    con=duckdb.connect()
    try:cases=con.read_parquet(str(source/'auditoria/atas/casos.parquet')).df().to_dict('records')
    finally:con.close()
    latest=json.loads((captures/'execucoes.json').read_text(encoding='utf8'));history=json.loads((captures/'tentativas.json').read_text(encoding='utf8'))
    check_coverage(cases,plan['queries'],latest,history)
    reviews=json.loads((captures/'revisao.json').read_text(encoding='utf8'))['results']
    if len(reviews)!=len({r['result_id'] for r in reviews}):raise ValueError('Revisão repetida')
    dest.mkdir(parents=True,exist_ok=True);(dest/'anterior').mkdir();(dest/'novas').mkdir()
    for name in old_manifest:(dest/'anterior'/name).write_bytes((previous/name).read_bytes())
    (dest/'anterior/manifesto.json').write_bytes((previous/'manifesto.json').read_bytes())
    research=deepcopy(json.loads((previous/'pesquisa.json').read_text(encoding='utf8')))
    for item in research['sources']:item['capture_file']='anterior/'+item['capture_file']
    for item in research['queries']:
        item.update(capture_file='anterior/'+item['capture_file'],round='inicial',status='concluida_com_resultados' if item['results'] else 'concluida_sem_resultados')
    by_content={(r['url'],r['capture_sha256']):r['source_id'] for r in research['sources']}
    index=len(research['results']);seen=[]
    for item in sorted(latest,key=lambda r:r['search_id']):
        path=(captures/item['capture_file']).resolve()
        if not path.is_relative_to(captures) or sha256(path)!=item['capture_sha256']:raise ValueError('Captura nova alterada')
        web=check_payload(item,json.loads(path.read_text(encoding='utf8')))
        output_name='novas/'+item['capture_file'];(dest/output_name).write_bytes(path.read_bytes())
        query={k:item[k] for k in ('search_id','year','turn','uf','municipality','zone','section','query')}
        query.update(capture_file=output_name,capture_sha256=item['capture_sha256'],saved_at=item['finished'],
            results=len(web),method='Firecrawl search --limit 3 --scrape; domínio eleitoral regional',specific_documents_obtained=0,
            interpretation='Busca concluída; não demonstra inexistência de ata ou de ocorrência',round='ampliacao',status=item['status'])
        research['queries'].append(query)
        for result in web:
            index+=1;rid=f'R{index:02d}';review=next((r for r in reviews if r['result_id']==rid),None)
            if not review or review['search_id']!=item['search_id'] or review['url']!=result['url']:raise ValueError('Resultado sem revisão correspondente')
            if review['specific_document_obtained'] or review['decision'] not in ('contexto_sem_evidencia_especifica','captura_limitada_sem_confronto'):raise ValueError('Documento candidato exige incorporação/revisão específica, sem aprovação automática')
            if not official_source(result['url']):raise ValueError('Origem fora do escopo desta captura')
            content=result.get('markdown','').encode('utf8');digest=hashlib.sha256(content).hexdigest();sid=by_content.get((result['url'],digest))
            if sid is None:
                sid=f'S{len(research["sources"])+1:02d}';filename=f'novas/{sid}.md';(dest/filename).write_bytes(content)
                research['sources'].append(dict(source_id=sid,url=result['url'],title=result.get('title',''),capture_file=filename,
                    capture_sha256=digest,kind=review['kind'],scope=review['scope'],year=None,turn=None,uf=None,
                    method='Extração textual Firecrawl; hash da captura, não dos bytes HTTP originais',specific_document=False))
                by_content[(result['url'],digest)]=sid
            research['results'].append(dict(result_id=rid,search_id=item['search_id'],url=result['url'],title=result.get('title',''),source_id=sid,
                electoral_official_host=True,decision=review['decision'],reason=review['scope']))
            seen.append(rid)
    if set(seen)!={r['result_id'] for r in reviews}:raise ValueError('Revisão não corresponde aos resultados completos')
    for filename in ('plano.json','execucoes.json','tentativas.json','revisao.json'):(dest/'novas'/filename).write_bytes((captures/filename).read_bytes())
    research.update(captured_at=datetime.now(timezone.utc).isoformat(),research_round='ampliacao',
        previous_capture_manifest_sha256=sha256(previous/'manifesto.json'),new_individual_searches=len(latest),
        new_search_attempts=len(history),failed_executor_attempts=sum(r['status']=='falha' for r in history),
        new_queries_without_results=sum(r['status']=='concluida_sem_resultados' for r in latest),
        scope='Segunda rodada: 22 consultas novas mais seis preservadas, cobrindo 28 unidades. Não é busca exaustiva nem obtenção de documentos específicos. Tentativas falhas são preservadas sem contar como buscas concluídas.',
        preparation_code_sha256=sha256(Path(__file__)))
    write_json(dest/'pesquisa.json',research)
    (dest/'evidencias.json').write_bytes((previous/'evidencias.json').read_bytes())
    write_json(dest/'manifesto.json',{p.relative_to(dest).as_posix():sha256(p) for p in sorted(dest.rglob('*')) if p.is_file() and p!=dest/'manifesto.json'})
    print(json.dumps(dict(new_queries=len(latest),total_queries=len(research['queries']),total_results=len(research['results']),
        context_captures=len(research['sources']),unique_context_urls=len({r['url'] for r in research['sources']}),executor_attempts=len(history)),ensure_ascii=False))
