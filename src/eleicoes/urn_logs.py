"""Leitor do layout textual observado, sem exportação de eventos individuais.

O token final é apenas conferido sintaticamente. Não se valida sua cadeia/hash.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import hashlib
import io
from pathlib import PurePosixPath
import re
import stat
import zipfile

LAYOUT = 'logd-observado-tab6-latin1-v1'
TARGET_DATES = {1: '2026-10-04', 2: '2026-10-25'}
LEVELS = {'INFO', 'ALERTA', 'ERRO', 'WHAT', 'EXTERNO'}
MODULES = {'LOGD', 'SCUE', 'GAP', 'ATUE', 'VOTA', 'INITJE', 'VPP'}
# Regras locais sobre mensagens observadas, não dicionário homologado pelo TSE.
RULES = [
    ('logd_inicio', 'LOGD', r'Início das operações do logd', 'Início declarado do serviço de log'),
    ('urna_ligada', 'LOGD', r'Urna ligada em .*', 'Registro de ligação, não contagem automática de reinícios'),
    ('vota_inicio', 'VOTA', r'Iniciando aplicação - .*', 'Inicialização do aplicativo VOTA'),
    ('urna_pronta', 'VOTA', r'Urna pronta para receber votos', 'Marco de disponibilidade declarado'),
    ('zeresima_gerada', 'VOTA', r'Gerando relatório \[ZERÉSIMA\] \[TÉRMINO\]', 'Término declarado da geração da zerésima'),
    ('encerramento_inicio', 'VOTA', r'Inicio do Encerramento', 'Início declarado do procedimento de encerramento'),
    ('encerramento_abortado', 'VOTA', r'Procedimento de encerramento abortado|Operador cancelou o encerramento da votação', 'Cancelamento/aborto do procedimento'),
    ('bu_gerado', 'VOTA', r'Gerando relatório \[BU\] \[TÉRMINO\]', 'Término declarado da geração do relatório BU'),
    ('votacao_encerrada', 'VOTA', r'Votação encerrada', 'Mensagem explícita de votação encerrada; pode faltar no recorte'),
    ('suspensao_votacao', 'VOTA', r'Votação suspensa', 'Registro agregado de suspensão, sem vincular a eleitor ou voto'),
    ('reinicio_solicitado', 'GAP', r'Reiniciando a urna', 'Solicitação de reinício, não comprovação da causa'),
    ('reinicio_registrado', 'GAP', r'Urna reiniciada a pedido do aplicativo', 'Registro distinto da solicitação; não somar como dois reinícios'),
    ('desligamento', '*', r'Desligando a urna|Urna desligada pela chave|Urna desligada a pedido do aplicativo', 'Mensagens de desligamento; várias podem se referir ao mesmo ciclo'),
    ('energia_rede', '*', r'Urna operando (?:com rede elétrica|na rede elétrica)', 'Mensagem de operação em rede elétrica'),
    ('energia_bateria', '*', r'Urna operando na bateria interna', 'Mensagem de operação em bateria; não é, por si, falha'),
    ('impressora_falha', '*', r'Impressora com falha.*', 'Mensagem explícita de falha da impressora'),
    ('mr_desmontagem_erro', 'GAP', r'Problema ao desmontar a MR', 'Mensagem de problema na desmontagem de MR; causa não confirmada'),
    ('impressora_erro_desconhecido', 'GAP', r'Impressora com erro desconhecido', 'Mensagem de erro desconhecido da impressora'),
    ('opensession_erro', 'VOTA', r'Não é possível continuar a execução \| Erro inesperado .*ERROR OpenSession command .*', 'Mensagem de impossibilidade de continuar a execução/OpenSession'),
    ('relogio_ajustado', '*', r'Data e hora da urna alterada de .*', 'Mensagem explícita de ajuste do relógio'),
    ('outro_evento', '*', r'.*', 'Demais mensagens, sem exportar seu conteúdo'),
]
COMPILED = [(code, module, re.compile(pattern)) for code, module, pattern, _ in RULES]


@dataclass(frozen=True)
class Event:
    stamp: datetime
    level: str
    module: str
    hardware: str
    message: str
    digest: str


def classify(event):
    for code, module, pattern in COMPILED:
        if module in ('*', event.module) and pattern.fullmatch(event.message):
            return code
    raise AssertionError('Regra final deve cobrir toda mensagem')


def read_payloads(content, *, max_bytes=32 * 1024 * 1024, max_depth=2):
    """Lê ZIPs aninhados em memória com limites e CRC, sem extrair caminhos."""
    payloads = []
    used = 0

    def walk(raw, prefix, depth):
        nonlocal used
        if depth > max_depth:
            raise ValueError('Limite de aninhamento excedido')
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                names = [e.filename for e in entries]
                if len(entries) > 16 or len(set(names)) != len(names) or names.count('logd.dat') != 1:
                    raise ValueError('Inventário interno ausente, repetido ou excessivo')
                for entry in entries:
                    name = entry.filename
                    if (PurePosixPath(name).name != name or '\\' in name or '..' in name
                            or not re.fullmatch(r'[A-Za-z0-9_.-]+', name)
                            or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1):
                        raise ValueError('Membro interno inseguro ou cifrado')
                    if name != 'logd.dat' and not name.endswith('.jez'):
                        raise ValueError('Membro interno não suportado')
                    if entry.file_size > max_bytes - used:
                        raise ValueError('Limite de descompressão excedido')
                    with archive.open(entry) as stream:
                        data = stream.read(max_bytes - used + 1)
                    used += len(data)
                    if used > max_bytes or len(data) != entry.file_size:
                        raise ValueError('Tamanho descomprimido incompatível')
                    member = prefix + name
                    if name == 'logd.dat':
                        payloads.append(dict(member=member, content=data, depth=depth,
                                             sha256=hashlib.sha256(data).hexdigest()))
                    else:
                        walk(data, member + '!', depth + 1)
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
            raise ValueError('ZIP/CRC interno não suportado ou inválido') from exc

    walk(content, '', 0)
    return payloads


def parse_payload(content):
    events, invalid = [], Counter()
    # splitlines() em texto Latin-1 poderia interpretar controles como separadores.
    for raw in content.split(b'\n'):
        if raw.endswith(b'\r'):
            raw = raw[:-1]
        if not raw:
            continue
        fields = raw.split(b'\t')
        if len(raw) > 64 * 1024 or len(fields) != 6:
            invalid['campos_ou_tamanho'] += 1
            continue
        if any(v < 32 and v != 9 or 127 <= v < 160 for v in raw):
            invalid['controle_nao_suportado'] += 1
            continue
        stamp, level, hardware, module, message, token = (f.decode('latin1') for f in fields)
        try:
            if not re.fullmatch(r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}', stamp):
                raise ValueError
            timestamp = datetime.strptime(stamp, '%d/%m/%Y %H:%M:%S')
        except ValueError:
            invalid['data_invalida'] += 1
            continue
        if not (re.fullmatch(r'\d{8}', hardware) and re.fullmatch(r'[0-9A-Fa-f]{16}', token)):
            invalid['identificador_ou_token'] += 1
            continue
        events.append(Event(timestamp, level if level in LEVELS else 'OUTRO_NIVEL',
                            module if module in MODULES else 'OUTRO_MODULO', hardware,
                            message, hashlib.sha256(raw).hexdigest()))
    return events, invalid


def window(event, target):
    day = event.stamp.date().isoformat()
    return 'data_alvo' if day == target else 'anterior' if day < target else 'posterior'


def summarize_parts(parts, target):
    """Conta sem ordenar linhas, deduplicar ou unir relógios de arquivos distintos."""
    counts = Counter()
    combined, member_rows = [], []
    previous_digests = set()
    for part in parts:
        events, invalid = parse_payload(part['content'])
        day = [e for e in events if window(e, target) == 'data_alvo']
        codes = [classify(e) for e in day]
        regression = sum(b.stamp < a.stamp for a, b in zip(events, events[1:]))
        day_regression = sum(b.stamp < a.stamp for a, b in zip(day, day[1:]))
        ready = [e.stamp for e, code in zip(day, codes) if code == 'urna_pronta']
        close = [e.stamp for e, code in zip(day, codes) if code == 'encerramento_inicio']
        interval_ok = bool(ready and close and not day_regression and min(ready) <= max(close))
        boots_inside = sum(min(ready) < e.stamp < max(close) and code == 'urna_ligada'
                           for e, code in zip(day, codes)) if interval_ok else None
        digests = {e.digest for e in events}
        error_context = Counter()
        context_ok = interval_ok and len({e.hardware for e in day}) == 1
        for e, code in zip(day, codes):
            if e.level != 'ERRO':
                continue
            context = ('nao_classificavel_por_marcos' if not context_ok else
                       'antes_da_primeira_prontidao' if e.stamp < min(ready) else
                       'apos_ultimo_inicio_encerramento' if e.stamp >= max(close) else
                       'entre_prontidao_e_inicio_encerramento')
            error_context[(code, context)] += 1
        member_rows.append(dict(member=part['member'], depth=part['depth'], sha256=part['sha256'],
            uncompressed_bytes=len(part['content']), records=len(events), invalid_rows=sum(invalid.values()),
            invalid_reasons=';'.join(f'{k}:{v}' for k, v in sorted(invalid.items())) or None,
            target_records=len(day), clock_regressions=regression, target_clock_regressions=day_regression,
            repeated_rows=len(events)-len(digests), overlap_previous_members=len(digests & previous_digests),
            marker_interval_evaluable=interval_ok, boots_between_markers=boots_inside,
            error_context_counts=error_context,
            first_date=min(e.stamp for e in events).date().isoformat() if events else None,
            last_date=max(e.stamp for e in events).date().isoformat() if events else None))
        previous_digests |= digests
        combined.extend(events)
        for e in events:
            counts[(window(e, target), e.module, e.level, classify(e))] += 1
    return counts, member_rows, combined
