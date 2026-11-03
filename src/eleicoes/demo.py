"""Amostra determinística explicitamente simulada, usada só em testes e demonstração."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


def create_demo(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(2026)
    votes, details = [], []
    for section in range(1, 91):
        aptos = 5000 if section == 1 else 400
        for turn in (1, 2):
            if section == 89 and turn == 2:
                continue
            attendance = 4000 if section == 1 else int(rng.integers(270, 330))
            if section == 2:
                attendance = 200 if turn == 1 else 350
            if section == 88 and turn == 2:
                aptos = 500  # composição alterada: não gerar alerta por seção
            blank, null = (0, 0) if section == 1 else (5, 5)
            valid = attendance - blank - null
            if section == 1:
                counts = {13: 2000, 22: 2000, 55: 0} if turn == 1 else {13: 4000, 22: 0, 55: 0}
            else:
                fraction = .45 + .15 * rng.random() + (.04 if turn == 2 else 0)
                a = int(valid * fraction)
                eliminated = int(valid * .05) if turn == 1 else 0
                counts = {13: a, 22: valid - a - eliminated, 55: eliminated}
            common = {"DT_GERACAO": "26/10/2026", "HH_GERACAO": "12:00:00", "ANO_ELEICAO": 2026,
                "NR_TURNO": turn, "SG_UF": "ZZ" if section == 90 else "SP", "CD_MUNICIPIO": 71072 if section <= 45 else 60011,
                "NM_MUNICIPIO": "MUNICÍPIO SIMULADO", "NR_ZONA": 1, "NR_SECAO": section,
                "NR_LOCAL_VOTACAO": 1000 + (section // 5), "CD_CARGO": 1, "CD_ELEICAO": 6256 + turn,
                "DT_ELEICAO": "04/10/2026" if turn == 1 else "25/10/2026"}
            for c, count in dict(counts, **{}).items():
                if turn == 2 and c == 55:
                    continue
                votes.append(dict(common, NR_VOTAVEL=c, NM_VOTAVEL=f"CANDIDATO SIMULADO {c}", QT_VOTOS=count))
            for c, count in [(95, blank), (96, null)]:
                votes.append(dict(common, NR_VOTAVEL=c, NM_VOTAVEL="BRANCO" if c == 95 else "NULO", QT_VOTOS=count))
            details.append(dict(common, QT_APTOS=aptos, QT_COMPARECIMENTO=attendance,
                QT_ABSTENCOES=aptos-attendance, QT_VOTOS_NOMINAIS=valid, QT_VOTOS_BRANCOS=blank,
                QT_VOTOS_NULOS=null, ST_SECAO_INSTALADA="Sim", ST_SECAO_ANULADA="Não"))
    v = pd.DataFrame(votes)
    d = pd.DataFrame(details)
    official_v = v.loc[v.NR_VOTAVEL.lt(95)].groupby(["ANO_ELEICAO", "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_VOTAVEL"], as_index=False).QT_VOTOS.sum()
    official_v["CD_CARGO"] = 1
    official_v["NM_MUNICIPIO"] = "MUNICÍPIO SIMULADO"
    official_d = d.groupby(["ANO_ELEICAO", "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA"], as_index=False)[["QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_VOTOS_NOMINAIS", "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS"]].sum()
    official_d["CD_CARGO"] = 1
    official_d["NM_MUNICIPIO"] = "MUNICÍPIO SIMULADO"
    bu = v.merge(d[["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES"]],
                 on=["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"], validate="many_to_one")
    bu["DS_SECOES_AGREGADAS"] = "#NULO#"
    bu.loc[bu.NR_SECAO.eq(87), "DS_SECOES_AGREGADAS"] = "87, 88"
    bu.loc[bu.NR_SECAO.eq(3) & bu.NR_TURNO.eq(2) & bu.NR_VOTAVEL.eq(13), "QT_VOTOS"] -= 3
    v = pd.concat([v, v.iloc[[10]]], ignore_index=True)  # duplicata idêntica rastreável
    paths = {}
    for kind, frame in [("votes", v), ("detail", d), ("official_votes", official_v), ("official_detail", official_d), ("bu", bu)]:
        path = root / f"SIMULADO_{kind}_2026.csv"
        frame.to_csv(path, sep=";", index=False, encoding="latin-1")
        paths[kind] = path
    return paths
