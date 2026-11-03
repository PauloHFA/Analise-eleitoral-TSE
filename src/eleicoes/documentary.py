"""Revisão de alertas contábeis com a situação oficial da seção."""
from pathlib import Path

import duckdb
import pandas as pd

from .analysis import export_frame
from .ingest import KEY


def review_issues(issues, metadata):
    """Explica apenas a regra inaplicável, preservando o alerta e as fontes originais."""
    evidence = metadata.rename(columns={c: "evidence_" + c for c in metadata.columns if c not in KEY})
    reviewed = issues.merge(evidence, on=KEY, how="left", validate="many_to_one")
    for column in ("aptos", "attendance", "abstention", "valid", "blank", "null_votes", "other_votes"):
        if column not in reviewed:
            reviewed[column] = pd.NA
    reviewed["review_status"] = "pendente de esclarecimento"
    reviewed["review_explanation"] = reviewed.status
    not_installed = reviewed.evidence_installed.fillna("").str.strip().str.upper().isin(["NÃO", "NAO", "N"])
    expected = (reviewed.status.eq("pendente: incompatibilidade aritmética nos dados por seção") &
        not_installed & reviewed.evidence_has_detail.eq(True) & reviewed.evidence_has_votes.eq(False) &
        reviewed.attendance.eq(0) & reviewed.abstention.eq(0) & reviewed.aptos.notna() &
        reviewed[["valid", "blank", "null_votes", "other_votes"]].isna().all(axis=1)).fillna(False)
    reviewed.loc[expected, "review_status"] = "explicado quanto ao alerta aritmético"
    reviewed.loc[expected, "review_explanation"] = (
        "O arquivo oficial marca ST_SECAO_INSTALADA=Não; não há registros de votação, "
        "e comparecimento e abstenções estão zerados. A igualdade comparecimento + abstenções = aptos "
        "foi aplicada fora de seu contexto e não permite classificar esta seção não instalada como "
        "inconsistência da votação. A seção continua excluída da comparação entre turnos. "
        "Esta revisão explica o alerta contábil; não determina o motivo da não instalação nem o destino dos eleitores.")
    return reviewed


def review_exported_issues(output, issues):
    output = Path(output)
    con = duckdb.connect()
    try:
        con.register("issue_keys", issues[KEY].drop_duplicates())
        metadata = con.execute(f"""SELECT {','.join('b.'+k for k in KEY)},
            b.installed,b.has_votes,b.has_detail,b.source_file,b.generation
            FROM read_parquet(?) b JOIN issue_keys k USING({','.join(KEY)})""",
            [str(output / "secoes_por_turno.parquet")]).df()
        reviewed = review_issues(issues, metadata)
        export_frame(con, reviewed, output / "revisao_documental")
        return reviewed
    finally:
        con.close()
