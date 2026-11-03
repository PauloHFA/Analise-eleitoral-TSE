"""Mapas e relatório nacional offline, reutilizando a cartografia conferida."""
import html
import json
import math
from pathlib import Path
import re

import duckdb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.path import Path as PlotPath
from matplotlib.patches import PathPatch
import pandas as pd
from reportlab.platypus import PageBreak

from .analysis import export_frame
from .national_common import begin,finish,failed,records
from .national_rates import mask_rates
from .pdf_layout import AnalysisPDF,WIDTH,heading,p,pdf_styles,table,picture
from .sources import sha256,write_json

GRAY='#c5cbd3'


def tint(base,strength):
    return '#'+''.join(f'{math.floor(255+(int(base[i:i+2],16)-255)*strength+.5):02x}' for i in (1,3,5))


def map_color(row,mode,turn=2,minimum=30,coverage=80):
    known=lambda value:value is not None and pd.notna(value) and math.isfinite(float(value))
    if mode=='rate':
        if not all(known(row.get(k)) for k in ('eligible_sections','eligible_coverage_pct','rate_per_1000')):return GRAY
        if row['eligible_sections']<minimum or row['eligible_coverage_pct']<coverage:return GRAY
        return tint('#6d28a8',math.sqrt(row['rate_per_1000']/1000))
    if mode=='margin':
        value=row.get('margin_change_pp')
        if not known(value):return GRAY
        if value==0:return '#ffffff'
        return tint('#165dcc' if value>0 else '#cf2639',.18+.82*math.sqrt(abs(value)/200))
    f,l=row.get(f'votes_22_{turn}'),row.get(f'votes_13_{turn}')
    if not known(f) or not known(l) or f+l<=0 or f==l:return GRAY
    return tint('#165dcc' if f>l else '#cf2639',.32+.68*abs(f-l)/(f+l))


def feature_rows(geography,municipalities,documents):
    keys=['uf','municipality']
    if municipalities.duplicated(keys).any():raise ValueError('Unidade municipal duplicada')
    docs=documents.groupby(keys)[['records_checked','pending_records']].sum(min_count=1).rename(columns={'records_checked':'document_records','pending_records':'document_pending'})
    municipalities=municipalities.merge(docs,on=keys,how='left',validate='one_to_one')
    fields=['year','uf','municipality','municipality_name_1','comparable','comparison_reason','selected_pattern','flip_to_13','flip_to_22','tie_1','tie_2','loss_22_10pp','loss_13_10pp',
        'margin_1_pp','margin_2_pp','margin_change_pp','delta_votes_22','delta_votes_13','eliminated_votes_1',
        'observed_sections','comparable_sections','eligible_sections','reference_alert_sections','eligible_coverage_pct','rate_per_1000','rate_map_status','rate_map_value',
        'cohort_sections','cohort_margin_1_pp','cohort_margin_2_pp','cohort_coverage_attendance_1_pct','cohort_coverage_attendance_2_pct','document_records','document_pending']
    fields += [f'{m}_{t}' for m in ('votes_13','votes_22','valid','attendance','aptos','blank','null_votes') for t in (1,2)]
    lookup={(row['uf'],row['municipality']):row for row in records(municipalities[fields])}
    result=[];codes=set()
    for geometry in geography['features']:
        key=(geometry['uf'],geometry['municipality'])
        if key not in lookup:raise ValueError('Polígono sem unidade eleitoral na tabela atual')
        if geometry['ibge_code'] in codes:raise ValueError('Código IBGE duplicado')
        codes.add(geometry['ibge_code'])
        if not re.fullmatch(r'[MLZ0-9.,eE+\- ]+',geometry['path']):raise ValueError('Caminho SVG inválido')
        if len(geometry['bounds'])!=4 or not all(math.isfinite(v) for v in geometry['bounds']):raise ValueError('Limites geográficos inválidos')
        result.append(dict(lookup[key],ibge_code=geometry['ibge_code'],path=geometry['path'],bounds=geometry['bounds']))
    return result


def static_maps(destination,features,minimum,coverage):
    for mode in ('margin','rate'):
        patches=[];colors=[]
        for row in features:
            paths=[]
            for ring in row['path'].split('M')[1:]:
                points=[[float(v) for v in pair.split(',')] for pair in ring.rstrip('Z').split('L')]
                paths.append(PlotPath(points,[PlotPath.MOVETO]+[PlotPath.LINETO]*(len(points)-2)+[PlotPath.CLOSEPOLY]))
            patches.append(PathPatch(PlotPath.make_compound_path(*paths)))
            colors.append(map_color(row,mode,minimum=minimum,coverage=coverage))
        fig,ax=plt.subplots(figsize=(8,7),layout='constrained')
        ax.add_collection(PatchCollection(patches,facecolors=colors,edgecolors='#ffffff',linewidths=.1))
        ax.autoscale_view();ax.invert_yaxis();ax.set_aspect('equal');ax.axis('off')
        ax.set_title('Mudança da margem entre finalistas' if mode=='margin' else 'Triagem original por 1.000 seções elegíveis')
        note='Azul: mudança a favor de Flávio; vermelho: a favor de Lula.\nEscala simétrica fixa ±200 pp; branco: zero; cinza: indisponível.' if mode=='margin' else f'Roxo: escala fixa 0–1.000; branco: zero conhecido; cinza: taxa sem exibição.\nExibição: ≥{minimum} elegíveis e ≥{coverage:g}% de cobertura; não é risco de fraude.'
        fig.text(.5,.015,note,ha='center',fontsize=9)
        fig.savefig(destination/(mode+'.png'),dpi=160,bbox_inches='tight');plt.close(fig)


def map_html(destination,features,minimum,coverage):
    esc=lambda value:html.escape(str(value),quote=True)
    shapes=''.join(f'<path data-code="{esc(r["ibge_code"])}" d="{esc(r["path"])}" fill="#c5cbd3" tabindex="0" role="button" aria-label="{esc(r["municipality_name_1"])} / {esc(r["uf"])}" fill-rule="evenodd" vector-effect="non-scaling-stroke"><title>{esc(r["municipality_name_1"])}</title></path>' for r in features)
    options=''.join(f'<option>{uf}</option>' for uf in sorted({r['uf'] for r in features}))
    data=json.dumps(dict(minimum=minimum,coverage=coverage,features=[{k:v for k,v in r.items() if k!='path'} for r in features]),ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('<','\\u003c')
    script=Path(__file__).with_name('national_ui.js').read_text(encoding='utf-8')
    page=f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Mapa nacional de mudanças</title>
<style>body{{font:16px/1.5 system-ui;color:#183447;margin:auto;max-width:1500px;padding:20px}}label{{display:inline-block;margin:6px}}select,input,button{{font:inherit;padding:5px}}.layout{{display:flex;flex-wrap:wrap;gap:20px}}svg{{flex:1 1 650px;width:100%;height:650px;background:#edf4f7;touch-action:none}}aside{{flex:1 1 270px;max-width:420px;background:#f2f5f8;padding:14px}}path:focus{{stroke:#111;stroke-width:2}}.note{{padding:14px;background:#edf4f7}}</style>
<h1>Mapa nacional: liderança, mudança de margem e triagem</h1><p><a href="relatorio.html">Abrir relatório nacional</a> · <a href="../taxas/municipios.csv">Tabela completa</a></p>
<p class="note">Mudanças observadas e alertas estatísticos são medidas distintas. Área geográfica não representa quantidade de eleitores; a taxa de alertas não é risco de fraude. Exterior aparece nas tabelas e não possui polígonos.</p>
<label>Visualização <select id="national-mode"><option value="margin">Mudança da margem</option><option value="winner">Liderança entre finalistas</option><option value="rate">Alertas por 1.000 elegíveis</option></select></label>
<label>Turno <select id="national-turn"><option value="1">1º</option><option value="2" selected>2º</option></select></label>
<label>UF <select id="national-uf"><option value="BR">Brasil</option>{options}</select></label>
<label>Padrão <select id="national-pattern"><option value="all">Todos</option><option value="flips">Inversões nos dois sentidos</option><option value="13">Flávio → Lula</option><option value="22">Lula → Flávio</option><option value="loss22">Redução da vantagem de Flávio ≥10 pp</option><option value="loss13">Redução da vantagem de Lula ≥10 pp</option><option value="ties">Mudança da condição de empate</option></select></label>
<label>Mínimo de elegíveis para taxa <input id="national-minimum" type="number" min="1" step="1" value="{minimum}" style="width:75px"></label>
<label>Cobertura mínima para taxa (%) <input id="national-coverage" type="number" min="0" max="100" value="{coverage}" style="width:75px"></label>
<p>Limites de exibição são operacionais e não estimam precisão. As taxas integrais continuam disponíveis na tabela.</p><p id="national-scale"></p><p id="national-count" aria-live="polite"></p>
<button id="national-plus" aria-label="Aproximar">+</button> <button id="national-minus" aria-label="Afastar">−</button> <button id="national-reset">Restaurar enquadramento da UF</button>
<div class="layout"><svg id="national-svg" role="img" aria-label="Mapa municipal de mudanças entre turnos">{shapes}</svg><aside id="national-info" aria-live="polite"></aside></div>
<p>Cartografia, projeção e vínculo TSE–IBGE preservados da referência. Tons de margem usam escala simétrica fixa ±200 pp e taxas usam escala fixa 0–1.000, sem renormalizar pela UF filtrada. A regra de cor difere entre os modos e está descrita acima.</p>
<noscript><p>Mapa estático de mudança de margem:</p><img src="margin.png" alt="Mudança da margem municipal" style="max-width:100%"></noscript>
<script id="national-data" type="application/json">{data}</script><script>{script}</script></html>'''
    (destination/'mapa.html').write_text(page,encoding='utf-8')


def report(destination,summary,municipalities,regions,counts,recon):
    esc=lambda value:html.escape(str(value))
    n=lambda value:f'{int(value):,}'.replace(',','.')
    brazil=municipalities.loc[municipalities.uf.ne('ZZ')]
    exterior=municipalities.loc[municipalities.uf.eq('ZZ')]
    rows=[]
    for label,frame in (('Brasil',brazil),('Exterior',exterior)):
        rows.append([label,len(frame),int(frame.flip_to_13.sum()),int(frame.flip_to_22.sum()),int(frame.tie_1.sum()),int(frame.tie_2.sum())])
    headers=['Universo','Unidades municipais','Flávio → Lula','Lula → Flávio','Empate no 1º','Empate no 2º']
    basic=pd.DataFrame(rows,columns=headers).to_html(index=False,escape=True)
    paragraphs=[
        f"O inventário nacional preserva {n(regions.observed_sections.sum())} seções e amplia os padrões para todos os estados. No resultado municipal completo do Brasil, {n(brazil.flip_to_13.sum())} unidades passaram de liderança de Flávio para Lula e {n(brazil.flip_to_22.sum())} fizeram o caminho inverso, entre os dois finalistas. Esses resultados são descritivos; a comparabilidade de cada território consta da tabela.",
        'A margem usa 100 × (Flávio − Lula)/(Flávio + Lula) em cada turno. A mudança é segundo menos primeiro: positivo favorece Flávio, negativo favorece Lula. Participações sobre todos os nominais usam outro denominador. Perder vantagem relativa pode ocorrer mesmo ganhando votos absolutos. Inversões são incluídas independentemente de limites de mudança; empates têm identificação própria.',
        'As reduções de vantagem de 5/10/15 pp são calculadas nos dois sentidos. Os resultados por seção, local, município e UF estão no inventário, inclusive os não comparáveis. O escore de margem reutiliza os mesmos 30 pares; a triagem original permanece em reference_alert. O escore adicional não altera aquela seleção.',
        f"As taxas usam contagens agregadas: 1.000 × alertas originais entre elegíveis / seções elegíveis. Elas não são médias de taxas municipais e não usam votos, eleitores ou área como denominador. Um denominador zero gera ausência. Os limites de {summary['minimum_eligible_sections']} elegíveis e {summary['minimum_eligible_coverage_pct']:g}% de cobertura são escolhas operacionais de apresentação, ajustáveis no mapa, sem interpretação de precisão estatística.",
        'A coorte das mesmas seções territorialmente comparáveis, incluindo pequenas, é uma análise complementar. Seus valores e coberturas dos dois turnos aparecem ao clicar no mapa e nas tabelas. Ela não substitui o total municipal. Ausências e somas incompletas permanecem ausentes.',
        'Os somatórios disponíveis dos finalistas são confrontados entre níveis e com a fonte oficial nominal. Contagens de linhas ausentes acompanham os somatórios. Conferência de linhas de BU não certifica completude de urnas, a causa de mudanças ou persistência. Brasil e exterior são separados.',
        'As listas estatísticas dependem do método de comparação: o estudo anterior de estabilidade mostrou sensibilidade do topo dos rankings. A lista nacional de prioridades deve ser examinada junto com magnitude absoluta, dispersão e documentação, sem equivalência automática com fraude. As fontes eleitorais, os mapas e as fichas anteriores foram preservados.'
    ]
    links=[('../inventario/secoes.csv','Seções completas'),('../inventario/locais.csv','Locais completos'),('../taxas/municipios.csv','Municípios e coortes'),('../taxas/ufs.csv','UFs e denominadores'),('../inventario/contagens.csv','Sensibilidade 5/10/15 pp por nível/UF'),('../taxas/reconciliacao.csv','Somatórios e ausências'),('../taxas/conferencia_bu.csv','Linhas de BU disponíveis'),('prioridades.csv','Até 50 seções elegíveis por UF, nos dois sentidos'),('../taxas/dicionario.csv','Dicionário'),('resumo.json','Fontes, parâmetros e hashes')]
    stat_table=regions[['region','observed_sections','comparable_sections','eligible_sections','reference_alert_sections','rate_per_1000']].rename(columns={'region':'Universo','observed_sections':'Observadas','comparable_sections':'Comparáveis','eligible_sections':'Elegíveis','reference_alert_sections':'Alertas originais','rate_per_1000':'Por 1.000 elegíveis'})
    sections=''.join('<p>'+esc(text)+'</p>' for text in paragraphs)
    page=f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Investigação nacional — 2026</title><style>body{{font:16px/1.6 system-ui;max-width:1250px;margin:auto;padding:28px;color:#183447}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #cad6df;padding:8px;text-align:left}}.note{{padding:16px;background:#edf4f7}}iframe{{width:100%;height:1120px;border:1px solid #cad6df}}img{{max-width:100%}}</style>
<h1>Investigação nacional de mudanças entre turnos</h1><p class="note">Mudanças observadas, alertas estatísticos e divergências documentais são categorias distintas. Este estudo amplia a localização dos padrões, sem concluir irregularidade ou reconstruir votos individuais.</p>
<h2>O que foi encontrado?</h2>{basic}{stat_table.to_html(index=False,escape=True,float_format=lambda v:f'{v:.2f}'.replace('.',','))}{sections}
<h2>Mapa com consulta dos dois turnos e cobertura</h2><p><a href="mapa.html">Abrir mapa em página própria</a> · <a href="relatorio.pdf">PDF explicativo</a></p><iframe src="mapa.html" title="Mapa nacional interativo" loading="lazy"></iframe>
<h2>Leitura das escalas</h2><p>No modo de mudança, azul indica deslocamento relativo em favor de Flávio e vermelho em favor de Lula, mesmo que a liderança final seja outra. A taxa de triagem é roxa e tem denominador próprio. Branco é zero conhecido e cinza identifica ausência ou taxa sem exibição conforme a legenda de cada modo.</p><img src="margin.png" alt="Mapa nacional de mudança de margem"><img src="rate.png" alt="Mapa nacional de taxa de triagem">
<h2>Dados completos e reprodução</h2><ul>{''.join(f'<li><a href="{path}">{label}</a></li>' for path,label in links)}</ul>
<p>Executar as etapas inventario, taxas e mapas do comando eleicoes nacional, nessa ordem. Saídas preenchidas são recusadas. Os critérios de exibição podem ser ajustados sem alterar os valores descritivos das tabelas.</p><p><a href="../../relatorio.html">Relatório de referência</a> · <a href="../../estabilidade/relatorio.html">Estabilidade dos pares</a> · <a href="../../pesquisa_categorias/relatorio.html">Pesquisa documental</a></p></html>'''
    (destination/'relatorio.html').write_text(page,encoding='utf-8')
    styles=pdf_styles();story=[heading('Investigação nacional de mudanças','nacional',styles),p('Eleições 2026 — resultados completos, coortes e taxas com cobertura explícita',styles,'Deck'),table(headers,rows,[WIDTH*.13,WIDTH*.19,WIDTH*.17,WIDTH*.17,WIDTH*.17,WIDTH*.17],styles)]
    for index,text in enumerate(paragraphs):
        if index in (0,2,3,4,5,6):story.append(heading(['Resultados descritivos','Método','Padrões e pares','Taxas e cobertura','Mesmas seções','Conferências','Limites'][index],f'tema-{index}',styles,level=1))
        story.append(p(text,styles))
    for mode,title in (('margin','Mudança da margem'),('rate','Triagem original por 1.000 elegíveis')):
        story.extend([PageBreak(),heading(title,'map-'+mode,styles),picture(destination/(mode+'.png'),max_height=540),p('Cartografia IBGE e vínculo TSE–IBGE preservados. Exterior nas tabelas; área geográfica não representa quantidade de eleitores. A versão HTML permite ajustar a exibição e consultar valores e coortes ao clicar.',styles)])
    story.extend([PageBreak(),heading('Rastreabilidade e inventários','arquivos',styles),table(['Arquivo','Conteúdo'],[[path,label] for path,label in links],[WIDTH*.49,WIDTH*.51],styles),p('Fontes, parâmetros e hashes estão nos resumos de cada etapa. Novos indicadores são complementares e não substituem a documentação dos casos anteriores.',styles)])
    AnalysisPDF(destination/'relatorio.pdf',title='Investigação nacional de mudanças — 2026',styles=styles).build(story)


def run_maps(source,destination=None,minimum=30,coverage=80):
    source=Path(source).resolve();destination=Path(destination).resolve() if destination else source/'nacional/mapas'
    names=['mapa_dados.json','indicadores_municipio.parquet','nacional/inventario/secoes.parquet','nacional/inventario/contagens.parquet',
           'nacional/taxas/municipios.parquet','nacional/taxas/regioes.parquet','nacional/taxas/conferencia_bu.parquet','nacional/taxas/reconciliacao.parquet']
    source,destination,state=begin(source,destination,names)
    con=duckdb.connect(config={'threads':2,'memory_limit':'1GB'})
    try:
        geography=json.loads((source/'mapa_dados.json').read_text(encoding='utf-8'))
        if geography['summary']['results_sha256']!=sha256(source/'indicadores_municipio.parquet'):raise ValueError('Cartografia vinculada a outra versão dos resultados')
        read=lambda name:con.read_parquet(str(source/(name+'.parquet'))).df()
        municipalities=mask_rates(read('nacional/taxas/municipios'),minimum,coverage)
        docs=read('nacional/taxas/conferencia_bu');regions=read('nacional/taxas/regioes')
        features=feature_rows(geography,municipalities,docs)
        expected=municipalities.loc[municipalities.uf.ne('ZZ')]
        missing=expected.merge(pd.DataFrame(features)[['uf','municipality']],on=['uf','municipality'],how='left',indicator=True).loc[lambda f:f._merge.eq('left_only'),['uf','municipality']]
        write_json(destination/'mapa_dados.json',dict(features=features,minimum=minimum,coverage=coverage,missing_geometry=records(missing),sources=geography['summary']['sources']))
        con.read_parquet(str(source/'nacional/inventario/secoes.parquet')).create_view('sections')
        priorities=con.execute('''SELECT * EXCLUDE(rn) FROM (SELECT *,row_number() OVER(PARTITION BY uf ORDER BY margin_robust_z DESC NULLS LAST,absolute_margin_change_pp DESC NULLS LAST,uf,municipality,zone,section) rn
            FROM sections WHERE eligible AND selected_pattern) WHERE rn<=50 ORDER BY uf,rn''').df()
        export_frame(con,priorities,destination/'prioridades')
        summary=dict(year=2026,mapped=len(features),domestic_municipal_units=len(expected),exterior_municipal_units=int(municipalities.uf.eq('ZZ').sum()),
            missing_geometry=records(missing),minimum_eligible_sections=minimum,minimum_eligible_coverage_pct=coverage,priorities=len(priorities),
            flips_brasil=dict(to_13=int(expected.flip_to_13.sum()),to_22=int(expected.flip_to_22.sum())),
            map_rate_displayed=int(expected.rate_map_value.notna().sum()),map_rate_masked=int(expected.rate_map_value.isna().sum()),
            interpretation='Escalas nacionais fixas; mudanças e triagem descritivas, sem risco de fraude estimado ou transferências individuais inferidas.')
        static_maps(destination,features,minimum,coverage);map_html(destination,features,minimum,coverage)
        report(destination,summary,municipalities,regions,read('nacional/inventario/contagens'),read('nacional/taxas/reconciliacao'))
        return finish(source,destination,state,summary,[Path(__file__),Path(__file__).with_name('national_ui.js'),Path(__file__).with_name('national_common.py')])
    except Exception as exc:failed(destination,state,exc);raise
    finally:con.close()
