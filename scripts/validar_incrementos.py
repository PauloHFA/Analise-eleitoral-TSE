"""Conferências independentes das análises incrementais, sem alterar a referência."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlparse

import duckdb

from eleicoes.sources import sha256
from eleicoes.validation import read_export_csv


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]

    def handle_starttag(self, tag, attrs):
        self.links += [v for k,v in attrs if k in ("href","src") and v]


def validate(root):
    root=Path(root).resolve()
    con=duckdb.connect(config={"threads":2,"memory_limit":"1GB"})
    con.execute("SET enable_progress_bar=false")
    result={}
    try:
        for study in ("estabilidade","cobertura"):
            folder=root/study
            summary=json.loads((folder/"resumo.json").read_text(encoding="utf-8"))
            state=json.loads((folder/"estado_execucao.json").read_text(encoding="utf-8"))
            assert summary["status"] == state["status"] == "concluído"
            for name,digest in summary["input_hashes"].items():
                assert sha256(root/name) == digest, f"Fonte alterada: {name}"
            for path in folder.glob("*.json"):
                json.loads(path.read_text(encoding="utf-8"),parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            checked={}
            for parquet in folder.glob("*.parquet"):
                columns={row[0]:row[1] for row in con.execute("DESCRIBE SELECT * FROM read_parquet(?)",[str(parquet)]).fetchall()}
                con.read_parquet(str(parquet)).create_view("checked_pq")
                # O COPY usa aspas duplas. A inferência pode não vê-las quando só há
                # poucos campos vazios entre mais de um milhão de registros.
                read_export_csv(con,parquet.with_suffix('.csv'),columns=columns).create_view("checked_csv")
                names=",".join('"'+name.replace('"','""')+'"' for name in columns)
                def fingerprint(view):
                    return con.execute(f"SELECT count(*),bit_xor(hash({names})),sum(hash({names})::HUGEINT) FROM {view}").fetchall()[0]
                pq,csv=fingerprint("checked_pq"),fingerprint("checked_csv")
                assert pq==csv, f"Conteúdo tipado CSV/Parquet diferente: {parquet.name}"
                checked[parquet.stem]=pq[0]
            links=Links()
            links.feed((folder/"relatorio.html").read_text(encoding="utf-8"))
            for link in links.links:
                parsed=urlparse(link)
                if not parsed.scheme and parsed.path:
                    assert (folder/parsed.path).is_file(), f"Link quebrado: {study}/{link}"
            result[study]={"status":"válido","tabelas":checked,"links":len(links.links),
                           "comparacao_csv_parquet":"quantidade e dois checksums agregados de linhas com tipos explícitos"}
        stability=root/"estabilidade"
        con.read_parquet(str(stability/"variantes.parquet")).create_view("variants")
        con.read_parquet(str(stability/"comparacao.parquet")).create_view("comparison")
        con.read_parquet(str(root/"indicadores_secoes.parquet")).create_view("baseline")
        stats=json.loads((stability/"resumo.json").read_text(encoding="utf-8"))
        assert con.execute("SELECT count(*) FROM variants").fetchall()[0][0] == stats["eligible_units"]*len(stats["sizes"])
        invalid=con.execute("""SELECT count(*) FROM variants WHERE
            (available AND (peer_count<>k OR len(string_split(peer_ids,'|'))<>k
                OR len(list_distinct(string_split(peer_ids,'|')))<>k
                OR list_contains(string_split(peer_ids,'|'),uf||'/'||municipality||'/'||zone||'/'||section)))
            OR (NOT available AND (peer_count<>0 OR robust_flag IS NOT NULL OR statistical_alert IS NOT NULL))
            OR (rank_common IS NOT NULL AND NOT common_universe)""").fetchall()[0][0]
        assert invalid==0, "Pares, disponibilidade ou ranking inválidos"
        different=con.execute("""SELECT count(*) FROM variants v JOIN baseline b USING(uf,municipality,zone,section)
            WHERE v.k=30 AND (v.statistical_alert IS DISTINCT FROM b.statistical_alert
            OR ((v.robust_max IS NULL)<>(b.robust_max IS NULL))
            OR abs(v.robust_max-b.robust_max)>1e-9+1e-12*abs(b.robust_max))""").fetchall()[0][0]
        assert different==0, "A referência não foi reproduzida"
        rank_differences=con.execute("""SELECT count(*) FROM (
            SELECT v.rank_common,row_number() OVER(ORDER BY b.priority) expected_rank
            FROM variants v JOIN baseline b USING(uf,municipality,zone,section)
            WHERE v.k=30 AND v.common_universe AND v.statistical_alert)
            WHERE rank_common<>expected_rank""").fetchall()[0][0]
        assert rank_differences==0, "A ordem da referência no universo comum não foi reproduzida"
        for lower,upper in zip(stats["sizes"],stats["sizes"][1:]):
            bad=con.execute("""SELECT count(*) FROM variants a JOIN variants b USING(uf,municipality,zone,section)
                WHERE a.k=? AND b.k=? AND a.available AND b.available AND NOT starts_with(b.peer_ids,a.peer_ids||'|')""",[lower,upper]).fetchall()[0][0]
            assert bad==0, "Conjuntos de pares não são aninhados"
        assert con.execute("SELECT count(*) FROM comparison WHERE all_available").fetchall()[0][0] == stats["common_units"]
        con.read_parquet(str(stability/"rankings.parquet")).create_view("ordered_cases")
        for overlap in stats["overlaps"]:
            def members(k):
                return set(con.execute("SELECT uf,municipality,zone,section FROM ordered_cases WHERE k=? AND rank_common<=?",[k,overlap["requested"]]).fetchall())
            left,right=members(overlap["left"]),members(overlap["right"])
            assert (len(left),len(right),len(left & right),len(left | right)) == (overlap["left_size"],overlap["right_size"],overlap["intersection"],overlap["union"])
        coverage=root/"cobertura"
        con.read_parquet(str(coverage/"municipios.parquet")).create_view("municipalities")
        con.read_parquet(str(coverage/"perfis.parquet")).create_view("profiles")
        assert con.execute("SELECT count(*) FROM municipalities WHERE observed<>eligible+comparable_small+not_comparable OR comparable<>eligible+comparable_small OR eligible_pct<0 OR eligible_pct>100 OR comparable_pct<0 OR comparable_pct>100").fetchall()[0][0]==0
        assert con.execute("SELECT count(*) FROM profiles WHERE units<>used+missing+nonfinite+out_of_range OR (used=0 AND median IS NOT NULL)").fetchall()[0][0]==0
        original=con.execute("SELECT count(*),count(*) FILTER(WHERE comparable),count(*) FILTER(WHERE comparable AND NOT small) FROM baseline").fetchall()[0]
        cov=json.loads((coverage/"resumo.json").read_text(encoding="utf-8"))
        assert original==(cov["observed_units"],cov["comparable_units"],cov["eligible_units"])
        result["invariantes"]="referência reproduzida; pares auditados; grupos e cobertura fecham; ausência preservada"
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:
        con.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("folder",nargs="?",default="outputs/2026")
    validate(parser.parse_args().folder)
