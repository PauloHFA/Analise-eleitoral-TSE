"""Inspeção do catálogo e de cabeçalhos sem carregar toda a base na memória."""
import json
import sys
import zipfile
from pathlib import Path

from eleicoes.sources import catalog, resources, download

root = Path("data")
year = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
items = resources(catalog(root, year), year)
print(json.dumps([{k: x.get(k) for k in ("kind", "name", "url")} for x in items], ensure_ascii=False, indent=2))
for item in items:
    if item["kind"] not in {"votes", "detail", "official_votes", "official_detail"}:
        continue
    path = download(root, item)
    with zipfile.ZipFile(path) as z:
        print(path.name, [(x.filename, x.file_size) for x in z.infolist()][:5])
        members = [x for x in z.namelist() if x.lower().endswith(".csv")]
        for name in members[:1]:
            with z.open(name) as f:
                for _ in range(3):
                    print(f.readline().decode("latin-1").strip())
