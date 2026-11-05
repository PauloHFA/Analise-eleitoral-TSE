import io
import zipfile
from datetime import datetime
import pandas as pd
import pytest
from eleicoes.urn_logs import read_payloads, parse_payload, summarize_parts, classify
from eleicoes.audit_logs import unit_summary, compare_turns, per_thousand


def line(message='Urna pronta para receber votos', stamp='04/10/2026 08:00:00', *, level='INFO', module='VOTA', hardware='12345678'):
    return f'{stamp}\t{level}\t{hardware}\t{module}\t{message}\t0123456789ABCDEF\r\n'.encode('latin1')


def archive(entries):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries:z.writestr(name,data)
    return out.getvalue()


def part(data, name='logd.dat'):
    return dict(content=data,member=name,depth=int('!' in name),sha256='fixture')


def case():
    return dict(year=2026,turn=1,uf='AA',municipality=1,zone=1,section=1,attendance=100)


def test_nested_log_is_read_even_when_first_member_is_binary_zip():
    nested=archive([('logd.dat',line('Início das operações do logd',module='LOGD'))])
    parts=read_payloads(archive([('previous.jez',nested),('logd.dat',line())]))
    assert len(parts)==2 and {p['depth'] for p in parts}=={0,1}
    assert sum(len(parse_payload(p['content'])[0]) for p in parts)==2


@pytest.mark.parametrize('name',['../logd.dat','folder/logd.dat','C:\\logd.dat','unexpected.txt'])
def test_unsafe_or_unsupported_zip_member_is_not_silently_ignored(name):
    with pytest.raises(ValueError):read_payloads(archive([('logd.dat',line()),(name,b'bad')]))


def test_decompression_and_nesting_limits_and_bad_zip():
    simple=archive([('logd.dat',line())])
    with pytest.raises(ValueError,match='descompressão'):read_payloads(simple,max_bytes=10)
    with pytest.raises(ValueError,match='aninhamento'):read_payloads(archive([('extra.jez',simple),('logd.dat',line())]),max_depth=0)
    with pytest.raises(ValueError,match='ZIP'):read_payloads(b'not a zip')


def test_duplicate_internal_member_is_rejected():
    with pytest.warns(UserWarning):data=archive([('logd.dat',line()),('logd.dat',line())])
    with pytest.raises(ValueError,match='repetido'):read_payloads(data)


def test_layout_dates_and_controls_are_counted_as_limitations():
    valid=line()
    malformed=b'bad\n'+line(stamp='31/02/2026 08:00:00')+line().replace(b'0123456789ABCDEF',b'bad')+line('bad\x85message')
    events,invalid=parse_payload(valid+malformed)
    assert len(events)==1 and sum(invalid.values())==4
    assert set(invalid)=={'campos_ou_tamanho','data_invalida','identificador_ou_token','controle_nao_suportado'}


def test_error_outside_target_date_does_not_become_election_day_error():
    counts,members,events=summarize_parts([part(line('arbitrary person data',stamp='03/10/2026 10:00:00',level='ERRO')+line())],'2026-10-04')
    unit=unit_summary(case(),counts,members,events,'2026-10-04')
    assert unit['records']==2 and unit['earlier_records']==1 and unit['target_error_records']==0
    assert 'arbitrary person data' not in str(counts) and 'arbitrary person data' not in str(unit)


def test_clock_regression_uses_physical_order_and_does_not_sort_away_evidence():
    counts,members,events=summarize_parts([part(line(stamp='04/10/2026 09:00:00')+line(stamp='04/10/2026 08:00:00'))],'2026-10-04')
    assert members[0]['clock_regressions']==1 and members[0]['target_clock_regressions']==1
    assert events[0].stamp>events[1].stamp


def test_overlap_and_repeated_lines_are_flagged_without_deduplication():
    raw=line()
    counts,members,events=summarize_parts([part(raw+raw),part(raw,'old.jez!logd.dat')],'2026-10-04')
    assert sum(counts.values())==3 and len(events)==3
    assert members[0]['repeated_rows']==1 and members[1]['overlap_previous_members']==1


def test_missing_markers_is_not_success_and_boot_window_stays_unknown():
    counts,members,events=summarize_parts([part(line())],'2026-10-04')
    unit=unit_summary(case(),counts,members,events,'2026-10-04')
    assert unit['marker_status']=='marcos_incompletos_no_recorte'
    assert unit['boots_between_markers'] is None


def test_boot_interval_is_only_within_same_member_and_has_no_duration_claim():
    before=line(stamp='04/10/2026 08:00:00')
    boot=line('Urna ligada em 04/10/2026 às 10:00:00',stamp='04/10/2026 10:00:00',module='LOGD')
    close=line('Inicio do Encerramento',stamp='04/10/2026 17:00:00')
    _,members,_=summarize_parts([part(before+boot+close)],'2026-10-04')
    assert members[0]['boots_between_markers']==1
    _,members,_=summarize_parts([part(before),part(boot+close,'old.jez!logd.dat')],'2026-10-04')
    assert all(m['boots_between_markers'] is None for m in members)


def test_unknown_modules_levels_do_not_export_arbitrary_text_and_rules_need_module():
    events,invalid=parse_payload(line('Início das operações do logd',module='private text',level='private name'))
    assert not invalid and events[0].level=='OUTRO_NIVEL' and events[0].module=='OUTRO_MODULO'
    assert classify(events[0])=='outro_evento'


def test_zero_denominator_and_absent_turn_stay_missing():
    assert per_thousand(2,0) is None and per_thousand(2,None) is None
    counts,members,events=summarize_parts([part(line())],'2026-10-04')
    unit=unit_summary(case(),counts,members,events,'2026-10-04')
    compared=compare_turns(pd.DataFrame([unit]))
    assert compared.iloc[0]['coverage']=='left_only'
    assert pd.isna(compared.iloc[0]['delta_target_error_records'])


def test_error_context_requires_same_member_markers_and_monotonic_clock():
    ready=line(stamp='04/10/2026 08:00:00')
    close=line('Inicio do Encerramento',stamp='04/10/2026 17:00:00')
    error=line('Problema ao desmontar a MR',stamp='04/10/2026 17:30:00',module='GAP',level='ERRO')
    _,members,_=summarize_parts([part(ready+close+error)],'2026-10-04')
    assert members[0]['error_context_counts'][('mr_desmontagem_erro','apos_ultimo_inicio_encerramento')]==1
    _,members,_=summarize_parts([part(ready+close),part(error,'old.jez!logd.dat')],'2026-10-04')
    assert members[1]['error_context_counts'][('mr_desmontagem_erro','nao_classificavel_por_marcos')]==1


def test_technical_error_classes_do_not_export_the_message():
    raw=line('Impressora com erro desconhecido',module='GAP',level='ERRO')
    events,_=parse_payload(raw)
    assert classify(events[0])=='impressora_erro_desconhecido'
    counter,_,_=summarize_parts([part(raw)],'2026-10-04')
    assert 'Impressora com erro desconhecido' not in str(counter)
