"""Complementa a entrega com as categorias oficiais preservando as diferenças nominais."""
import json
from pathlib import Path

from eleicoes.analysis import export_frame
from eleicoes.cli import save_analysis_cache
from eleicoes.ingest import connect
from eleicoes.reconciliation import reconcile_categories
from eleicoes.sources import write_json

con = connect("data/analysis.duckdb")
root = Path("outputs/2026")
for year in (2018, 2022, 2026):
    folder = root if year == 2026 else root / "historico" / str(year)
    metadata = json.loads((folder / "analise_concluida.json").read_text(encoding="utf-8"))
    nominal = con.execute("SELECT * FROM read_parquet(?)", [str(folder / "reconciliacao_municipio_zona.parquet")]).df()
    frame = reconcile_categories(con, year, nominal)
    export_frame(con, frame, folder / "reconciliacao_categorias")
    n = int(frame.technical_category_match.sum())
    votes = int(frame.loc[frame.technical_category_match, "official_null_technical"].sum())
    metadata["summary"].update(zonas_reclassificacao_compativel=n, votos_reclassificacao_compativel=votes)
    save_analysis_cache(con, year, folder, metadata["history"], metadata["summary"], metadata["finalists"])
    if year == 2026:
        summary = json.loads((folder / "resumo.json").read_text(encoding="utf-8"))
        summary.update(metadata["summary"])
        write_json(folder / "resumo.json", summary)
    print(year, "zonas compatíveis:", n, "votos:", votes, flush=True)
con.close()
