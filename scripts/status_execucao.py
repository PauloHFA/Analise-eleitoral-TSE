"""Mostra os últimos eventos de uma execução redirecionada para os logs locais."""
import json
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding="utf-8")
print(datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"))
for name in ("execucao.log", "execucao-erros.log", "prefetch-bu-erros.log"):
    path = Path(name)
    if path.exists():
        raw = path.read_bytes()
        content = raw.decode("utf-16" if raw.startswith(b"\xff\xfe") else "utf-8", errors="replace")
        print(name)
        print("\n".join(content.splitlines()[-1:] if name.startswith("prefetch") else content.splitlines()[-10:]))
state = Path("outputs/2026/estado_execucao.json")
if state.exists():
    print(state.read_text(encoding="utf-8"))
manifest = Path("data/manifest.json")
if manifest.exists():
    records = json.loads(manifest.read_text(encoding="utf-8"))
    print("Arquivos de BU obtidos:", len({r["url"] for r in records if r.get("kind") == "bu"}))
for folder in (Path("outputs/2026/historico/2018"), Path("outputs/2026/historico/2022"), Path("outputs/2026")):
    if folder.exists():
        files = list(folder.glob("*.parquet"))
        print(folder, "Parquets:", len(files), "MB:", round(sum(p.stat().st_size for p in files) / 1024**2, 1))
