"""Reedita somente o PDF a partir dos artefatos existentes."""
import argparse
import json

from eleicoes.pdf_report import build_pdf_report, load_pdf_inputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default="outputs/2026")
    args = parser.parse_args()
    print(json.dumps(build_pdf_report(**load_pdf_inputs(args.folder)), ensure_ascii=False, indent=2))
