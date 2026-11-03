"""Catálogo CKAN, downloads verificáveis e arquivos originais imutáveis."""
from __future__ import annotations

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOG = logging.getLogger(__name__)
API = "https://dadosabertos.tse.jus.br/api/3/action/"
_MANIFEST_LOCK = Lock()


class RangeUnsupported(ValueError):
    pass


def session():
    s = requests.Session()
    s.headers["User-Agent"] = "AnaliseEleitoralReproduzivel/0.1 (dados publicos; pesquisa)"
    s.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504])))
    return s


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def catalog(root, year):
    """Salva uma cópia datada; não presume URLs ou conteúdo de arquivos."""
    root = Path(root)
    names = [f"resultados-{year}", f"resultados-{year}-boletim-de-urna"]
    packs = {}
    for name in names:
        r = session().get(API + "package_show", params={"id": name}, timeout=(15, 90))
        r.raise_for_status()
        payload = r.json()
        if not payload.get("success"):
            raise ValueError(f"Catálogo não disponível: {name}")
        packs[name] = payload["result"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    write_json(root / "catalog" / f"{year}-{stamp}.json", packs)
    write_json(root / "catalog" / f"{year}-latest.json", packs)
    return packs


def resources(packs, year):
    """Seleciona Presidente BR (não somar novamente os arquivos das UFs)."""
    items = []
    for res in packs[f"resultados-{year}"]["resources"]:
        url = res["url"]
        name = Path(urlparse(url).path).name.lower()
        kind = None
        if name == f"votacao_secao_{year}_br.zip":
            kind = "votes"
        elif name == f"detalhe_votacao_secao_{year}.zip":
            kind = "detail"
        elif name == f"votacao_candidato_munzona_{year}.zip":
            kind = "official_votes"
        elif name == f"detalhe_votacao_munzona_{year}.zip":
            kind = "official_detail"
        if kind:
            items.append(dict(res, kind=kind, year=year))
    if {r["kind"] for r in items} != {"votes", "detail", "official_votes", "official_detail"}:
        raise ValueError(f"Recursos obrigatórios ausentes no catálogo de {year}")
    for res in packs[f"resultados-{year}-boletim-de-urna"]["resources"]:
        name = Path(urlparse(res["url"]).path).name.lower()
        # Arquivos SHA e PDF são metadados, não dados tabulares de BU.
        if name.endswith(".zip") and "bweb" in name:
            items.append(dict(res, kind="bu", year=year))
    return items


def download(root, resource):
    """Versões por hash; reuso só após validar SHA e ETag/Last-Modified remotos."""
    root = Path(root)
    url = resource["url"]
    host = urlparse(url).hostname or ""
    if not (host == "tse.jus.br" or host.endswith(".tse.jus.br")):
        raise ValueError(f"Download fora do domínio oficial: {host}")
    index_path = root / "manifest.json"
    manifest = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    s = session()
    head = s.head(url, timeout=(15, 90), allow_redirects=True)
    head.raise_for_status()
    remote = {k: head.headers.get(k) for k in ("ETag", "Last-Modified", "Content-Length")}
    old = [m for m in manifest if m["url"] == url and m.get("remote") == remote]
    for m in reversed(old):
        path = root / m["path"]
        if (remote["ETag"] or remote["Last-Modified"]) and path.exists() and sha256(path) == m["sha256"]:
            LOG.info("Cache validado: %s", path.name)
            return path
    name = Path(urlparse(url).path).name
    tmp = root / "raw" / f"{name}.part"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    LOG.info("Baixando %s (%s bytes)", name, remote["Content-Length"])
    length = int(remote["Content-Length"] or 0)
    headers = remote
    total = 0
    ranged = head.headers.get("Accept-Ranges") == "bytes" and bool(length)
    if ranged:
        step = 8 * 1024 * 1024
        def fetch(start):
            end = min(start + step, length) - 1
            hdr = {"Range": f"bytes={start}-{end}"}
            if remote["ETag"]:
                hdr["If-Match"] = remote["ETag"]
            with session().get(url, headers=hdr, stream=True, timeout=(15, 90)) as r:
                if r.status_code in (200, 412, 416):
                    raise RangeUnsupported(f"Faixas indisponíveis ou versão alterada: {url}")
                r.raise_for_status()
                if r.status_code != 206 or r.headers.get("Content-Range") != f"bytes {start}-{end}/{length}":
                    raise RangeUnsupported(f"Servidor não respeitou Range: {url}")
                block = r.content
                if len(block) != end - start + 1:
                    raise ValueError("Bloco de download incompleto")
                return start, block
        try:
            with tmp.open("wb") as f, ThreadPoolExecutor(max_workers=4) as pool:
                starts = iter(range(0, length, step))
                pending = {pool.submit(fetch, start) for start in [next(starts, None) for _ in range(4)] if start is not None}
                while pending:
                    completed, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for future in completed:
                        start, block = future.result()
                        f.seek(start)
                        f.write(block)
                        total += len(block)
                        if total % (32 * 1024 * 1024) == 0:
                            LOG.info("%s: %.0f%%", name, 100 * total / length)
                        following = next(starts, None)
                        if following is not None:
                            pending.add(pool.submit(fetch, following))
                    completed.clear()
            if total != length:
                raise ValueError("Download incompleto")
        except RangeUnsupported:
            ranged = False
            total = 0
            LOG.info("Servidor sem faixas consistentes; usando transferência sequencial: %s", name)
    if not ranged:
        with s.get(url, stream=True, timeout=(15, 90)) as r:
            r.raise_for_status()
            if r.status_code != 200:
                raise ValueError("Resposta parcial inesperada no download sequencial; arquivo recusado")
            headers = {k: r.headers.get(k) for k in remote}
            with tmp.open("wb") as f:
                for block in r.iter_content(1024 * 1024):
                    if block:
                        f.write(block)
                        total += len(block)
            if headers["Content-Length"] and int(headers["Content-Length"]) != total:
                raise ValueError(f"Download incompleto: {name}")
    digest = sha256(tmp)
    dest = tmp.parent / digest[:16] / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp.replace(dest)
    entry = {"url": url, "path": str(dest.relative_to(root)), "sha256": digest,
        "bytes": total, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "remote": headers, "resource_id": resource.get("id"), "kind": resource["kind"],
        "year": resource["year"], "resource_metadata_modified": resource.get("metadata_modified"),
        "license": "CC-BY — Tribunal Superior Eleitoral"}
    with _MANIFEST_LOCK:
        latest = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
        if not any(m["url"] == url and m["sha256"] == digest for m in latest):
            latest.append(entry)
        write_json(index_path, latest)
    return dest
