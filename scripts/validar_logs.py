"""Conferência de tabelas tipadas, recorte temporal, preservação, filtros e PDF."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse
import duckdb
from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv
from eleicoes.urn_logs import read_payloads, TARGET_DATES, RULES
from validar_assinaturas import Page


def validate(source, data):
    source,data=Path(source).resolve(),Path(data).resolve()
    root=Path(__file__).resolve().parents[1];dest=source/'auditoria/logs'
    summary=json.loads((dest/'resumo.json').read_text(encoding='utf8'))
    for name,digest in json.loads((dest/'manifesto.json').read_text(encoding='utf8')).items():assert sha256(dest/name)==digest,name
    for name,digest in summary['input_hashes'].items():assert sha256(source/name)==digest,name
    for name,digest in summary['code_hashes'].items():assert sha256(root/'src/eleicoes'/name)==digest,name
    con=duckdb.connect();pairs=[]
    try:
        for path in sorted(dest.glob('*.parquet')):
            types={r[0]:r[1] for r in con.execute('DESCRIBE SELECT * FROM read_parquet(?)',[str(path)]).fetchall()}
            read_export_csv(con,path.with_suffix('.csv'),columns=types).create_view('csv_checked',replace=True)
            con.read_parquet(str(path)).create_view('parquet_checked',replace=True)
            assert con.sql('SELECT count(*) FROM ((SELECT * FROM csv_checked EXCEPT ALL SELECT * FROM parquet_checked) UNION ALL (SELECT * FROM parquet_checked EXCEPT ALL SELECT * FROM csv_checked))').fetchall()[0][0]==0,path.name
            pairs.append(path.stem)
        assert pairs==['comparacao_turnos','contagens','erros_contexto','membros','pendencias','regras','unidades']
        units,counts,members,issues,comparison=[con.read_parquet(str(dest/(name+'.parquet'))).df() for name in ('unidades','contagens','membros','pendencias','comparacao_turnos')]
        geo=['year','turn','uf','municipality','zone','section']
        assert len(units)==48 and len(members)==49 and len(comparison)==24
        assert not units.duplicated(geo).any() and not members.duplicated(geo+['member']).any()
        assert units.groupby('turn').size().eq(24).all() and comparison.coverage.eq('both').all()
        assert set(counts.columns)==set(geo+['window','module','level','event','count'])
        assert counts['count'].gt(0).all() and set(counts.event).issubset({r[0] for r in RULES})
        assert units.previous_hash_status.eq('concordante').all()
        assert units.previous_hardware_signature_status.eq('valida_com_chave_embutida').all()
        assert units.trust_status.eq('inconclusivo_sem_ancora_na_etapa_pkix').all()
        assert summary['invalid_rows']==0 and units.invalid_rows.eq(0).all()
        assert units.records.sum()==summary['records']==counts['count'].sum()==members.records.sum()
        assert units.target_records.sum()==summary['target_records']==counts.loc[counts.window.eq('data_alvo'),'count'].sum()
        assert units.earlier_records.sum()+units.target_records.sum()+units.later_records.sum()==summary['records']
        assert members.depth.gt(0).sum()==summary['nested_payloads']==1
        raw_totals=Counter();raw_rechecks=0
        for unit in units.to_dict('records'):
            path=(data/unit['source_path']).resolve()
            assert path.is_relative_to(data) and sha256(path)==unit['source_sha256']
            counter=Counter()
            for payload in read_payloads(path.read_bytes()):
                for raw in payload['content'].split(b'\n'):
                    raw=raw.removesuffix(b'\r')
                    if not raw:continue
                    fields=raw.split(b'\t');assert len(fields)==6
                    stamp=datetime.strptime(fields[0].decode('ascii'),'%d/%m/%Y %H:%M:%S')
                    day=stamp.date().isoformat();target=TARGET_DATES[unit['turn']]
                    window='data_alvo' if day==target else 'anterior' if day<target else 'posterior'
                    counter['records']+=1;counter[window]+=1
                    if window=='data_alvo':counter[fields[1].decode('ascii')]+=1
            assert counter['records']==unit['records'] and counter['data_alvo']==unit['target_records']
            assert counter['ERRO']==unit['target_error_records'] and counter['ALERTA']==unit['target_alert_records']
            raw_totals.update(counter);raw_rechecks+=1
        assert raw_rechecks==48 and raw_totals['records']==summary['records']
        assert len(issues)==summary['review_rows'] and len(issues[geo].drop_duplicates())==summary['review_units']
        assert units.target_error_records.gt(0).sum()==summary['units_with_target_errors']
        errors=con.read_parquet(str(dest/'erros_contexto.parquet')).df()
        assert errors['count'].sum()==summary['target_error_records']
        assert errors.groupby('event')['count'].sum().to_dict()=={'mr_desmontagem_erro':31,'opensession_erro':1,'impressora_erro_desconhecido':1}
    finally:con.close()
    previous=('amostra','documentos','conferencia','relatorio','assinaturas','ed521','ed521_referencia','cadeia','caminho_pkix')
    for stage in previous:
        folder=source/'auditoria'/stage
        for name,digest in json.loads((folder/'manifesto.json').read_text(encoding='utf8')).items():assert sha256(folder/name)==digest,(stage,name)
    page=Page();page.feed((dest/'relatorio.html').read_text(encoding='utf8'));links=0
    for link in page.links:
        u=urlparse(link)
        if not u.scheme and u.path:assert (dest/u.path).is_file(),link;links+=1
    js=subprocess.run(['node',str(root/'scripts/validar_logs.cjs'),str(dest/'relatorio.html')],capture_output=True,text=True,encoding='utf8',check=True)
    filters=json.loads(js.stdout);assert filters['units']==48
    try:import pymupdf
    except ImportError:
        sys.path.insert(0,str(root/'outputs/publicacao/pdfqa'));import pymupdf
    with pymupdf.open(dest/'relatorio.pdf') as pdf:
        content=' '.join(' '.join(p.get_text() for p in pdf).split())
        for value in ('ERRO','ALERTA','Latin-1','2026','aninhado','não','relógio'):assert value in content,value
        for p in pdf:
            assert len(p.get_text())>150
            for x0,y0,x1,y1,*_ in p.get_text('blocks'):assert x0>=36 and x1<=p.rect.width-35 and y0>=18 and y1<=p.rect.height-20,(p.number,(x0,y0,x1,y1))
        pdf_info=dict(pages=len(pdf),bookmarks=len(pdf.get_toc()),geometry='dentro das margens')
    return dict(status='válido',csv_parquet_pairs=len(pairs),section_turns=48,text_payloads=49,
        raw_logs_rechecked=raw_rechecks,records=summary['records'],target_records=summary['target_records'],
        target_error_records=summary['target_error_records'],review_rows=summary['review_rows'],
        previous_stage_manifests_preserved=len(previous),local_links_and_images=links,filters=filters,pdf=pdf_info)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='outputs/2026');parser.add_argument('--data',default='data');args=parser.parse_args()
    print(json.dumps(validate(args.output,args.data),ensure_ascii=False,indent=2))
