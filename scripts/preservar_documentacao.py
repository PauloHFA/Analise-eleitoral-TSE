"""Inventário de preservação antes/depois da revisão documental, sem alterar as fontes."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
output = root / "outputs/2026"
record = root / "outputs/logs/preservacao-documentacao.json"

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

if args.check:
    saved = json.loads(record.read_text(encoding="utf-8"))
    for name, sha in saved.items():
        assert digest(output / name) == sha, f"Artefato alterado: {name}"
    print(f"Preservados por SHA256: {len(saved)} artefatos analíticos, fichas e mapas.")
else:
    if record.exists():
        raise RuntimeError("O inventário já existe; não substituir a referência anterior")
    paths = set(output.rglob("*.parquet")) | set(output.rglob("*.csv"))
    paths |= set((output / "fichas").glob("*.json")) | set((output / "investigacao_fichas").glob("*.json"))
    paths |= set((output / "graficos").glob("mapa*.png"))
    paths |= {output / "fontes_utilizadas.json", output / "mapa_dados.json", output / "mapa_eleitoral.html", output / "investigacao_resumo.json"}
    record.write_text(json.dumps({str(p.relative_to(output)): digest(p) for p in sorted(paths)}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Referência SHA256 de {len(paths)} artefatos preservada.")
