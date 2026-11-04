"""Conferência documental e criptográfica de vínculos, com caminho incompleto."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
import duckdb,pandas as pd
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from .analysis import export_frame
from .national_common import begin,finish,failed,records
from .sources import sha256,write_json
from .audit_signature import parse_vsc,certificate
from .certificate_chain import issuer_binding,assess_crl,extension

GEO=['year','turn','uf','municipality','zone','section']


def run_chain(source,data='data',destination=None):
    source=Path(source).resolve();data=Path(data).resolve();sources=data/'auditoria/cadeia/v1'
    destination=Path(destination).resolve() if destination else source/'auditoria/cadeia'
    names=['auditoria/documentos/inventario.parquet','auditoria/amostra/turnos.parquet','auditoria/ed521/manifesto.json',
           'auditoria/ed521_referencia/manifesto.json','auditoria/assinaturas/manifesto.json']
    source,destination,state=begin(source,destination,names);con=duckdb.connect()
    try:
        sources_manifest=json.loads((sources/'manifesto.json').read_text(encoding='utf8'))
        for name,digest in sources_manifest.items():
            if sha256(sources/name)!=digest:raise ValueError('Fonte local alterada: '+name)
        provenance=json.loads((sources/'fontes.json').read_text(encoding='utf8'))
        if provenance['anchors_trusted']:raise ValueError('Esta versão não promove âncoras automaticamente')
        candidates=[];ca_rows=[]
        for entry in provenance['candidates']:
            ca,info=certificate((sources/entry['file']).read_bytes())
            if info['sha256']!=entry['der_sha256']:raise ValueError('Certificado candidato diferente da versão registrada')
            candidates.append((entry,ca,info))
            ca_rows.append(dict(name=entry['name'],der_sha256=info['sha256'],not_before=info['not_before'],not_after=info['not_after'],
                issuer_cn=info['issuer_cn'],key_oid=info['key_oid'],source=entry['origin'],trust_anchor=False,
                basic_constraints_critical=ca.extensions.get_extension_for_class(x509.BasicConstraints).critical,
                key_usage_critical=ca.extensions.get_extension_for_class(x509.KeyUsage).critical))
        # Ler somente objetos obtidos; páginas de erro nunca são tratadas como LCR.
        crls=[]
        for attempt in provenance['attempts']:
            if attempt['kind']=='crl' and attempt.get('saved_file'):
                raw=(sources/attempt['saved_file']).read_bytes()
                try:crl=x509.load_pem_x509_crl(raw) if raw.startswith(b'-----BEGIN') else x509.load_der_x509_crl(raw)
                except ValueError:continue
                crls.append(crl)
        inventory=con.read_parquet(str(source/names[0])).df();turns=con.read_parquet(str(source/names[1])).df();rows=[]
        for turn in turns.to_dict('records'):
            key={k:turn[k] for k in GEO};part=inventory
            for k,v in key.items():part=part.loc[part[k].eq(v)]
            signature=part.loc[part.kind.eq('assinatura')]
            if len(signature)!=1:raise ValueError('VSC ausente ou repetido')
            record=signature.iloc[0];path=(data/record['path']).resolve()
            if not path.is_relative_to(data) or sha256(path)!=record['sha256']:raise ValueError('Original local alterado')
            obj=parse_vsc(path.read_bytes());leaf,info=certificate(obj['hw']['certificate']);stamp=obj['hw']['created']
            choices=[(entry,ca,ci) for entry,ca,ci in candidates if ca.subject==leaf.issuer]
            row=dict(**key,leaf_sha256=info['sha256'],leaf_issuer=info['issuer_cn'],signed_at=stamp,vsc_sha256=record['sha256'],
                path_status='incompleto_sem_ancora',root_verified=False,revocation_status='indeterminado_lcr_nao_obtida',
                aia_present=extension(leaf,x509.AuthorityInformationAccess) is not None)
            if len(choices)!=1:row.update(signature_status='candidato_ausente_ou_ambiguo',issuer_candidate=None)
            else:
                entry,ca,ci=choices[0];row.update(issuer_binding(leaf,ca,stamp));row.update(issuer_candidate=entry['name'],issuer_sha256=ci['sha256'],issuer_not_before=ci['not_before'],issuer_not_after=ci['not_after'])
                matching=[c for c in crls if c.issuer==ca.subject]
                if len(matching)==1:
                    # Sem fuso autenticado, não promover um resultado pontual de LCR a status definitivo.
                    moment=datetime.strptime(stamp,'%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc)
                    row['crl_point_observation']=assess_crl(leaf,ca,matching[0],moment)
                    row['revocation_status']='indeterminado_sem_validacao_historica_e_fuso'
                else:row['revocation_status']='indeterminado_lcr_nao_obtida' if not matching else 'indeterminado_lcr_ambigua'
            rows.append(row)
        links=pd.DataFrame(rows);cas=pd.DataFrame(ca_rows);attempts=pd.DataFrame(provenance['attempts'])
        pending=links.loc[links.issuer_time_status.eq('fora_do_intervalo_de_validade')].copy()
        for name,frame in (('vinculos',links),('intermediarios',cas),('tentativas',attempts),('pendencias_vigencia',pending)):export_frame(con,frame,destination/name)
        write_json(destination/'fontes_resumo.json',dict(package_sha256=provenance['package_sha256'],origin=provenance['package_origin'],
            candidates=provenance['candidates'],anchors_trusted=provenance['anchors_trusted'],source_manifest_sha256=sha256(sources/'manifesto.json')))
        summary=dict(sections=len(turns)//2,section_turns=len(turns),unique_leaf_certificates=int(links.leaf_sha256.nunique()),candidate_intermediates=len(cas),
            certificate_signatures_match=int(links.signature_status.eq('confere_com_candidato').sum()),issuer_period_compatible=int(links.issuer_time_status.eq('compativel_em_todos_os_fusos_considerados').sum()),
            issuer_period_outside=int(links.issuer_time_status.eq('fora_do_intervalo_de_validade').sum()),complete_paths_verified=0,
            revocation_obtained_crls=len(crls),revocation_statuses=records(links.groupby('revocation_status').size().reset_index(name='section_turns')),
            access_attempts=len(attempts),http_200=int(attempts.http_status.eq(200).sum()),tls_errors=int(attempts.error_type.eq('SSLError').sum()),
            source_manifest_sha256=sha256(sources/'manifesto.json'),sources_hashes=sources_manifest,
            interpretation='Conferência de um vínculo até intermediário candidato, não validação integral RFC 5280. Nenhuma âncora promovida. Vigência incompatível do candidato disponível é pendência documental, sem inferir renovação, causa ou irregularidade nos votos. LCR não obtida não significa ausência de revogação.')
        from .audit_chain_report import render
        render(destination,summary,links,cas,attempts,pending)
        return finish(source,destination,state,summary,[Path(__file__),Path(__file__).with_name('certificate_chain.py'),Path(__file__).with_name('audit_chain_report.py')])
    except Exception as exc:failed(destination,state,exc);raise
    finally:con.close()
