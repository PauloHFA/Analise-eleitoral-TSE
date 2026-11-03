"""Mapa municipal offline: geometria IBGE e resultados TSE, com vínculo auditável."""
from __future__ import annotations

import html
import json
import logging
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.path import Path as PlotPath
from matplotlib.patches import PathPatch, Patch
import pandas as pd
import requests

from .analysis import export_frame
from .sources import sha256, write_json

LOG = logging.getLogger(__name__)
BLUE, RED, GRAY = "#165dcc", "#cf2639", "#c5cbd3"
LOCALITIES = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"
MESH = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application%2Fvnd.geo%2Bjson&qualidade=minima&intrarregiao=municipio"
MT_2025 = "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2025/UFs/MT/MT_Municipios_2025.zip"
# Variantes conferidas entre os nomes das duas fontes; nunca fazer aproximação difusa.
NAME_VARIANTS = {
    ("GO","92690","BOM JESUS"):"5203500",
    ("MG","41092","BARÃO DE MONTE ALTO"):"3105509",
    ("MG","44571","DONA EUSÉBIA"):"3122900",
    ("MG","53031","SÃO THOMÉ DAS LETRAS"):"3165206",
    ("MT","91553","SANTO ANTÔNIO DO LEVERGER"):"5107800",
    ("PA","4120","ELDORADO DOS CARAJÁS"):"1502954",
    ("PR","77119","MUNHOZ DE MELLO"):"4116307",
    ("RN","17035","BOA SAÚDE"):"2405306",
    ("RO","256","ESPIGÃO DO OESTE"):"1100098",
    ("RO","337","ALVORADA DO OESTE"):"1100346",
    ("RR","3158","SÃO LUIZ"):"1400605",
    ("SE","31011","AMPARO DE SÃO FRANCISCO"):"2800100",
    ("SP","71013","SÃO LUÍS DO PARAITINGA"):"3550001",
}


def normalize_name(value):
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", text)


def cached_json(folder, name, url, offline=False):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    index = folder / (name + ".json")
    if index.exists():
        record = json.loads(index.read_text(encoding="utf-8"))
        path = folder / record["file"]
        if path.exists() and sha256(path) == record["sha256"]:
            return json.loads(path.read_text(encoding="utf-8")), record
    if offline:
        raise FileNotFoundError(f"Geografia local ausente ou alterada: {name}")
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    payload = response.json()
    import hashlib
    digest = hashlib.sha256(response.content).hexdigest()
    path = folder / f"{name}-{digest[:16]}.json"
    path.write_bytes(response.content)
    record = dict(url=response.url,sha256=digest,file=path.name,bytes=len(response.content),retrieved_utc=datetime.now(timezone.utc).isoformat(),source="IBGE")
    write_json(index,record)
    return payload, record


def locality_index(localities):
    records = []
    for item in localities:
        if "municipio-id" in item:
            code, name, uf = item["municipio-id"], item["municipio-nome"], item["UF-sigla"]
        else:
            state = ((item.get("microrregiao") or {}).get("mesorregiao") or {}).get("UF")
            state = state or ((item.get("regiao-imediata") or {}).get("regiao-intermediaria") or {}).get("UF")
            code, name, uf = item["id"], item["nome"], state["sigla"]
        records.append(dict(ibge_code=str(code),ibge_name=name,uf=uf,normalized_name=normalize_name(name)))
    result = pd.DataFrame(records).drop_duplicates("ibge_code")
    if result.duplicated(["uf","normalized_name"]).any():
        raise ValueError("Nomes municipais ambíguos na mesma UF; não vincular automaticamente")
    return result


def match_municipalities(votes, localities):
    municipalities = locality_index(localities)
    base = votes.copy()
    base["normalized_name"] = base.municipality_name_1.map(normalize_name)
    joined = base.merge(municipalities,on=["uf","normalized_name"],how="left",validate="many_to_one")
    joined["mapping_method"] = "UF e nome normalizado exatos"
    joined.loc[joined.ibge_code.isna(),"mapping_method"] = "sem correspondência: revisar nome/código"
    for index,row in joined.loc[joined.ibge_code.isna()].iterrows():
        alias = next((code for (uf,tse,name),code in NAME_VARIANTS.items()
            if uf==row.uf and tse==row.municipality and normalize_name(name)==row.normalized_name),None)
        target = municipalities.loc[municipalities.ibge_code.eq(alias) & municipalities.uf.eq(row.uf)]
        if len(target)==1:
            joined.loc[index,["ibge_code","ibge_name","mapping_method"]] = [alias,target.iloc[0].ibge_name,"variante de nome revisada entre TSE e IBGE"]
    if joined.loc[joined.ibge_code.notna()].ibge_code.duplicated().any():
        raise ValueError("Mais de um código TSE vinculado ao mesmo município IBGE")
    return joined


def mt_mesh(folder,offline=False):
    import hashlib
    import shapefile
    folder=Path(folder)
    index=folder / "mt_2025.json"
    record=json.loads(index.read_text(encoding="utf-8")) if index.exists() else None
    path=folder / record["file"] if record else None
    if not path or not path.exists() or sha256(path)!=record["sha256"]:
        if offline:
            raise FileNotFoundError("Malha MT 2025 ausente do cache")
        response=requests.get(MT_2025,timeout=120)
        response.raise_for_status()
        digest=hashlib.sha256(response.content).hexdigest()
        path=folder / f"MT_Municipios_2025-{digest[:16]}.zip"
        path.write_bytes(response.content)
        record=dict(url=MT_2025,file=path.name,sha256=digest,bytes=len(response.content),retrieved_utc=datetime.now(timezone.utc).isoformat(),source="IBGE — malha municipal MT 2025")
        write_json(index,record)
    features=[]
    with shapefile.Reader(str(path),encoding="utf-8") as reader:
        for item in reader.iterShapeRecords():
            features.append(dict(type="Feature",properties=dict(codarea=str(item.record["CD_MUN"])),geometry=item.shape.__geo_interface__))
    return features,record


def winner_color(flavio, lula):
    if pd.isna(flavio) or pd.isna(lula) or flavio+lula <= 0 or flavio == lula:
        return GRAY
    base = BLUE if flavio > lula else RED
    strength = .32 + .68 * abs(flavio-lula)/(flavio+lula)
    channels = [int(base[i:i+2],16) for i in (1,3,5)]
    return "#" + "".join(f"{math.floor(255+(v-255)*strength+.5):02x}" for v in channels)


def rings(geometry):
    if geometry["type"] == "Polygon":
        return geometry["coordinates"]
    if geometry["type"] == "MultiPolygon":
        return [ring for polygon in geometry["coordinates"] for ring in polygon]
    raise ValueError("Geometria municipal não poligonal")


def project(lon,lat):
    return lon*math.cos(math.radians(15)), -lat


def geometry_path(geometry):
    parts, points = [], []
    for ring in rings(geometry):
        xy = [project(*p[:2]) for p in ring]
        if len(xy) < 3:
            continue
        points.extend(xy)
        parts.append("M" + "L".join(f"{x:.4f},{y:.4f}" for x,y in xy) + "Z")
    xs,ys = zip(*points)
    bounds = [min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)]
    return "".join(parts),bounds


def prepare_map(output="outputs/2026", data="data/geografia", offline=False):
    output = Path(output)
    locations, loc_source = cached_json(data,"municipios_ibge",LOCALITIES,offline)
    mesh, mesh_source = cached_json(data,"malha_municipal_ibge",MESH,offline)
    updated_mt,mt_source=mt_mesh(data,offline)
    mesh["features"]=[f for f in mesh["features"] if not str(f["properties"].get("codarea","")).startswith("51")]+updated_mt
    con = duckdb.connect()
    con.execute("SET threads=2")
    try:
        votes = con.execute("""SELECT year,uf,municipality,municipality_name_1,
            votes_22_1,votes_13_1,votes_22_2,votes_13_2,valid_1,valid_2,attendance_1,attendance_2,
            comparable,comparison_reason FROM read_parquet(?) WHERE uf<>'ZZ'""", [str(output / "indicadores_municipio.parquet")]).df()
        matched = match_municipalities(votes,locations)
        export_frame(con,matched,output / "mapa_correspondencia_municipios")
        unknown = matched.loc[matched.ibge_code.isna(),["uf","municipality","municipality_name_1"]]
        if len(unknown):
            LOG.warning("Municípios ainda sem vínculo IBGE:\n%s",unknown.to_string(index=False))
        lookup = {row["ibge_code"]:row for row in matched.loc[matched.ibge_code.notna()].to_dict("records")}
        zero_counts = {}
        zpath = output / "investigacao_zeros.parquet"
        if zpath.exists():
            zero_counts = {(uf,mun):int(n) for uf,mun,n in con.execute("SELECT uf,municipality,count(*) FROM read_parquet(?) WHERE positive_to_zero GROUP BY uf,municipality",[str(zpath)]).fetchall()}
        features = []
        feature_codes = set()
        for feature in mesh["features"]:
            properties = feature["properties"]
            code = str(properties.get("codarea") or properties.get("CD_MUN") or feature.get("id"))
            feature_codes.add(code)
            row = lookup.get(code)
            if row is None:
                continue
            path,bounds = geometry_path(feature["geometry"])
            row = {k:(None if pd.isna(v) else v) for k,v in row.items()}
            row.update(path=path,bounds=bounds,zero_sections=zero_counts.get((row["uf"],row["municipality"]),0),
                flipped=(row["votes_22_1"]>row["votes_13_1"] and row["votes_22_2"]<row["votes_13_2"]) or (row["votes_22_1"]<row["votes_13_1"] and row["votes_22_2"]>row["votes_13_2"]))
            case = output / "investigacao_fichas" / f"virada-municipio-{row['uf']}-{row['municipality']}.json"
            row["case_file"] = "investigacao_fichas/"+case.name if case.exists() else ""
            features.append(row)
        summary = dict(mapped=len(features),electoral_municipalities=len(votes),unmatched_names=len(unknown),
            missing_geometry=matched.loc[matched.ibge_code.notna() & ~matched.ibge_code.isin(feature_codes),["uf","municipality","municipality_name_1","ibge_code"]].to_dict("records"),
            sources=[loc_source,mesh_source,mt_source],results_sha256=sha256(output / "indicadores_municipio.parquet"),
            projection="Equirretangular, longitude × cos(15°), latitude invertida para o SVG; malha simplificada do IBGE.",
            note="Cor indica o candidato com mais votos no município. Área geográfica não representa quantidade de eleitores. Exterior não possui polígonos neste mapa.")
        write_json(output / "mapa_dados.json",dict(summary=summary,features=features))
        static_maps(output,features,mesh)
        return summary
    finally:
        con.close()


def static_maps(output,features,mesh):
    by_code = {str(f["properties"].get("codarea") or f["properties"].get("CD_MUN") or f.get("id")):f["geometry"] for f in mesh["features"]}
    graph = Path(output) / "graficos"
    graph.mkdir(exist_ok=True)
    for scope in ("BR","RJ","MG"):
        selected = [r for r in features if scope=="BR" or r["uf"]==scope]
        fig,axes = plt.subplots(1,2,figsize=(11,6),layout="constrained")
        for turn,ax in enumerate(axes,1):
            patches,colors = [],[]
            for row in selected:
                paths=[]
                for ring in rings(by_code[row["ibge_code"]]):
                    coords = [project(*p[:2]) for p in ring]
                    if len(coords)<3:
                        continue
                    paths.append(PlotPath(coords,[PlotPath.MOVETO]+[PlotPath.LINETO]*(len(coords)-2)+[PlotPath.CLOSEPOLY]))
                patches.append(PathPatch(PlotPath.make_compound_path(*paths)))
                colors.append(winner_color(row[f"votes_22_{turn}"],row[f"votes_13_{turn}"]))
            ax.add_collection(PatchCollection(patches,facecolors=colors,edgecolors="#ffffff",linewidths=.12))
            # As coordenadas SVG têm Y crescente para o sul; manter o norte no topo no PNG/PDF.
            ax.autoscale_view(); ax.invert_yaxis(); ax.set_aspect("equal"); ax.axis("off")
            ax.set_title(f"{scope} — {turn}º turno")
        fig.legend(handles=[Patch(facecolor=BLUE,label="Flávio"),Patch(facecolor=RED,label="Lula"),Patch(facecolor=GRAY,label="Empate/sem dados")],loc="lower center",ncol=3)
        fig.suptitle("Vencedor por município — intensidade pela margem entre os finalistas")
        fig.savefig(graph / f"mapa_{scope.lower()}.png",dpi=160)
        plt.close(fig)
