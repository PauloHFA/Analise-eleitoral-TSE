"""Executa só as buscas públicas das unidades ainda não pesquisadas, via CLI."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import duckdb
from eleicoes.audit_atas import GEO, case_id
from eleicoes.sources import write_json, sha256


def plan(cases):
    pending=cases.loc[cases.individual_searches.eq(0)].sort_values(GEO)
    rows=[]
    for i,case in enumerate(pending.to_dict('records'),7):
        domain='tre-df.jus.br' if case['uf']=='ZZ' else f"tre-{case['uf'].lower()}.jus.br"
        date=datetime.fromisoformat(case['target_date'])
        if date.year!=int(case['year']):raise ValueError('Data-alvo não corresponde ao ano do caso')
        month=['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'][date.month-1]
        query=f"site:{domain} {case['municipality_name_1']} zona {case['zone']} seção {case['section']} {date.day} {month} {date.year} ata ocorrência urna"
        if any(c in query for c in '&|<>"%^\r\n'):raise ValueError('Caracteres não permitidos na consulta ao CLI')
        rows.append(dict(search_id=f'B{i:02d}',**{k:case[k] for k in GEO},case_id=case_id(case),query=query,capture_file=f'B{i:02d}.json'))
    return rows


def run(source, destination, workers=2, resume=False, batch_size=None):
    if workers not in (1,2) or (batch_size is not None and batch_size<=0):raise ValueError('Limites de execução inválidos')
    source,dest=Path(source).resolve(),Path(destination).resolve()
    filled=dest.exists() and any(dest.iterdir())
    if filled and not resume:raise FileExistsError('Capturas existentes; usar pasta nova ou --resume')
    cli=shutil.which('firecrawl')
    if not cli:raise RuntimeError('CLI Firecrawl não encontrada')
    con=duckdb.connect()
    try:cases=con.read_parquet(str(source/'auditoria/atas/casos.parquet')).df()
    finally:con.close()
    jobs=plan(cases);dest.mkdir(parents=True,exist_ok=True);completed=[];history=[]
    expected=dict(reference_sha256=sha256(source/'auditoria/atas/casos.parquet'),queries=jobs)
    if filled:
        if json.loads((dest/'plano.json').read_text(encoding='utf8'))!=expected:raise ValueError('Plano ou referência diferentes do checkpoint')
        completed=json.loads((dest/'execucoes.json').read_text(encoding='utf8'))
        history=json.loads((dest/'tentativas.json').read_text(encoding='utf8')) if (dest/'tentativas.json').exists() else list(completed)
        for item in completed:
            if item['status'].startswith('concluida_') and sha256(dest/item['capture_file'])!=item['capture_sha256']:raise ValueError('Captura concluída foi alterada')
    else:write_json(dest/'plano.json',expected)
    already={r['search_id'] for r in completed if r['status'].startswith('concluida_')}
    jobs=[j for j in jobs if j['search_id'] not in already]
    if batch_size is not None:jobs=jobs[:batch_size]

    def search(job):
        record=dict(**job,started=datetime.now(timezone.utc).isoformat())
        try:
            proc=subprocess.run([cli,'search',job['query'],'--limit','3','--scrape','-o',str(dest/job['capture_file']),'--json'],capture_output=True,text=True,encoding='utf8',timeout=100)
            path=dest/job['capture_file']
            if proc.returncode==0 and path.is_file():
                obj=json.loads(path.read_text(encoding='utf8'));web=obj.get('data',{}).get('web')
                if obj.get('success') is False or not isinstance(web,list):raise ValueError('Resposta sem resultado de busca válido')
                record.update(status='concluida_com_resultados' if web else 'concluida_sem_resultados',results=len(web),provider_search_id=obj.get('id'))
            elif proc.returncode==0 and 'No results found' in proc.stdout+proc.stderr:
                write_json(path,dict(success=True,data=dict(web=[]),capture_note='CLI retornou No results found com exit 0; arquivo vazio estruturado pelo projeto'))
                record.update(status='concluida_sem_resultados',results=0,provider_search_id=None)
            else:record.update(status='falha',results=None,error_type='cli_failure',return_code=proc.returncode,
                diagnostic_sha256=__import__('hashlib').sha256((proc.stdout+proc.stderr).encode('utf8')).hexdigest())
            if path.is_file():record['capture_sha256']=sha256(path)
        except (OSError,ValueError,subprocess.TimeoutExpired) as exc:record.update(status='falha',results=None,error_type=type(exc).__name__)
        record['finished']=datetime.now(timezone.utc).isoformat();return record

    latest={r['search_id']:r for r in completed};batch=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(search,j) for j in jobs]):
            item=future.result();latest[item['search_id']]=item;batch.append(item);history.append(item)
            write_json(dest/'execucoes.json',sorted(latest.values(),key=lambda r:r['search_id']))
            write_json(dest/'tentativas.json',history)
            print(json.dumps({k:item.get(k) for k in ('search_id','status','results')},ensure_ascii=False),flush=True)
    if any(r['status']=='falha' for r in batch):raise RuntimeError('Houve falha de busca; não contabilizar como pesquisa concluída')
    print(json.dumps(dict(planned=len(expected['queries']),completed=sum(r['status'].startswith('concluida_') for r in latest.values()),executor_attempts=len(history))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='outputs/2026');p.add_argument('--dest',default='.firecrawl/atas-ampliacao-v1');p.add_argument('--resume',action='store_true');p.add_argument('--workers',type=int,choices=[1,2],default=2);p.add_argument('--batch-size',type=int);a=p.parse_args();run(a.output,a.dest,a.workers,a.resume,a.batch_size)
