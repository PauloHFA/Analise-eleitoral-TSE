"""Confere a execução PKIX sem confundir testes sintéticos com confiança real."""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse
import duckdb
from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv
from validar_assinaturas import Page


def validate(source, data):
    source, data = Path(source).resolve(), Path(data).resolve()
    root = Path(__file__).resolve().parents[1]
    dest = source / 'auditoria/caminho_pkix'
    summary = json.loads((dest / 'resumo.json').read_text(encoding='utf8'))
    for name, digest in json.loads((dest / 'manifesto.json').read_text(encoding='utf8')).items():
        assert sha256(dest / name) == digest, name
    for name, digest in summary['input_hashes'].items():
        assert sha256(source / name) == digest, name
    for name, digest in summary['source_hashes'].items():
        assert sha256(data / name) == digest, name
    for name, digest in summary['code_hashes'].items():
        assert sha256(root / 'src/eleicoes' / name) == digest, name
    for folder in ('pkix', 'cadeia'):
        raw = data / 'auditoria' / folder / 'v1'
        for name, digest in json.loads((raw / 'manifesto.json').read_text(encoding='utf8')).items():
            assert sha256(raw / name) == digest, name
    policy = json.loads((dest / 'politica_executada.json').read_text(encoding='utf8'))
    assert policy['trust_manifest']['anchors'] == []
    assert policy['allow_fetching'] is False and policy['system_trust_store'] is False
    assert policy['retroactive_revinfo'] is False and policy['time_tolerance_seconds'] == 0
    assert summary['environment']['pyhanko-certvalidator'] == '0.33.0'
    assert (summary['anchors_supplied'], summary['crls_supplied']) == (0, 0)
    con = duckdb.connect()
    pairs = []
    try:
        for path in sorted(dest.glob('*.parquet')):
            types = {r[0]: r[1] for r in con.execute('DESCRIBE SELECT * FROM read_parquet(?)', [str(path)]).fetchall()}
            read_export_csv(con, path.with_suffix('.csv'), columns=types).create_view('csv_checked', replace=True)
            con.read_parquet(str(path)).create_view('parquet_checked', replace=True)
            assert con.sql('SELECT count(*) FROM ((SELECT * FROM csv_checked EXCEPT ALL SELECT * FROM parquet_checked) UNION ALL (SELECT * FROM parquet_checked EXCEPT ALL SELECT * FROM csv_checked))').fetchall()[0][0] == 0, path.name
            pairs.append(path.stem)
        assert pairs == ['novas_tentativas', 'unidades', 'validacoes']
        validations = con.read_parquet(str(dest / 'validacoes.parquet')).df()
        units = con.read_parquet(str(dest / 'unidades.parquet')).df()
        attempts = con.read_parquet(str(dest / 'novas_tentativas.parquet')).df()
        geo = ['year', 'turn', 'uf', 'municipality', 'zone', 'section']
        assert len(validations) == 144 and len(units) == 48 and len(attempts) == 11
        assert validations.leaf_sha256.nunique() == 25
        assert not validations.duplicated(geo + ['scenario']).any() and not units.duplicated(geo).any()
        assert validations.groupby(geo).size().eq(3).all()
        assert set(validations.scenario) == {'hipotese_UTC', 'hipotese_UTC_mais_14', 'hipotese_UTC_menos_12'}
        assert validations.path_status.eq('inconclusivo_sem_ancora').all()
        assert validations.revocation_status.eq('nao_avaliada_sem_caminho').all()
        assert validations.anchors_supplied.eq(0).all()
        assert units.scenarios.eq(3).all() and units.paths_conferred.eq(0).all() and units.revocations_conferred.eq(0).all()
        assert units.issuer_time_status.eq('fora_do_intervalo_de_validade').sum() == 14
        assert attempts.http_status.eq(403).all() and attempts.tls_verification.all()
        assert not attempts.redirects_followed.any()
        for unit in validations.groupby(geo):
            values = unit[1].set_index('scenario').moment
            from datetime import datetime, timedelta
            base = datetime.fromisoformat(values['hipotese_UTC'])
            assert datetime.fromisoformat(values['hipotese_UTC_mais_14']) == base - timedelta(hours=14)
            assert datetime.fromisoformat(values['hipotese_UTC_menos_12']) == base + timedelta(hours=12)
    finally:
        con.close()
    previous = ('amostra', 'documentos', 'conferencia', 'relatorio', 'assinaturas', 'ed521', 'ed521_referencia', 'cadeia')
    for stage in previous:
        folder = source / 'auditoria' / stage
        for name, digest in json.loads((folder / 'manifesto.json').read_text(encoding='utf8')).items():
            assert sha256(folder / name) == digest, (stage, name)
    page = Page()
    page.feed((dest / 'relatorio.html').read_text(encoding='utf8'))
    local_links = 0
    for link in page.links:
        url = urlparse(link)
        if not url.scheme and url.path:
            assert (dest / url.path).is_file(), link
            local_links += 1
    try:
        import pymupdf
    except ImportError:
        sys.path.insert(0, str(root / 'outputs/publicacao/pdfqa'))
        import pymupdf
    with pymupdf.open(dest / 'relatorio.pdf') as pdf:
        content = ' '.join(' '.join(p.get_text() for p in pdf).split())
        for value in ('144', '48', '14', '11', '21', 'sintético', 'inconclusiv', 'LCR'):
            assert value in content, value
        for p in pdf:
            assert len(p.get_text()) > 150
            for x0, y0, x1, y1, *_ in p.get_text('blocks'):
                assert x0 >= 36 and x1 <= p.rect.width - 35 and y0 >= 18 and y1 <= p.rect.height - 20, (p.number, (x0, y0, x1, y1))
        pdf_info = dict(pages=len(pdf), bookmarks=len(pdf.get_toc()), geometry='dentro das margens')
    return dict(status='válido', csv_parquet_pairs=len(pairs), section_turns=48, time_scenarios=144,
                explicit_anchors=0, real_paths_conferred=0, revocation='não avaliada sem caminho, não aprovação',
                new_attempts=11, new_http_403=11, previous_attempts_preserved=21, issuer_period_outside=14,
                previous_stage_manifests_preserved=len(previous), local_links=local_links, pdf=pdf_info)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='outputs/2026')
    parser.add_argument('--data', default='data')
    args = parser.parse_args()
    print(json.dumps(validate(args.output, args.data), ensure_ascii=False, indent=2))
