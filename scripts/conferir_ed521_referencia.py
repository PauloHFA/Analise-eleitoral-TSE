"""Compara o verificador de produção com Noble configurado separadamente.

Não escreve nas entregas anteriores; não usa rede e não publica dados de votos.
"""
import argparse
from pathlib import Path
import hashlib,json,subprocess
import duckdb,pandas as pd
from eleicoes.sources import sha256
from eleicoes.national_common import begin,finish,failed
from eleicoes.analysis import export_frame
from eleicoes.audit_signature import parse_vsc,certificate
from eleicoes.ed521_reference import reference_metadata
from eleicoes import ed521


def run(source,data,destination=None):
    source=Path(source).resolve();data=Path(data).resolve();root=Path(__file__).resolve().parents[1]
    destination=Path(destination).resolve() if destination else source/'auditoria/ed521_referencia'
    names=['auditoria/ed521/manifesto.json','auditoria/documentos/inventario.parquet']
    source,destination,state=begin(source,destination,names);con=duckdb.connect()
    try:
        reference=reference_metadata();inventory=con.read_parquet(str(source/names[1])).df();cases=[];metadata=[]
        for row in inventory.loc[inventory.kind.eq('assinatura')].to_dict('records'):
            raw=(data/row['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('VSC original alterado')
            obj=parse_vsc(raw)
            if obj['platform']['algorithm']!=4:continue
            cert,_=certificate(obj['hw']['certificate']);key=ed521.public_key_from_certificate(cert)
            selected=inventory
            for k in ('year','turn','uf','municipality','zone','section'):selected=selected.loc[selected[k].eq(row[k])]
            members=set(selected.member)
            signatures=[('lista_hw',row['member'],obj['hw']['auto']['signature'])]
            signatures += [('documento',r['name'],r['signature']) for r in obj['hw']['files'] if r['name'] in members]
            for kind,member,dig in signatures:
                msg=hashlib.sha512(dig['hash']).digest()
                for mutation in (False,True):
                    test_msg=bytes([msg[0]^1])+msg[1:] if mutation else msg
                    cases.append(dict(public_key=key.hex(),message=test_msg.hex(),signature=dig['signature'].hex(),context=''))
                    metadata.append(dict(**{k:row[k] for k in ('year','turn','uf','municipality','zone','section')},member=member,kind=kind,
                        mutation='mensagem_alterada' if mutation else 'original',expected=not mutation,
                        python_result=ed521.verify(key,test_msg,dig['signature']),key_sha256=hashlib.sha256(key).hexdigest(),
                        message_sha256=hashlib.sha256(test_msg).hexdigest(),signature_sha256=hashlib.sha256(dig['signature']).hexdigest()))
        command=['node',str(root/'scripts/ed521_reference/reference.mjs'),'verify']
        completed=subprocess.run(command,input=json.dumps(cases),text=True,encoding='utf8',capture_output=True,check=True,timeout=120)
        results=json.loads(completed.stdout)
        if len(results)!=len(metadata):raise ValueError('Cobertura diferente na referência')
        for r,answer in zip(metadata,results):r['reference_result']=answer;r['agreement']=r['python_result']==answer;r['expected_result']=r['python_result']==r['expected'] and answer==r['expected']
        frame=pd.DataFrame(metadata)
        if not frame.agreement.all() or not frame.expected_result.all():raise ValueError('Divergência com a referência; não promover resultados')
        export_frame(con,frame,destination/'comparacao')
        # Fronteira intencional: Noble verifica a equação cofatada; produção exige subgrupo.
        point=ed521.add(ed521.BASE,(0,ed521.P-1,1,0));x,y,z,_=point;inv=pow(z,ed521.P-2,ed521.P)
        key=((y*inv%ed521.P)|(((x*inv%ed521.P)&1)<<527)).to_bytes(66,'little');r=(1).to_bytes(66,'little');msg=b'controlled subgroup policy'
        scalar=int.from_bytes(hashlib.shake_256(b'SigEd521\x00\x00'+r+key+msg).digest(132),'little')%ed521.L
        sig=r+scalar.to_bytes(66,'little')
        policy_case=dict(public_key=key.hex(),message=msg.hex(),signature=sig.hex(),context='')
        completed=subprocess.run(command,input=json.dumps([policy_case]),text=True,encoding='utf8',capture_output=True,check=True,timeout=30)
        policy_reference=json.loads(completed.stdout)[0];policy_python=ed521.verify(key,msg,sig)
        if policy_python or not policy_reference:raise ValueError('Fronteira de política diferente da esperada')
        installed=root/'scripts/ed521_reference/node_modules/@noble'
        package_versions={n:json.loads((installed/n/'package.json').read_text(encoding='utf8'))['version'] for n in ('curves','hashes')}
        if set(package_versions.values())!={'2.4.0'}:raise ValueError('Versão instalada da referência diferente da fixada')
        summary=dict(status='concluído',original_checks=int(frame.mutation.eq('original').sum()),mutated_checks=int(frame.mutation.eq('mensagem_alterada').sum()),
            comparisons=len(frame),agreement_checks=int(frame.agreement.sum()),expected_checks=int(frame.expected_result.sum()),reference=reference,
            installed_versions=package_versions,reference_command='node scripts/ed521_reference/reference.mjs verify',
            policy_boundary=dict(python_result=policy_python,noble_result=policy_reference,expected_difference=True,
                explanation='Chave com componente de torção: a equação cofatada aceita; a política estrita de subgrupo rejeita. Não é caso da amostra.'),
            interpretation='Comparação de duas implementações configuradas para o mesmo perfil. Não são vetores oficiais nem certificação; não valida cadeia ou revogação.')
        return finish(source,destination,state,summary,[Path(__file__),root/'src/eleicoes/ed521.py',root/'scripts/ed521_reference/reference.mjs'])
    except Exception as exc:failed(destination,state,exc);raise
    finally:con.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='outputs/2026');p.add_argument('--data',default='data');p.add_argument('--dest');a=p.parse_args()
    print(json.dumps(run(a.output,a.data,a.dest),ensure_ascii=False,indent=2))
