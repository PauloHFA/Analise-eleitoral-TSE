from __future__ import annotations

import argparse
import gc
import json
import logging
import sys
from pathlib import Path

import pandas as pd

from .analysis import (export_frame, export_table, create_bu_reconciliation, paired, peers, rank,
                       reconciliation_totals, section_base)
from .ingest import KEY, clean, connect, has_table, load, load_bu
from .report import build_report
from .sources import catalog, download, resources, sha256, write_json
from .reconciliation import reconcile_categories

LOG = logging.getLogger(__name__)


def cached(root, resource):
    path = Path(root) / "manifest.json"
    records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    for m in reversed(records):
        if m["url"] == resource["url"]:
            p = Path(root) / m["path"]
            if p.exists() and sha256(p) == m["sha256"]:
                return p
    raise FileNotFoundError(f"Arquivo ausente ou hash inválido: {resource['url']}")


def prepare(root, year, offline=False, with_bu=False):
    if offline:
        packs = json.loads((Path(root) / "catalog" / f"{year}-latest.json").read_text(encoding="utf-8"))
    else:
        packs = catalog(root, year)
    chosen = [r for r in resources(packs, year) if r["kind"] != "bu" or with_bu]
    files = {}
    for item in chosen:
        path = cached(root, item) if offline else download(root, item)
        files.setdefault(item["kind"], []).append(path)
    return files


def ingest_files(con, paths, year, resume=False):
    provenance = pd.DataFrame([{"year": year, "kind": kind, "path": str(path), "sha256": sha256(path)}
        for kind, files in paths.items() for path in files])
    for kind in ("votes", "detail", "official_votes", "official_detail"):
        load(con, paths[kind][0], kind, year, resume=resume)
        clean(con, kind, year)
    if paths.get("bu"):
        load_bu(con, paths["bu"], year)
        clean(con, "bu", year)
    con.register("input_versions", provenance)
    con.execute(f"CREATE OR REPLACE TABLE inputs_{year} AS SELECT * FROM input_versions")
    con.unregister("input_versions")


def historical_row(frame, year):
    domestic = frame.loc[~frame.is_exterior]
    eligible = domestic.comparable & ~domestic.small
    n = int(eligible.sum())
    return {"ano": year, "secoes_observadas": len(domestic), "comparaveis_ge50": n,
        "alertas_5pp": int(domestic.flag_5pp.sum()), "alertas_10pp": int(domestic.flag_10pp.sum()),
        "alertas_15pp": int(domestic.flag_15pp.sum()), "alertas_robustos": int(domestic.robust_flag.sum()),
        "frequencia_10pp_pct": 100 * int(domestic.flag_10pp.sum()) / n if n else None,
        "frequencia_robusta_pct": 100 * int(domestic.robust_flag.sum()) / n if n else None,
        "tipo": "referência descritiva; eleitores e candidatos variam entre anos"}


def analyze_year(con, year, output, do_peers=True, use_bu=True):
    LOG.info("Analisando %s", year)
    output = Path(output)
    base, finalists, candidates = section_base(con, year, use_bu=use_bu)
    names = con.execute(f"SELECT year,turn,candidate,max(candidate_name) candidate_name,sum(votes)::BIGINT votes FROM votes_{year} GROUP BY year,turn,candidate ORDER BY turn,candidate").df()
    export_frame(con, names, output / "candidatos")
    export_frame(con, base, output / "secoes_por_turno")
    for kind in ("votes", "detail", "official_votes", "official_detail", "bu"):
        if has_table(con, f"duplicates_{kind}_{year}"):
            export_frame(con, con.execute(f"SELECT * FROM duplicates_{kind}_{year}").df(), output / f"duplicidades_{kind}")
    frame = paired(base, finalists, candidates)
    if do_peers:
        frame = peers(frame, finalists, candidates)
    frame = rank(frame)
    checks_count = 0
    issues = pd.DataFrame(columns=KEY + ["candidate", "status"])
    if use_bu and has_table(con, f"bu_{year}"):
        table = create_bu_reconciliation(con, year)
        export_table(con, table, output / "conferencia_bu")
        checks_count = con.execute(f"SELECT count(*) FROM {table}").fetchall()[0][0]
        issues = con.execute(f"SELECT * FROM {table} WHERE status<>'concordante'").df()
        check_status = con.execute(f"SELECT {','.join(KEY)},bool_or(status<>'concordante') issue FROM {table} GROUP BY {','.join(KEY)}").df()
        first = check_status.loc[check_status.turn.eq(1)].rename(columns={"issue": "issue_1"}).drop(columns="turn")
        second = check_status.loc[check_status.turn.eq(2)].rename(columns={"issue": "issue_2"}).drop(columns="turn")
        status = first.merge(second, on=["year", "uf", "municipality", "zone", "section"], how="outer")
        status["bu_check"] = "concordante nos dois turnos"
        status.loc[status.issue_1.fillna(True) | status.issue_2.fillna(True), "bu_check"] = "diferença ou cobertura incompleta: revisar"
        frame = frame.merge(status[["year", "uf", "municipality", "zone", "section", "bu_check"]],
                            on=["year", "uf", "municipality", "zone", "section"], how="left", validate="one_to_one")
    else:
        frame["bu_check"] = "BU não processado"
    export_frame(con, frame, output / "indicadores_secoes")
    export_frame(con, frame.loc[frame.is_exterior], output / "indicadores_exterior")
    export_frame(con, frame.loc[~frame.comparable], output / "secoes_sem_comparacao")
    export_frame(con, frame.loc[frame.statistical_alert], output / "alertas_secoes")
    export_frame(con, frame.groupby(["is_exterior", "comparison_reason"], dropna=False, observed=True).size().reset_index(name="sections"), output / "cobertura_por_motivo")
    for level in ("local", "municipio", "uf"):
        agg = paired(base, finalists, candidates, level=level)
        export_frame(con, agg, output / f"indicadores_{level}")
    zone_totals, totals = reconciliation_totals(con, year)
    export_frame(con, zone_totals, output / "reconciliacao_municipio_zona")
    export_frame(con, totals, output / "reconciliacao_totais")
    categories = reconcile_categories(con, year, zone_totals)
    export_frame(con, categories, output / "reconciliacao_categorias")
    # Conferência de aptos/comparecimento por zona, respeitando partições do voto em trânsito.
    key = "year,turn,uf,municipality,zone"
    attendance = con.execute(f"""WITH s AS (SELECT {key},sum(aptos) aptos_sections,
        sum(attendance) attendance_sections FROM detail_{year} GROUP BY {key}),
        o AS (SELECT {key},sum(aptos) aptos_official,sum(attendance) attendance_official
        FROM official_detail_{year} GROUP BY {key}) SELECT * FROM s FULL OUTER JOIN o USING({key})""").df()
    attendance["aptos_difference"] = attendance.aptos_sections - attendance.aptos_official
    attendance["attendance_difference"] = attendance.attendance_sections - attendance.attendance_official
    export_frame(con, attendance, output / "reconciliacao_comparecimento")
    summary = {"ano": year, "secoes_no_universo": len(frame), "secoes_brasil": int((~frame.is_exterior).sum()),
        "secoes_exterior": int(frame.is_exterior.sum()), "comparaveis": int(frame.comparable.sum()),
        "sem_comparacao": int((~frame.comparable).sum()), "presentes_so_1turno": int(frame.coverage.eq("left_only").sum()),
        "presentes_so_2turno": int(frame.coverage.eq("right_only").sum()), "pequenas": int(frame.small.sum()),
        "alertas_estatisticos": int(frame.statistical_alert.sum()),
        "alertas_brasil": int((frame.statistical_alert & ~frame.is_exterior).sum()),
        "alertas_exterior": int((frame.statistical_alert & frame.is_exterior).sum()),
        "registros_bu_conferidos": checks_count,
        "registros_bu_com_diferenca_ou_lacuna": len(issues) if checks_count else None,
        "divergencias_persistentes_confirmadas": 0,
        "linhas_totalizacao_diferentes": int(zone_totals.status.ne("concordante").sum()),
        "linhas_com_zero_implicito": int(zone_totals.zero_imputed.sum()),
        "linhas_com_incompatibilidade_aritmetica": int(base.structural_issue.sum()),
        "pares": "30; município primeiro e complemento na UF", "estado": "processado; alertas requerem revisão"}
    hist = historical_row(frame, year)
    structural = base.loc[base.structural_issue, KEY + ["aptos", "attendance", "abstention", "valid", "blank", "null_votes", "other_votes", "generation", "vote_generation"]].copy()
    if not structural.empty:
        structural["status"] = "pendente: incompatibilidade aritmética nos dados por seção"
        issues = pd.concat([issues, structural], ignore_index=True)
    if use_bu and "bu_aptos" in base:
        mismatch = (base.bu_aptos.notna() & base.aptos.notna() & base.bu_aptos.ne(base.aptos)) | (base.bu_attendance.notna() & base.attendance.notna() & base.bu_attendance.ne(base.attendance))
        counts = base.loc[mismatch, KEY + ["aptos", "attendance", "bu_aptos", "bu_attendance"]].copy()
        if not counts.empty:
            counts["status"] = "pendente: aptos/comparecimento diferem entre detalhe e BU"
            issues = pd.concat([issues, counts], ignore_index=True)
    export_frame(con, issues, output / "pendencias_documentais")
    summary["zonas_reclassificacao_compativel"] = int(categories.technical_category_match.sum())
    summary["votos_reclassificacao_compativel"] = int(categories.loc[categories.technical_category_match, "official_null_technical"].sum())
    del base, zone_totals, totals, attendance, categories
    gc.collect()
    return frame, hist, summary, finalists, issues


def analysis_signature(con, year):
    files = [Path(__file__), Path(__file__).with_name("analysis.py"), Path(__file__).with_name("ingest.py"), Path(__file__).with_name("reconciliation.py")]
    return {"code": [sha256(p) for p in files],
        "inputs": sorted(x[0] for x in con.execute(f"SELECT sha256 FROM inputs_{year}").fetchall())}


def save_analysis_cache(con, year, directory, hist, summary, finalists):
    directory = Path(directory)
    artifacts = {p.name: sha256(p) for p in directory.iterdir() if p.suffix in (".csv", ".parquet")}
    write_json(directory / "analise_concluida.json", {"signature": analysis_signature(con, year),
        "artifacts": artifacts, "history": hist, "summary": summary, "finalists": finalists})


def cached_analysis(con, year, directory):
    directory = Path(directory)
    try:
        data = json.loads((directory / "analise_concluida.json").read_text(encoding="utf-8"))
        if data["signature"] != analysis_signature(con, year):
            return None
        if not data["artifacts"] or not all((directory / n).exists() and sha256(directory / n) == h for n, h in data["artifacts"].items()):
            return None
        return data
    except (OSError, KeyError, ValueError):
        return None


def run(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    db = Path(args.data) / "analysis.duckdb"
    con = connect(db)
    history = []
    state = {"status": "em execução", "years_requested": args.years, "completed": []}
    write_json(output / "estado_execucao.json", state)
    try:
        # Histórico primeiro: libera memória antes da análise corrente.
        years = sorted(set(args.years), key=lambda y: (y == 2026, y))
        if 2026 not in years:
            raise ValueError("Execução final requer 2026; use --years 2026 para omitir histórico explicitamente")
        for year in years:
            if not args.reuse_db:
                files = prepare(args.data, year, args.offline, with_bu=(year == 2026 and not args.no_bu))
                ingest_files(con, files, year, resume=args.resume)
            directory = output if year == 2026 else output / "historico" / str(year)
            cache = cached_analysis(con, year, directory) if args.resume and year != 2026 else None
            if cache:
                LOG.info("Análise histórica validada por hash; reutilizando %s", year)
                history.append(cache["history"])
                state["completed"].append(year)
                write_json(output / "estado_execucao.json", state)
                continue
            frame, hist, summary, finalists, issues = analyze_year(con, year, directory, use_bu=not args.no_bu)
            save_analysis_cache(con, year, directory, hist, summary, finalists)
            history.append(hist)
            state["completed"].append(year)
            write_json(output / "estado_execucao.json", state)
            if year != 2026:
                del frame, issues
                gc.collect()
        manifest = json.loads((Path(args.data) / "manifest.json").read_text(encoding="utf-8"))
        hashes = set()
        for year in years:
            if has_table(con, f"inputs_{year}"):
                hashes.update(x[0] for x in con.execute(f"SELECT sha256 FROM inputs_{year}").fetchall())
        if hashes:
            manifest = [m for m in manifest if m["sha256"] in hashes]
        write_json(output / "fontes_utilizadas.json", manifest)
        build_report(output, frame, history, summary, finalists, issues, manifest)
        state["status"] = "concluído"
        state["limitations"] = ["Alertas exploratórios; revisão documental de persistência não automatizada"]
        write_json(output / "estado_execucao.json", state)
    except Exception as exc:
        state.update(status="incompleto", error=f"{type(exc).__name__}: {exc}")
        write_json(output / "estado_execucao.json", state)
        raise
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description="Comparação presidencial reproduzível — TSE")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run", help="Baixar, processar, conferir e gerar relatório")
    execute.add_argument("--years", nargs="+", type=int, choices=[2018, 2022, 2026], default=[2018, 2022, 2026])
    execute.add_argument("--data", default="data")
    execute.add_argument("--output", default="outputs/2026")
    execute.add_argument("--offline", action="store_true", help="Usar só arquivos locais com hash validado")
    execute.add_argument("--reuse-db", action="store_true", help="Analisar tabelas já carregadas, sem downloads")
    execute.add_argument("--resume", action="store_true", help="Retomar tabelas brutas já confirmadas do mesmo ZIP/hash; usar com a mesma versão do programa")
    execute.add_argument("--no-bu", action="store_true", help="Triagem explicitamente sem conferência de BU")
    fetch = sub.add_parser("fetch", help="Somente obter e verificar fontes")
    fetch.add_argument("--years", nargs="+", type=int, choices=[2018, 2022, 2026], default=[2026])
    fetch.add_argument("--data", default="data")
    fetch.add_argument("--bu", action="store_true")
    demo = sub.add_parser("demo", help="Relatório isolado, com dados simulados e marca explícita")
    demo.add_argument("--output", default="outputs/demo")
    inquiry = sub.add_parser("investigar", help="Investigar zeros e viradas usando os Parquets locais, sem baixar novamente")
    inquiry.add_argument("--output", default="outputs/2026")
    inquiry.add_argument("--ufs", nargs="+", default=["RJ", "MG"], help="UFs para a investigação de viradas; zeros são nacionais")
    stability = sub.add_parser("estabilidade", help="Comparar pares aninhados, preservando a análise publicada")
    stability.add_argument("--output", default="outputs/2026", help="Pasta da referência já processada")
    stability.add_argument("--dest", help="Nova pasta de saída; padrão: <output>/estabilidade")
    stability.add_argument("--pares", nargs="+", type=int, default=[15,30,50])
    coverage = sub.add_parser("cobertura", help="Examinar cobertura e perfis incluídos/excluídos sem reingestão")
    coverage.add_argument("--output", default="outputs/2026", help="Pasta da referência já processada")
    coverage.add_argument("--dest", help="Nova pasta de saída; padrão: <output>/cobertura")
    coverage.add_argument("--limiares",nargs="+",type=float,default=[50,80,95])
    dossier = sub.add_parser("dossie", help="Organizar diferenças nominais, categorias e versões locais, sem downloads")
    dossier.add_argument("--output", default="outputs/2026", help="Pasta da referência já processada")
    dossier.add_argument("--data", default="data", help="Pasta dos arquivos originais preservados")
    dossier.add_argument("--dest", help="Nova pasta de saída; padrão: <output>/dossie_categorias")
    national = sub.add_parser("nacional", help="Ampliar a investigação em saída própria, sem downloads")
    national.add_argument("--output", default="outputs/2026")
    national.add_argument("--dest", help="Pasta nova para a etapa selecionada")
    national.add_argument("--etapa", choices=["inventario","taxas","mapas"], default="inventario")
    national.add_argument("--min-elegiveis",type=int,default=30)
    national.add_argument("--cobertura-minima",type=float,default=80)
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    if args.command == "run":
        run(args)
    elif args.command == "fetch":
        for year in args.years:
            prepare(args.data, year, with_bu=args.bu)
    elif args.command == "investigar":
        from .investigation import investigate
        investigate(args.output, args.ufs)
    elif args.command == "estabilidade":
        from .stability import run_stability
        result = run_stability(args.output,args.dest,args.pares)
        LOG.info("Estabilidade concluída: %s elegíveis; %s no universo comum",result["eligible_units"],result["common_units"])
    elif args.command == "cobertura":
        from .coverage import run_coverage
        result = run_coverage(args.output,args.dest,args.limiares)
        LOG.info("Cobertura concluída: %s observadas; %s elegíveis",result["observed_units"],result["eligible_units"])
    elif args.command == "dossie":
        from .dossier import run_dossier
        result = run_dossier(args.output, args.data, args.dest)
        LOG.info("Dossiê concluído: %s unidades por turno; %s com correspondência aritmética", result["selected_unit_turns"], result["technical_units"])
    elif args.command == "nacional":
        if args.etapa=="inventario":
            from .national_inventory import run_inventory
            result = run_inventory(args.output,args.dest)
        elif args.etapa=="taxas":
            from .national_rates import run_rates
            result = run_rates(args.output,args.dest,args.min_elegiveis,args.cobertura_minima)
        else:
            from .national_map import run_maps
            result = run_maps(args.output,args.dest,args.min_elegiveis,args.cobertura_minima)
        LOG.info("Etapa nacional concluída: %s", result.get("tables",result.get("mapped")))
    else:
        from .demo import create_demo
        root = Path(args.output)
        paths = create_demo(root / "simulados")
        con = connect(root / "demo.duckdb")
        ingest_files(con, {k: [v] for k, v in paths.items()}, 2026)
        frame, hist, summary, finalists, issues = analyze_year(con, 2026, root)
        build_report(root, frame, [dict(hist, tipo="SIMULADO; não é referência histórica real")], summary, finalists, issues, [], demo=True)
        con.close()
    LOG.info("Concluído: %s", getattr(args, "output", args.data if hasattr(args, "data") else ""))


if __name__ == "__main__":
    main()
