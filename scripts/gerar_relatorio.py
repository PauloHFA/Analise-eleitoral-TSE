"""Regera HTML/PDF usando somente as tabelas exportadas, sem baixar ou recalcular."""
import argparse
import json
from pathlib import Path

import duckdb

from eleicoes.report import build_report


def main(folder):
    folder = Path(folder)
    saved = json.loads((folder / "resumo.json").read_text(encoding="utf-8"))
    con = duckdb.connect()
    frame = con.execute("SELECT * FROM read_parquet(?)", [str(folder / "indicadores_secoes.parquet")]).df()
    issues = con.execute("SELECT * FROM read_parquet(?)", [str(folder / "pendencias_documentais.parquet")]).df()
    candidates = con.execute("SELECT DISTINCT candidate FROM read_parquet(?) WHERE turn=2 AND candidate BETWEEN 1 AND 94 ORDER BY candidate",
        [str(folder / "candidatos.parquet")]).fetchall()
    manifest_path = folder / "fontes_utilizadas.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    summary = {k: v for k, v in saved.items() if k not in ("generated", "demo", "historical")}
    build_report(folder, frame, saved.get("historical", []), summary, [int(x[0]) for x in candidates], issues, manifest, demo=saved.get("demo", False))
    con.close()
    print("Relatórios regenerados:", folder)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default="outputs/2026")
    main(parser.parse_args().folder)
