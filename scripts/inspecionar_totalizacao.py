"""Inspeciona categorias oficiais sem alterar os dados da análise."""
import csv
import io
import json
import zipfile
from pathlib import Path

manifest = json.loads(Path("data/manifest.json").read_text(encoding="utf-8"))
for name in ("votacao_candidato_munzona_2026.zip", "detalhe_votacao_munzona_2026.zip"):
    entry = next(m for m in reversed(manifest) if Path(m["path"]).name == name)
    print(name, entry["sha256"], flush=True)
    with zipfile.ZipFile(Path("data") / entry["path"]) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        members = [n for n in members if Path(n).stem.upper().endswith("_BR")] or members
        totals = {}
        examples = []
        for member in members:
            with archive.open(member) as stream:
                reader = csv.DictReader(io.TextIOWrapper(stream, encoding="latin-1"), delimiter=";")
                if not totals:
                    print("Campos:", reader.fieldnames, flush=True)
                for row in reader:
                    if row.get("CD_CARGO") != "1":
                        continue
                    turn = row["NR_TURNO"]
                    if row.get("NR_CANDIDATO") == "28" and len(examples) < 3:
                        examples.append(row)
                    for field, value in row.items():
                        if field.startswith("QT_") and any(s in field for s in ("ANUL", "NUL", "VALID", "NOMINA")):
                            key = turn + "/" + field
                            totals[key] = totals.get(key, 0) + int(value)
        print(json.dumps({"totais": totals, "exemplos_28": examples}, ensure_ascii=False, indent=2), flush=True)
