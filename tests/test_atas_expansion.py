from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pandas as pd
import duckdb
import pytest
from eleicoes.atas_expansion import check_coverage,check_payload

spec=importlib.util.spec_from_file_location('collector',Path(__file__).resolve().parents[1]/'scripts/pesquisar_atas_ampliacao.py')
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)


def case(section=1,searched=0):
    return dict(year=2026,turn=2,uf='SP',municipality='71072',zone='2',section=str(section),
        municipality_name_1='SÃO PAULO',target_date='2026-10-25',individual_searches=searched)


def execution(job,status='concluida_sem_resultados'):
    return dict(**job,status=status,results=0)


def test_plan_selects_only_pending_cases_and_keeps_date_and_exterior_scope():
    a=case();b=case(2,1);c=case(3);c.update(uf='ZZ',municipality_name_1='BOSTON',target_date='2026-10-04',turn=1)
    jobs=collector.plan(pd.DataFrame([a,b,c]))
    assert len(jobs)==2 and all(r['section']!='2' for r in jobs)
    assert any('site:tre-df.jus.br' in r['query'] and '4 outubro 2026' in r['query'] for r in jobs)
    assert any('site:tre-sp.jus.br' in r['query'] and '25 outubro 2026' in r['query'] for r in jobs)


def test_query_rejects_unsafe_cli_input_and_mismatched_year():
    a=case();a['municipality_name_1']='CITY & command'
    with pytest.raises(ValueError,match='Caracteres'):collector.plan(pd.DataFrame([a]))
    a=case();a['target_date']='2022-10-25'
    with pytest.raises(ValueError,match='ano'):collector.plan(pd.DataFrame([a]))


def test_coverage_rejects_duplicate_queries_and_missing_or_failed_execution():
    c=case();job=collector.plan(pd.DataFrame([c]))[0];done=execution(job)
    check_coverage([c],[job],[done],[done])
    with pytest.raises(ValueError,match='repetido'):check_coverage([c],[job,job],[done],[done])
    with pytest.raises(ValueError,match='incompleta'):check_coverage([c],[job],[],[done])
    failed=execution(job,'falha')
    with pytest.raises(ValueError,match='Falha'):check_coverage([c],[job],[failed],[failed])


def test_history_retains_failed_attempt_before_success_and_requires_latest_outcome():
    c=case();job=collector.plan(pd.DataFrame([c]))[0];done=execution(job);failed=execution(job,'falha')
    check_coverage([c],[job],[done],[failed,done])
    with pytest.raises(ValueError,match='Histórico'):check_coverage([c],[job],[done],[done,failed])


def test_wrong_case_or_query_is_not_counted_as_coverage():
    c=case();job=collector.plan(pd.DataFrame([c]))[0];done=execution(job)
    other=deepcopy(done);other['section']='99'
    with pytest.raises(ValueError,match='fora do plano'):check_coverage([c],[job],[other],[other])
    other=deepcopy(done);other['query']='other query'
    with pytest.raises(ValueError,match='Consulta diferente'):check_coverage([c],[job],[other],[other])


def test_no_results_is_distinct_from_provider_failure_and_bad_count():
    empty=dict(success=True,data=dict(web=[]));row=dict(status='concluida_sem_resultados',results=0)
    assert check_payload(row,empty)==[]
    with pytest.raises(ValueError):check_payload(row,dict(success=False,data=dict(web=[])))
    with pytest.raises(ValueError):check_payload(dict(status='concluida_com_resultados',results=1),empty)


def reference(tmp_path):
    source=tmp_path/'source';folder=source/'auditoria/atas';folder.mkdir(parents=True)
    con=duckdb.connect()
    try:con.from_df(pd.DataFrame([case()])).write_parquet(str(folder/'casos.parquet'))
    finally:con.close()
    return source


def test_resume_does_not_rerun_success_and_rejects_modified_capture(tmp_path,monkeypatch):
    source=reference(tmp_path);dest=tmp_path/'capture';calls=[]
    monkeypatch.setattr(collector.shutil,'which',lambda _: 'fixture-cli')
    def fake(args,**kwargs):
        calls.append(args);Path(args[args.index('-o')+1]).write_text(json.dumps(dict(success=True,data=dict(web=[dict(url='https://www.tre-sp.jus.br/context')]))))
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    monkeypatch.setattr(collector.subprocess,'run',fake)
    collector.run(source,dest,workers=1);collector.run(source,dest,workers=1,resume=True)
    assert len(calls)==1
    (dest/'B07.json').write_text('changed')
    with pytest.raises(ValueError,match='alterada'):collector.run(source,dest,workers=1,resume=True)


def test_failed_attempt_is_recorded_and_successful_retry_closes_only_one_query(tmp_path,monkeypatch):
    source=reference(tmp_path);dest=tmp_path/'capture';calls=[]
    monkeypatch.setattr(collector.shutil,'which',lambda _: 'fixture-cli')
    def fake(args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1 if len(calls)==1 else 0,stdout='No results found.',stderr='')
    monkeypatch.setattr(collector.subprocess,'run',fake)
    with pytest.raises(RuntimeError,match='falha'):collector.run(source,dest,workers=1)
    collector.run(source,dest,workers=1,resume=True)
    history=json.loads((dest/'tentativas.json').read_text(encoding='utf8'));latest=json.loads((dest/'execucoes.json').read_text(encoding='utf8'))
    assert [r['status'] for r in history]==['falha','concluida_sem_resultados']
    assert len(latest)==1 and latest[0]['results']==0
    assert 'capture_note' in json.loads((dest/'B07.json').read_text(encoding='utf8'))


def test_filled_capture_requires_explicit_resume(tmp_path,monkeypatch):
    source=reference(tmp_path);dest=tmp_path/'capture';dest.mkdir();(dest/'anything').write_text('preserved')
    with pytest.raises(FileExistsError):collector.run(source,dest)
