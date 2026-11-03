"""Reúne etapas anuais já concluídas em uma entrega única e rastreável."""
import argparse
import json
from pathlib import Path

from eleicoes.ingest import connect
from eleicoes.sources import write_json

parser = argparse.ArgumentParser()
parser.add_argument("--aguardar-boletins", action="store_true")
args = parser.parse_args()
output = Path("outputs/2026")
state_path = output / "estado_execucao.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
if args.aguardar_boletins:
    state["status"] = "aguardando integração de boletins; processo principal encerrado"
    write_json(state_path, state)
else:
    summary = json.loads((output / "resumo.json").read_text(encoding="utf-8"))
    history = []
    con = connect("data/analysis.duckdb")
    hashes = set()
    for year in (2018, 2022, 2026):
        folder = output if year == 2026 else output / "historico" / str(year)
        metadata = json.loads((folder / "analise_concluida.json").read_text(encoding="utf-8"))
        history.append(metadata["history"])
        hashes.update(row[0] for row in con.execute(f"SELECT sha256 FROM inputs_{year}").fetchall())
    con.close()
    summary["historical"] = history
    write_json(output / "resumo.json", summary)
    manifest = json.loads(Path("data/manifest.json").read_text(encoding="utf-8"))
    write_json(output / "fontes_utilizadas.json", [m for m in manifest if m["sha256"] in hashes])
    state.update(status="concluído", years_requested=[2018, 2022, 2026], completed=[2018, 2022, 2026],
        historical_checkpoints_reused=[2018, 2022])
    write_json(state_path, state)
    print("Etapas anuais consolidadas")
