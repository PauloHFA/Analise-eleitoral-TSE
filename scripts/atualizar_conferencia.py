"""Reexecuta só a conferência documental e atualiza os checkpoints de uma entrega."""
import json
import argparse
from pathlib import Path

from eleicoes.analysis import export_frame, paired
from eleicoes.cli import save_analysis_cache
from eleicoes.ingest import connect
from eleicoes.reconciliation import reconcile_totals
from eleicoes.sources import write_json

output = Path("outputs/2026")
parser = argparse.ArgumentParser()
parser.add_argument("--years", nargs="+", type=int, default=[2018, 2022, 2026])
parser.add_argument("--agrupamentos", action="store_true", help="Atualizar também composição declarada nas tabelas agregadas")
args = parser.parse_args()
con = connect("data/analysis.duckdb")
for year in args.years:
    folder = output if year == 2026 else output / "historico" / str(year)
    metadata = json.loads((folder / "analise_concluida.json").read_text(encoding="utf-8"))
    if args.agrupamentos:
        base = con.execute("SELECT * FROM read_parquet(?)", [str(folder / "secoes_por_turno.parquet")]).df()
        candidates = [int(c[6:]) for c in base.columns if c.startswith("votes_") and c[6:].isdigit()]
        for level in ("local", "municipio", "uf"):
            export_frame(con, paired(base, metadata["finalists"], candidates, level), folder / f"indicadores_{level}")
        del base
    zones, totals = reconcile_totals(con, year)
    export_frame(con, zones, folder / "reconciliacao_municipio_zona")
    export_frame(con, totals, folder / "reconciliacao_totais")
    metadata["summary"]["linhas_totalizacao_diferentes"] = int(zones.status.ne("concordante").sum())
    metadata["summary"]["linhas_com_zero_implicito"] = int(zones.zero_imputed.sum())
    save_analysis_cache(con, year, folder, metadata["history"], metadata["summary"], metadata["finalists"])
    print(year, "conferências pendentes:", metadata["summary"]["linhas_totalizacao_diferentes"])
    if year == 2026:
        summary = json.loads((folder / "resumo.json").read_text(encoding="utf-8"))
        summary.update(metadata["summary"])
        write_json(folder / "resumo.json", summary)
con.close()
