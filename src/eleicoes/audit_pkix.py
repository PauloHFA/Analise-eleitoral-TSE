"""Executa a validação de caminho com âncoras explícitas e captura de fontes própria."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from importlib.metadata import version
import json
import duckdb,pandas as pd
from cryptography import x509
from .sources import sha256,write_json
from .analysis import export_frame
from .national_common import begin,finish,failed,records
from .audit_signature import parse_vsc,certificate
from .pkix_path import validate_path,load_explicit_anchors

GEO=['year','turn','uf','municipality','zone','section']


def run_pkix(source,data='data',destination=None):
    source=Path(source).resolve();data=Path(data).resolve();raw=data/'auditoria/pkix/v1';previous=data/'auditoria/cadeia/v1'
    destination=Path(destination).resolve() if destination else source/'auditoria/caminho_pkix'
    names=['auditoria/documentos/inventario.parquet','auditoria/amostra/turnos.parquet','auditoria/cadeia/manifesto.json','auditoria/cadeia/vinculos.parquet']
    source,destination,state=begin(source,destination,names);con=duckdb.connect()
    try:
        raw_hashes={}
        for folder in (raw,previous):
            manifest=json.loads((folder/'manifesto.json').read_text(encoding='utf8'))
            for name,digest in manifest.items():
                if sha256(folder/name)!=digest:raise ValueError('Fonte alterada: '+name)
                raw_hashes[(folder.relative_to(data)/name).as_posix()]=digest
        anchors,policy=load_explicit_anchors(raw)
        sources=json.loads((raw/'fontes.json').read_text(encoding='utf8'));old=json.loads((previous/'fontes.json').read_text(encoding='utf8'))
        if sources['previous_manifest_sha256']!=sha256(previous/'manifesto.json'):raise ValueError('Captura complementar não corresponde à captura anterior')
        intermediates=[certificate((previous/r['file']).read_bytes())[0] for r in old['candidates']]
        crls=[];object_notes=[]
        for folder,metadata in ((raw,sources),(previous,old)):
            for record in metadata['attempts']:
                if record.get('saved_file'):
                    content=(folder/record['saved_file']).read_bytes()
                    if record.get('kind') in ('lcr','crl'):
                        try:crls.append(x509.load_pem_x509_crl(content) if content.startswith(b'-----BEGIN') else x509.load_der_x509_crl(content))
                        except ValueError:object_notes.append(dict(url=record['url'],status='resposta_nao_decodificada_como_lcr'))
                    else:object_notes.append(dict(url=record['url'],status='objeto_candidato_nao_promovido_a_ancora'))
        inv=con.read_parquet(str(source/names[0])).df();turns=con.read_parquet(str(source/names[1])).df();rows=[]
        for unit in turns.to_dict('records'):
            selected=inv
            for key in GEO:selected=selected.loc[selected[key].eq(unit[key])]
            selected=selected.loc[selected.kind.eq('assinatura')]
            if len(selected)!=1:raise ValueError('VSC ausente ou repetido')
            record=selected.iloc[0];path=(data/record['path']).resolve()
            if not path.is_relative_to(data) or sha256(path)!=record['sha256']:raise ValueError('Original alterado')
            obj=parse_vsc(path.read_bytes());leaf,info=certificate(obj['hw']['certificate'])
            base=datetime.strptime(obj['hw']['created'],'%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc)
            for label,offset in (('hipotese_UTC',0),('hipotese_UTC_mais_14',-14),('hipotese_UTC_menos_12',12)):
                result=validate_path(leaf,intermediates,anchors,base+timedelta(hours=offset),crls)
                rows.append(dict(**{k:unit[k] for k in GEO},scenario=label,leaf_sha256=info['sha256'],declared_time=obj['hw']['created'],**result))
        frame=pd.DataFrame(rows)
        if len(frame)!=3*len(turns):raise ValueError('Cobertura dos cenários não fecha')
        old_links=con.read_parquet(str(source/names[3])).df()
        units=frame.groupby(GEO).agg(scenarios=('scenario','size'),paths_conferred=('path_status',lambda s:int(s.eq('confere_no_instante_com_ancora_explicita').sum())),revocations_conferred=('revocation_status',lambda s:int(s.eq('conferida_por_lcr_no_instante').sum()))).reset_index()
        units=units.merge(old_links[GEO+['issuer_candidate','issuer_time_status']],on=GEO,validate='one_to_one')
        attempts=pd.DataFrame(sources['attempts'])
        for name,table in (('validacoes',frame),('unidades',units),('novas_tentativas',attempts)):export_frame(con,table,destination/name)
        write_json(destination/'politica_executada.json',dict(trust_manifest=policy,allow_fetching=False,system_trust_store=False,
            path_only_revocation_rule='NO_CHECK, sem promover êxito a status de revogação',strict_revocation_rule='CRL_REQUIRED em ponta e intermediários',
            retroactive_revinfo=False,time_tolerance_seconds=0,time_claim='Hipóteses UTC e limites de fuso, não carimbo autenticado nem prova contínua de revogação em todo o intervalo'))
        summary=dict(sections=len(turns)//2,section_turns=len(turns),scenarios=len(frame),anchors_supplied=len(anchors),intermediates_supplied=len(intermediates),crls_supplied=len(crls),
            path_statuses=records(frame.groupby('path_status').size().reset_index(name='scenarios')),
            revocation_statuses=records(frame.groupby('revocation_status').size().reset_index(name='scenarios')),
            new_source_attempts=len(attempts),new_http_403=int(attempts.http_status.eq(403).sum()),previous_source_attempts=len(old['attempts']),
            issuer_period_outside=int(units.issuer_time_status.eq('fora_do_intervalo_de_validade').sum()),
            environment={n:version(n) for n in ('pyhanko-certvalidator','asn1crypto','cryptography')},source_hashes=raw_hashes,object_notes=object_notes,
            interpretation='Validação de caminho completo implementada com backend PKIX e adaptador Ed521, testada com cadeias sintéticas. Resultados reais permanecem inconclusivos sem âncoras/emissores. Nenhum êxito em dados de teste é atribuído à amostra; hipóteses de horário não são prova de tempo ou de confiança.')
        from .audit_pkix_report import render
        render(destination,summary,frame,units,attempts)
        return finish(source,destination,state,summary,[Path(__file__),Path(__file__).with_name('pkix_path.py'),Path(__file__).with_name('audit_pkix_report.py')])
    except Exception as exc:failed(destination,state,exc);raise
    finally:con.close()
