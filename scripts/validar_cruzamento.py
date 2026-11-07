"""Validação independente das tabelas e relatórios do cruzamento integrado."""
import argparse
from html.parser import HTMLParser
from importlib import import_module
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

import duckdb

from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.extend(value for name, value in attrs if name == "href")


def validate(source="outputs/2026", destination=None):
    source = Path(source).resolve()
    destination = Path(destination).resolve() if destination else (
        source / "auditoria" / "cruzamento_integrado")
    root = Path(__file__).resolve().parents[1]
    summary = json.loads((destination / "resumo.json").read_text(encoding="utf-8"))
    assert summary["status"] == "concluído" and summary["preservation_verified"]
    for name, digest in summary["input_hashes"].items():
        assert sha256(source / name) == digest, name
    for name, digest in summary["code_hashes"].items():
        assert sha256(root / "src" / "eleicoes" / name) == digest, name
    manifest = json.loads((destination / "manifesto.json").read_text(encoding="utf-8"))
    for name, digest in manifest.items():
        assert sha256(destination / name) == digest, name

    frames = {}
    for name in ("unidades", "apontamentos", "conferencia_candidatos",
                 "sem_correspondencia", "contingencias"):
        parquet = destination / (name + ".parquet")
        csv = destination / (name + ".csv")
        con = duckdb.connect()
        try:
            schema = {row[0]: row[1] for row in con.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(parquet)]).fetchall()}
            read_export_csv(con, csv, columns=schema).create_view("csv_checked", replace=True)
            con.read_parquet(str(parquet)).create_view("parquet_checked", replace=True)
            difference = con.execute(
                "SELECT count(*) FROM ((SELECT * FROM csv_checked EXCEPT ALL SELECT * FROM parquet_checked) "
                "UNION ALL (SELECT * FROM parquet_checked EXCEPT ALL SELECT * FROM csv_checked))"
            ).fetchall()[0][0]
            assert difference == 0, name
            frames[name] = con.execute(
                "SELECT * FROM read_parquet(?)", [str(parquet)]).fetchdf()
        finally:
            con.close()
    units, issues = frames["unidades"], frames["apontamentos"]
    candidates, unmatched = frames["conferencia_candidatos"], frames["sem_correspondencia"]
    assert len(units) == summary["section_turns"]
    assert units.duplicated(["year", "turn", "uf", "municipality", "zone", "section"]).sum() == 0
    assert len(issues) == summary["log_issue_rows"]
    assert len(candidates) == summary["sample_vote_candidate_rows"]
    assert int(units.sample_discordant_rows.sum()) == summary["sample_vote_discordant_rows"]
    assert int(units.national_nonzero_difference_rows.fillna(0).sum()) == (
        summary["national_vote_nonzero_difference_rows"])
    assert int(candidates.candidate_match_status.eq(
        "sem_linha_correspondente_na_conferencia_nacional").sum()) == (
            summary["candidate_rows_without_national_match"])
    assert int(candidates.candidate_match_status.eq(
        "somente_na_conferencia_nacional").sum()) == summary["candidate_rows_only_in_national"]
    absent_national = candidates.loc[~candidates.national_record_present]
    assert absent_national.national_votes_result.isna().all()
    assert absent_national.national_votes_bu.isna().all()
    assert absent_national.national_difference.isna().all()
    assert summary["signature_chain_validated"] == 0
    assert summary["causes_confirmed"] is None
    assert summary["external_contact_made"] is False

    parser = Links()
    report_path = destination / "relatorio.html"
    parser.feed(report_path.read_text(encoding="utf-8"))
    local_links = 0
    for link in parser.hrefs:
        parsed = urlparse(link)
        if parsed.scheme or parsed.netloc:
            raise AssertionError(f"Relatório contém link externo: {link}")
        if parsed.path:
            assert (destination / parsed.path).is_file(), link
            local_links += 1

    try:
        pymupdf = import_module("pymupdf")
    except ImportError:
        sys.path.insert(0, str(root / "outputs" / "publicacao" / "pdfqa"))
        pymupdf = import_module("pymupdf")
    with pymupdf.open(destination / "relatorio.pdf") as pdf:
        text = " ".join(" ".join(page.get_text() for page in pdf).split())
        for value in ("Cruzamento integrado", "48", "265", "lacuna", "causa"):
            assert value.casefold() in text.casefold(), value
        for page in pdf:
            assert len(page.get_text()) > 100
            for x0, y0, x1, y1, *_ in page.get_text("blocks"):
                assert x0 >= 36 and x1 <= page.rect.width - 35
                assert y0 >= 18 and y1 <= page.rect.height - 20
        pdf_info = dict(pages=len(pdf), bookmarks=len(pdf.get_toc()),
                        geometry="dentro das margens")

    return dict(
        status="válido", units=len(units), issue_rows=len(issues),
        candidate_rows=len(candidates), unmatched_rows=len(unmatched),
        csv_parquet_pairs=5, local_links=local_links, pdf=pdf_info,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="outputs/2026")
    parser.add_argument("--dest")
    args = parser.parse_args()
    print(json.dumps(validate(args.output, args.dest), ensure_ascii=False, indent=2))
