"""Refresh national-stage references after editorial-only report changes."""
import json
from datetime import datetime, timezone
from pathlib import Path

from .sources import sha256, write_json


PHASES = ("inventario", "taxas", "mapas")
REPORT_INPUTS = ("relatorio.html", "relatorio.pdf")
UPSTREAM_SUMMARIES = {
    "nacional/taxas/resumo.json": "taxas",
    "nacional/inventario/resumo.json": "inventario",
}
REASON = (
    "Referências atualizadas após revisão editorial dos relatórios principais; "
    "indicadores e resultados nacionais não foram recalculados."
)


def refresh_report_provenance(output):
    """Refresh only changed main-report hashes; reject any analytical input change."""
    output = Path(output).resolve()
    current_report_hashes = {
        name: sha256(output / name)
        for name in REPORT_INPUTS
    }
    phase_records = {}

    for phase in PHASES:
        folder = output / "nacional" / phase
        summary_path = folder / "resumo.json"
        state_path = folder / "estado_execucao.json"
        manifest_path = folder / "manifesto.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        if summary.get("status") != "concluído" or state.get("status") != "concluído":
            raise ValueError(f"A etapa nacional não está concluída: {phase}")
        if summary.get("input_hashes") != state.get("input_hashes"):
            raise ValueError(f"Snapshots de entrada divergentes entre resumo e estado: {phase}")
        for name, digest in manifest.items():
            path = folder / name
            if not path.is_file() or sha256(path) != digest:
                raise ValueError(f"Saída nacional não confere com o manifesto: {path}")
        phase_records[phase] = {
            "folder": folder,
            "summary": summary,
            "state": state,
            "manifest": manifest,
        }

    # Preflight every source before writing anything. Upstream summary hashes can
    # change during this refresh, but only when their provenance records confirm
    # the same report-only update and their output manifest is intact.
    for phase in PHASES:
        record = phase_records[phase]
        for name, expected in record["summary"]["input_hashes"].items():
            path = output / name
            actual = current_report_hashes.get(name)
            if actual is None:
                actual = sha256(path)
            if expected == actual or name in REPORT_INPUTS:
                continue
            producer = UPSTREAM_SUMMARIES.get(name)
            producer_record = phase_records.get(producer)
            if producer_record is None or producer_record["summary"].get("provenance_refresh", {}).get(
                    "reason") != REASON:
                raise ValueError(f"Entrada analítica mudou; não atualizar proveniência: {name}")
            producer_manifest = producer_record["manifest"]
            producer_summary_path = producer_record["folder"] / "resumo.json"
            if producer_manifest.get("resumo.json") != sha256(producer_summary_path):
                raise ValueError(f"Resumo da etapa anterior não confere com o manifesto: {producer_summary_path}")

    updated = []
    for phase in PHASES:
        record = phase_records[phase]
        folder = record["folder"]
        summary = json.loads((folder / "resumo.json").read_text(encoding="utf-8"))
        state = json.loads((folder / "estado_execucao.json").read_text(encoding="utf-8"))
        manifest = json.loads((folder / "manifesto.json").read_text(encoding="utf-8"))
        changed_reports = {}
        changed_upstream_summaries = {}
        for name, expected in summary["input_hashes"].items():
            actual = current_report_hashes.get(name)
            if actual is None:
                actual = sha256(output / name)
            if expected == actual:
                continue
            if name in REPORT_INPUTS:
                changed_reports[name] = expected
            elif name in UPSTREAM_SUMMARIES:
                producer_record = phase_records[UPSTREAM_SUMMARIES[name]]
                producer_summary_path = producer_record["folder"] / "resumo.json"
                if producer_record["summary"].get("provenance_refresh", {}).get("reason") != REASON:
                    raise ValueError(f"Entrada analítica mudou; não atualizar proveniência: {name}")
                changed_upstream_summaries[name] = expected
            else:
                raise ValueError(f"Entrada analítica mudou; não atualizar proveniência: {name}")

        if not changed_reports and not changed_upstream_summaries:
            continue

        provenance = summary.get("provenance_refresh", {})
        provenance["refreshed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        provenance["reason"] = REASON
        provenance["recalculated"] = False
        provenance.setdefault("previous_report_hashes", {}).update(changed_reports)
        provenance.setdefault("current_report_hashes", {}).update({
            name: current_report_hashes[name] for name in changed_reports
        })
        provenance.setdefault("previous_upstream_summary_hashes", {}).update(changed_upstream_summaries)
        provenance.setdefault("current_upstream_summary_hashes", {}).update({
            name: sha256(output / name) for name in changed_upstream_summaries
        })
        summary["provenance_refresh"] = provenance
        state["provenance_refresh"] = provenance
        for name in changed_reports:
            summary["input_hashes"][name] = current_report_hashes[name]
        for name in changed_upstream_summaries:
            summary["input_hashes"][name] = sha256(output / name)
        state["input_hashes"] = dict(summary["input_hashes"])
        write_json(folder / "resumo.json", summary)
        write_json(folder / "estado_execucao.json", state)
        manifest["resumo.json"] = sha256(folder / "resumo.json")
        write_json(folder / "manifesto.json", manifest)
        record["summary"] = summary
        record["state"] = state
        record["manifest"] = manifest
        updated.append(phase)

    return {
        "status": "atualizado" if updated else "já atualizado",
        "phases_updated": updated,
        "reports": current_report_hashes,
        "updated_summary_dependencies": {
            phase: phase_records[phase]["summary"].get("provenance_refresh", {}).get(
                "current_upstream_summary_hashes", {})
            for phase in updated
            if phase_records[phase]["summary"].get("provenance_refresh", {}).get(
                "current_upstream_summary_hashes")
        },
        "recalculated": False,
    }
