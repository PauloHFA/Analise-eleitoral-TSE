"""Pesquisa documental revisada: norma, cadastro e aplicação temporal separadas."""
from __future__ import annotations

from datetime import datetime, timezone
import html
import json
from pathlib import Path
from urllib.parse import urlparse

import duckdb

from .analysis import export_frame
from .pdf_layout import AnalysisPDF, WIDTH, heading, p, pdf_styles, table
from .sources import sha256, write_json


def project_candidate(payload):
    """Publica somente identificação e situação eleitoral necessárias à pesquisa."""
    fields = ('id','numero','nomeUrna','nomeCompleto','descricaoSituacao','descricaoTotalizacao',
              'dataUltimaAtualizacao','numeroProcesso','motivoSituacao')
    result={key:payload.get(key) for key in fields}
    result['cargo']={key:(payload.get('cargo') or {}).get(key) for key in ('codigo','nome')}
    result['eleicao']={key:(payload.get('eleicao') or {}).get(key) for key in ('id','ano')}
    result['partido']={key:(payload.get('partido') or {}).get(key) for key in ('numero','sigla')}
    return result


def assess(evidence, candidate):
    """Não usa atualização cadastral ou notícia como data de eficácia jurídica."""
    identity=(candidate.get('id'),candidate.get('numero'),candidate.get('cargo',{}).get('codigo'),
              candidate.get('eleicao',{}).get('ano'),candidate.get('eleicao',{}).get('id'))
    expected=(evidence['candidate_id'],evidence['candidate_number'],evidence['cargo_code'],evidence['year'],evidence['election_id'])
    if identity!=expected:
        raise ValueError('Candidatura não corresponde ao ID, cargo, número, ano e eleição revisados')
    sources={row['id']:row for row in evidence['sources']}
    if len(sources)!=len(evidence['sources']):
        raise ValueError('Identificador de fonte duplicado')
    for row in sources.values():
        host=urlparse(row['url']).hostname or ''
        if row['official'] and not (host=='tse.jus.br' or host.endswith('.tse.jus.br')):
            raise ValueError('Fonte marcada oficial fora do domínio eleitoral revisado')
    for role in ('norma_explicativa','norma_majoritaria','cadastro_individual'):
        if not any(row['official'] and row['kind']==role for row in sources.values()):
            raise ValueError(f'Fonte oficial ausente para {role}')
    if evidence.get('primary_act_obtained') or evidence.get('primary_act_effective_date'):
        raise ValueError('Um ato novo exige revisão documental própria; esta rotina não confirma automaticamente sua eficácia')
    if candidate.get('descricaoSituacao')!='Renúncia':
        raise ValueError('Situação cadastral diferente da pesquisa revisada; revisar as conclusões')
    return dict(normative_rule_status='identificada em fonte oficial',
        candidate_status='Renúncia confirmada no cadastro consultado',
        causal_assessment='compatível com renúncia; aplicação temporal não confirmada',
        primary_act_status='não obtido nesta pesquisa',
        persistence_status='não avaliada nesta pesquisa',
        cause_confirmed=False,registration_update_is_act_date=False)


def sections(summary, evidence, candidate):
    return [
        ('O que a pesquisa estabeleceu',[
            f"O guia oficial descreve nulos técnicos para candidaturas excluídas que permaneceram na urna por limitações do momento de carga. Esses votos podem constar da urna e do BU sem aparecer como votos nominais na divulgação. Fonte: guia.",
            'A Resolução-TSE 23.677/2021, art. 17, disciplina a totalização majoritária e a exclusão da chapa entre o fechamento do CAND e o dia da eleição. O inciso III trata da irregularidade decorrente da falta de substituição de componente falecido ou renunciante. Foi consultado o texto compilado, incluindo a redação de 2026. O art. 21 trata de eleições proporcionais e não fundamenta esta análise presidencial. Fonte: resolucao.',
            f"A consulta individual identifica {candidate['nomeCompleto']}, nome de urna {candidate['nomeUrna']}, número {candidate['numero']}, cargo Presidente, ano {candidate['eleicao']['ano']}, ID {candidate['id']}, com situação Renúncia. Fonte: cadastro. O painel também contém outro registro de número 28; número e partido isoladamente não identificam uma candidatura."]),
        ('Ligação com os arquivos analisados',[
            f"O dossiê anterior conferiu {summary['technical_votes']:,} votos em {summary['technical_units']:,} unidades município/zona do primeiro turno. Este incremento verificou que, em cada unidade, a diferença corresponde ao número {candidate['numero']}, com soma nominal oficial zero implícita na referência e compensação no campo de nulos técnicos. Não houve nova imputação ou alteração dos arquivos anteriores.".replace(',','.'),
            'A regra oficial e a situação cadastral oferecem uma explicação compatível para a classificação. Esse vínculo é uma inferência apoiada nas fontes e nos arquivos; não substitui o ato individual, sua data de eficácia e o histórico da chapa no pleito.',
            'As gerações diferentes dos arquivos permanecem documentadas no primeiro dossiê. Não foi demonstrado que expliquem a diferença nominal. As consultas atuais não reconstituem automaticamente o estado do cadastro na geração de cada arquivo.']),
        ('Cronologia e limite da prova',[
            'A Agência Brasil publicou em 30/09/2026 relato do anúncio público de desistência. A notícia oferece contexto temporal e não substitui documento processual da Justiça Eleitoral. Fonte: ebc.',
            f"O primeiro turno ocorreu em {evidence['election_date']}. O campo dataUltimaAtualizacao do cadastro consultado contém {candidate.get('dataUltimaAtualizacao')}. Esse campo não foi interpretado como data de apresentação, homologação ou eficácia da renúncia.",
            'O próprio guia ressalva que a renúncia após o pleito não produz o mesmo efeito na destinação dos votos. Por isso, a aplicação temporal precisa ser comprovada, além da consulta da situação atual. Fonte: guia.',
            f"Foi tentada a consulta pública do processo {evidence['process_number']}. O portal apresentou indisponibilidade e, depois, CAPTCHA. A consulta foi interrompida; nenhum ato individual foi obtido. A limitação de acesso e buscas sem resultado não comprovam inexistência do ato. Fonte: pje."]),
        ('O que permanece pendente',evidence['pending_questions']),
        ('Preservação e alcance',[
            'As seis capturas integrais foram preservadas localmente por SHA256, fora do Git e dos pacotes públicos. Os hashes identificam extrações Firecrawl, não os bytes originais do servidor. O download binário direto do guia retornou HTTP 403; a pesquisa utilizou a extração textual consultada, cujo extrator informou status 200.',
            'A distribuição contém metadados, síntese própria e projeção reduzida dos campos eleitorais do cadastro. A versão integral da resposta individual não é distribuída. Datas de captura, atualização cadastral, geração e atos jurídicos são conceitos distintos.',
            'O HTML, PDF, síntese e dossiê anteriores foram preservados por hash. Este relatório complementar não reclassifica automaticamente os casos como causa explicada ou divergência persistente. As lacunas com comparecimento zero e a auditoria de documentos das urnas permanecem em seus escopos próprios.'])]


def render(destination, summary, evidence, candidate):
    esc=lambda value:html.escape(str(value))
    chapters=sections(summary,evidence,candidate)
    rows=[['Regra sobre nulos técnicos','Identificada','guia; resolucao'],
          ['Candidatura de ID 280002554479','Renúncia no cadastro consultado','cadastro; painel'],
          ['Correspondência local com o candidato 28',f"{summary['technical_units']} unidades / {summary['technical_votes']} votos",'dossiê preservado'],
          ['Anúncio de desistência em 30/09/2026','Contexto jornalístico','ebc'],
          ['Ato individual e eficácia temporal','Pendentes','pje: acesso limitado'],
          ['Causa jurídica individual confirmada','Não confirmada nesta pesquisa','regra + cadastro não substituem o ato'],
          ['Persistência de divergência','Não avaliada','fora da conclusão deste incremento']]
    head=['Questão','Situação','Evidências']
    source_rows=''.join(f"<tr><th>{esc(s['id'])}</th><td><a href=\"{esc(s['url'])}\">{esc(s['title'])}</a><p>{esc(s['note'])}</p></td><td>{esc(s['kind'])}<br>{esc(s['captured_utc'])}<br><code>{esc(s['capture_sha256'])}</code></td></tr>" for s in evidence['sources'])
    body=''.join('<h2>'+esc(title)+'</h2>'+''.join('<p>'+esc(text)+'</p>' for text in texts) for title,texts in chapters)
    header=''.join('<th>'+esc(text)+'</th>' for text in head)
    matrix=''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)
    page=f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pesquisa documental — nulos técnicos — 2026</title><style>body{{font:16px/1.6 system-ui,sans-serif;max-width:1080px;margin:auto;padding:28px;color:#183447}}h1,h2{{line-height:1.25}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #cad6df;padding:10px;vertical-align:top;text-align:left}}th{{background:#edf4f7}}code{{overflow-wrap:anywhere}}.status{{background:#edf4f7;border-left:5px solid #12677a;padding:16px}}@media print{{body{{padding:0}}tr{{break-inside:avoid}}}}</style>
<h1>Pesquisa documental: por que esses votos podem ser nulos técnicos?</h1><p class="status"><strong>Regra identificada e situação Renúncia confirmada no cadastro. Aplicação temporal ao caso ainda não confirmada.</strong></p>
<p>Há uma explicação documental compatível para os {summary['technical_votes']} votos nas {summary['technical_units']} unidades. O ato e a eficácia da renúncia continuam pendentes. Este relatório preserva a diferença entre fato verificado, inferência e questão aberta.</p>
<table><thead><tr>{header}</tr></thead><tbody>{matrix}</tbody></table>{body}
<h2>Fontes consultadas</h2><p>As URLs podem mudar de conteúdo. O hash abaixo identifica a captura textual local, sem equivalência com o binário original da página ou PDF.</p><table><thead><tr><th>ID</th><th>Fonte e uso</th><th>Tipo, captura e SHA256</th></tr></thead><tbody>{source_rows}</tbody></table>
<h2>Arquivos verificáveis</h2><p><a href="relatorio.pdf">PDF complementar</a> · <a href="resumo.json">Síntese e hashes</a> · <a href="fontes.json">Metadados das fontes</a> · <a href="candidatura.json">Projeção eleitoral do cadastro</a> · <a href="unidades.csv">Unidades CSV</a> / <a href="unidades.parquet">Parquet</a> · <a href="../dossie_categorias/relatorio.html">Dossiê local preservado</a>.</p></html>'''
    (destination/'relatorio.html').write_text(page,encoding='utf-8')
    styles=pdf_styles()
    story=[heading('Pesquisa documental de nulos técnicos','pesquisa',styles),
           p('Regra identificada e situação Renúncia confirmada no cadastro. Aplicação temporal ainda não confirmada.',styles,'Deck'),
           table(head,rows,[WIDTH*.34,WIDTH*.41,WIDTH*.25],styles)]
    for index,(title,texts) in enumerate(chapters):
        story.append(heading(title,f'cap-{index}',styles,level=1))
        story.extend(p(text,styles) for text in texts)
    story.append(heading('Fontes e rastreabilidade','fontes',styles,level=1))
    for source in evidence['sources']:
        story.append(p(source['id']+' — '+source['title'],styles,'Subhead'))
        story.append(p(source['note'],styles))
        story.append(p(f'<link href="{esc(source["url"])}" color="#12677a">Abrir fonte</link>',styles,markup=True))
        story.append(p('Captura: '+source['captured_utc']+' | SHA256 da extração: '+source['capture_sha256'],styles,'Small'))
    story.append(p('Tabelas completas, projeção do cadastro, hashes e relatório HTML acompanham este PDF na mesma pasta. A confirmação de causa e de persistência permanece pendente.',styles))
    pdf=AnalysisPDF(destination/'relatorio.pdf',title='Pesquisa documental — nulos técnicos — 2026',styles=styles)
    pdf.build(story)


def run_research(source,evidence_path,candidate_path,destination=None):
    source=Path(source).resolve()
    destination=Path(destination).resolve() if destination else source/'pesquisa_categorias'
    if destination==source or source.is_relative_to(destination):raise ValueError('Saída deve ser separada da referência')
    if destination.exists() and any(destination.iterdir()):raise FileExistsError('Saída preenchida; escolha outra pasta com --dest')
    evidence_path,candidate_path=Path(evidence_path).resolve(),Path(candidate_path).resolve()
    evidence=json.loads(evidence_path.read_text(encoding='utf-8'))
    candidate_doc=json.loads(candidate_path.read_text(encoding='utf-8'))
    candidate=project_candidate(candidate_doc['candidate'])
    assessment=assess(evidence,candidate)
    candidate_source=next(s for s in evidence['sources'] if s['kind']=='cadastro_individual')
    if candidate_doc['source_capture_sha256']!=candidate_source['capture_sha256']:raise ValueError('Projeção vinculada a outra captura')
    dossier=source/'dossie_categorias'
    inputs={str(p):sha256(p) for p in [evidence_path,candidate_path,dossier/'resumo.json',dossier/'unidades.parquet',dossier/'nominais.parquet',dossier/'relatorio.html',source/'relatorio.html',source/'relatorio.pdf',source/'sintese_analise.json']}
    destination.mkdir(parents=True,exist_ok=True)
    state=dict(status='em execução',started=datetime.now(timezone.utc).isoformat(),input_hashes=inputs)
    write_json(destination/'estado_execucao.json',state)
    con=duckdb.connect(config={'threads':2,'memory_limit':'1GB'})
    try:
        con.read_parquet(str(dossier/'unidades.parquet')).create_view('units')
        con.read_parquet(str(dossier/'nominais.parquet')).create_view('nominal')
        # As fontes individuais revisadas só podem ser associadas à diferença do mesmo candidato.
        mismatches=con.execute('''SELECT count(*) FROM units u JOIN nominal n USING(year,turn,uf,municipality,zone)
            WHERE u.technical_arithmetic_match AND n.nonzero_difference AND (n.candidate<>? OR n.difference<>u.official_null_technical OR n.turn<>1 OR n.year<>?)''',[candidate['numero'],evidence['year']]).fetchall()[0][0]
        if mismatches:raise ValueError('Há diferenças que não pertencem à candidatura pesquisada')
        units=con.execute('''SELECT u.year,u.turn,u.uf,u.municipality,u.zone,u.official_null_technical technical_votes,
            n.candidate,n.difference nominal_difference,n.zero_imputed FROM units u JOIN nominal n USING(year,turn,uf,municipality,zone)
            WHERE u.technical_arithmetic_match AND n.nonzero_difference ORDER BY u.uf,u.municipality,u.zone''').df()
        if units.empty or units.duplicated(['year','turn','uf','municipality','zone']).any():raise ValueError('Vínculo individual ausente ou ambíguo')
        baseline=json.loads((dossier/'resumo.json').read_text(encoding='utf-8'))
        if len(units)!=baseline['technical_units'] or int(units.technical_votes.sum())!=baseline['technical_votes']:raise ValueError('As unidades não reproduzem o dossiê')
        units['candidate_id']=candidate['id']
        units['documentary_assessment']=assessment['causal_assessment']
        units['primary_act_status']=assessment['primary_act_status']
        units['cause_confirmed']=False
        units['evidence_ids']='guia|resolucao|cadastro|painel'
        export_frame(con,units,destination/'unidades')
        write_json(destination/'candidatura.json',dict(candidate=candidate,source_capture_sha256=candidate_doc['source_capture_sha256']))
        write_json(destination/'fontes.json',evidence['sources'])
        write_json(destination/'evidencias.json',evidence)
        summary=dict(status='concluído',year=evidence['year'],technical_units=len(units),technical_votes=int(units.technical_votes.sum()),
            assessment=assessment,candidate_id=candidate['id'],input_hashes=inputs,code_hash=sha256(Path(__file__)),
            capture_hash_meaning='SHA256 de extrações Firecrawl, não binários originais; capturas integrais locais fora da distribuição',
            sources=len(evidence['sources']),primary_act_obtained=False,pending_questions=evidence['pending_questions'])
        render(destination,summary,evidence,candidate)
        for path,digest in inputs.items():
            if sha256(path)!=digest:raise ValueError('Entrada alterada: '+path)
        summary['preservation_verified']=True
        write_json(destination/'resumo.json',summary)
        write_json(destination/'manifesto.json',{p.name:sha256(p) for p in sorted(destination.iterdir()) if p.name not in ('manifesto.json','estado_execucao.json')})
        state.update(status='concluído',finished=datetime.now(timezone.utc).isoformat())
        write_json(destination/'estado_execucao.json',state)
        return summary
    except Exception as exc:
        state.update(status='incompleto',error=f'{type(exc).__name__}: {exc}')
        write_json(destination/'estado_execucao.json',state)
        raise
    finally:con.close()
