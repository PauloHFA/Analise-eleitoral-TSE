"""Confere coerência entre artefatos, síntese, README, HTML e texto do PDF ReportLab."""
import argparse
import base64
import json
import re
import zlib
from pathlib import Path
from urllib.parse import unquote, urlparse

from eleicoes.synthesis import build_synthesis, number, EXECUTIVE_IDS


def pdf_text(pdf):
    """Extrai strings Tj dos streams Flate/ASCII85 produzidos pelo nosso ReportLab."""
    pieces = []
    for stream in re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            payload = base64.a85decode(stream.strip(), adobe=True) if stream.strip().endswith(b"~>") else stream
            decoded = zlib.decompress(payload)
        except (ValueError, zlib.error):
            continue
        for text in re.findall(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", decoded):
            pieces.append(text.decode("latin-1"))
    return "\n".join(pieces)


def validate(folder):
    root = Path(folder).resolve()
    repo = Path(__file__).resolve().parents[1]
    saved = json.loads((root / "sintese_analise.json").read_text(encoding="utf-8"))
    # Derivar novamente sem reescrever a síntese entregue.
    fresh = build_synthesis(root, write=False)
    for key in saved:
        if key != "generated":
            assert saved[key] == fresh[key], f"Síntese desatualizada: {key}"
    metrics = {m["id"]: m for m in saved["metrics"]}
    assert metrics["observed"]["value"] == metrics["comparable"]["value"] + metrics["excluded"]["value"]
    assert metrics["comparable"]["value"] == metrics["eligible"]["value"] + metrics["comparable_small"]["value"]
    assert metrics["combined"]["value"] == metrics["cutoff10"]["value"] + metrics["robust"]["value"] - metrics["overlap"]["value"]
    assert saved["persistence"]["value"] is None and saved["persistence"]["status"] == "não investigado"
    readme = (repo / "README.md").read_text(encoding="utf-8")
    html = (root / "relatorio.html").read_text(encoding="utf-8")
    assert html.index("id='sintese-analise'") < html.index("<section id='mapa-eleitoral'")
    text = pdf_text((root / "relatorio.pdf").read_bytes())
    assert text, "Texto do PDF não extraído"
    for m in saved["metrics"]:
        assert number(m["value"]) in readme, f"Métrica ausente no README: {m['id']}"
        if m["id"] in EXECUTIVE_IDS:
            assert number(m["value"]) in html and number(m["value"]) in text, f"Métrica ausente no relatório: {m['id']}"
    assert "confirmação de persistência de divergências" in html and "não realizada; zero legado não é conclusão" in html
    assert "83 zonas" not in readme
    checked_links = 0
    for link in re.findall(r"\]\(([^)]+)\)", readme):
        parsed = urlparse(link)
        if not parsed.scheme and parsed.path:
            assert (repo / unquote(parsed.path)).exists(), f"Link quebrado no README: {link}"
            checked_links += 1
    assert "{{" not in readme
    print(json.dumps({"status": "síntese e documentação coerentes", "metricas": len(metrics),
        "links_locais_readme": checked_links, "texto_pdf_verificado": True,
        "cobertura_nominal": saved["nominal_coverage"], "persistencia": saved["persistence"]["status"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default="outputs/2026")
    validate(parser.parse_args().folder)
