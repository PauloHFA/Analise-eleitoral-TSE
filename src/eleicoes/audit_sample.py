"""Amostra dirigida registrada antes da obtenção dos documentos das urnas."""
from pathlib import Path
import numpy as np
import pandas as pd
import duckdb

from .analysis import export_frame
from .national_common import begin,finish,failed,records
from .sources import write_json

GEO=['year','uf','municipality','zone','section']
REGIONS={**dict.fromkeys(['AC','AM','AP','PA','RO','RR','TO'],'Norte'),
    **dict.fromkeys(['AL','BA','CE','MA','PB','PE','PI','RN','SE'],'Nordeste'),
    **dict.fromkeys(['DF','GO','MS','MT'],'Centro-Oeste'),**dict.fromkeys(['ES','MG','RJ','SP'],'Sudeste'),
    **dict.fromkeys(['PR','RS','SC'],'Sul'),'ZZ':'Exterior'}
PROTOCOL=dict(version=1,priority_per_region=2,regions=['Norte','Nordeste','Centro-Oeste','Sudeste','Sul','Exterior'],
    selection='Dirigida, determinística, sem probabilidade de inclusão estimada. Não permite estimar frequência populacional de irregularidade.',
    priority='Elegível, padrão nacional selecionado, alerta original e alerta em todas as configurações disponíveis, com pelo menos duas. Priorizar ausência de aviso de MAD abaixo de uma unidade, menor escore robusto entre configurações, mudança absoluta e chave geográfica.',
    allocation='Uma mudança de margem positiva e uma negativa por região, preferindo UFs distintas quando possível. Falta de sentido ou estrato é registrada; não é preenchida após consultar documentos.',
    control='Sem alerta original, sem alerta nas configurações disponíveis e sem padrão nacional selecionado. Mesma UF; priorizar mesmo município; não reutilizar controle.',
    matching='Distância euclidiana usando ln(1+aptos), comparecimento/aptos e participações dos dois finalistas nos nominais do primeiro turno, centrados pela mediana e escalados pelo desvio padrão da UF (ddof=0). Nenhuma característica do segundo turno no pareamento.',
    exterior='Pode ter apenas duas configurações disponíveis; essa limitação é explícita e não é chamada de estabilidade 3/3.',
    documents='Dois turnos por seção; RDV, BU binário, assinatura, imagem do BU e log quando disponíveis. Correspondência de arquivos não é fonte independente do equipamento.')


def choose(frame):
    f=frame.sort_values(GEO,kind='stable').reset_index(drop=True).copy()
    if f.duplicated(GEO).any():raise ValueError('Chave repetida na população da amostra')
    f['region']=f.uf.map(REGIONS)
    if f.region.isna().any():raise ValueError('UF sem estrato definido')
    f['case_key']=f[GEO].astype(str).agg('/'.join,axis=1)
    zcols=['robust_max_15','robust_max_30','robust_max_50']
    f['minimum_robust']=f[zcols].min(axis=1,skipna=True)
    f['mad_warning']=f[['mad_below_one_unit_15','mad_below_one_unit_30','mad_below_one_unit_50']].fillna(False).any(axis=1)
    eligible=f.eligible.fillna(False)&f.available_configurations.ge(2)
    features=np.column_stack([np.log1p(f.aptos_1.astype(float)),f.turnout_1,f.share_13_1,f.share_22_1]).astype(float)
    if not np.isfinite(features[eligible]).all():raise ValueError('Característica de pareamento ausente entre elegíveis')
    f['_position']=np.arange(len(f))
    priorities=f.loc[eligible&f.reference_alert.fillna(False)&f.selected_pattern.fillna(False)&f.alert_configurations.eq(f.available_configurations)].copy()
    controls=f.loc[eligible&~f.reference_alert.fillna(True)&~f.selected_pattern.fillna(True)&f.alert_configurations.eq(0)].copy()
    sort=['mad_warning','minimum_robust','absolute_margin_change_pp','uf','municipality','zone','section']
    priorities=priorities.sort_values(sort,ascending=[True,False,False,True,True,True,True],kind='stable',na_position='last')
    selected=[];shortfalls=[]
    for region in PROTOCOL['regions']:
        pool=priorities.loc[priorities.region.eq(region)]
        used_ufs=set()
        for desired in (1,-1):
            unused=pool.loc[~pool.case_key.isin([r['case_key'] for r in selected])]
            matching=unused.loc[np.sign(unused.margin_change_pp).eq(desired)]
            reason='sentido solicitado disponível'
            if matching.empty:
                matching=unused;reason='sentido solicitado ausente; alternativa registrada antes dos documentos'
            distinct=matching.loc[~matching.uf.isin(used_ufs)]
            if not distinct.empty:matching=distinct
            if matching.empty:
                shortfalls.append(dict(region=region,desired_direction=desired,reason='nenhum prioritário elegível disponível'));continue
            row=matching.iloc[0].to_dict();row.update(group='prioritario',requested_direction=desired,allocation_note=reason)
            selected.append(row);used_ufs.add(row['uf'])
    used_controls=set();pairs=[]
    for pair_number,priority in enumerate(selected,1):
        uf=priority['uf'];uf_positions=f.loc[eligible&f.uf.eq(uf),'_position'].to_numpy()
        base=features[uf_positions];center=np.median(base,axis=0);scale=np.std(base,axis=0);scale=np.where(scale>1e-12,scale,1.)
        pool=controls.loc[controls.uf.eq(uf)&~controls.case_key.isin(used_controls)].copy()
        local=pool.loc[pool.municipality.eq(priority['municipality'])]
        scope='mesmo município' if not local.empty else 'mesma UF'
        if not local.empty:pool=local
        pair_id=f'P{pair_number:02d}'
        priority.update(pair_id=pair_id,match_scope=scope,match_distance=None)
        pairs.append(priority)
        if pool.empty:
            shortfalls.append(dict(pair_id=pair_id,region=priority['region'],reason='controle sem alerta não disponível na mesma UF'));continue
        candidate_features=(features[pool._position.to_numpy()]-center)/scale
        target=(features[int(priority['_position'])]-center)/scale
        pool['distance']=np.sqrt(np.square(candidate_features-target).sum(axis=1))
        control=pool.sort_values(['distance','uf','municipality','zone','section'],kind='stable').iloc[0].to_dict()
        control.update(group='comparacao',pair_id=pair_id,requested_direction=None,allocation_note='controle sem alerta nos critérios registrados',match_scope=scope,match_distance=float(control['distance']))
        priority['match_distance']=control['match_distance']
        pairs.append(control);used_controls.add(control['case_key'])
    result=pd.DataFrame(pairs).drop(columns=['_position','distance'],errors='ignore')
    if result.empty:raise ValueError('Nenhuma seção elegível para a amostra')
    if result.duplicated(GEO).any():raise ValueError('A amostra reutilizou uma seção')
    return result.sort_values(['pair_id','group'],ascending=[True,False]).reset_index(drop=True),shortfalls


def run_sample(source,destination=None):
    source=Path(source).resolve();destination=Path(destination).resolve() if destination else source/'auditoria/amostra'
    names=['nacional/inventario/secoes.parquet','estabilidade/variantes.parquet','secoes_por_turno.parquet','fontes_utilizadas.json']
    source,destination,state=begin(source,destination,names)
    con=duckdb.connect(config={'threads':2,'memory_limit':'1GB'})
    try:
        frame=con.execute('''WITH s AS (SELECT year,uf,municipality,zone,section,
            count(*) FILTER(WHERE available) available_configurations,
            count(*) FILTER(WHERE available AND statistical_alert) alert_configurations,
            max(robust_max) FILTER(WHERE k=15 AND available) robust_max_15,
            max(robust_max) FILTER(WHERE k=30 AND available) robust_max_30,
            max(robust_max) FILTER(WHERE k=50 AND available) robust_max_50,
            bool_or(mad_below_one_unit) FILTER(WHERE k=15 AND available) mad_below_one_unit_15,
            bool_or(mad_below_one_unit) FILTER(WHERE k=30 AND available) mad_below_one_unit_30,
            bool_or(mad_below_one_unit) FILTER(WHERE k=50 AND available) mad_below_one_unit_50
            FROM read_parquet(?) WHERE k IN (15,30,50) GROUP BY year,uf,municipality,zone,section)
            SELECT n.*,s.* EXCLUDE(year,uf,municipality,zone,section)
            FROM read_parquet(?) n JOIN s USING(year,uf,municipality,zone,section)
            WHERE n.eligible''',[str(source/names[1]),str(source/names[0])]).df()
        if set(frame.year)!={2026}:raise ValueError('Amostra específica de 2026')
        sample,shortfalls=choose(frame)
        export_frame(con,sample,destination/'secoes')
        con.register('selected_sections',sample[GEO])
        turns=con.execute('''SELECT b.year,b.turn,b.uf,b.municipality,b.zone,b.section,b.election_id,b.vote_election_id,
            b.installed,b.has_votes,b.has_detail,b.aptos,b.attendance,b.valid,b.blank,b.null_votes,b.other_votes,
            b.vote_conflict,b.generation,b.vote_generation FROM read_parquet(?) b
            JOIN selected_sections s USING(year,uf,municipality,zone,section) ORDER BY b.uf,b.municipality,b.zone,b.section,b.turn''',[str(source/'secoes_por_turno.parquet')]).df()
        if len(turns)!=2*len(sample) or turns.duplicated(['year','turn','uf','municipality','zone','section']).any():raise ValueError('Amostra sem os dois turnos únicos na referência')
        export_frame(con,turns,destination/'turnos')
        write_json(destination/'protocolo.json',PROTOCOL)
        summary=dict(year=2026,sections=len(sample),priority_sections=int(sample.group.eq('prioritario').sum()),control_sections=int(sample.group.eq('comparacao').sum()),
            section_turns=len(turns),strata=records(sample.groupby(['region','group']).size().reset_index(name='sections')),
            shortfalls=shortfalls,selection_before_documents=True,document_status='ainda não obtidos nesta etapa de seleção',
            protocol=PROTOCOL,available_configurations=records(sample.groupby(['uf','available_configurations']).size().reset_index(name='sections')),
            interpretation='Amostra dirigida não representativa; divergência, concordância ou indisponibilidade precisam ser avaliadas por documento, sem inferência populacional.')
        return finish(source,destination,state,summary,[Path(__file__),Path(__file__).with_name('national_common.py')])
    except Exception as exc:failed(destination,state,exc);raise
    finally:con.close()
