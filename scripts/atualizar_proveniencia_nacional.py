"""Atualiza hashes de referência após mudança editorial nos relatórios principais."""
import argparse
import json

from eleicoes.national_provenance import refresh_report_provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="outputs/2026")
    args = parser.parse_args()
    print(json.dumps(refresh_report_provenance(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
