"""Valida o dossiê local, seus vínculos e a preservação da referência."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlparse

import duckdb

from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids, self.cases = [], set(), []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            assert attrs['id'] not in self.ids, f"ID HTML repetido: {attrs['id']}"
            self.ids.add(attrs['id'])
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag == 'tr' and 'data-finding' in attrs:
            self.cases.append(attrs['id'])


def validate(source, data="data", destination=None):
    source, data = Path(source).resolve(), Path(data).resolve()
    folder = Path(destination).resolve() if destination else source / "dossie_categorias"
    read = lambda name: json.loads((folder / name).read_text(encoding='utf-8'),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    summary, state, manifest = read('resumo.json'), read('estado_execucao.json'), read('manifesto.json')
    assert summary['status'] == state['status'] == 'concluído'
    assert summary['preservation_verified']
    assert summary['input_hashes'] == state['input_hashes']
    for name, digest in summary['input_hashes'].items():
        assert sha256(source / name) == digest, f"Referência alterada: {name}"
    for name, digest in manifest.items():
        assert sha256(folder / name) == digest, f"Artefato alterado: {name}"
    for entry in read('fontes.json'):
        relative = Path(entry['path'].replace('\\','/'))
        path = (data / relative).resolve()
        assert path.is_relative_to(data), relative
        assert sha256(path) == entry['sha256'] == summary['original_hashes'][entry['source_id']]
    assert sha256(Path(__file__).resolve().parents[1] / 'src/eleicoes/dossier.py') == summary['code_hash']
    con=duckdb.connect(config={'threads':2,'memory_limit':'1GB'})
    try:
        checked={}
        for path in folder.glob('*.parquet'):
            relation=con.read_parquet(str(path))
            schema={name:str(dtype) for name,dtype in zip(relation.columns,relation.types)}
            relation.create_view('expected')
            read_export_csv(con,path.with_suffix('.csv'),columns=schema).create_view('actual')
            # Comparação tipada do multiconjunto completo, nos dois sentidos.
            for a,b in (('expected','actual'),('actual','expected')):
                assert con.execute(f'SELECT count(*) FROM (SELECT * FROM {a} EXCEPT ALL SELECT * FROM {b})').fetchall()[0][0] == 0, path.name
            checked[path.stem]=con.execute('SELECT count(*) FROM expected').fetchall()[0][0]
        for name in ('unidades','nominais','categorias_originais'):
            con.read_parquet(str(folder / (name+'.parquet'))).create_view(name)
        baseline = con.read_parquet(str(source / 'reconciliacao_municipio_zona.parquet'))
        baseline.create_view('baseline')
        columns=','.join('"'+n+'"' for n in baseline.columns)
        assert con.execute(f'SELECT count(*) FROM (SELECT {columns} FROM nominais EXCEPT ALL SELECT * FROM baseline)').fetchall()[0][0] == 0
        assert checked['nominais']==con.execute('SELECT count(*) FROM baseline').fetchall()[0][0]
        total,selected,technical,votes=con.execute('''SELECT count(*),count(*) FILTER(WHERE selected),
            count(*) FILTER(WHERE technical_arithmetic_match),sum(official_null_technical) FILTER(WHERE technical_arithmetic_match) FROM unidades''').fetchall()[0]
        assert (total,selected,technical,votes or 0)==(summary['unit_turns'],summary['selected_unit_turns'],summary['technical_units'],summary['technical_votes'])
        assert con.execute('SELECT count(*) FROM unidades WHERE technical_arithmetic_match AND (NOT raw_categories_confirmed OR NOT published_arithmetic_consistent OR nominal_coverage_rows<>0 OR nominal_difference<>official_null_technical OR section_valid-official_valid<>official_null_technical OR section_null-official_null_total<>-official_null_technical OR section_null<>official_null_regular OR section_blank<>official_blank OR section_total<>official_attendance)').fetchall()[0][0]==0
        coverage=con.execute('''SELECT count(*),count(DISTINCT (uf,municipality,zone))
            FROM unidades WHERE zero_attendance_coverage''').fetchall()[0]
        assert coverage==(summary['coverage_turn_units'],summary['coverage_geographic_units'])
        lines=con.execute('''SELECT count(*) FROM nominais n JOIN unidades u USING(year,turn,uf,municipality,zone)
            WHERE u.zero_attendance_coverage AND n.coverage_gap''').fetchall()[0][0]
        assert lines==summary['coverage_candidate_rows']
        assert con.execute('''SELECT count(*) FROM unidades WHERE zero_attendance_coverage AND
            (attendance_sections IS DISTINCT FROM 0 OR attendance_official IS DISTINCT FROM 0 OR official_nominal_votes IS DISTINCT FROM 0)''').fetchall()[0][0]==0
        assert con.execute("SELECT count(*) FROM unidades WHERE documentary_cause_status<>'não investigada neste incremento' OR persistence_status<>'não investigada neste incremento'").fetchall()[0][0]==0
        inventory=Inventory()
        inventory.feed((folder/'relatorio.html').read_text(encoding='utf-8'))
        cases={r[0] for r in con.execute("SELECT 'caso-'||case_id FROM unidades WHERE selected").fetchall()}
        assert len(inventory.cases)==len(cases)==selected and set(inventory.cases)==cases
        for link in inventory.links:
            parsed=urlparse(link)
            if parsed.scheme:continue
            if parsed.path:assert (folder/parsed.path).is_file(),link
            elif parsed.fragment:assert parsed.fragment in inventory.ids,link
        return dict(status='válido',tables=checked,selected_unit_turns=selected,
            technical_units=technical,technical_votes=votes or 0,coverage_geographic_units=coverage[1],
            coverage_turn_units=coverage[0],coverage_candidate_rows=lines,html_case_anchors=len(cases),
            csv_parquet='multiconjunto tipado completo por EXCEPT ALL nos dois sentidos',
            preservation='entradas, originais e manifesto conferidos por SHA256',
            documentary_cause_status=summary['documentary_cause_status'],persistence_status=summary['persistence_status'])
    finally:
        con.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='outputs/2026')
    parser.add_argument('--data',default='data')
    parser.add_argument('--dest')
    args=parser.parse_args()
    print(json.dumps(validate(args.output,args.data,args.dest),ensure_ascii=False,indent=2))
