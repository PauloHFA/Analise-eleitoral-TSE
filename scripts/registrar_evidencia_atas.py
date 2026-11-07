"""Preserva documentos recebidos em nova versão local; não transmite pedidos."""
import argparse
import json

from eleicoes.atas_evidence import prepare_evidence_revision


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registro", required=True, help="JSON revisado com documentos e metadados")
    parser.add_argument("--output", default="outputs/2026", help="Saídas validadas da ampliação")
    parser.add_argument("--data", default="data", help="Pasta local de originais preservados")
    args = parser.parse_args()
    result = prepare_evidence_revision(args.output, args.data, args.registro)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Gere o novo confronto com: eleicoes auditoria --output "
          f"{args.output} --data {args.data} --etapa atas-confronto")
