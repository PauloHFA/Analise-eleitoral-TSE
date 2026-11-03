"""Aceitação dos casos dirigidos e execução dos filtros JavaScript sem rede."""
import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess

import duckdb

from eleicoes.sources import sha256


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.scripts, self.current = [], [], None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "script":
            self.current = dict(attrs, text="")

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.scripts.append(self.current)
            self.current = None


def validate_investigation(root, con=None):
    root = Path(root)
    own_connection = con is None
    con = con or duckdb.connect()
    con.execute("SET threads=2")
    summary = json.loads((root / "investigacao_resumo.json").read_text(encoding="utf-8"))
    try:
        for name, digest in summary["input_hashes"].items():
            assert sha256(root / name) == digest, f"Fonte alterada: {name}"
        for name, digest in summary["original_statistical_case_hashes"].items():
            assert sha256(root / "fichas" / name) == digest, f"Ficha original alterada: {name}"
        if not summary.get("demo"):
            assert not summary["baseline_differences"], "Contagens iniciais mudaram e exigem revisão"
        zpath = str(root / "investigacao_zeros.parquet")
        vpath = str(root / "investigacao_viradas.parquet")
        zero_count, positives, already, total_previous, maximum_previous, led = con.execute("""SELECT
            count(*),count(*) FILTER(WHERE positive_to_zero),count(*) FILTER(WHERE already_zero),
            sum(previous_zero_candidate_votes),max(previous_zero_candidate_votes),count(*) FILTER(WHERE margin_1_pp>0)
            FROM read_parquet(?) WHERE zero_candidate=22""", [zpath]).fetchone()
        assert [zero_count, positives, already, total_previous, maximum_previous, led] == [summary[k] for k in (
            "zero_22_second", "positive_to_zero_22", "already_zero_22", "total_previous_22", "max_previous_22", "led_first_positive_to_zero_22")]
        invalid, nonfinite, bad_cohort = con.execute("""SELECT
            count(*) FILTER(WHERE ballot_balance_residual<>0),
            count(*) FILTER(WHERE margin_robust_z IS NOT NULL AND NOT isfinite(margin_robust_z)),
            count(*) FILTER(WHERE cohort_coverage_attendance_1_pct < 0 OR cohort_coverage_attendance_1_pct>100.000001 OR cohort_coverage_attendance_2_pct<0 OR cohort_coverage_attendance_2_pct>100.000001)
            FROM read_parquet(?)""", [vpath]).fetchone()
        assert invalid == nonfinite == bad_cohort == 0, "Indicadores ou coorte inválidos"
        urls = [r[0] for r in con.execute("""SELECT case_file FROM read_parquet(?)
            UNION SELECT case_file FROM read_parquet(?) WHERE case_file<>''""", [zpath,vpath]).fetchall()]
        expected = {Path(url).name for url in urls}
        assert len(expected) == summary["fichas"]
        assert expected == {p.name for p in (root / "investigacao_fichas").glob("*.json")}
        for url in urls:
            case = json.loads((root / url).read_text(encoding="utf-8"))
            indicators = case["indicators"]
            if indicators["level"] == "secao":
                assert case["section_metadata"], f"Situação da seção ausente: {url}"
                if indicators["investigation_status"] in ("mudança confirmada nos arquivos", "observação confirmada nos arquivos"):
                    for turn in (1,2):
                        proof = [r for r in case["bu_records"] if r["turn"] == turn]
                        assert proof and any(r["raw_votes_bu"] is not None for r in proof), f"BU ausente: {url}"
                        for candidate in (13,22):
                            count = sum(r["votes_bu"] or 0 for r in proof if r["candidate"] == candidate)
                            assert count == indicators[f"votes_{candidate}_{turn}"], f"Votos da ficha divergem do BU: {url}"
        for uf in summary["ufs"]:
            expected_top = {r[0] for r in con.execute("""SELECT 'virada-secao-' || uf || '-' || municipality || '-' || zone || '-' || section || '.json'
                FROM read_parquet(?) WHERE level='secao' AND uf=? AND comparable AND NOT small AND selected_pattern
                ORDER BY margin_robust_z DESC NULLS LAST,margin_loss_22_pp DESC,uf,municipality,zone,section LIMIT 50""", [vpath,uf]).fetchall()}
            actual_top = {n for n in expected if n.startswith("virada-secao-"+uf+"-")}
            assert actual_top == expected_top, f"Prioridades dirigidas divergentes: {uf}"
        parser = Scripts()
        parser.feed((root / "relatorio.html").read_text(encoding="utf-8"))
        assert len(parser.ids) == len(set(parser.ids)), "IDs HTML duplicados"
        data = next(s for s in parser.scripts if s.get("id") == "inv-data")
        script = next(s for s in parser.scripts if "const all=JSON.parse" in s["text"])
        payload = dict(ids=parser.ids, data=json.loads(data["text"]), script=script["text"])
        node = shutil.which("node")
        if node:
            result = subprocess.run([node,str(Path(__file__).with_name("validar_filtros.cjs"))],
                input=json.dumps(payload,ensure_ascii=False),encoding="utf-8",capture_output=True,check=True,timeout=30)
            filters = json.loads(result.stdout)
        else:
            filters = dict(status="Node ausente: filtros não executados pelo validador")
        return dict(status="investigação válida", fichas=len(expected), filtros=filters,
            zeros_22=zero_count, positivos_para_zero_22=positives, preservadas_fichas_originais=len(summary["original_statistical_case_hashes"]))
    finally:
        if own_connection:
            con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder",nargs="?",default="outputs/2026")
    print(json.dumps(validate_investigation(parser.parse_args().folder),ensure_ascii=False,indent=2))
