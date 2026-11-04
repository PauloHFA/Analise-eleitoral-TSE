"""Executa a conferência das assinaturas preservando a primeira entrega amostral."""
from pathlib import Path
import json
import hashlib
import platform
from importlib.metadata import version
import duckdb
import pandas as pd
from .analysis import export_frame
from .national_common import begin,finish,failed,records
from .sources import sha256,write_json
from .audit_signature import LAYOUT_ID,SCHEMA,parse_vsc,certificate,temporal_status,hash_status,verify_signature

GEO=['year','turn','uf','municipality','zone','section']


def run_signatures(source,data='data',destination=None,*,enable_ed521=False):
    source=Path(source).resolve();data=Path(data).resolve()
    destination=Path(destination).resolve() if destination else source/('auditoria/ed521' if enable_ed521 else 'auditoria/assinaturas')
    names=['auditoria/documentos/inventario.parquet','auditoria/documentos/manifesto.json',
           'auditoria/amostra/turnos.parquet','auditoria/amostra/secoes.parquet',
           'auditoria/conferencia/manifesto.json','auditoria/relatorio/manifesto.json']
    if enable_ed521:names+=['auditoria/assinaturas/manifesto.json']
    source,destination,state=begin(source,destination,names);con=duckdb.connect();file_rows=[];envelopes=[];certs=[];units=[]
    try:
        inventory=con.read_parquet(str(source/names[0])).df()
        turns=con.read_parquet(str(source/names[2])).df()
        sample=con.read_parquet(str(source/names[3])).df()
        if inventory.duplicated(GEO+['kind']).any():raise ValueError('Inventário duplicado')
        for item in inventory.to_dict('records'):
            if item['status']!='obtido':raise ValueError('Documento não obtido nesta versão da amostra')
            p=(data/item['path']).resolve()
            if not p.is_relative_to(data) or sha256(p)!=item['sha256']:raise ValueError('Original local fora da pasta ou alterado')
        for case in turns.to_dict('records'):
            key={k:case[k] for k in GEO};rows=inventory
            for k,v in key.items():rows=rows.loc[rows[k].eq(v)]
            signature=rows.loc[rows.kind.eq('assinatura')]
            unit=dict(**key,layout=LAYOUT_ID,status='leitura_limitada',reason=None)
            try:
                if len(signature)!=1:raise ValueError('Assinatura ausente ou duplicada')
                signature=signature.iloc[0];raw=(data/signature['path']).read_bytes();obj=parse_vsc(raw)
                prefix=f'o{3220 if case["turn"]==1 else 3221:05}{case["uf"].lower()}{int(case["municipality"]):05}{int(case["zone"]):04}{int(case["section"]):04}-'
                lookup={r['member']:r for r in rows.loc[rows.kind.ne('assinatura')].to_dict('records')}
                if len(lookup)!=4:raise ValueError('Inventário não contém os quatro documentos únicos previstos')
                hw=obj['hw'];cert=None;cert_info=None;cert_reason=None
                try:cert,cert_info=certificate(hw.get('certificate',b''))
                except Exception as exc:cert_reason=f'{type(exc).__name__}: {exc}'
                cert_row=dict(**key,status='extraido' if cert_info else 'leitura_limitada',reason=cert_reason,
                    chain_status='nao_validada',revocation_status='nao_consultada',time_status=temporal_status(cert,hw['created']) if cert else 'inconclusivo',
                    signed_at=hw['created'],**(cert_info or {}))
                certs.append(cert_row)
                signatures={}
                for role in ('sw','hw'):
                    ent=obj[role];alg=ent['auto']['algorithm']['algorithm'];dig=ent['auto']['signature']
                    crypto,reason=verify_signature(cert if role=='hw' else None,alg,dig['hash'],dig['signature'],enable_ed521=enable_ed521)
                    envelopes.append(dict(**key,role=role,created=ent['created'],algorithm=alg,
                        hash_status=hash_status(ent['payload'],dig['hash']),crypto_status=crypto,crypto_reason=reason,
                        signed_files=len(ent['files']),signature_sha256=signature['sha256'],certificate_sha256=(cert_info or {}).get('sha256')))
                    signatures[role]={}
                    for signed in ent['files']:
                        name=signed['name']
                        if not name.startswith(prefix):raise ValueError('Arquivo assinado pertence a outra unidade/turno')
                        signatures[role][name]=signed['signature']['hash']
                        actual=lookup.get(name);digest=signed['signature']['hash']
                        if actual:
                            content=(data/actual['path']).read_bytes();digest_state=hash_status(content,digest)
                            crypto,reason=verify_signature(cert if role=='hw' else None,alg,digest,signed['signature']['signature'],enable_ed521=enable_ed521)
                        else:digest_state='fora_do_escopo';crypto='nao_verificado_fora_escopo';reason='Documento não obtido na amostra de cinco tipos'
                        file_rows.append(dict(**key,role=role,member=name,kind=actual['kind'] if actual else None,
                            scope='documento_obtido' if actual else 'nao_obtido_no_escopo',signed_sha512=digest.hex(),
                            local_sha512=hashlib.sha512(content).hexdigest() if actual else None,
                            local_sha256=actual['sha256'] if actual else None,hash_status=digest_state,
                            crypto_status=crypto,crypto_reason=reason,algorithm=alg))
                    if not set(lookup).issubset(signatures[role]):raise ValueError('Documento obtido não consta da lista assinada')
                disagreements=sum(signatures['sw'][name]!=signatures['hw'][name] for name in signatures['sw'])
                unit.update(status='lido',model=obj['platform']['model'],hardware_algorithm=obj['platform']['algorithm'],
                    sw_hw_digest_differences=disagreements,selected_documents=len(lookup),signature_sha256=signature['sha256'])
            except Exception as exc:unit['reason']=f'{type(exc).__name__}: {exc}'
            units.append(unit)
        frames={'arquivos_assinados':pd.DataFrame(file_rows),'envelopes':pd.DataFrame(envelopes),
                'certificados':pd.DataFrame(certs),'unidades':pd.DataFrame(units)}
        for name,frame in frames.items():export_frame(con,frame,destination/name)
        selected=frames['arquivos_assinados'].loc[lambda f:f.scope.eq('documento_obtido')]
        summary=dict(sections=len(sample),section_turns=len(turns),read_units=int(frames['unidades'].status.eq('lido').sum()),
            observed_layout=LAYOUT_ID,layout_authority='Adaptação explícita ao layout observado, não homologada nem obtida como especificação oficial do TSE',
            layout_sha256=hashlib.sha256(SCHEMA.encode()).hexdigest(),listed_file_entries=len(frames['arquivos_assinados']),
            selected_file_checks=len(selected),outside_scope_entries=int(frames['arquivos_assinados'].scope.ne('documento_obtido').sum()),
            file_hash_statuses=records(selected.groupby('hash_status').size().reset_index(name='checks')),
            envelope_hash_statuses=records(frames['envelopes'].groupby('hash_status').size().reset_index(name='checks')),
            file_crypto_statuses=records(selected.groupby(['role','algorithm','crypto_status']).size().reset_index(name='checks')),
            envelope_crypto_statuses=records(frames['envelopes'].groupby(['role','algorithm','crypto_status']).size().reset_index(name='checks')),
            certificate_statuses=records(frames['certificados'].groupby(['status','time_status','chain_status']).size().reset_index(name='certificates')),
            models=records(frames['unidades'].groupby(['model','hardware_algorithm']).size().reset_index(name='section_turns')),
            environment=dict(python=platform.python_version(),packages={n:version(n) for n in ('asn1tools','cryptography','duckdb','pandas')}),
            interpretation=('ECDSA e Ed521 verificados somente com a chave embutida; CEPESC, cadeia e revogação não verificados. Data declarada não é carimbo de tempo autenticado. Sem conclusão de auditoria integral ou causalidade eleitoral.' if enable_ed521 else 'Integridade SHA512 separada de assinatura criptográfica. ECDSA verificada somente com a chave embutida, sem cadeia/revogação. Ed521 e CEPESC não verificados; data do VSC não é carimbo de tempo autenticado. Sem conclusão de auditoria integral ou causalidade eleitoral.'))
        (destination/'layout_observado.asn1').write_text(SCHEMA,encoding='utf8')
        if enable_ed521:
            from .audit_ed521_report import render
            from .ed521_reference import reference_metadata
            summary['ed521_reference']=reference_metadata()
        else:
            from .audit_signature_report import render
        render(destination,summary,frames,sample)
        code_files=[Path(__file__),Path(__file__).with_name('audit_signature.py'),Path(__file__).with_name('audit_ed521_report.py' if enable_ed521 else 'audit_signature_report.py')]
        if enable_ed521:code_files+=[Path(__file__).with_name('ed521.py'),Path(__file__).with_name('ed521_reference.py')]
        return finish(source,destination,state,summary,code_files)
    except Exception as exc:failed(destination,state,exc);raise
    finally:con.close()
