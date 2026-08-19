"""Build a DuckDB database of views over the ingested Parquet.

Layering:

``raw_<table>``
    A view straight onto the Parquet file. Every column is text, exactly as it
    left EPA. Nothing here is cleaned, so it is always possible to see what the
    source actually said.

``<table>``
    The normalised view: whitespace collapsed, empties nulled, dates parsed,
    country and state codes canonicalised, coordinates cast. Derived columns
    carry a suffix, and :func:`_derived_columns` refuses to create one whose
    name EPA already uses, because DuckDB would silently disambiguate the
    duplicate to ``NAME_1`` and leave every downstream reference resolving to
    the wrong column.

``crosswalk`` / ``water_system``
    Materialised, because they are joins that would otherwise be recomputed on
    every query. See :mod:`j2d.frs.crosswalk`.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from . import normalize as nz
from .schema import TABLES, Table

#: Columns handled by a rule other than the default text cleanup.
_STATE_COLUMNS = {"STATE_CODE", "STD_STATE_CODE"}
_COUNTRY_COLUMNS = {"COUNTRY_NAME", "STD_COUNTRY"}
_POSTAL_COLUMNS = {"POSTAL_CODE", "STD_POSTAL_CODE"}

#: Coordinate columns and their valid ranges. Latitude is not ±180: using one
#: range for both would accept a transposed lat/long pair as valid.
_COORD_BOUNDS = {
    "LATITUDE83": (-90.0, 90.0),
    "LONGITUDE83": (-180.0, 180.0),
}


def quote_ident(name: str) -> str:
    """Quote a SQL identifier, escaping any embedded double quote.

    EPA column names are currently well behaved, but the registry exists to
    survive schema drift, and a name containing a quote would otherwise produce
    unparseable SQL and abort the build half-way through.
    """
    return '"' + name.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    """Quote a SQL string literal, escaping any embedded single quote."""
    return "'" + str(value).replace("'", "''") + "'"


def connect(db_path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path), read_only=read_only)


def _column_expr(table: Table, col: str) -> str:
    """The normalised SQL expression for one column, aliased to its own name."""
    quoted = quote_ident(col)
    if col in table.date_columns or col.endswith("_DATE"):
        expr = nz.sql_date(quoted)
    elif col in _COORD_BOUNDS:
        lo, hi = _COORD_BOUNDS[col]
        expr = nz.sql_coord(quoted, lo=lo, hi=hi)
    elif col in _STATE_COLUMNS:
        expr = nz.sql_state(quoted)
    elif col in _COUNTRY_COLUMNS:
        expr = nz.sql_country(quoted)
    else:
        expr = nz.sql_text(quoted)
    return f"{expr} AS {quoted}"


def _derived_columns(table: Table, cols: list[str]) -> list[str]:
    """Extra columns appended to a normalised view.

    Raises if EPA has started shipping a column under a derived name: that is
    schema drift, and surfacing it is the entire point of holding a registry.
    """
    existing = set(cols)
    out: list[str] = []

    def add(alias: str, expr: str) -> None:
        if alias in existing:
            raise RuntimeError(
                f"{table.name}: EPA now ships a column named {alias!r}, which "
                f"collides with a derived column. Rename the derived column."
            )
        out.append(f"{expr} AS {quote_ident(alias)}")

    for col in cols:
        if col in _POSTAL_COLUMNS:
            add(f"{col}_ZIP5", nz.sql_zip5(quote_ident(col)))
    if "STATE_CODE" in existing:
        # Preserve the value we nulled, so an out-of-domain code stays visible.
        add("STATE_CODE_RAW", nz.sql_upper(quote_ident("STATE_CODE")))
    if "FIPS_CODE" in existing and "STATE_CODE" in existing:
        # FIPS_CODE holds four incompatible shapes; only one is a county FIPS.
        add(
            "FIPS_CODE_COUNTY5",
            nz.sql_county_fips(quote_ident("FIPS_CODE"), quote_ident("STATE_CODE")),
        )
    return out


def parquet_columns(con: duckdb.DuckDBPyConnection, path: Path) -> list[str]:
    """Column names of a Parquet file, in file order."""
    desc = con.execute(
        f"SELECT * FROM read_parquet({quote_literal(path.as_posix())}) LIMIT 0"
    ).description
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
        src = f"read_parquet({quote_literal(path.as_posix())})"
        con.execute(f"CREATE OR REPLACE VIEW raw_{name} AS SELECT * FROM {src}")
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
