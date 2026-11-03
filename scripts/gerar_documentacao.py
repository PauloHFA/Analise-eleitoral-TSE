"""Deriva a síntese e o README dos artefatos; não baixa ou recalcula a eleição."""
import argparse
import json
import re
from pathlib import Path

from eleicoes.synthesis import build_synthesis
from eleicoes.documentation import write_readme


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="outputs/2026")
    parser.add_argument("--validation", help="JSON final emitido pelo validador de entrega")
    parser.add_argument("--tests", help="Log final do pytest")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    synthesis = build_synthesis(args.output)
    validation = json.loads(Path(args.validation).read_text(encoding="utf-8-sig")) if args.validation else None
    test_result = None
    if args.tests:
        log = Path(args.tests).read_text(encoding="utf-8-sig")
        match = re.search(r"\d+ passed[^\r\n]*", log)
        if not match or re.search(r"\d+ (failed|error)", log):
            raise ValueError("O log não registra uma suíte aprovada")
        test_result = match.group(0).strip("= ")
    write_readme(root, synthesis, validation, test_result)
    print("Síntese e README atualizados a partir dos artefatos locais.")


if __name__ == "__main__":
    main()
