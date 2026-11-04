"""Conferência agregada, sem exportar votos individuais do RDV."""
from collections import Counter
from pathlib import Path
import re
import duckdb
import pandas as pd
import asn1tools
from .analysis import export_frame
from .national_common import begin,finish,failed,records
from .sources import sha256,write_json

GEO=['year','turn','uf','municipality','zone','section']
SCHEMA_HASHES={'bu': 'e53e28e9812bb7e19cc4bcc77b6ce48f25c413f62a60369a91c4f269e19b7ed6', 'rdv': '282dcde0c7ba1f1bb128fe27443ad8d18f7490416c9546d033910a7ec557a465', 'assinatura': '66dfa7bcb79f31b2d6a4d1427dc0e1d1b7134aba83fb62c496713a4ac2c7e083'}


def decode_strict(codec,name,data):
    obj,length=codec.decode_with_length(name,data,check_constraints=True)
    if length!=len(data):raise ValueError('Bytes adicionais após a entidade ASN.1')
    return obj


def identity(obj,expected):
    mz=obj['municipioZona']
    got=(str(mz['municipio']),str(mz['zona']),str(obj['secao']))
    want=tuple(str(expected[k]) for k in ('municipality','zone','section'))
    if got!=want:raise ValueError('Identificação territorial do conteúdo diferente da amostra')


def compare_values(values):
    known=[v for v in values if v is not None]
    complete=len(known)==len(values)
    return ('divergencia_de_valores' if len(set(known))>1 else 'concordante' if complete else 'comparacao_limitada'),complete


def rdv_counts(obj,expected):
    rdv=obj['rdv'];identity(rdv['identificacao'],expected)
    if rdv['fase']!=2:raise ValueError('RDV não oficial')
    election_id=int(expected['election_id'])
    elections=[e for e in rdv['eleicoes'][1] if e['idEleicao']==election_id]
    if len(elections)!=1:raise ValueError('Eleição ausente ou duplicada no RDV')
    cargos=[c for c in elections[0]['votosCargos'] if c['idCargo']==('cargoConstitucional',1)]
    if len(cargos)!=1 or cargos[0]['quantidadeEscolhas']!=1:raise ValueError('Cargo presidencial ausente, repetido ou com escolhas incompatíveis')
    out=Counter()
    for vote in cargos[0]['votos']:
        kind=vote['tipoVoto']
        if kind==2:
            digits=vote.get('digitacao','')
            if not re.fullmatch(r'\d{2}',digits):raise ValueError('Voto nominal presidencial sem número válido')
            candidate=int(digits)
            if candidate in (95,96):raise ValueError('Número nominal conflita com categoria de exportação')
        elif kind in (3,5):candidate=95
        elif kind in (4,6,7,8,9):candidate=96
        else:raise ValueError('Tipo de voto presidencial não suportado')
        out[candidate]+=1
    return out


def bu_counts(obj,expected):
    identity(obj['identificacaoSecao'],expected)
    if obj['fase']!=2:raise ValueError('BU não oficial')
    elections=[e for e in obj['resultadosVotacaoPorEleicao'] if e['idEleicao']==int(expected['election_id'])]
    if len(elections)!=1:raise ValueError('Eleição ausente ou duplicada no BU')
    election=elections[0];results=[];attendance=[]
    for result in election['resultadosVotacao']:
        cargos=[c for c in result['totaisVotosCargo'] if c['codigoCargo']==('cargoConstitucional',1)]
        for cargo in cargos:results.append(cargo);attendance.append(result['qtdComparecimento'])
    if len(results)!=1:raise ValueError('Cargo presidencial ausente ou duplicado no BU')
    out=Counter()
    for row in results[0]['votosVotaveis']:
        kind=row['tipoVoto'];value=row['quantidadeVotos']
        if kind==1:
            candidate=row['identificacaoVotavel']['codigo']
            if candidate in (95,96):raise ValueError('Número nominal conflita com categoria de exportação')
        elif kind==2:candidate=95
        elif kind==3:candidate=96
        else:raise ValueError('Tipo de voto presidencial não suportado')
        if candidate in out:raise ValueError('Votável repetido no BU')
        if value<0:raise ValueError('Contagem negativa no BU')
        out[candidate]=value
    return out,dict(aptos=election['qtdEleitoresAptos'],attendance=attendance[0],generation=obj['cabecalho']['dataGeracao'],
                    software_version=obj['urna']['versaoVotacao'])


def image_counts(content,expected):
    # Limitar ao texto anterior ao BU DIGITAL; os bytes seguintes contêm QR/imagem.
    text=content.decode('latin1').split('BU DIGITAL',1)[0]
    def one(pattern,source=text):
        found=re.findall(pattern,source,re.M)
        if len(found)!=1:raise ValueError('Campo da imagem ausente ou ambíguo: '+pattern)
        return int(found[0])
    if one(r'^Município\s+(\d+)\s*$')!=int(expected['municipality']):raise ValueError('Município da imagem diferente')
    if one(r'^Zona Eleitoral\s+(\d+)\s*$')!=int(expected['zone']):raise ValueError('Zona da imagem diferente')
    if one(r'^Seção Eleitoral\s+(\d+)\s*$')!=int(expected['section']):raise ValueError('Seção da imagem diferente')
    if len(re.findall(r'^-+PRESIDENTE-+\s*$',text,re.M))!=1:raise ValueError('Bloco presidencial da imagem ausente ou repetido')
    block=re.split(r'^-+PRESIDENTE-+\s*$',text,flags=re.M)[1]
    rows=re.findall(r'^  \S[^\r\n]*?\s+(\d{2})\s+(\d{4})\s*$',block,re.M)
    out=Counter()
    for number,value in rows:
        candidate=int(number)
        if candidate in out or candidate in (95,96):raise ValueError('Votável inválido ou repetido na imagem')
        out[candidate]=int(value)
    out[95]=one(r'^Brancos\s+(\d+)\s*$',block);out[96]=one(r'^Nulos\s+(\d+)\s*$',block)
    nominal=one(r'^Total de votos Nominais\s+(\d+)\s*$',block)
    total=one(r'^Total Apurado\s+(\d+)\s*$',block)
    if sum(v for k,v in out.items() if k not in (95,96))!=nominal or sum(out.values())!=total:raise ValueError('Extração da imagem não reconcilia seus totais')
    return out,dict(aptos=one(r'^Eleitores aptos\s+(\d+)\s*$',block),attendance=total)


def run_count(source,data='data',schema=None,destination=None):
    source=Path(source).resolve();data=Path(data).resolve()
    spec=Path(schema).resolve() if schema else data/'auditoria/documentacao/spec-v2'
    destination=Path(destination).resolve() if destination else source/'auditoria/conferencia'
    names=['auditoria/amostra/turnos.parquet','auditoria/amostra/secoes.parquet','auditoria/amostra/manifesto.json',
           'auditoria/documentos/inventario.parquet','auditoria/documentos/manifesto.json','conferencia_bu.parquet']
    source,destination,state=begin(source,destination,names);con=duckdb.connect();checks=[];counts=[];unit_metadata=[]
    try:
        codecs={};specs={}
        for name in ('bu','rdv','assinatura'):
            path=spec/(name+'.asn1');digest=sha256(path)
            if digest!=SCHEMA_HASHES[name]:raise ValueError('Especificação diferente da versão revisada: '+name)
            specs[name]=dict(sha256=digest,bytes=path.stat().st_size)
            codecs[name]=asn1tools.compile_files(str(path),codec='ber',numeric_enums=True)
        turns=con.execute('SELECT * FROM read_parquet(?)',[str(source/names[0])]).df()
        inventory=con.execute('SELECT * FROM read_parquet(?)',[str(source/names[3])]).df()
        con.register('sample_turns',turns[GEO])
        reference=con.execute('SELECT b.* FROM read_parquet(?) b JOIN sample_turns USING(year,turn,uf,municipality,zone,section)',[str(source/'conferencia_bu.parquet')]).df()
        if reference.duplicated(GEO+['candidate']).any():raise ValueError('Referência nominal duplicada')
        for expected in turns.to_dict('records'):
            key={k:expected[k] for k in GEO};mask=pd.Series(True,index=inventory.index)
            base_mask=pd.Series(True,index=reference.index)
            for k,v in key.items():mask&=inventory[k].eq(v);base_mask&=reference[k].eq(v)
            docs=inventory.loc[mask];base=reference.loc[base_mask]
            valid_reference=bool(expected['installed'] and expected['has_votes'] and len(base))
            extracted={};metadata={};results={}
            for kind in ('rdv','bu','imagem','assinatura','log'):
                rows=docs.loc[docs.kind.eq(kind)]
                check=dict(**key,kind=kind,status='limitado',reason=None,path=None,sha256=None)
                try:
                    if len(rows)!=1 or rows.iloc[0]['status']!='obtido':raise ValueError('Documento não obtido de forma única')
                    row=rows.iloc[0];path=(data/row['path']).resolve()
                    if not path.is_relative_to(data):raise ValueError('Caminho fora da pasta de dados')
                    if sha256(path)!=row['sha256']:raise ValueError('Original local alterado após obtenção')
                    check.update(path=row['path'],sha256=row['sha256'])
                    content=path.read_bytes()
                    if kind=='rdv':
                        obj=decode_strict(codecs['rdv'],'EntidadeResultadoRDV',content)
                        extracted[kind]=rdv_counts(obj,expected);check['status']='recontado'
                        metadata[kind]=dict(generation=obj['cabecalho']['dataGeracao'],pleito=obj['rdv']['pleito'])
                    elif kind in ('bu','imagem'):
                        envelope=decode_strict(codecs['bu'],'EntidadeEnvelopeGenerico',content)
                        if envelope['fase']!=2 or envelope.get('seguranca'):raise ValueError('Envelope não oficial ou cifrado não suportado')
                        if kind=='bu':
                            obj=decode_strict(codecs['bu'],'EntidadeBoletimUrna',envelope['conteudo'])
                            extracted[kind],metadata[kind]=bu_counts(obj,expected)
                        else:extracted[kind],metadata[kind]=image_counts(envelope['conteudo'],expected)
                        metadata[kind]['pleito']=envelope['cabecalho']['idEleitoral'][1]
                        check['status']='extraido'
                    elif kind=='assinatura':
                        decode_strict(codecs['assinatura'],'EntidadeAssinaturaEcourna',content)
                        check.update(status='nao_verificado',reason='Decodificação não equivale a validação criptográfica; cadeia e assinatura ainda não verificadas')
                    else:check.update(status='preservado',reason='Log preservado por hash; conteúdo/eventos não analisados')
                except Exception as exc:check['reason']=f'{type(exc).__name__}: {exc}'
                checks.append(check);results[kind]=check['status']
            if extracted:
                all_candidates=set(base.candidate.astype(int)) if valid_reference else set()
                for values in extracted.values():all_candidates.update(values)
                all_candidates.update([95,96])
                for candidate in sorted(all_candidates):
                    refs=base.loc[base.candidate.eq(candidate)]
                    br=refs.iloc[0] if len(refs)==1 else None
                    result_votes=(int(br.votes_result) if br is not None and pd.notna(br.votes_result) else 0 if valid_reference and br is None else None)
                    bu_csv=(int(br.votes_bu) if br is not None and pd.notna(br.votes_bu) else 0 if valid_reference and br is None else None)
                    values={name:(int(extracted[name][candidate]) if name in extracted else None) for name in ('rdv','bu','imagem')}
                    known=list(values.values())+[result_votes,bu_csv]
                    status,complete=compare_values(known)
                    counts.append(dict(**key,candidate=candidate,rdv_votes=values['rdv'],binary_bu_votes=values['bu'],image_votes=values['imagem'],
                        result_votes=result_votes,csv_bu_votes=bu_csv,reference_row_present=br is not None,
                        result_source=br.result_source if br is not None else None,bu_source=br.bu_source if br is not None else None,
                        comparison_complete=complete,status=status))
            for kind,values in metadata.items():
                if 'pleito' in values:
                    expected_pleito=3220 if int(expected['turn'])==1 else 3221
                    if values['pleito']!=expected_pleito:raise ValueError('Pleito não corresponde ao turno')
            meta=dict(**key)
            for kind in ('bu','imagem'):
                values=metadata.get(kind,{})
                meta[kind+'_aptos']=values.get('aptos');meta[kind+'_attendance']=values.get('attendance')
                meta[kind+'_generation']=values.get('generation')
            meta['software_version']=metadata.get('bu',{}).get('software_version')
            unit_metadata.append(meta)
        documents=pd.DataFrame(checks);votes=pd.DataFrame(counts)
        export_frame(con,documents,destination/'documentos');export_frame(con,votes,destination/'votacao')
        if len(documents)!=len(turns)*5:raise ValueError('Conferência não cobriu o inventário inteiro')
        comparisons=[]
        for key,group in votes.groupby(GEO):
            compare=turns
            for k,v in zip(GEO,key):compare=compare.loc[compare[k].eq(v)]
            expected=compare.iloc[0]
            unit=dict(zip(GEO,key));unit['vote_status']='concordante' if group.status.eq('concordante').all() else 'divergencia_de_valores' if group.status.eq('divergencia_de_valores').any() else 'comparacao_limitada'
            for col in ('rdv_votes','binary_bu_votes','image_votes','result_votes','csv_bu_votes'):
                unit[col+'_total']=int(group[col].sum()) if group[col].notna().all() else None
            unit['reference_attendance']=int(expected.attendance);unit['reference_aptos']=int(expected.aptos)
            unit['sum_matches_attendance']=unit['rdv_votes_total']==int(expected.attendance) and unit['binary_bu_votes_total']==int(expected.attendance) and unit['image_votes_total']==int(expected.attendance)
            comparisons.append(unit)
        # Incluir também unidades sem nenhuma extração, sem desaparecer do denominador.
        units=turns[GEO].merge(pd.DataFrame(comparisons),on=GEO,how='left').merge(pd.DataFrame(unit_metadata),on=GEO,how='left')
        units['vote_status']=units.vote_status.fillna('comparacao_limitada')
        units['sum_matches_attendance']=units.sum_matches_attendance.fillna(False)
        units['denominators_match']=units.bu_aptos.eq(units.reference_aptos)&units.imagem_aptos.eq(units.reference_aptos)&units.bu_attendance.eq(units.reference_attendance)&units.imagem_attendance.eq(units.reference_attendance)
        export_frame(con,units,destination/'unidades')
        summary=dict(sections=len(turns)//2,section_turns=len(turns),documents=len(documents),vote_rows=len(votes),
            document_statuses=records(documents.groupby(['kind','status']).size().reset_index(name='documents')),
            vote_statuses=records(votes.groupby('status').size().reset_index(name='rows')),
            unit_statuses=records(units.groupby('vote_status').size().reset_index(name='section_turns')),
            attendance_reconciled=int(units.sum_matches_attendance.sum()),denominators_reconciled=int(units.denominators_match.sum()),schemas=specs,
            interpretation='Conferência de totais presidenciais e integridade local. Assinaturas criptográficas, cadeia de confiança, eventos dos logs e papel independente não verificados. Concordância não explica escolhas individuais nem constitui auditoria integral.')
        return finish(source,destination,state,summary,[Path(__file__)])
    except Exception as exc:failed(destination,state,exc);raise
    finally:con.close()
