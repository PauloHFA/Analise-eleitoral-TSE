"""Análise descritiva de eventos operacionais, preservando a amostra e os originais."""
from collections import Counter
from pathlib import Path
import json
import platform
import pandas as pd
import duckdb
from .analysis import export_frame
from .national_common import begin, finish, failed, records
from .sources import sha256, write_json
from .urn_logs import LAYOUT, TARGET_DATES, RULES, read_payloads, summarize_parts, classify, window

GEO = ['year', 'turn', 'uf', 'municipality', 'zone', 'section']
COUNT_CODES = [row[0] for row in RULES if row[0] != 'outro_evento']


def per_thousand(count, denominator):
    return 1000 * count / denominator if pd.notna(denominator) and denominator > 0 else None


def unit_summary(case, counts, members, events, target):
    day = [e for e in events if window(e, target) == 'data_alvo']
    codes = Counter(classify(e) for e in day)
    levels = Counter(e.level for e in day)
    result = dict(**{k: case[k] for k in GEO}, target_date=target,
        records=sum(counts.values()), target_records=len(day),
        earlier_records=sum(n for (w, *_), n in counts.items() if w == 'anterior'),
        later_records=sum(n for (w, *_), n in counts.items() if w == 'posterior'),
        payloads=len(members), nested_payloads=sum(r['depth'] > 0 for r in members),
        invalid_rows=sum(r['invalid_rows'] for r in members),
        repeated_rows=sum(r['repeated_rows'] for r in members),
        overlap_previous_members=sum(r['overlap_previous_members'] for r in members),
        clock_regressions=sum(r['clock_regressions'] for r in members),
        target_clock_regressions=sum(r['target_clock_regressions'] for r in members),
        target_hardware_identifiers=len({e.hardware for e in day}),
        target_error_records=levels['ERRO'], target_alert_records=levels['ALERTA'],
        target_other_levels=levels['WHAT'] + levels['EXTERNO'] + levels['OUTRO_NIVEL'],
        attendance=case['attendance'],
        errors_per_1000_attendees=per_thousand(levels['ERRO'], case['attendance']),
        marker_intervals_evaluable=sum(r['marker_interval_evaluable'] for r in members),
        boots_between_markers=sum(r['boots_between_markers'] or 0 for r in members)
            if any(r['marker_interval_evaluable'] for r in members) else None)
    result.update({code: codes[code] for code in COUNT_CODES})
    for code in ('urna_pronta', 'encerramento_inicio', 'bu_gerado'):
        stamps = [e.stamp for e in day if classify(e) == code]
        result[code + '_first'] = min(stamps).isoformat() if stamps else None
        result[code + '_last'] = max(stamps).isoformat() if stamps else None
    result['reading_status'] = 'layout_observado_lido' if not result['invalid_rows'] else 'leitura_parcial'
    result['marker_status'] = 'marcos_presentes_cobertura_nao_provada' if all(codes[c] for c in ('urna_pronta', 'encerramento_inicio', 'bu_gerado')) else 'marcos_incompletos_no_recorte'
    return result


ISSUES = [
    ('invalid_rows', 'leitura_limitada', 'Linhas não interpretadas; não afirmar cobertura integral do conteúdo'),
    ('overlap_previous_members', 'sobreposicao_de_fontes', 'Linhas idênticas entre membros; contagens mantidas, sem deduplicação automática'),
    ('target_clock_regressions', 'cronologia_limitada', 'Relógio retrocede na ordem física do mesmo membro na data-alvo; causa não inferida'),
    ('target_error_records', 'evento_para_revisao', 'Mensagens com nível ERRO na data-alvo; quantidade não mede votos afetados'),
    ('reinicio_solicitado', 'evento_para_revisao', 'Mensagem de solicitação de reinício; causa e efeito não determinados'),
    ('impressora_falha', 'evento_para_revisao', 'Mensagem de falha da impressora; necessidade de documento operacional complementar'),
    ('impressora_erro_desconhecido', 'evento_para_revisao', 'Mensagem de erro desconhecido da impressora; causa e efeito não determinados'),
]


def issue_rows(unit):
    result = []
    for field, status, reason in ISSUES:
        if unit[field]:
            result.append(dict(**{k: unit[k] for k in GEO}, indicator=field, count=unit[field], status=status, reason=reason))
    for condition, field, reason in (
        (unit['nested_payloads'] > 0, 'nested_payloads', 'Conteúdo aninhado incluído; origem operacional e composição precisam de confirmação'),
        (unit['target_hardware_identifiers'] > 1, 'target_hardware_identifiers', 'Mais de um identificador de hardware na data-alvo; não inferir substituição sem documentação'),
        (unit['marker_status'] == 'marcos_incompletos_no_recorte', 'marker_status', 'Falta de marco no arquivo não demonstra ausência da operação'),
        (unit['target_records'] == 0, 'target_records', 'Nenhuma linha válida na data-alvo configurada; não converter em ausência de eventos'),
        (pd.notna(unit['boots_between_markers']) and unit['boots_between_markers'] > 0, 'boots_between_markers', 'Ligação entre marcos do mesmo membro; não inferir causa nem intervalo sem funcionamento'),
    ):
        if condition:
            result.append(dict(**{k: unit[k] for k in GEO}, indicator=field,
                count=unit[field] if isinstance(unit[field], (int, float)) else None,
                status='contexto_limitado', reason=reason))
    return result


def compare_turns(units):
    keys = [k for k in GEO if k != 'turn']
    if units.duplicated(GEO).any():
        raise ValueError('Unidade seção/turno repetida')
    fields = ['target_records', 'target_error_records', 'target_alert_records', 'urna_ligada',
              'energia_bateria', 'reinicio_solicitado', 'target_hardware_identifiers', 'attendance',
              'errors_per_1000_attendees', 'marker_status', 'reading_status']
    result = units.loc[units.turn.eq(1), keys + fields].merge(
        units.loc[units.turn.eq(2), keys + fields], on=keys, how='outer',
        suffixes=('_1', '_2'), validate='one_to_one', indicator=True)
    result['coverage'] = result.pop('_merge').astype(str)
    for name in ('target_error_records', 'target_alert_records', 'urna_ligada', 'energia_bateria', 'attendance', 'errors_per_1000_attendees'):
        result['delta_' + name] = result[name + '_2'] - result[name + '_1']
    return result


def run_logs(source, data='data', destination=None):
    source, data = Path(source).resolve(), Path(data).resolve()
    destination = Path(destination).resolve() if destination else source / 'auditoria/logs'
    names = ['auditoria/documentos/inventario.parquet', 'auditoria/amostra/turnos.parquet',
             'auditoria/amostra/secoes.parquet', 'auditoria/ed521/arquivos_assinados.parquet',
             'auditoria/caminho_pkix/manifesto.json']
    source, destination, state = begin(source, destination, names)
    con = duckdb.connect()
    try:
        for stage in ('documentos', 'amostra', 'ed521'):
            folder = source / 'auditoria' / stage
            for name, digest in json.loads((folder / 'manifesto.json').read_text(encoding='utf8')).items():
                if sha256(folder / name) != digest:
                    raise ValueError('Entrada não corresponde ao manifesto anterior')
        inventory, turns, sample, signed = [con.read_parquet(str(source / name)).df() for name in names[:4]]
        if inventory.duplicated(GEO + ['kind']).any() or turns.duplicated(GEO).any():
            raise ValueError('Unidade ou documento repetido')
        if set(turns.year) != {2026} or not set(turns.turn).issubset(TARGET_DATES):
            raise ValueError('Datas-alvo configuradas apenas para os dois turnos de 2026')
        units, members, counts, issues, error_context = [], [], [], [], []
        for case in turns.to_dict('records'):
            key = {k: case[k] for k in GEO}
            selected = inventory.loc[inventory.kind.eq('log')]
            signature = signed.loc[signed.kind.eq('log') & signed.role.eq('hw')]
            for name, value in key.items():
                selected = selected.loc[selected[name].eq(value)]
                signature = signature.loc[signature[name].eq(value)]
            if len(selected) != 1 or selected.iloc[0]['status'] != 'obtido':
                raise ValueError('Log ausente, repetido ou não obtido')
            original = selected.iloc[0]
            path = (data / original['path']).resolve()
            if not path.is_relative_to(data) or sha256(path) != original['sha256'] or path.stat().st_size != original['size']:
                raise ValueError('Original local alterado ou fora da pasta')
            if len(signature) != 1 or signature.iloc[0]['local_sha256'] != original['sha256']:
                raise ValueError('Log não vinculado à conferência de assinatura anterior')
            counter, parts, events = summarize_parts(read_payloads(path.read_bytes()), TARGET_DATES[case['turn']])
            unit = unit_summary(case, counter, parts, events, TARGET_DATES[case['turn']])
            unit.update(source_path=original['path'], source_sha256=original['sha256'],
                previous_hash_status=signature.iloc[0]['hash_status'],
                previous_hardware_signature_status=signature.iloc[0]['crypto_status'],
                trust_status='inconclusivo_sem_ancora_na_etapa_pkix')
            units.append(unit)
            for part in parts:
                context = part.pop('error_context_counts')
                error_context.extend(dict(**key, member=part['member'], event=event, context=label, count=count)
                                     for (event, label), count in sorted(context.items()))
            members.extend(dict(**key, **part) for part in parts)
            counts.extend(dict(**key, window=w, module=module, level=level, event=event, count=count)
                          for (w, module, level, event), count in sorted(counter.items()))
            issues.extend(issue_rows(unit))
        units = pd.DataFrame(units).merge(sample[[k for k in GEO if k != 'turn'] + ['group', 'region', 'pair_id', 'municipality_name_1']],
            on=[k for k in GEO if k != 'turn'], validate='many_to_one')
        members, counts = pd.DataFrame(members), pd.DataFrame(counts)
        issues = pd.DataFrame(issues, columns=GEO + ['indicator', 'count', 'status', 'reason'])
        comparison = compare_turns(units)
        rules = pd.DataFrame(RULES, columns=['event', 'module', 'fullmatch_regex', 'meaning'])
        error_context = pd.DataFrame(error_context, columns=GEO + ['member', 'event', 'context', 'count'])
        tables = dict(unidades=units, membros=members, contagens=counts, pendencias=issues,
                      comparacao_turnos=comparison, regras=rules, erros_contexto=error_context)
        for name, frame in tables.items():
            export_frame(con, frame, destination / name)
        write_json(destination / 'protocolo.json', dict(layout=LAYOUT, target_dates=TARGET_DATES,
            dates_scope='Datas-alvo explícitas da análise; timestamps locais declarados, sem conversão de fuso ou autenticação do relógio',
            classification='Regras locais após inspeção do formato; não dicionário oficial ou análise pré-registrada',
            preservation='Sem deduplicação, reordenação de linhas ou união cronológica de membros distintos',
            final_token='16 dígitos hexadecimais conferidos somente na sintaxe; algoritmo/integridade deste campo não validados',
            privacy='Nenhuma mensagem, identificação pessoal, tecla, biometria ou sequência/horário individual de votação é exportada',
            figures='Contagens de registros, não pessoas, votos afetados ou interrupções físicas medidas',
            archive_limits=dict(bytes=32*1024*1024, depth=2, members_per_zip=16)))
        totals = counts.groupby(['window', 'level'], as_index=False)['count'].sum()
        by_group = units.assign(territory=units.uf.map(lambda x: 'Exterior' if x == 'ZZ' else 'Brasil')).groupby(['territory', 'group', 'turn'], as_index=False).agg(
            section_turns=('section', 'size'), records=('target_records', 'sum'),
            error_records=('target_error_records', 'sum'), units_with_errors=('target_error_records', lambda v: int(v.gt(0).sum())))
        summary = dict(sections=len(comparison), section_turns=len(units), payloads=len(members),
            nested_payloads=int(members.depth.gt(0).sum()), records=int(units.records.sum()),
            target_records=int(units.target_records.sum()), earlier_records=int(units.earlier_records.sum()),
            later_records=int(units.later_records.sum()), invalid_rows=int(units.invalid_rows.sum()),
            repeated_rows=int(units.repeated_rows.sum()), overlap_previous_members=int(units.overlap_previous_members.sum()),
            target_error_records=int(units.target_error_records.sum()), units_with_target_errors=int(units.target_error_records.gt(0).sum()),
            target_alert_records=int(units.target_alert_records.sum()), clock_regressions=int(units.clock_regressions.sum()),
            target_clock_regressions=int(units.target_clock_regressions.sum()),
            units_multiple_target_hardware=int(units.target_hardware_identifiers.gt(1).sum()),
            units_with_incomplete_markers=int(units.marker_status.eq('marcos_incompletos_no_recorte').sum()),
            units_with_boots_between_markers=int(units.boots_between_markers.gt(0).sum()),
            review_rows=len(issues), review_units=len(issues[GEO].drop_duplicates()),
            by_window_level=records(totals), by_group=records(by_group), environment=dict(python=platform.python_version()),
            target_errors_by_type_context=records(error_context.groupby(['event','context'], as_index=False)['count'].sum()),
            interpretation='Eventos observados e cobertura do recorte; não medem votos afetados, causas ou frequência nacional de irregularidade. Confiança criptográfica da cadeia permanece pendente na etapa própria.')
        from .audit_logs_report import render
        render(destination, summary, units, counts, issues)
        return finish(source, destination, state, summary, [Path(__file__), Path(__file__).with_name('urn_logs.py'), Path(__file__).with_name('audit_logs_report.py')])
    except Exception as exc:
        failed(destination, state, exc)
        raise
    finally:
        con.close()
