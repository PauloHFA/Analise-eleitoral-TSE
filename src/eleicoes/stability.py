"""Sensibilidade aninhada dos pares; preserva a referência publicada de 30."""
from __future__ import annotations

import html
from datetime import datetime
from importlib.metadata import version
import itertools
import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import numpy as np
import pandas as pd

from .analysis import GEO, export_table, peers
from .sources import sha256, write_json

LOG = logging.getLogger(__name__)
BASE_K = 30


def metric_names(finalists):
    return ["delta_turnout_pp", "delta_blank_pp", "delta_null_pp"] + [f"delta_share_{c}_pp" for c in finalists]


def nested_neighbors(frame, finalists, candidates, sizes):
    """A âncora mantém os desempates publicados; a extensão prioriza município/UF."""
    if frame.uf.nunique() != 1:
        raise ValueError("Calcule os pares separadamente por UF")
    keys = frame[GEO].astype(str).agg("/".join, axis=1).to_numpy()
    if len(set(keys)) != len(keys):
        raise ValueError("Chaves geográficas repetidas na referência")
    lookup = {key: i for i,key in enumerate(keys)}
    anchor = np.empty((len(frame), BASE_K), dtype=np.int32)
    municipalities = frame.municipality.astype(str).to_numpy()
    counts = frame.municipality.astype(str).value_counts()
    for i, row in enumerate(frame.itertuples()):
        ids = str(row.peer_ids).split("|")
        if row.peer_count != BASE_K or len(ids) != BASE_K or len(set(ids)) != BASE_K or keys[i] in ids:
            raise ValueError(f"Referência de 30 pares inválida: {keys[i]}")
        if any(key not in lookup for key in ids):
            raise ValueError(f"Par fora da UF ou do universo elegível: {keys[i]}")
        anchor[i] = [lookup[key] for key in ids]
        expected_local = min(BASE_K, int(counts[municipalities[i]])-1)
        actual_local = int((municipalities[anchor[i]] == municipalities[i]).sum())
        if actual_local != expected_local:
            raise ValueError(f"Referência não preserva a prioridade municipal: {keys[i]}")
    result = {k:anchor[:,:k].copy() for k in sizes if k <= BASE_K}
    for k in sizes:
        if k <= BASE_K:
            continue
        if len(frame) < k+1:
            result[k] = None
            continue
        extension = peers(frame, finalists, candidates, k=k)
        selected = np.empty((len(frame), k),dtype=np.int32)
        for i, ids in enumerate(extension.peer_ids):
            old = anchor[i].tolist()
            present = set(old)
            extras = [lookup[key] for key in ids.split("|") if lookup[key] not in present]
            chosen = old + extras[:k-BASE_K]
            if len(chosen) != k or len(set(chosen)) != k:
                raise ValueError(f"Não foi possível estender os pares: {keys[i]}")
            selected[i] = chosen
        result[k] = selected
    return result, keys


def score_variant(frame, neighbors, keys, finalists, k):
    metrics = metric_names(finalists)
    size = len(frame)
    available = neighbors is not None
    result = frame[["year",*GEO,"municipality_name_1","flag_10pp","max_change_pp","any_zero"]].copy()
    result = result.rename(columns={"flag_10pp":"absolute_flag"})
    result["k"] = k
    result["available"] = available
    result["peer_count"] = k if available else 0
    result["peer_ids"] = ["|".join(keys[r]) for r in neighbors] if available else ""
    result["status"] = "calculado" if available else "pares insuficientes na UF"
    result["peer_scope"] = ""
    if available:
        municipality = frame.municipality.astype(str).to_numpy()
        result["peer_scope"] = np.where((municipality[neighbors] == municipality[:,None]).all(axis=1), "município", "município + UF")
    z_values = np.full((size,len(metrics)),np.nan)
    medians, mads = {}, {}
    for j,metric in enumerate(metrics):
        median = np.full(size,np.nan)
        mad = np.full(size,np.nan)
        if available:
            values = frame[metric].to_numpy(float)
            peer_values = values[neighbors]
            median = np.median(peer_values,axis=1)
            mad = np.median(np.abs(peer_values-median[:,None]),axis=1)
            z_values[:,j] = np.divide(np.abs(values-median),1.4826*mad,out=np.full(size,np.nan),where=mad>1e-9)
        medians[metric],mads[metric] = median,mad
        result["median_"+metric] = median
        result["mad_"+metric] = mad
        result["z_"+metric] = z_values[:,j]
    scores = np.fmax.reduce(z_values,axis=1)
    result["robust_max"] = scores
    result["robust_flag"] = pd.array(scores>3.5,dtype="boolean") if available else pd.array([pd.NA]*size,dtype="boolean")
    result["statistical_alert"] = (result.absolute_flag | result.robust_flag) if available else pd.array([pd.NA]*size,dtype="boolean")
    informative = np.isfinite(scores)
    driver = np.argmax(np.where(np.isfinite(z_values),z_values,-np.inf),axis=1)
    result["driver_metric"] = pd.Series([metrics[j] if ok else None for j,ok in zip(driver,informative)],index=result.index,dtype="string")
    for column in ("driver_change_pp","driver_median_pp","driver_mad_pp","numerator_1","numerator_2","denominator_1","denominator_2","one_unit_pp_1","one_unit_pp_2"):
        result[column] = np.nan
    numerator_keys = {"delta_turnout_pp":("attendance","aptos"),"delta_blank_pp":("blank","attendance"),"delta_null_pp":("null_votes","attendance")}
    numerator_keys.update({f"delta_share_{c}_pp":(f"votes_{c}","valid") for c in finalists})
    for j,metric in enumerate(metrics):
        mask = informative & (driver==j)
        result.loc[mask,"driver_change_pp"] = frame.loc[mask,metric]
        result.loc[mask,"driver_median_pp"] = medians[metric][mask]
        result.loc[mask,"driver_mad_pp"] = mads[metric][mask]
        num,den = numerator_keys[metric]
        for turn in (1,2):
            result.loc[mask,f"numerator_{turn}"] = frame.loc[mask,f"{num}_{turn}"]
            result.loc[mask,f"denominator_{turn}"] = frame.loc[mask,f"{den}_{turn}"]
            result.loc[mask,f"one_unit_pp_{turn}"] = 100/frame.loc[mask,f"{den}_{turn}"]
    diagnostic = result.driver_mad_pp < result[["one_unit_pp_1","one_unit_pp_2"]].max(axis=1)
    result["mad_below_one_unit"] = pd.array(diagnostic.where(informative),dtype="boolean")
    result["uninformative_metrics"] = (~np.isfinite(z_values)).sum(axis=1)
    if available:
        result.loc[~informative,"status"] = "MAD insuficiente em todos os indicadores"
    return result


def top_overlap(left, right, requested):
    left,right = set(left),set(right)
    intersection,union = len(left & right),len(left | right)
    return {"requested":requested,"left_size":len(left),"right_size":len(right),
            "intersection":intersection,"union":union,"jaccard":intersection/union if union else None,
            "retention_left":intersection/len(left) if left else None}


def run_stability(source, destination=None, sizes=(15,30,50)):
    source = Path(source).resolve()
    destination = Path(destination).resolve() if destination else source / "estabilidade"
    if destination == source or source.is_relative_to(destination):
        raise ValueError("A saída deve ser uma pasta separada da referência")
    sizes = list(sizes)
    if BASE_K not in sizes or len(set(sizes)) != len(sizes) or any(isinstance(k,bool) or not isinstance(k,int) or k<1 for k in sizes):
        raise ValueError("Informe quantidades inteiras positivas distintas, incluindo 30")
    sizes.sort()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("A saída já contém arquivos; escolha uma nova pasta para preservar a execução")
    destination.mkdir(parents=True,exist_ok=True)
    input_names = ["indicadores_secoes.parquet","candidatos.parquet","sintese_analise.json","relatorio.pdf"]
    hashes = {name:sha256(source/name) for name in input_names if (source/name).exists()}
    state = dict(status="em execução",started=datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),source=str(source),sizes=sizes,input_hashes=hashes)
    write_json(destination/"estado_execucao.json",state)
    con = duckdb.connect(str(destination/"trabalho.duckdb"),config={"threads":2,"memory_limit":"1GB"})
    con.execute("SET enable_progress_bar=false")
    try:
        path = str(source/"indicadores_secoes.parquet")
        candidates = [r[0] for r in con.execute("SELECT DISTINCT candidate FROM read_parquet(?) WHERE turn=1 AND candidate BETWEEN 1 AND 94 ORDER BY candidate",[str(source/"candidatos.parquet")]).fetchall()]
        finalists = [r[0] for r in con.execute("SELECT DISTINCT candidate FROM read_parquet(?) WHERE turn=2 AND candidate BETWEEN 1 AND 94 ORDER BY candidate",[str(source/"candidatos.parquet")]).fetchall()]
        metrics = metric_names(finalists)
        columns = list(dict.fromkeys(["year",*GEO,"municipality_name_1","comparable","small","aptos_1","aptos_2","attendance_1","attendance_2","valid_1","valid_2","blank_1","blank_2","null_votes_1","null_votes_2","turnout_1","peer_ids","peer_count","robust_max","robust_flag","statistical_alert","priority","flag_10pp","max_change_pp","any_zero",*metrics,*[f"votes_{c}_1" for c in candidates],*[f"votes_{c}_2" for c in finalists]]))
        ufs = [r[0] for r in con.execute("SELECT DISTINCT uf FROM read_parquet(?) WHERE comparable AND NOT small ORDER BY uf",[path]).fetchall()]
        universe = con.execute("SELECT count(*) FROM read_parquet(?) WHERE comparable AND NOT small",[path]).fetchone()[0]
        first,checks = True,[]
        for uf in ufs:
            frame = con.execute(f"SELECT {','.join(columns)} FROM read_parquet(?) WHERE comparable AND NOT small AND uf=? ORDER BY uf,municipality,zone,section",[path,uf]).df().reset_index(drop=True)
            LOG.info("Estabilidade %s: %s seções",uf,len(frame))
            neighbors,keys = nested_neighbors(frame,finalists,candidates,sizes)
            for k in sizes:
                result = score_variant(frame,neighbors[k],keys,finalists,k)
                if k == BASE_K:
                    observed = result.robust_max.to_numpy(float)
                    baseline = frame.robust_max.to_numpy(float)
                    if not np.allclose(observed,baseline,atol=1e-9,rtol=1e-12,equal_nan=True) or not result.statistical_alert.to_numpy(bool).tolist() == frame.statistical_alert.to_numpy(bool).tolist():
                        raise ValueError(f"A referência de 30 pares não foi reproduzida: {uf}")
                    checks.append(dict(uf=uf,sections=len(frame),baseline_reproduced=True))
                con.register("variant_frame",result)
                if first:
                    con.execute("CREATE TABLE variants AS SELECT * FROM variant_frame")
                    first=False
                else:
                    con.execute("INSERT INTO variants BY NAME SELECT * FROM variant_frame")
                con.unregister("variant_frame")
            write_json(destination/"estado_execucao.json",dict(state,completed_ufs=[r["uf"] for r in checks]))
        geo = ",".join(GEO)
        con.execute(f"CREATE TABLE common_units AS SELECT {geo} FROM variants GROUP BY {geo} HAVING count(*) FILTER(WHERE available)={len(sizes)}")
        con.execute(f"""CREATE TABLE rankings AS SELECT k,{geo},robust_max,max_change_pp,driver_metric,driver_mad_pp,
            mad_below_one_unit,row_number() OVER(PARTITION BY k ORDER BY robust_max DESC NULLS LAST,max_change_pp DESC,{geo}) rank_common
            FROM variants JOIN common_units USING({geo}) WHERE statistical_alert""")
        con.execute(f"CREATE VIEW details AS SELECT v.*,c.uf IS NOT NULL common_universe,r.rank_common FROM variants v LEFT JOIN common_units c USING({geo}) LEFT JOIN rankings r USING(k,{geo})")
        pivots = ",".join(f"max(CASE WHEN k={k} THEN {column} END) {column}_{k}" for k in sizes for column in ("robust_max","statistical_alert","rank_common","mad_below_one_unit"))
        con.execute(f"""CREATE TABLE comparison AS SELECT {geo},any_value(municipality_name_1) municipality_name,
            bool_and(available) all_available,sum(available::INT)::BIGINT available_configurations,
            CASE WHEN bool_and(available) THEN sum(statistical_alert::INT)::BIGINT END alert_configurations,
            CASE WHEN bool_and(available) THEN sum(coalesce(rank_common<=100,false)::INT)::BIGINT END top100_configurations,
            CASE WHEN count(rank_common)={len(sizes)} THEN max(rank_common)-min(rank_common) END rank_span,
            {pivots} FROM details GROUP BY {geo}""")
        export_table(con,"details",destination/"variantes")
        export_table(con,"rankings",destination/"rankings")
        export_table(con,"comparison",destination/"comparacao")
        export_table(con,"(SELECT * FROM rankings WHERE rank_common<=100 ORDER BY k,rank_common)",destination/"top100")
        fields = [r[0] for r in con.execute("DESCRIBE details").fetchall()]
        definitions = {"k":"Quantidade de pares desta configuração.","available":"Há pares suficientes para esta configuração na UF.",
            "peer_ids":"Lista dos pares auditáveis; 15 é prefixo de 30, e 50 preserva os 30 publicados.",
            "robust_max":"Máximo escore informativo entre os indicadores; ausente com MAD insuficiente.",
            "robust_flag":"Escore >3,5; ausente quando faltam pares, falso para MAD inconclusivo sem escore.",
            "statistical_alert":"União do critério absoluto e robusto, somente na configuração disponível.",
            "absolute_flag":"Critério de 10 pp ou passagem a zero, preservado da referência.",
            "common_universe":"Pares suficientes em todas as configurações solicitadas.",
            "rank_common":"Prioridade entre alertas somente no universo comum; ausente fora dele ou sem alerta.",
            "mad_below_one_unit":"MAD do indicador de maior afastamento abaixo de max(100/denominador_1,100/denominador_2); diagnóstico de escala, sem novo alerta.",
            "driver_metric":"Indicador com maior escore robusto disponível; não é causa política da mudança.",
            "uninformative_metrics":"Quantidade de indicadores sem escore informativo nesta configuração."}
        pd.DataFrame([dict(campo=f,definicao=definitions.get(f,"Identificação territorial ou medida por configuração; sufixos _1/_2 indicam turno. Mudanças, medianas e MAD em pp; numeradores e denominadores são quantidades publicadas.")) for f in fields]).to_csv(destination/"dicionario.csv",index=False,encoding="utf-8")
        configuration = con.execute("""SELECT k,count(*) units,count(*) FILTER(WHERE available) available,
            count(*) FILTER(WHERE statistical_alert) alerts,count(*) FILTER(WHERE common_universe) common_units,
            count(*) FILTER(WHERE common_universe AND statistical_alert) common_alerts,
            count(*) FILTER(WHERE statistical_alert AND mad_below_one_unit) alert_small_mad
            FROM details GROUP BY k ORDER BY k""").df().to_dict("records")
        regional = con.execute("""SELECT k,uf='ZZ' is_exterior,count(*) units,
            count(*) FILTER(WHERE available) available,count(*) FILTER(WHERE common_universe) common_units,
            count(*) FILTER(WHERE common_universe AND statistical_alert) common_alerts
            FROM details GROUP BY k,is_exterior ORDER BY k,is_exterior""").df().to_dict("records")
        overlaps=[]
        for left,right in itertools.combinations(sizes,2):
            for top in (25,50,100):
                def members(k):
                    return [tuple(r) for r in con.execute(f"SELECT {geo} FROM rankings WHERE k=? AND rank_common<=?",[k,top]).fetchall()]
                overlaps.append(dict(left=left,right=right,**top_overlap(members(left),members(right),top)))
        transition = con.execute("SELECT alert_configurations,count(*) units FROM comparison WHERE all_available GROUP BY alert_configurations ORDER BY alert_configurations").df().to_dict("records")
        common = con.execute("SELECT count(*) FROM common_units").fetchone()[0]
        result = dict(status="concluído",generated=datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),sizes=sizes,eligible_units=universe,common_units=common,
            configurations=configuration,regional=regional,overlaps=overlaps,triage_stability=transition,baseline_checks=checks,
            method="Pares aninhados: prefixo dos 30 publicados e extensão por vizinhos do primeiro turno, com prioridade municipal e complemento na UF.",
            ties="A ordem publicada ancora os desempates; a extensão usa entrada em ordem geográfica e as versões registradas do algoritmo/bibliotecas.",
            mad_diagnostic="MAD comparado a max(100/denominador_1,100/denominador_2): escala de uma unidade no numerador com denominadores fixos; não é teste probabilístico nem novo critério de alerta.",
            input_hashes=hashes,code_hashes={p.name:sha256(p) for p in (Path(__file__),Path(__file__).with_name("analysis.py"))},
            dependencies={name:version(name) for name in ("numpy","pandas","scipy","duckdb")})
        for name,digest in hashes.items():
            if sha256(source/name) != digest:
                raise ValueError(f"Fonte alterada durante a execução: {name}")
        write_json(destination/"resumo.json",result)
        _report(destination,result)
        write_json(destination/"estado_execucao.json",dict(state,status="concluído"))
        return result
    except Exception as exc:
        write_json(destination/"estado_execucao.json",dict(state,status="incompleto",error=f"{type(exc).__name__}: {exc}"))
        raise
    finally:
        con.close()


def _report(destination, result):
    labels = {"k":"Pares","units":"Elegíveis","available":"Pares suficientes","alerts":"Na triagem",
        "common_units":"Universo comum","common_alerts":"Triagem no universo comum","alert_small_mad":"Alertas com MAD abaixo de uma unidade",
        "left":"Pares A","right":"Pares B","requested":"Primeiros solicitados","left_size":"Tamanho da lista A","right_size":"Tamanho da lista B",
        "intersection":"Interseção","union":"União","jaccard":"Jaccard (0–1)","retention_left":"Retenção de A (0–1)",
        "alert_configurations":"Configurações que selecionam","is_exterior":"Exterior (ZZ)"}
    def table(rows):
        def fmt(value):
            if isinstance(value,bool):
                return "sim" if value else "não"
            if isinstance(value,(int,float)) and pd.notna(value):
                return f"{value:,.0f}".replace(",", ".") if float(value).is_integer() else f"{value:.4f}".replace(".",",")
            return "não disponível" if value is None else value
        return pd.DataFrame(rows).map(fmt).rename(columns=labels).to_html(index=False,escape=True,na_rep="não disponível")
    text = f"""<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>Estabilidade dos pares</title>
    <style>body{{font:16px/1.6 system-ui;max-width:1150px;margin:40px auto;padding:20px;color:#183447}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:9px;border-bottom:1px solid #ccd9df;text-align:left}}section{{margin:32px 0}}.note{{background:#edf4f7;padding:18px}}</style>
    <h1>Estabilidade dos pares e das prioridades</h1>
    <p class='note'>Estudo de sensibilidade, sem alteração da referência publicada. Estabilidade de um alerta não demonstra irregularidade; instabilidade identifica dependência da configuração.</p>
    <p>Universo elegível: {result['eligible_units']:,}. Universo comum às configurações: {result['common_units']:,}. Os demais casos permanecem nas tabelas, sem receber posição comparável quando faltam pares.</p>
    <section><h2>Como a comparação foi feita</h2><p>{html.escape(result['method'])}</p><p>{html.escape(result['ties'])}</p><p>A variante de 30 reproduziu os escores e a seleção publicados em todas as UFs conferidas. Os rankings abaixo usam o mesmo universo comum.</p></section>
    <section><h2>Configurações</h2>{table(result['configurations'])}<p>O universo comum exige pares suficientes em todas as configurações. MAD abaixo da escala de uma unidade é um diagnóstico do indicador de maior afastamento, não um novo critério de seleção.</p><h3>Brasil e exterior</h3>{table(result['regional'])}</section>
    <section><h2>Quanto os primeiros casos se repetem?</h2>{table(result['overlaps'])}<p>Interseção conta casos presentes nas duas listas. Jaccard é interseção/união; retenção usa o tamanho efetivo da lista da esquerda. Se não há casos, o indicador fica ausente, não 100%.</p></section>
    <section><h2>Seleção nas configurações</h2>{table(result['triage_stability'])}<p>Somente universo comum; zero configurações significa sem triagem nesses parâmetros, não ausência comprovada de irregularidades.</p></section>
    <section><h2>Diagnóstico de dispersão</h2><p>{html.escape(result['mad_diagnostic'])}</p><p>As tabelas mostram mudança em pp, numeradores e denominadores de cada turno, MAD e mediana. As quantidades não representam transferências individuais de voto.</p></section>
    <section><h2>Tabelas e reprodução</h2><ul>{''.join(f"<li><a href='{n}.csv'>{n}.csv</a> / <a href='{n}.parquet'>Parquet</a></li>" for n in ('variantes','rankings','comparacao','top100'))}<li><a href='resumo.json'>Resumo, método, versões e hashes</a></li></ul></section></html>"""
    (destination/"relatorio.html").write_text(text,encoding="utf-8")
