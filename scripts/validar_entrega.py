"""Valida os artefatos gerados, sem baixar dados ou alterar os resultados."""
import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote

import duckdb


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links.extend(v for k, v in attrs if k in ("href", "src") and v)


def validate(folder):
    root = Path(folder).resolve()
    for file in ("relatorio.html", "relatorio.pdf", "resumo.json", "dicionario.csv", "indicadores_secoes.csv", "indicadores_secoes.parquet"):
        assert (root / file).is_file(), f"Artefato ausente: {file}"
    doc = Links()
    doc.feed((root / "relatorio.html").read_text(encoding="utf-8"))
    for link in doc.links:
        parsed = urlparse(link)
        if not parsed.scheme and parsed.path:
            assert (root / unquote(parsed.path)).is_file(), f"Link local quebrado: {link}"
    def nonfinite(value):
        raise ValueError(f"JSON não padrão: {value}")
    for path in root.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"), parse_constant=nonfinite)
    pdf = (root / "relatorio.pdf").read_bytes()
    assert pdf.startswith(b"%PDF-") and b"%%EOF" in pdf[-1024:]
    assert b"/FontFile2" in pdf, "PDF sem fonte Unicode incorporada"
    con = duckdb.connect()
    expected = con.execute("SELECT uf,municipality,zone,section FROM read_parquet(?) WHERE statistical_alert ORDER BY priority LIMIT 100",
        [str(root / "indicadores_secoes.parquet")]).fetchall()
    expected_links = {"fichas/" + "-".join(map(str, row)) + ".json" for row in expected}
    case_links = {link for link in doc.links if link.startswith("fichas/") and not link.startswith("fichas/documental-")}
    assert case_links == expected_links, "As fichas do HTML não correspondem às 100 primeiras prioridades"
    case_files = {"fichas/" + p.name for p in (root / "fichas").glob("*.json") if not p.name.startswith("documental-")}
    assert case_files == expected_links, "Há fichas estatísticas ausentes ou antigas na pasta da entrega"
    counts = {}
    for file in root.rglob("*.parquet"):
        csv = file.with_suffix(".csv")
        if not csv.exists():
            continue
        pq_count = con.execute("SELECT count(*) FROM read_parquet(?)", [str(file)]).fetchone()[0]
        csv_count = con.execute("SELECT count(*) FROM read_csv(?,header=true,all_varchar=true,max_line_size=16777216)", [str(csv)]).fetchone()[0]
        assert pq_count == csv_count, f"Contagens CSV/Parquet divergem: {file.name}"
        counts[str(file.relative_to(root).with_suffix(""))] = pq_count
    quality = {}
    for file in root.rglob("indicadores_secoes.parquet"):
        invalid_alerts, nonfinite_scores, unordered_thresholds = con.execute("""
            SELECT count(*) FILTER(WHERE statistical_alert AND (NOT comparable OR small)),
                   count(*) FILTER(WHERE robust_max IS NOT NULL AND NOT isfinite(robust_max)),
                   count(*) FILTER(WHERE (flag_15pp AND NOT flag_10pp) OR (flag_10pp AND NOT flag_5pp))
            FROM read_parquet(?)""", [str(file)]).fetchone()
        assert invalid_alerts == nonfinite_scores == unordered_thresholds == 0, f"Triagem inválida: {file}"
        quality[str(file.relative_to(root))] = "elegibilidade, escores finitos e sensibilidade válidos"
    for file in root.rglob("indicadores_local.parquet"):
        invalid_composition = con.execute("""SELECT count(*) FROM read_parquet(?)
            WHERE comparable AND (membership_1<>membership_2 OR aptos_1<>aptos_2)""", [str(file)]).fetchone()[0]
        assert invalid_composition == 0, f"Composição incompatível: {file}"
    investigation = None
    if (root / "investigacao_resumo.json").exists():
        from validar_investigacao import validate_investigation
        investigation = validate_investigation(root,con)
    electoral_map = None
    if (root / "mapa_dados.json").exists():
        from validar_mapa import validate_map
        electoral_map = validate_map(root)
    con.close()
    print(json.dumps({"status": "artefatos válidos", "links": len(doc.links),
        "paginas_pdf": len(re.findall(rb"/Type\s*/Page\b", pdf)), "tabelas": counts,
        "qualidade_triagem": quality, "investigacao_dirigida": investigation, "mapa":electoral_map}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default="outputs/2026")
    validate(parser.parse_args().folder)
