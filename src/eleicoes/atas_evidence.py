"""Registro local, versionado e revisado de documentos de atas e atendimento."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

import duckdb

from .audit_atas import GEO, SPECIFIC_TYPES, key, official_source
from .sources import sha256, write_json

RESPONSE_TYPES = {"resposta_oficial"}
FINDINGS = {"corrobora_registro", "contradiz_registro", "inconclusivo"}
REVIEW_STATUS = "revisao_documental_registrada"
ALLOWED_SUFFIXES = {".pdf", ".html", ".htm", ".txt", ".json", ".xml",
                    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".eml"}
MAX_DOCUMENT_BYTES = 50 * 1024 * 1024


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _verify_manifest(folder):
    manifest_path = folder / "manifesto.json"
    manifest = _read_json(manifest_path)
    for name, digest in manifest.items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder.resolve()) or sha256(path) != digest:
            raise ValueError(f"Arquivo ausente, fora da pasta ou alterado: {name}")
    return manifest


def _next_id(items, field, prefix):
    values = [int(match.group(1)) for item in items
              if (match := re.fullmatch(rf"{prefix}(\d+)", str(item.get(field, ""))))]
    return f"{prefix}{max(values, default=0) + 1:02d}"


def _text(record, field, limit):
    value = record.get(field)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f"Campo {field} ausente ou inválido")
    return value.strip()


def _canonical_identity(identity):
    if not isinstance(identity, dict) or set(GEO) - identity.keys():
        raise ValueError("Identidade territorial incompleta")
    values = key(identity)
    year, turn, uf, municipality, zone, section = values
    return dict(year=year, turn=turn, uf=uf, municipality=str(municipality),
                zone=str(zone), section=str(section))


def _validate_output(output):
    folder = output / "auditoria" / "atas_ampliacao"
    summary = _read_json(folder / "resumo.json")
    if summary.get("status") != "concluído" or not summary.get("preservation_verified"):
        raise ValueError("A saída da pesquisa ampliada não está validada")
    current_manifest = _verify_manifest(folder)
    if sha256(folder / "resumo.json") != current_manifest.get("resumo.json"):
        raise ValueError("Síntese fora do manifesto")
    return folder, summary


def prepare_evidence_revision(output, data, records_path):
    """Cria data/auditoria/atas/v3 sem alterar v2 nem publicar o original."""
    output = Path(output).resolve()
    data = Path(data).resolve()
    records_path = Path(records_path).resolve()
    current_output, summary = _validate_output(output)
    previous = data / "auditoria" / "atas" / "v2"
    destination = data / "auditoria" / "atas" / "v3"
    if destination.exists():
        raise FileExistsError("Captura v3 já existe; preserve-a e escolha uma nova árvore --data")
    previous_manifest = _verify_manifest(previous)
    if sha256(previous / "manifesto.json") != summary.get("capture_manifest_sha256"):
        raise ValueError("A captura v2 não corresponde à saída validada")
    for name, digest in summary.get("capture_hashes", {}).items():
        if previous_manifest.get(name) != digest:
            raise ValueError("Hash da captura v2 difere da síntese")

    records = _read_json(records_path)
    documents = records.get("documents") if isinstance(records, dict) else None
    if not isinstance(documents, list) or not documents:
        raise ValueError("O registro deve conter uma lista não vazia em 'documents'")

    cases_path = current_output / "casos.parquet"
    issues_path = current_output / "confronto.parquet"
    con = duckdb.connect()
    try:
        cases = con.read_parquet(str(cases_path)).df().to_dict("records")
        issues = con.read_parquet(str(issues_path)).df().to_dict("records")
    finally:
        con.close()
    cases_by_key = {key(case): case for case in cases}
    issue_pairs = {(key(issue), str(issue["indicator"])) for issue in issues}

    research = _read_json(previous / "pesquisa.json")
    registry = _read_json(previous / "evidencias.json")
    if research.get("version") != 1 or registry.get("version") != 1:
        raise ValueError("Versão de registro não suportada")
    sources = research.get("sources")
    evidence = registry.get("evidence")
    if not isinstance(sources, list) or not isinstance(evidence, list):
        raise ValueError("Catálogo de fontes ou registro de evidências inválido")
    source_ids = {item["source_id"] for item in sources}
    evidence_ids = {item["evidence_id"] for item in evidence}
    if len(source_ids) != len(sources) or len(evidence_ids) != len(evidence):
        raise ValueError("Identificadores existentes repetidos")

    prepared = []
    seen_items = set()
    for item in documents:
        if not isinstance(item, dict):
            raise ValueError("Cada documento deve ser um objeto")
        identity = _canonical_identity(item.get("case"))
        case_key = key(identity)
        if case_key not in cases_by_key:
            raise ValueError("Documento não corresponde a uma unidade do inventário")
        indicator = _text(item, "indicator", 100)
        if (case_key, indicator) not in issue_pairs:
            raise ValueError("Apontamento não pertence à unidade selecionada")
        kind = item.get("document_kind")
        if kind not in SPECIFIC_TYPES | RESPONSE_TYPES:
            raise ValueError("Tipo documental fora da lista permitida")
        url = _text(item, "source_url", 2048)
        if not official_source(url) or "#" in url:
            raise ValueError("Origem deve ser URL HTTPS oficial, sem fragmento")
        title = _text(item, "title", 500)
        locator = _text(item, "locator", 1000)
        justification = _text(item, "justification", 4000)
        finding = item.get("finding")
        if finding not in FINDINGS:
            raise ValueError("Resultado da revisão documental inválido")
        if kind in RESPONSE_TYPES and finding != "inconclusivo":
            raise ValueError("Resposta oficial registra escopo, mas não corrobora ocorrência")
        if item.get("review_status") != REVIEW_STATUS:
            raise ValueError("Documento exige revisão documental registrada")
        document_path = Path(_text(item, "document_path", 4096)).expanduser()
        if document_path.is_symlink():
            raise ValueError("Não são aceitos arquivos de evidência por link simbólico")
        document_path = document_path.resolve()
        if not document_path.is_file():
            raise FileNotFoundError("Arquivo documental local não encontrado")
        suffix = document_path.suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise ValueError("Formato documental não permitido")
        if document_path.stat().st_size <= 0 or document_path.stat().st_size > MAX_DOCUMENT_BYTES:
            raise ValueError("Tamanho do documento fora dos limites permitidos")
        uniqueness = (case_key, indicator, url, sha256(document_path))
        if uniqueness in seen_items:
            raise ValueError("Documento repetido para o mesmo apontamento")
        seen_items.add(uniqueness)
        prepared.append(dict(identity=identity, case_key=case_key, indicator=indicator, kind=kind,
            url=url, title=title, locator=locator, justification=justification, finding=finding,
            document_path=document_path, suffix=suffix, digest=sha256(document_path)))

    base = destination.parent
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".v3-stage-", dir=base) as temporary:
        staged = Path(temporary) / "v3"
        shutil.copytree(previous, staged)
        staged_sources = _read_json(staged / "pesquisa.json")
        staged_registry = _read_json(staged / "evidencias.json")
        for item in prepared:
            source_id = _next_id(staged_sources["sources"], "source_id", "S")
            evidence_id = _next_id(staged_registry["evidence"], "evidence_id", "E")
            if source_id in source_ids or evidence_id in evidence_ids:
                raise ValueError("Colisão de identificadores")
            relative = Path("documentos") / f"{source_id}{item['suffix']}"
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item["document_path"], target)
            if sha256(target) != item["digest"]:
                raise ValueError("Cópia do documento não preservou o hash")
            staged_sources["sources"].append(dict(
                source_id=source_id, url=item["url"], title=item["title"],
                capture_file=relative.as_posix(), capture_sha256=item["digest"],
                kind=item["kind"], scope=item["justification"],
                year=item["identity"]["year"], turn=item["identity"]["turn"],
                uf=item["identity"]["uf"], municipality=item["identity"]["municipality"],
                zone=item["identity"]["zone"], section=item["identity"]["section"],
                method="Arquivo local preservado byte a byte; SHA256 do arquivo; URL declarada, não autenticada automaticamente",
                specific_document=item["kind"] in SPECIFIC_TYPES))
            staged_registry["evidence"].append(dict(
                evidence_id=evidence_id, source_id=source_id, case=item["identity"],
                indicator=item["indicator"], finding=item["finding"], locator=item["locator"],
                justification=item["justification"], review_status=REVIEW_STATUS,
                registered_at=datetime.now(timezone.utc).isoformat()))
            source_ids.add(source_id)
            evidence_ids.add(evidence_id)
        staged_sources.update(evidence_revision=dict(
            based_on_capture_manifest_sha256=sha256(previous / "manifesto.json"),
            evidence_entries=len(prepared), prepared_at=datetime.now(timezone.utc).isoformat(),
            preparation_code_sha256=sha256(Path(__file__)),
            interpretation="Originais preservados localmente; URL e revisão são declarações, não autenticação automática"))
        staged_registry["scope"] = (
            "Registro local revisado; evidências documentais não confirmam causa automaticamente. "
            "Respostas oficiais registram apenas o escopo consultado.")
        write_json(staged / "pesquisa.json", staged_sources)
        write_json(staged / "evidencias.json", staged_registry)
        manifest = {path.relative_to(staged).as_posix(): sha256(path)
                    for path in sorted(staged.rglob("*")) if path.is_file() and path.name != "manifesto.json"}
        write_json(staged / "manifesto.json", manifest)
        if destination.exists():
            raise FileExistsError("Captura v3 já existe")
        os.replace(staged, destination)
    return dict(status="preparado", version="v3", evidence_entries=len(prepared),
                capture_manifest_sha256=sha256(destination / "manifesto.json"),
                original_documents="preservados em data/auditoria/atas/v3/documentos")
