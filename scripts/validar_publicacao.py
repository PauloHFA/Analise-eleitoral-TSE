"""Verifica pacotes e conteúdos contra o manifesto publicado, sem mudar os dados."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def sha256(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packages", default="outputs/publicacao")
    parser.add_argument("--workspace", action="store_true", help="Comparar também a pasta de trabalho com o snapshot da release")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "docs/resultados-publicados.json").read_text(encoding="utf-8"))
    count = 0
    for asset in manifest["assets"]:
        path = root / args.packages / asset["name"]
        assert path.stat().st_size == asset["bytes"], f"Tamanho do pacote: {path}"
        assert sha256(path) == asset["sha256"], f"Hash do pacote: {path}"
        with zipfile.ZipFile(path) as archive:
            assert set(archive.namelist()) == {f["path"] for f in asset["files"]}
            for file in asset["files"]:
                info = archive.getinfo(file["path"])
                assert info.file_size == file["bytes"], f"Tamanho do arquivo: {file['path']}"
                digest = hashlib.sha256()
                with archive.open(file["path"]) as stream:
                    for block in iter(lambda: stream.read(4*1024*1024), b""):
                        digest.update(block)
                assert digest.hexdigest() == file["sha256"], f"Conteúdo do pacote: {file['path']}"
                if args.workspace:
                    source = root / file["path"]
                    assert source.resolve().is_relative_to(root), "Caminho fora do projeto"
                    assert source.stat().st_size == file["bytes"] and sha256(source) == file["sha256"], f"Fonte diferente do snapshot: {file['path']}"
                count += 1
        print(f"Pacote e conteúdos conferidos: {asset['name']}", flush=True)
    print(json.dumps({"status": "publicação local validada", "pacotes": len(manifest["assets"]), "arquivos": count}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
