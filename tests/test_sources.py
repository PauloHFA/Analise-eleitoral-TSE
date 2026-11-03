import json
import zipfile

import pandas as pd
import pytest

from eleicoes.cli import cached
from eleicoes.ingest import csv_chunks
from eleicoes.sources import resources, sha256, download


def test_cache_detects_modified_file(tmp_path):
    original = tmp_path / "original.zip"
    original.write_bytes(b"original")
    resource = {"url": "https://cdn.tse.jus.br/original.zip"}
    record = dict(resource, path="original.zip", sha256=sha256(original))
    (tmp_path / "manifest.json").write_text(json.dumps([record]), encoding="utf-8")
    assert cached(tmp_path, resource) == original
    original.write_bytes(b"modificado")
    with pytest.raises(FileNotFoundError, match="hash"):
        cached(tmp_path, resource)


def test_zip_prefers_br_without_double_counting(tmp_path):
    path = tmp_path / "archive.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("dados_BR.csv", "CD_CARGO;QT_VOTOS\n1;100\n")
        z.writestr("dados_SP.csv", "CD_CARGO;QT_VOTOS\n1;100\n")
        z.writestr("dados_BRASIL.csv", "CD_CARGO;QT_VOTOS\n1;100\n")
    chunks = list(csv_chunks(path))
    assert sum(len(c) for c in chunks) == 1
    assert chunks[0].QT_VOTOS.iloc[0] == "100"


def test_resource_selection_requires_all_four_datasets():
    with pytest.raises(ValueError, match="Recursos obrigatórios"):
        resources({"resultados-2026": {"resources": []}}, 2026)


def test_server_ignoring_ranges_uses_validated_stream(tmp_path, monkeypatch):
    payload = b"PK-dados-simulados"
    calls = []

    class Response:
        status_code = 200
        headers = {"Accept-Ranges": "bytes", "Content-Length": str(len(payload)), "ETag": "versao-1"}
        def raise_for_status(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def iter_content(self, size):
            yield payload
        @property
        def content(self):
            raise AssertionError("Uma resposta completa não deve ser materializada para testar Range")

    class Session:
        def head(self, *args, **kwargs):
            return Response()
        def get(self, *args, **kwargs):
            calls.append(kwargs.get("headers", {}))
            return Response()

    monkeypatch.setattr("eleicoes.sources.session", Session)
    resource = {"url": "https://cdn.tse.jus.br/dados.zip", "kind": "votes", "year": 2026}
    result = download(tmp_path, resource)
    assert result.read_bytes() == payload
    assert any("Range" in c for c in calls) and any("Range" not in c for c in calls)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest[0]["bytes"] == len(payload) and manifest[0]["sha256"] == sha256(result)
