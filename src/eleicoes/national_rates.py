"""Taxas com denominadores, coortes territoriais e reconciliação explícita."""
from pathlib import Path

import duckdb
import pandas as pd

from .analysis import export_frame
from .investigation import metrics,VALUES
from .national_common import begin,finish,failed,records


def rates(con,keys):
    grouped=','.join(keys)
    table="(SELECT *,CASE WHEN uf='ZZ' THEN 'Exterior' ELSE 'Brasil' END region FROM sections)" if 'region' in keys else 'sections'
    return con.execute(f'''WITH counts AS (SELECT {grouped},count(*) observed_sections,
        count(*) FILTER(WHERE comparable) comparable_sections,count(*) FILTER(WHERE eligible) eligible_sections,
        count(*) FILTER(WHERE eligible AND reference_alert) reference_alert_sections,
        count(*) FILTER(WHERE eligible AND selected_pattern) pattern_eligible_sections,
        count(*) FILTER(WHERE eligible AND margin_robust_z IS NULL) margin_inconclusive_sections
        FROM {table} GROUP BY {grouped}) SELECT *,
        100.*comparable_sections/observed_sections comparable_coverage_pct,
        100.*eligible_sections/observed_sections eligible_coverage_pct,
        1000.*reference_alert_sections/nullif(eligible_sections,0) rate_per_1000
        FROM counts''').df()


def mask_rates(frame,minimum=30,coverage=80):
    if minimum<1 or not 0<=coverage<=100:raise ValueError('Limites de exibição inválidos')
    out=frame.copy()
    out['rate_map_status']='apresentável pelos limites escolhidos'
    out.loc[out.eligible_coverage_pct.lt(coverage)|out.eligible_coverage_pct.isna(),'rate_map_status']='cobertura elegível abaixo do limite ou desconhecida'
    out.loc[out.eligible_sections.lt(minimum),'rate_map_status']='quantidade de elegíveis abaixo do limite'
    out.loc[out.eligible_sections.eq(0)|out.eligible_sections.isna(),'rate_map_status']='sem denominador elegível'
    out['rate_map_value']=out.rate_per_1000.where(out.rate_map_status.eq('apresentável pelos limites escolhidos'))
    return out


def cohort(con):
    quantities=[f'{m}_{t}' for m in VALUES for t in (1,2)]
    expressions=','.join(f'CASE WHEN count({name})=count(*) THEN sum({name}) END "{name}"' for name in quantities)
    frame=con.execute(f'''SELECT year,uf,municipality,count(*) cohort_sections,{expressions}
        FROM sections WHERE comparable GROUP BY year,uf,municipality''').df()
    frame=metrics(frame)
    return frame.rename(columns={name:'cohort_'+name for name in frame.columns if name not in ('year','uf','municipality','cohort_sections')})


def reconciliation(con):
    quantities={}
    for name in ('sections','locals','municipalities','states'):
        con.execute(f"CREATE OR REPLACE TEMP VIEW scoped_{name} AS SELECT *,uf scope FROM {name} UNION ALL BY NAME SELECT *,'Brasil' scope FROM {name} WHERE uf<>'ZZ'")
        for t in (1,2):
            for candidate in (13,22):
                field=f'votes_{candidate}_{t}'
                rows=con.execute(f'SELECT scope,sum({field}),count(*) FILTER(WHERE {field} IS NULL) FROM scoped_{name} GROUP BY scope').fetchall()
                for scope,total,missing in rows:
                    item=quantities.setdefault((scope,t,candidate),dict(scope=scope,turn=t,candidate=candidate))
                    item[name+'_available_votes']=float(total) if total is not None else None
                    item[name+'_missing_rows']=missing
    for scope,turn,candidate,total,missing in con.execute("""WITH s AS (SELECT *,uf scope FROM official
        UNION ALL BY NAME SELECT *,'Brasil' scope FROM official WHERE uf<>'ZZ')
        SELECT scope,turn,candidate,sum(official_votes),count(*) FILTER(WHERE official_votes IS NULL)
        FROM s WHERE candidate IN (13,22) GROUP BY scope,turn,candidate""").fetchall():
        item=quantities.setdefault((scope,turn,candidate),dict(scope=scope,turn=turn,candidate=candidate))
        item['official_available_votes']=float(total) if total is not None else None
        item['official_missing_rows']=missing
    result=pd.DataFrame(quantities.values()).sort_values(['scope','turn','candidate']).reset_index(drop=True)
    fields=[name+'_available_votes' for name in ('sections','locals','municipalities','states','official')]
    complete=result[fields].notna().all(axis=1)
    equal=result[fields].nunique(axis=1).eq(1)
    result['status']='limitação de cobertura ou parcela indisponível'
    result.loc[complete & equal,'status']='concordante nos somatórios disponíveis'
    result.loc[complete & ~equal,'status']='diferença entre somatórios: revisar cobertura'
    return result


def run_rates(source,destination=None,minimum=30,coverage=80):
    if minimum<1 or not 0<=coverage<=100:raise ValueError('Limites de exibição inválidos')
    source=Path(source).resolve();destination=Path(destination).resolve() if destination else source/'nacional/taxas'
    names=[f'nacional/inventario/{name}.parquet' for name in ('secoes','locais','municipios','ufs')]+[
        'nacional/inventario/resumo.json','reconciliacao_municipio_zona.parquet','conferencia_bu.parquet']
    source,destination,state=begin(source,destination,names)
    con=duckdb.connect(config={'threads':2,'memory_limit':'1GB'})
    try:
        for table,name in (('sections','secoes'),('locals','locais'),('municipalities','municipios'),('states','ufs')):
            con.read_parquet(str(source/f'nacional/inventario/{name}.parquet')).create_view(table)
        con.read_parquet(str(source/'reconciliacao_municipio_zona.parquet')).create_view('official')
        section_counts=rates(con,['year','uf','municipality'])
        municipalities=con.execute('SELECT * FROM municipalities').df().merge(section_counts,on=['year','uf','municipality'],how='outer',validate='one_to_one')
        municipalities=municipalities.merge(cohort(con),on=['year','uf','municipality'],how='left',validate='one_to_one')
        municipalities['cohort_sections']=municipalities.cohort_sections.fillna(0).astype(int)
        for t in (1,2):
            for measure in ('aptos','attendance','valid'):
                numerator=municipalities[f'cohort_{measure}_{t}']
                denominator=municipalities[f'{measure}_{t}']
                municipalities[f'cohort_coverage_{measure}_{t}_pct']=100*numerator/denominator.where(denominator>0)
        municipalities=mask_rates(municipalities,minimum,coverage)
        states=con.execute('SELECT * FROM states').df().merge(rates(con,['year','uf']),on=['year','uf'],validate='one_to_one')
        states=mask_rates(states,minimum,coverage)
        regions=rates(con,['year','region'])
        # Esta conferência descreve linhas disponíveis; não certifica completude das urnas.
        documents=con.execute('''SELECT year,uf,municipality,turn,count(*) records_checked,
            count(*) FILTER(WHERE status<>'concordante') pending_records,
            count(*) FILTER(WHERE difference<>0) different_records,
            count(*) FILTER(WHERE result_election IS NOT NULL AND bu_election IS NOT NULL AND result_election<>bu_election) election_mismatch_records,
            string_agg(DISTINCT result_generation,' | ' ORDER BY result_generation) result_generations,
            string_agg(DISTINCT bu_generation,' | ' ORDER BY bu_generation) bu_generations
            FROM read_parquet(?) GROUP BY year,uf,municipality,turn ORDER BY uf,municipality,turn''',[str(source/'conferencia_bu.parquet')]).df()
        recon=reconciliation(con)
        tables=dict(municipios=municipalities,ufs=states,regioes=regions,conferencia_bu=documents,reconciliacao=recon)
        for name,frame in tables.items():export_frame(con,frame,destination/name)
        definitions=[
            ('rate_per_1000','1.000 × seções elegíveis com reference_alert / seções elegíveis. Zero elegíveis produz ausência; não usa votos, eleitores ou área como denominador.'),
            ('eligible_coverage_pct','100 × seções elegíveis / seções observadas na unidade. Não é cobertura ponderada por eleitores.'),
            ('rate_map_value / rate_map_status',f'Exibição padrão exige ao menos {minimum} seções elegíveis e {coverage}% de cobertura elegível. Limites operacionais de leitura; não representam precisão ou teste de validade.'),
            ('reference_alert_sections','Numerador da triagem combinada original, preservada; não é contagem de irregularidades ou de viradas.'),
            ('pattern_eligible_sections','Padrões dirigidos entre elegíveis: inversões, reduções de margem de 10 pp e mudança de condição de empate; medida distinta da triagem original.'),
            ('cohort_*','Totais das mesmas seções territorialmente comparáveis, incluindo pequenas. Uma soma exige todas as parcelas; coorte vazia tem quantidade zero e medidas ausentes.'),
            ('cohort_coverage_*_pct','100 × quantidade da coorte / total territorial da mesma medida e turno; denominador zero ou ausente produz ausência. Coorte não substitui resultado completo.'),
            ('*_available_votes / *_missing_rows','Somatórios das quantidades conhecidas, com contagem de linhas ausentes por nível. Ausência por local/turno pode indicar criação ou remanejamento, não voto zero imputado.'),
            ('records_checked / pending_records','Linhas da conferência BU armazenada, não urnas ou pessoas distintas; não demonstra completude ou causa das escolhas.'),
        ]
        export_frame(con,pd.DataFrame(definitions,columns=['field','definition']),destination/'dicionario')
        result=dict(year=2026,minimum_eligible_sections=minimum,minimum_eligible_coverage_pct=coverage,
            tables={name:len(frame) for name,frame in tables.items()},regions=records(regions),
            map_status_counts=records(municipalities.groupby(['is_exterior','rate_map_status']).size().reset_index(name='municipal_units')),
            reconciliation_status=records(recon.groupby('status').size().reset_index(name='rows')),
            documental_records=int(documents.records_checked.sum()),documental_pending_records=int(documents.pending_records.sum()),
            interpretation='Taxa descritiva da triagem original em população não aleatória; não estima risco de fraude. Coortes e resultado territorial completo permanecem distintos.')
        return finish(source,destination,state,result,[Path(__file__),Path(__file__).with_name('national_common.py'),Path(__file__).with_name('investigation.py')])
    except Exception as exc:failed(destination,state,exc);raise
    finally:con.close()
