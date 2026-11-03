"""Inventário nacional simétrico, preservando os resultados dirigidos de RJ/MG."""
from pathlib import Path
import logging

import duckdb
import numpy as np
import pandas as pd

from .analysis import export_table,export_frame
from .investigation import metrics,VALUES
from .national_common import begin,finish,failed,records

LOG=logging.getLogger(__name__)
LEVELS={'secoes':['year','uf','municipality','zone','section'],
        'locais':['year','uf','municipality','zone','local'],
        'municipios':['year','uf','municipality'],'ufs':['year','uf']}
ORIGINS={'secoes':'indicadores_secoes','locais':'indicadores_local','municipios':'indicadores_municipio','ufs':'indicadores_uf'}


def margin_scores(frame):
    """Vetoriza a margem nos 30 pares já publicados; não escolhe novos vizinhos."""
    out=frame.copy().reset_index(drop=True)
    ids=out[['uf','municipality','zone','section']].astype(str).agg('/'.join,axis=1)
    if ids.duplicated().any():raise ValueError('Seção duplicada no inventário')
    eligible=out.comparable.fillna(False).astype(bool)&~out.small.fillna(True).astype(bool)
    out['eligible']=eligible
    out['margin_peer_median']=np.nan;out['margin_peer_mad']=np.nan;out['margin_robust_z']=np.nan
    out['margin_peer_status']='não elegível ou sem 30 pares'
    available=eligible & out.peer_count.eq(30)
    lookup=pd.Index(ids)
    positions=np.flatnonzero(available.to_numpy())
    values=out.margin_loss_22_pp.to_numpy(dtype=float,na_value=np.nan)
    for start in range(0,len(positions),20000):
        selected=positions[start:start+20000]
        lists=out.loc[selected,'peer_ids'].str.split('|')
        if lists.isna().any() or not lists.str.len().eq(30).all():raise ValueError('Quantidade inválida de pares')
        peers=lookup.get_indexer(lists.explode().to_numpy()).reshape(-1,30)
        if (peers<0).any():raise ValueError('Par ausente na UF de referência')
        if (np.diff(np.sort(peers,axis=1),axis=1)==0).any() or (peers==selected[:,None]).any():raise ValueError('Par duplicado ou a própria seção')
        if not eligible.to_numpy()[peers].all():raise ValueError('Par não elegível')
        if not (out.uf.to_numpy()[peers]==out.uf.to_numpy()[selected,None]).all():raise ValueError('Par de outra UF')
        changes=values[peers]
        valid=np.isfinite(changes).all(axis=1)&np.isfinite(values[selected])
        out.loc[selected[~valid],'margin_peer_status']='indicadores dos pares indisponíveis'
        selected=selected[valid];changes=changes[valid]
        median=np.median(changes,axis=1);mad=np.median(np.abs(changes-median[:,None]),axis=1)
        out.loc[selected,'margin_peer_median']=median;out.loc[selected,'margin_peer_mad']=mad
        out.loc[selected,'margin_peer_status']='dispersão insuficiente'
        informative=mad>1e-9
        out.loc[selected[informative],'margin_robust_z']=np.abs(values[selected[informative]]-median[informative])/(1.4826*mad[informative])
        out.loc[selected[informative],'margin_peer_status']='calculado com os mesmos 30 pares'
    out['margin_robust_flag']=pd.array(np.where(out.margin_robust_z.notna(),out.margin_robust_z.gt(3.5),None),dtype='boolean')
    return out


def read_level(con,source,level,uf=None):
    path=source/(ORIGINS[level]+'.parquet')
    names=con.read_parquet(str(path)).columns
    selected=list(dict.fromkeys(LEVELS[level]+['municipality_name_1','municipality_name_2','level','comparable','comparison_reason','small','is_exterior','coverage',
        'local_1','local_2','aggregation_1','aggregation_2','generation_1','generation_2','vote_generation_1','vote_generation_2',
        'n_sections_1','n_sections_2']+[f'{m}_{t}' for m in VALUES for t in (1,2)]+
        (['peer_ids','peer_count','statistical_alert','robust_max','bu_check'] if level=='secoes' else [])))
    selected=[c for c in selected if c in names]
    where=' WHERE uf=?' if uf is not None else ''
    frame=con.execute('SELECT '+','.join(selected)+' FROM read_parquet(?)'+where,[str(path)]+([uf] if uf is not None else [])).df()
    if frame[LEVELS[level]].isna().any().any() or frame.duplicated(LEVELS[level]).any():raise ValueError('Chave ausente ou duplicada: '+level)
    if set(frame.year)!={2026}:raise ValueError('Inventário específico de 2026')
    return frame


def add_patterns(frame):
    out=metrics(frame)
    out['margin_change_pp']=-out.margin_loss_22_pp
    out['absolute_margin_change_pp']=out.margin_change_pp.abs()
    out['comparison_scope']=np.where(out.comparable.fillna(False),'composição e aptos compatíveis','comparação territorial limitada')
    return out


def run_inventory(source,destination=None):
    source=Path(source).resolve();destination=Path(destination).resolve() if destination else source/'nacional/inventario'
    required=[name+'.parquet' for name in ORIGINS.values()]+['candidatos.parquet','fontes_utilizadas.json']
    source,destination,state=begin(source,destination,required)
    con=duckdb.connect(config={'threads':2,'memory_limit':'1GB'})
    con.execute('SET enable_progress_bar=false')
    try:
        finals=con.execute('SELECT DISTINCT candidate FROM read_parquet(?) WHERE turn=2 AND votes>0 AND candidate BETWEEN 1 AND 94 ORDER BY candidate',[str(source/'candidatos.parquet')]).fetchall()
        if finals!=[(13,),(22,)]:raise ValueError('Finalistas diferentes dos registros 13 e 22 revisados')
        ufs=[r[0] for r in con.execute('SELECT DISTINCT uf FROM read_parquet(?) ORDER BY uf',[str(source/'indicadores_secoes.parquet')]).fetchall()]
        for number,uf in enumerate(ufs):
            LOG.info('Inventário e margem com pares: %s (%s/%s)',uf,number+1,len(ufs))
            frame=margin_scores(add_patterns(read_level(con,source,'secoes',uf)))
            if (frame.statistical_alert.fillna(False)&~frame.eligible).any():raise ValueError('Alerta original fora do universo elegível')
            frame=frame.drop(columns='peer_ids').rename(columns={'statistical_alert':'reference_alert','robust_max':'reference_robust_max'})
            con.register('frame',frame)
            if number==0:con.execute('CREATE TABLE secoes AS SELECT * FROM frame')
            else:con.execute('INSERT INTO secoes BY NAME SELECT * FROM frame')
            con.unregister('frame')
        tables={}
        for level in LEVELS:
            if level!='secoes':
                frame=add_patterns(read_level(con,source,level))
                con.register('frame',frame)
                con.execute('CREATE TABLE '+level+' AS SELECT * FROM frame')
                con.unregister('frame')
            export_table(con,level,destination/level)
            tables[level]=con.execute('SELECT count(*) FROM '+level).fetchall()[0][0]
        rows=[]
        for level in LEVELS:
            part=con.execute('''SELECT uf,count(*) observed,count(*) FILTER(WHERE comparable) comparable,
                count(*) FILTER(WHERE selected_pattern) selected,count(*) FILTER(WHERE flip_to_13) flip_to_13,
                count(*) FILTER(WHERE flip_to_22) flip_to_22,count(*) FILTER(WHERE tie_1) tie_1,count(*) FILTER(WHERE tie_2) tie_2,
                count(*) FILTER(WHERE loss_22_5pp) loss_22_5pp,count(*) FILTER(WHERE loss_22_10pp) loss_22_10pp,count(*) FILTER(WHERE loss_22_15pp) loss_22_15pp,
                count(*) FILTER(WHERE loss_13_5pp) loss_13_5pp,count(*) FILTER(WHERE loss_13_10pp) loss_13_10pp,count(*) FILTER(WHERE loss_13_15pp) loss_13_15pp FROM '''+level+' GROUP BY uf ORDER BY uf').df()
            part['level']=level;rows.append(part)
        counts=pd.concat(rows,ignore_index=True)
        export_frame(con,counts,destination/'contagens')
        summary=dict(year=2026,ufs=ufs,tables=tables,counts=records(counts),
            margin_denominator='Flávio + Lula, em cada turno; participações sobre todos os nominais são campos distintos.',
            original_alert='reference_alert preserva a triagem combinada de referência; margin_robust_flag é outro indicador, não altera aquela triagem.',
            peers='Os mesmos 30 IDs da referência, sem selecionar pelo segundo turno; mediana e MAD da mudança de margem. MAD insuficiente ou indicador indisponível gera ausência.',
            baseline_cities_to_13={uf:int(con.execute('SELECT count(*) FROM municipios WHERE uf=? AND flip_to_13',[uf]).fetchall()[0][0]) for uf in ('RJ','MG') if uf in ufs},
            interpretation='Mudanças agregadas e triagem exploratória; não identificam escolhas individuais ou demonstram irregularidade.')
        return finish(source,destination,state,summary,[Path(__file__),Path(__file__).with_name('national_common.py'),Path(__file__).with_name('investigation.py')])
    except Exception as exc:failed(destination,state,exc);raise
    finally:con.close()
