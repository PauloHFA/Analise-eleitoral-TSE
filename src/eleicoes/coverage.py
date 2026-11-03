"""Cobertura e perfis descritivos; não supõe seleção aleatória nem imputa ausências."""
from __future__ import annotations

from datetime import datetime
import html
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd

from .analysis import export_table
from .sources import sha256, write_json

GROUPS = {"eligible":"Elegível estatística", "comparable_small":"Comparável pequena", "not_comparable":"Sem comparação territorial"}


def coverage_views(con, path, finalists):
    con.read_parquet(str(path)).create_view("input_sections")
    con.execute("""CREATE TEMP VIEW base AS SELECT *,
        CASE WHEN NOT comparable THEN 'not_comparable' WHEN small THEN 'comparable_small' ELSE 'eligible' END analysis_group,
        CASE WHEN uf='ZZ' THEN 'Exterior' ELSE 'Brasil' END region FROM input_sections""")
    con.execute("""CREATE TEMP TABLE municipalities AS SELECT uf,municipality,any_value(municipality_name_1) municipality_name,
        count(*) observed,count(*) FILTER(WHERE comparable) comparable,
        count(*) FILTER(WHERE analysis_group='eligible') eligible,
        count(*) FILTER(WHERE analysis_group='comparable_small') comparable_small,
        count(*) FILTER(WHERE analysis_group='not_comparable') not_comparable,
        100.*count(*) FILTER(WHERE comparable)/count(*) comparable_pct,
        100.*count(*) FILTER(WHERE analysis_group='eligible')/count(*) eligible_pct,
        count(aptos_1) aptos_known_1,count(attendance_1) attendance_known_1,
        sum(aptos_1) FILTER(WHERE isfinite(aptos_1) AND aptos_1>=0) aptos_available_1,
        sum(attendance_1) FILTER(WHERE isfinite(attendance_1) AND attendance_1>=0) attendance_available_1,
        100.*sum(aptos_1) FILTER(WHERE comparable AND isfinite(aptos_1) AND aptos_1>=0)/nullif(sum(aptos_1) FILTER(WHERE isfinite(aptos_1) AND aptos_1>=0),0) comparable_aptos_available_pct_1,
        100.*sum(attendance_1) FILTER(WHERE comparable AND isfinite(attendance_1) AND attendance_1>=0)/nullif(sum(attendance_1) FILTER(WHERE isfinite(attendance_1) AND attendance_1>=0),0) comparable_attendance_available_pct_1
        FROM base GROUP BY uf,municipality""")
    con.execute("""CREATE TEMP TABLE states AS SELECT uf,region,count(*) observed,
        count(*) FILTER(WHERE comparable) comparable,
        count(*) FILTER(WHERE analysis_group='eligible') eligible,
        count(*) FILTER(WHERE analysis_group='comparable_small') comparable_small,
        count(*) FILTER(WHERE analysis_group='not_comparable') not_comparable,
        100.*count(*) FILTER(WHERE comparable)/count(*) comparable_pct,
        100.*count(*) FILTER(WHERE analysis_group='eligible')/count(*) eligible_pct
        FROM base GROUP BY uf,region""")
    measures = [("aptos_1","Eleitorado apto","eleitores",False),
        ("attendance_1","Comparecimento","comparecentes",False),
        ("100*turnout_1","Taxa de comparecimento","%",True),
        ("100*blank_share_1","Brancos/comparecentes","%",True),
        ("100*null_share_1","Nulos/comparecentes","%",True)]
    measures += [(f"100*share_{c}_1",f"Participação do candidato {c}","%",True) for c in finalists]
    values = ",".join(f"('{name}',({expr})::DOUBLE,'{unit}',{'true' if rate else 'false'})" for expr,name,unit,rate in measures)
    con.execute(f"""CREATE TEMP VIEW long_measures AS SELECT uf,region,analysis_group,metric,raw_value,unit,
        CASE WHEN raw_value IS NULL THEN 'missing' WHEN NOT isfinite(raw_value) THEN 'nonfinite'
        WHEN raw_value<0 OR (is_rate AND raw_value>100) THEN 'out_of_range' ELSE 'usable' END quality
        FROM base,LATERAL (VALUES {values}) m(metric,raw_value,unit,is_rate)""")
    con.execute("""CREATE TEMP VIEW scoped AS SELECT 'uf' level,uf scope,analysis_group,metric,raw_value,unit,quality FROM long_measures
        UNION ALL SELECT 'region',region,analysis_group,metric,raw_value,unit,quality FROM long_measures""")
    con.execute("""CREATE TEMP TABLE profile_values AS SELECT level,scope,analysis_group,metric,unit,count(*) units,
        count(*) FILTER(WHERE quality='usable') used,count(*) FILTER(WHERE quality='missing') missing,
        count(*) FILTER(WHERE quality='nonfinite') nonfinite,count(*) FILTER(WHERE quality='out_of_range') out_of_range,
        quantile_cont(CASE WHEN quality='usable' THEN raw_value END,[.25,.5,.75]) quantiles
        FROM scoped GROUP BY level,scope,analysis_group,metric,unit""")
    # Uma combinação sem unidades tem contagens zero e quartis ausentes, sem mediana zero artificial.
    con.execute("""CREATE TEMP TABLE profiles AS WITH dims AS (SELECT DISTINCT level,scope FROM scoped),
        metrics AS (SELECT DISTINCT metric,unit FROM scoped),
        group_types AS (SELECT * FROM (VALUES ('eligible'),('comparable_small'),('not_comparable')) g(analysis_group))
        SELECT d.level,d.scope,g.analysis_group,m.metric,m.unit,
        coalesce(v.units,0) units,coalesce(v.used,0) used,coalesce(v.missing,0) missing,
        coalesce(v.nonfinite,0) nonfinite,coalesce(v.out_of_range,0) out_of_range,
        v.quantiles[1] q25,v.quantiles[2] median,v.quantiles[3] q75
        FROM dims d CROSS JOIN metrics m CROSS JOIN group_types g
        LEFT JOIN profile_values v USING(level,scope,analysis_group,metric,unit)""")
    con.execute("""CREATE TEMP TABLE differences AS SELECT a.level,a.scope,b.analysis_group comparison_group,a.metric,
        CASE WHEN a.unit='%' THEN 'pp' ELSE a.unit END difference_unit,
        a.used eligible_used,b.used comparison_used,a.median eligible_median,b.median comparison_median,
        b.median-a.median median_difference
        FROM profiles a JOIN profiles b USING(level,scope,metric,unit)
        WHERE a.analysis_group='eligible' AND b.analysis_group<>'eligible'""")
    con.execute("""CREATE TEMP TABLE geography AS SELECT uf,region,analysis_group,count(*) units,
        100.*count(*)/sum(count(*)) OVER(PARTITION BY region,analysis_group) group_share_in_region_pct
        FROM base GROUP BY uf,region,analysis_group""")


def run_coverage(source, destination=None, thresholds=(50,80,95)):
    source = Path(source).resolve()
    destination = Path(destination).resolve() if destination else source/"cobertura"
    if destination == source or source.is_relative_to(destination):
        raise ValueError("A saída deve ser uma pasta separada da referência")
    if not thresholds or len(set(thresholds)) != len(thresholds) or any(not 0<t<=100 for t in thresholds):
        raise ValueError("Os limiares devem ser distintos, entre 0 e 100")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("A saída já contém arquivos; escolha uma nova pasta")
    destination.mkdir(parents=True,exist_ok=True)
    hashes = {name:sha256(source/name) for name in ("indicadores_secoes.parquet","candidatos.parquet","sintese_analise.json","relatorio.pdf") if (source/name).exists()}
    state = dict(status="em execução",started=datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),input_hashes=hashes,thresholds=list(thresholds))
    write_json(destination/"estado_execucao.json",state)
    con = duckdb.connect(config={"threads":2,"memory_limit":"1GB"})
    con.execute("SET enable_progress_bar=false")
    try:
        finalists = [int(r[0]) for r in con.execute("SELECT DISTINCT candidate FROM read_parquet(?) WHERE turn=2 AND candidate BETWEEN 1 AND 94 ORDER BY candidate",[str(source/"candidatos.parquet")]).fetchall()]
        coverage_views(con,source/"indicadores_secoes.parquet",finalists)
        grouping = con.execute("SELECT region,analysis_group,count(*) units FROM base GROUP BY region,analysis_group ORDER BY region,analysis_group").df().to_dict("records")
        total,comparable,eligible,small,excluded = con.execute("""SELECT count(*),count(*) FILTER(WHERE comparable),
            count(*) FILTER(WHERE analysis_group='eligible'),count(*) FILTER(WHERE analysis_group='comparable_small'),
            count(*) FILTER(WHERE analysis_group='not_comparable') FROM base""").fetchall()[0]
        if total != eligible+small+excluded or comparable != eligible+small:
            raise ValueError("Os grupos não fecham com o universo original")
        bands=[]
        for threshold in sorted(thresholds):
            for region, predicate in (("Brasil","uf<>'ZZ'"),("Exterior","uf='ZZ'")):
                units,below_comp,below_eligible = con.execute(f"SELECT count(*),count(*) FILTER(WHERE comparable_pct<?),count(*) FILTER(WHERE eligible_pct<?) FROM municipalities WHERE {predicate}",[threshold,threshold]).fetchall()[0]
                bands.append(dict(region=region,threshold_pct=threshold,municipal_units=units,below_comparable=below_comp,below_eligible=below_eligible))
        band_frame = pd.DataFrame(bands)
        con.register("bands",band_frame)
        tables = {"municipios":"municipalities","resumo_uf":"states","perfis":"profiles","diferencas":"differences","distribuicao_geografica":"geography","faixas":"bands",
                  "unidades":"(SELECT year,uf,municipality,zone,section,analysis_group,comparison_reason,comparable,small FROM base)"}
        for name,table in tables.items():
            export_table(con,table,destination/name)
        original_summary = source/"sintese_analise.json"
        if original_summary.exists():
            saved = {m["id"]:m["value"] for m in json.loads(original_summary.read_text(encoding="utf-8"))["metrics"]}
            for key,actual in (("observed",total),("comparable",comparable),("eligible",eligible),("comparable_small",small),("excluded",excluded)):
                if actual != saved[key]:
                    raise ValueError(f"A contagem difere da síntese: {key}")
        profiles = con.execute("SELECT * FROM profiles WHERE level='region' ORDER BY scope,metric,analysis_group").df()
        differences = con.execute("SELECT * FROM differences WHERE level='region' ORDER BY scope,metric,comparison_group").df()
        # JSON padrão: ausências nos perfis não se tornam NaN nem zero.
        def records(frame):
            return json.loads(frame.to_json(orient="records",force_ascii=False))
        result = dict(status="concluído",generated=datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
            observed_units=total,comparable_units=comparable,eligible_units=eligible,comparable_small_units=small,excluded_units=excluded,
            groups=grouping,thresholds=bands,regional_profiles=records(profiles),regional_differences=records(differences),input_hashes=hashes,
            code_sha256=sha256(Path(__file__)),groups_mutually_exclusive=True,
            interpretation="Diferenças descritivas entre grupos no primeiro turno; não demonstram viés causal ou representatividade de uma seleção não aleatória.",
            coverage_denominators="Cobertura principal = unidades do grupo/unidades observadas no município. Coberturas ponderadas usam somente somas disponíveis no inventário de seções, não substituem a totalização oficial; quantidades conhecidas acompanham os resultados.",
            missing_policy="Ausentes, não finitos e fora do intervalo são contados separadamente. Quartis utilizam somente medidas utilizáveis; grupo sem dados não recebe mediana zero.")
        definitions = [
            ("analysis_group","eligible: comparável e não pequena; comparable_small: comparável pequena; not_comparable: sem comparação territorial."),
            ("comparable_pct / eligible_pct","100 × quantidade de unidades do grupo / quantidade observada na unidade municipal."),
            ("units / used / missing / nonfinite / out_of_range","Universo do grupo e cobertura da medida; categorias de qualidade mutuamente exclusivas."),
            ("q25 / median / q75","Quartis das medidas utilizáveis do primeiro turno; taxas em %, quantidades em eleitores/comparecentes."),
            ("median_difference","Mediana do grupo de comparação menos mediana dos elegíveis no primeiro turno; taxas em pp. Não é mudança entre turnos."),
            ("group_share_in_region_pct","Participação da UF no total de unidades desse grupo, no Brasil ou no exterior."),
            ("aptos_known_1 / attendance_known_1","Número de unidades com medida conhecida; zero publicado é conhecido, ausência não é zero."),
            ("comparable_*_available_pct_1","Cobertura das somas disponíveis do inventário no primeiro turno; não é certificação de total oficial reconciliado."),
        ]
        pd.DataFrame(definitions,columns=["campo","definicao"]).to_csv(destination/"dicionario.csv",index=False,encoding="utf-8")
        for name,digest in hashes.items():
            if sha256(source/name) != digest:
                raise ValueError(f"Fonte alterada: {name}")
        write_json(destination/"resumo.json",result)
        _report(destination,result)
        write_json(destination/"estado_execucao.json",dict(state,status="concluído"))
        return result
    except Exception as exc:
        write_json(destination/"estado_execucao.json",dict(state,status="incompleto",error=f"{type(exc).__name__}: {exc}"))
        raise
    finally:
        con.close()


def _report(destination,result):
    labels = {"region":"Universo","analysis_group":"Grupo","units":"Unidades","threshold_pct":"Limite de cobertura (%)",
        "municipal_units":"Unidades municipais","below_comparable":"Abaixo: comparáveis","below_eligible":"Abaixo: elegíveis",
        "scope":"Universo","metric":"Medida","unit":"Unidade","used":"Utilizáveis","missing":"Ausentes",
        "nonfinite":"Não finitas","out_of_range":"Fora do intervalo","q25":"1º quartil","median":"Mediana","q75":"3º quartil",
        "comparison_group":"Grupo de comparação","difference_unit":"Unidade da diferença","eligible_used":"Elegíveis com medida",
        "comparison_used":"Grupo com medida","eligible_median":"Mediana elegíveis","comparison_median":"Mediana grupo","median_difference":"Diferença entre medianas"}
    def table(rows):
        frame = pd.DataFrame(rows).drop(columns=["level"],errors="ignore").replace({"analysis_group":GROUPS,"comparison_group":GROUPS})
        return frame.rename(columns=labels).to_html(index=False,escape=True,na_rep="não disponível",float_format=lambda v:f"{v:.2f}".replace(".",","))
    body = f"""<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>Cobertura e exclusões</title>
    <style>body{{font:16px/1.6 system-ui;max-width:1200px;margin:40px auto;padding:20px;color:#183447}}table{{border-collapse:collapse;width:100%;font-size:12px}}td,th{{padding:8px;border-bottom:1px solid #cbd9df;text-align:left}}section{{margin:30px 0;overflow:auto}}.note{{padding:18px;background:#edf4f7}}</style>
    <h1>Cobertura e perfil das unidades excluídas</h1><p class='note'>{html.escape(result['interpretation'])}</p>
    <p>Observadas: {result['observed_units']:,}; comparáveis: {result['comparable_units']:,}; elegíveis: {result['eligible_units']:,}; comparáveis pequenas: {result['comparable_small_units']:,}; sem comparação: {result['excluded_units']:,}.</p>
    <section><h2>Grupos que fecham o universo</h2>{table(result['groups'])}<p>Os três grupos são mutuamente exclusivos. Comparáveis = elegíveis + comparáveis pequenas.</p></section>
    <section><h2>Onde a cobertura é menor?</h2>{table(result['thresholds'])}<p>Os limites são descritivos, não cortes automáticos de validade. Brasil e exterior são contados separadamente. As unidades do exterior são localidades de votação na classificação do TSE.</p><p>{html.escape(result['coverage_denominators'])}</p></section>
    <section><h2>Perfis do primeiro turno</h2>{table(result['regional_profiles'])}<p>{html.escape(result['missing_policy'])}</p></section>
    <section><h2>Diferenças entre grupos</h2>{table(result['regional_differences'])}<p>Diferenças de taxas são pontos percentuais entre medianas dos grupos no primeiro turno; não representam variação entre turnos. Composição territorial e características observadas podem explicar parte das diferenças. A análise não produz margem de erro de amostragem aleatória.</p></section>
    <section><h2>Dados completos e reprodução</h2><ul>{''.join(f"<li><a href='{name}.csv'>{name}.csv</a> / <a href='{name}.parquet'>Parquet</a></li>" for name in ('municipios','resumo_uf','perfis','diferencas','distribuicao_geografica','faixas','unidades'))}<li><a href='dicionario.csv'>Dicionário</a></li><li><a href='resumo.json'>Resumo, método e hashes</a></li></ul></section></html>"""
    (destination/"relatorio.html").write_text(body,encoding="utf-8")
