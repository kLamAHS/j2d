"""Build a DuckDB database of views over the ingested Parquet.

Layering:

``raw_<table>``
    A view straight onto the Parquet file. Every column is text, exactly as it
    left EPA. Nothing here is cleaned, so it is always possible to see what the
    source actually said.

``<table>``
    The normalised view: whitespace collapsed, empties nulled, dates parsed,
    country and state codes canonicalised, coordinates cast. Derived columns
    are suffixed so they can never collide with a future EPA column name.

``crosswalk`` / ``facility_programs``
    Materialised tables, because they are joins that would otherwise be
    recomputed on every query. See :mod:`j2d.frs.crosswalk`.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from . import normalize as nz
from .schema import TABLES, Table

#: Columns handled by a rule other than the default text cleanup.
_COORD_COLUMNS = {"LATITUDE83", "LONGITUDE83"}
_STATE_COLUMNS = {"STATE_CODE", "STD_STATE_CODE"}
_COUNTRY_COLUMNS = {"COUNTRY_NAME", "STD_COUNTRY"}
_POSTAL_COLUMNS = {"POSTAL_CODE", "STD_POSTAL_CODE"}


def connect(db_path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path), read_only=read_only)


def _column_expr(table: Table, col: str) -> str:
    """The normalised SQL expression for one column, aliased to its own name."""
    quoted = f'"{col}"'
    if col in table.date_columns or col.endswith("_DATE"):
        return f"{nz.sql_date(quoted)} AS {quoted}"
    if col in _COORD_COLUMNS:
        return f"{nz.sql_coord(quoted)} AS {quoted}"
    if col in _STATE_COLUMNS:
        return f"{nz.sql_state(quoted)} AS {quoted}"
    if col in _COUNTRY_COLUMNS:
        return f"{nz.sql_country(quoted)} AS {quoted}"
    return f"{nz.sql_text(quoted)} AS {quoted}"


def _derived_columns(table: Table, cols: list[str]) -> list[str]:
    """Extra columns appended to a normalised view."""
    out: list[str] = []
    for col in cols:
        if col in _POSTAL_COLUMNS:
            quoted = '"' + col + '"'
            out.append(nz.sql_zip5(quoted) + ' AS "' + col + '_ZIP5"')
    if "STATE_CODE" in cols:
        # Preserve the value we nulled, so an out-of-domain code stays visible.
        out.append(nz.sql_upper('"STATE_CODE"') + ' AS "STATE_CODE_RAW"')
    return out


def parquet_columns(con: duckdb.DuckDBPyConnection, path: Path) -> list[str]:
    rows = con.execute(
        "SELECT name FROM parquet_schema(?) WHERE num_children = 0 OR num_children IS NULL",
        [str(path)],
    ).fetchall()
    # parquet_schema includes the root; filter to real leaves by re-reading.
    desc = con.execute(f"SELECT * FROM read_parquet('{path}') LIMIT 0").description
    return [d[0] for d in desc]


def build_views(
    con: duckdb.DuckDBPyConnection, parquet_dir: Path, *, only: list[str] | None = None
) -> list[str]:
    """Create ``raw_*`` and normalised views for every ingested table."""
    built: list[str] = []
    for name, table in sorted(TABLES.items()):
        if only and name not in only:
            continue
        path = parquet_dir / f"{name}.parquet"
        if not path.exists():
            continue
        con.execute(
            f"CREATE OR REPLACE VIEW raw_{name} AS "
            f"SELECT * FROM read_parquet('{path.as_posix()}')"
        )
        cols = parquet_columns(con, path)
        select = ",\n       ".join(
            [_column_expr(table, c) for c in cols] + _derived_columns(table, cols)
        )
        con.execute(f"CREATE OR REPLACE VIEW {name} AS\nSELECT {select}\nFROM raw_{name}")
        built.append(name)
    return built


def table_row_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    out = {}
    for name in sorted(TABLES):
        try:
            out[name] = con.execute(f"SELECT count(*) FROM raw_{name}").fetchone()[0]
        except duckdb.Error:
            continue
    return out
