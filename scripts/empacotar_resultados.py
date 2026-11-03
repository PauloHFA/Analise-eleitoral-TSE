"""Empacota a entrega existente para a release, preservando caminhos e hashes."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time
import zipfile


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package(root, destination, name, paths):
    archive = destination / name
    if archive.exists():
        raise FileExistsError(f"O pacote já existe: {archive}")
    files, started = [], time.monotonic()
    print(f"Iniciando {name}: {len(paths)} arquivos", flush=True)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as output:
        for path in sorted(paths):
            relative = path.relative_to(root).as_posix()
            original_size = path.stat().st_size
            digest = hashlib.sha256()
            with path.open("rb") as source, output.open(relative, "w", force_zip64=True) as target:
                for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
                    target.write(block)
                    digest.update(block)
            assert path.stat().st_size == original_size, f"Fonte alterada durante empacotamento: {relative}"
            files.append({"path": relative, "bytes": original_size, "sha256": digest.hexdigest()})
            if original_size > 100_000_000:
                print(f"{name}: incluído {relative} ({original_size:,} bytes)", flush=True)
    print(f"Validando CRC: {name}", flush=True)
    with zipfile.ZipFile(archive) as check:
        invalid = check.testzip()
        assert invalid is None, f"CRC inválido: {invalid}"
        assert set(check.namelist()) == {f["path"] for f in files}
    size = archive.stat().st_size
    # Os pacotes individuais são mantidos abaixo de 2 GB para o transporte.
    assert size < 2_000_000_000, f"Dividir pacote antes de publicar: {name}"
    print(f"Concluído {name}: {size:,} bytes em {time.monotonic()-started:.1f}s", flush=True)
    return {"name": name, "bytes": size, "sha256": sha256(archive), "files": files}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="resultados-2026-v1")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = root / "outputs/publicacao"
    destination.mkdir(parents=True, exist_ok=True)
    results = root / "outputs/2026"
    current = [p for p in results.rglob("*") if p.is_file() and "historico" not in p.relative_to(results).parts]
    current += [p for p in (root / "data/geografia").glob("*") if p.is_file()]
    jobs = [("resultados-2026.zip", current)] + [
        (f"referencia-{year}.zip", [p for p in (results / "historico" / str(year)).rglob("*") if p.is_file()])
        for year in (2018,2022)]
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(package, root, destination, name, paths) for name, paths in jobs]
        assets = [f.result() for f in futures]
    base = f"https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/download/{args.tag}"
    for asset in assets:
        asset["url"] = f"{base}/{asset['name']}"
    manifest = {"schema_version": 1, "tag": args.tag,
        "release": f"https://github.com/PauloHFA/Analise-eleitoral-TSE/releases/tag/{args.tag}",
        "scope": "Resultados processados de 2026, referências 2018/2022 e geografia. ZIPs eleitorais originais e banco DuckDB não integram estes pacotes.",
        "extraction": "Extrair na raiz do clone; os arquivos preservam caminhos outputs/2026 e data/geografia.",
        "assets": assets}
    serialized = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    (root / "docs/resultados-publicados.json").write_text(serialized, encoding="utf-8")
    (destination / "manifesto-resultados.json").write_text(serialized, encoding="utf-8")
    sums = "".join(f"{a['sha256']}  {a['name']}\n" for a in assets)
    sums += f"{sha256(destination / 'manifesto-resultados.json')}  manifesto-resultados.json\n"
    (destination / "SHA256SUMS.txt").write_text(sums, encoding="utf-8")
    print("Manifesto por arquivo e SHA256SUMS gerados.", flush=True)


if __name__ == "__main__":
    main()
