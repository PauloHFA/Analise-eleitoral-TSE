"""Conferência independente dos três incrementos nacionais e da interface offline."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
from urllib.parse import urlparse

import duckdb
import numpy as np

from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv
from eleicoes.national_map import map_color
from eleicoes.investigation import peer_margin_scores


class Page(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=[];self.codes=[];self.scripts={};self.current=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if tag=='path' and 'data-code' in attrs:self.codes.append(attrs['data-code'])
        self.links.extend(attrs[k] for k in ('href','src') if k in attrs)
        if tag=='script':self.current=attrs.get('id','script');self.scripts[self.current]=''
    def handle_data(self,data):
        if self.current:self.scripts[self.current]+=data
    def handle_endtag(self,tag):
        if tag=='script':self.current=None


def validate(source):
    source=Path(source).resolve();root=Path(__file__).resolve().parents[1]
    con=duckdb.connect(config={'threads':2,'memory_limit':'1GB','temp_directory':str(root/'outputs/trabalho-validacao-nacional')})
    result={}
    try:
        for phase in ('inventario','taxas','mapas'):
            folder=source/'nacional'/phase
            summary=json.loads((folder/'resumo.json').read_text(encoding='utf-8'))
            state=json.loads((folder/'estado_execucao.json').read_text(encoding='utf-8'))
            assert summary['status']==state['status']=='concluído'
            for name,digest in summary['input_hashes'].items():assert sha256(source/name)==digest,name
            for name,digest in summary['code_hashes'].items():assert sha256(root/'src/eleicoes'/name)==digest,name
            manifest=json.loads((folder/'manifesto.json').read_text(encoding='utf-8'))
            for name,digest in manifest.items():assert sha256(folder/name)==digest,name
            for path in folder.glob('*.json'):json.loads(path.read_text(encoding='utf-8'),parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))
            checked={}
            for path in folder.glob('*.parquet'):
                expected=con.read_parquet(str(path));expected.create_view('expected')
                schema={name:str(t) for name,t in zip(expected.columns,expected.types)}
                read_export_csv(con,path.with_suffix('.csv'),columns=schema).create_view('actual')
                for a,b in (('expected','actual'),('actual','expected')):
                    assert con.execute(f'SELECT count(*) FROM (SELECT * FROM {a} EXCEPT ALL SELECT * FROM {b})').fetchall()[0][0]==0,path
                checked[path.stem]=con.execute('SELECT count(*) FROM expected').fetchall()[0][0]
            result[phase]={'tables':checked,'csv_parquet':'multiconjunto tipado completo nos dois sentidos'}
        for name,path in [('sections','nacional/inventario/secoes'),('municipalities','nacional/taxas/municipios'),('baseline','indicadores_secoes'),('previous','investigacao_viradas')]:
            con.read_parquet(str(source/(path+'.parquet'))).create_view(name)
        bad=con.execute('''SELECT count(*) FROM sections n JOIN baseline b USING(year,uf,municipality,zone,section)
            WHERE n.reference_alert IS DISTINCT FROM b.statistical_alert OR n.eligible IS DISTINCT FROM (b.comparable AND NOT b.small)
            OR n.margin_change_pp IS DISTINCT FROM -n.margin_loss_22_pp
            OR n.flip_to_13 IS DISTINCT FROM coalesce(n.votes_22_1>n.votes_13_1 AND n.votes_22_2<n.votes_13_2,false)
            OR n.flip_to_22 IS DISTINCT FROM coalesce(n.votes_22_1<n.votes_13_1 AND n.votes_22_2>n.votes_13_2,false)
            OR (n.margin_peer_mad<=1e-9 AND n.margin_robust_z IS NOT NULL)''').fetchall()[0][0]
        assert bad==0
        original=con.execute('SELECT count(*),count(*) FILTER(WHERE comparable),count(*) FILTER(WHERE comparable AND NOT small),count(*) FILTER(WHERE statistical_alert) FROM baseline').fetchall()[0]
        observed=con.execute('SELECT count(*),count(*) FILTER(WHERE comparable),count(*) FILTER(WHERE eligible),count(*) FILTER(WHERE reference_alert) FROM sections').fetchall()[0]
        assert observed==original
        rjmg=con.execute('''SELECT count(*) FROM municipalities n JOIN previous o USING(year,uf,municipality)
            WHERE o.level='municipio' AND o.uf IN ('RJ','MG') AND (n.flip_to_13 IS DISTINCT FROM o.flip_to_13
            OR n.flip_to_22 IS DISTINCT FROM o.flip_to_22 OR abs(n.margin_loss_22_pp-o.margin_loss_22_pp)>1e-9)''').fetchall()[0][0]
        assert rjmg==0
        # Recalcula contagens a partir das seções, sem usar as taxas exportadas.
        rate_config=json.loads((source/'nacional/taxas/resumo.json').read_text(encoding='utf-8'))
        invalid=con.execute('''WITH counts AS (SELECT year,uf,municipality,count(*) observed,
            count(*) FILTER(WHERE eligible) eligible,count(*) FILTER(WHERE eligible AND reference_alert) alerts FROM sections GROUP BY year,uf,municipality)
            SELECT count(*) FROM municipalities m JOIN counts c USING(year,uf,municipality)
            WHERE m.observed_sections<>c.observed OR m.eligible_sections<>c.eligible OR m.reference_alert_sections<>c.alerts
            OR ((m.rate_per_1000 IS NULL)<>(c.eligible=0))
            OR abs(m.rate_per_1000-1000.*c.alerts/nullif(c.eligible,0))>1e-9
            OR abs(m.eligible_coverage_pct-100.*c.eligible/c.observed)>1e-9
            OR (m.rate_map_value IS NOT NULL AND (m.eligible_sections<? OR m.eligible_coverage_pct<?))''',
            [rate_config['minimum_eligible_sections'],rate_config['minimum_eligible_coverage_pct']]).fetchall()[0][0]
        assert invalid==0
        for column in ('votes_13_1','votes_13_2','votes_22_1','votes_22_2','attendance_1','attendance_2'):
            assert con.execute(f'''WITH c AS (SELECT year,uf,municipality,count(*) units,
                CASE WHEN count({column})=count(*) THEN sum({column}) END value FROM sections WHERE comparable GROUP BY year,uf,municipality)
                SELECT count(*) FROM municipalities m LEFT JOIN c USING(year,uf,municipality)
                WHERE m.cohort_sections<>coalesce(c.units,0) OR ((m.cohort_{column} IS NULL)<>(c.value IS NULL))
                OR abs(m.cohort_{column}-c.value)>1e-8''').fetchall()[0][0]==0
        # Amostra estratificada por UF comparada à implementação anterior dos escores.
        frame=con.execute('SELECT year,uf,municipality,zone,section,margin_loss_22_pp FROM sections').df()
        neighbors=con.execute('''SELECT b.year,b.uf,b.municipality,b.zone,b.section,b.peer_ids,b.peer_count,b.comparable,b.small
            FROM baseline b WHERE b.comparable AND NOT b.small AND b.peer_count=30
            QUALIFY row_number() OVER(PARTITION BY b.uf ORDER BY b.robust_max DESC NULLS LAST,b.municipality,b.zone,b.section)<=3''').df()
        scores=peer_margin_scores(frame,neighbors)
        con.register('checked_scores',scores)
        bad_scores=con.execute('''SELECT count(*) FROM sections n JOIN checked_scores o USING(year,uf,municipality,zone,section)
            WHERE ((n.margin_robust_z IS NULL)<>(o.margin_robust_z IS NULL)) OR abs(n.margin_robust_z-o.margin_robust_z)>1e-9+1e-12*abs(o.margin_robust_z)''').fetchall()[0][0]
        assert bad_scores==0
        maps=source/'nacional/mapas';payload=json.loads((maps/'mapa_dados.json').read_text(encoding='utf-8'))
        old=json.loads((source/'mapa_dados.json').read_text(encoding='utf-8'))
        lookup={r['ibge_code']:r for r in old['features']}
        assert len(payload['features'])==len(lookup)==len(set(r['ibge_code'] for r in payload['features']))
        for row in payload['features']:
            original_row=lookup[row['ibge_code']]
            assert row['path']==original_row['path'] and row['bounds']==original_row['bounds'] and row['uf']!='ZZ'
        parsed=Page();parsed.feed((maps/'mapa.html').read_text(encoding='utf-8'))
        assert len(parsed.ids)==len(set(parsed.ids)) and set(parsed.codes)==set(lookup)
        jsdata=json.loads(parsed.scripts['national-data'])
        colors={mode:{str(t):{r['ibge_code']:map_color(r,mode,t,minimum=jsdata['minimum'],coverage=jsdata['coverage']) for r in jsdata['features']} for t in (1,2)} for mode in ('margin','rate','winner')}
        js_payload=dict(ids=parsed.ids,codes=parsed.codes,data=jsdata,script=parsed.scripts['script'],colors=colors)
        completed=subprocess.run(['node',str(Path(__file__).with_suffix('.cjs'))],input=json.dumps(js_payload,ensure_ascii=False),encoding='utf-8',capture_output=True,check=True)
        result['interface']=json.loads(completed.stdout)
        for file in maps.glob('*.html'):
            parsed=Page();parsed.feed(file.read_text(encoding='utf-8'))
            for link in parsed.links:
                url=urlparse(link)
                if not url.scheme and url.path:assert (file.parent/url.path).is_file(),link
        assert (maps/'relatorio.pdf').read_bytes().startswith(b'%PDF')
        result.update(status='válido',reference_counts=dict(observed=observed[0],comparable=observed[1],eligible=observed[2],alerts=observed[3]),
                      rjmg='resultados territoriais preservados',peer_score_sample=len(scores),geometry='polígonos, códigos e limites preservados')
        return result
    finally:con.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='outputs/2026');args=parser.parse_args()
    print(json.dumps(validate(args.output),ensure_ascii=False,indent=2))
