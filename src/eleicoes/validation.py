"""Leitura estrita do formato CSV produzido pelos exportadores do projeto."""
from pathlib import Path


def read_export_csv(con, path, *, columns=None):
    options=dict(header=True,delimiter=",",quotechar='"',escapechar='"',
        allow_quoted_nulls=False,max_line_size=16777216,strict_mode=True,ignore_errors=False)
    if columns is None:
        options["all_varchar"]=True
    else:
        options["columns"]=columns
    return con.read_csv(str(Path(path)),**options)
