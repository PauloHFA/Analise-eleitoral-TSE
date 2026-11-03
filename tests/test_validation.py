import duckdb
import pandas as pd
import pytest

from eleicoes.analysis import export_frame
from eleicoes.validation import read_export_csv


def test_exported_csv_preserves_rare_quotes_empty_strings_and_null(tmp_path):
    con=duckdb.connect()
    source=pd.DataFrame(dict(id=range(30003),value=["texto"]*30000+["fonte ausente, campo com vírgula","",None]))
    export_frame(con,source,tmp_path/"records")
    parsed=read_export_csv(con,tmp_path/"records.csv").df()
    assert len(parsed)==len(source)
    assert parsed.value.iloc[-3]=="fonte ausente, campo com vírgula"
    assert parsed.value.iloc[-2]=="" and pd.isna(parsed.value.iloc[-1])
    con.close()


def test_malformed_csv_is_not_silently_skipped(tmp_path):
    path=tmp_path/"malformed.csv"
    path.write_text("id,value\n1,ok\n2,extra,column\n",encoding="utf-8")
    con=duckdb.connect()
    with pytest.raises(duckdb.InvalidInputException):
        read_export_csv(con,path,columns={"id":"BIGINT","value":"VARCHAR"}).fetchall()
    con.close()
