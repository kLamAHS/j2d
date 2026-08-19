"""Data-quality checks over the built database.

The checks *measure*; they never mutate. Anything that would drop or rewrite a
row belongs in :mod:`j2d.frs.normalize`, where it is a visible, testable rule.
The output of a run is a list of :class:`Check` results — a report you can
diff between two monthly FRS extracts to see what EPA changed underneath you.

Severity is deliberately blunt:

``ok``
    Measured, nothing to say.
``warn``
    A real defect in the source data that you must model around. Most FRS
    findings land here — the data is what it is, and pretending otherwise is
    how you get a silently wrong join.
``fail``
    Something that breaks an assumption the pipeline itself relies on, e.g. a
    duplicate facility key. These should be zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import duckdb

from . import normalize as nz
from .schema import TABLES


@dataclass
class Check:
    name: str
    status: str
    value: Any
    detail: str = ""
    rows: list[tuple] = field(default_factory=list)

    def __str__(self) -> str:
        mark = {"ok": "ok  ", "warn": "WARN", "fail": "FAIL"}[self.status]
        head = f"[{mark}] {self.name}: {self.value}"
        return head + (f"\n         {self.detail}" if self.detail else "")


def _views(con: duckdb.DuckDBPyConnection) -> set[str]:
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "UNION SELECT view_name FROM duckdb_views()"
    ).fetchall()
    return {r[0] for r in rows}


def check_row_counts(con: duckdb.DuckDBPyConnection, present: set[str]) -> list[Check]:
    out = []
    for name in sorted(TABLES):
        if name not in present:
            out.append(Check(f"rows.{name}", "warn", 0, "table not ingested"))
            continue
        n = con.execute(f"SELECT count(*) FROM raw_{name}").fetchone()[0]
        out.append(Check(f"rows.{name}", "ok" if n else "fail", n))
    return out


def check_facility_key_unique(con, present) -> list[Check]:
    if "facility" not in present:
        return []
    dup = con.execute(
        "SELECT count(*) FROM (SELECT REGISTRY_ID FROM raw_facility "
        "GROUP BY 1 HAVING count(*) > 1)"
    ).fetchone()[0]
    return [
        Check(
            "facility.registry_id_unique",
            "ok" if dup == 0 else "fail",
            dup,
            "REGISTRY_ID must be the primary key of the facility table",
        )
    ]


def check_orphans(con, present) -> list[Check]:
    """Child rows whose REGISTRY_ID has no facility record."""
    if "facility" not in present:
        return []
    out = []
    for name in sorted(TABLES):
        if name in ("facility",) or name not in present:
            continue
        n = con.execute(
            f"SELECT count(*) FROM raw_{name} c "
            "WHERE NOT EXISTS (SELECT 1 FROM raw_facility f "
            "                  WHERE f.REGISTRY_ID = c.REGISTRY_ID)"
        ).fetchone()[0]
        out.append(
            Check(
                f"orphans.{name}",
                "ok" if n == 0 else "warn",
                n,
                "rows referencing a REGISTRY_ID absent from the facility table",
            )
        )
    return out


def check_dates(con, present) -> list[Check]:
    """Unparseable dates, and dates pulled back a century by the pivot rule.

    The adjustment count is deliberately reported even when it is large: the
    century rule is a judgement call about ambiguous input, and a silent
    judgement call over 8 million rows is how a dataset quietly goes wrong.
    """
    out = []
    for name, table in sorted(TABLES.items()):
        if name not in present or not table.date_columns:
            continue
        cols = {d[0] for d in con.execute(f"SELECT * FROM raw_{name} LIMIT 0").description}
        for col in table.date_columns:
            if col not in cols:
                continue
            q = f"""
                SELECT
                  sum(CASE WHEN raw IS NOT NULL AND parsed IS NULL THEN 1 ELSE 0 END),
                  sum(CASE WHEN parsed IS NOT NULL
                            AND year(parsed) BETWEEN {nz.AMBIGUOUS_CENTURY_FIRST_YEAR}
                                                 AND {nz.AMBIGUOUS_CENTURY_LAST_YEAR}
                           THEN 1 ELSE 0 END),
                  count(*)
                FROM (
                  SELECT nullif(trim("{col}"), '') AS raw,
                         try_strptime(nullif(trim("{col}"), ''), '%d-%b-%y') AS parsed
                  FROM raw_{name}
                )
            """
            bad, adjusted, total = con.execute(q).fetchone()
            bad, adjusted = bad or 0, adjusted or 0
            out.append(
                Check(
                    f"dates.{name}.{col}.unparseable",
                    "ok" if bad == 0 else "warn",
                    bad,
                    f"of {total:,} rows; these become NULL",
                )
            )
            if adjusted:
                out.append(
                    Check(
                        f"dates.{name}.{col}.century_adjusted",
                        "warn",
                        adjusted,
                        "two-digit year resolved to "
                        f"{nz.AMBIGUOUS_CENTURY_FIRST_YEAR}-"
                        f"{nz.AMBIGUOUS_CENTURY_LAST_YEAR} and shifted back a century",
                    )
                )
    return out


def check_state_codes(con, present) -> list[Check]:
    if "facility" not in present:
        return []
    rows = con.execute(
        "SELECT STATE_CODE_RAW, count(*) c FROM facility "
        "WHERE STATE_CODE IS NULL AND STATE_CODE_RAW IS NOT NULL "
        "GROUP BY 1 ORDER BY c DESC LIMIT 20"
    ).fetchall()
    total = sum(r[1] for r in rows)
    return [
        Check(
            "facility.state_code_out_of_domain",
            "ok" if total == 0 else "warn",
            total,
            "values outside the USPS domain; nulled in the normalised view",
            rows=rows,
        )
    ]


def check_fips_shapes(con, present) -> list[Check]:
    """``FIPS_CODE`` mixes four incompatible formats; only one is a county FIPS.

    This replaced an earlier check whose correlated subquery referenced the same
    table it selected from, so the inner ``STATE_CODE = facility.STATE_CODE``
    bound to the *inner* row and was always true. The subquery therefore returned
    every prefix and ``NOT IN (everything)`` was always false: the check reported
    zero disagreements no matter what the data said. A check that structurally
    cannot fail is worse than no check, because it manufactures confidence.
    """
    if "facility" not in present:
        return []
    rows = con.execute(
        """
        SELECT CASE
                 WHEN FIPS_CODE IS NULL THEN 'null'
                 WHEN regexp_matches(FIPS_CODE, '^[0-9]{5}$') THEN 'county_fips_5'
                 WHEN regexp_matches(FIPS_CODE, '^[A-Z]{2}[0-9]{3}$') THEN 'usps_prefix_3'
                 WHEN regexp_matches(FIPS_CODE, '^[0-9]+$') THEN 'numeric_wrong_length'
                 ELSE 'other' END AS shape,
               count(*) AS n
        FROM facility GROUP BY 1 ORDER BY n DESC
        """
    ).fetchall()
    shapes = dict(rows)
    nonnull = sum(n for sh, n in rows if sh != "null")
    usable = shapes.get("county_fips_5", 0)
    unusable = nonnull - usable
    out = [
        Check(
            "facility.fips_code_shapes",
            "ok" if unusable == 0 else "warn",
            f"{usable:,} usable of {nonnull:,} non-null",
            "FIPS_CODE mixes formats; only 5-digit numeric is a county FIPS",
            rows=rows,
        )
    ]
    mismatch = con.execute(
        "SELECT count(*) FROM facility "
        "WHERE regexp_matches(FIPS_CODE, '^[0-9]{5}$') AND STATE_CODE IS NOT NULL "
        "  AND FIPS_CODE_COUNTY5 IS NULL"
    ).fetchone()[0]
    out.append(
        Check(
            "facility.fips_state_disagreement",
            "ok" if mismatch == 0 else "warn",
            mismatch,
            "rows whose 5-digit FIPS state prefix contradicts STATE_CODE; "
            "excluded from FIPS_CODE_COUNTY5",
        )
    )
    return out


def check_coordinates(con, present) -> list[Check]:
    """Coordinate coverage, and range sanity when there is anything to check."""
    if "facility" not in present:
        return []
    total, has = con.execute("SELECT count(*), count(LATITUDE83) FROM facility").fetchone()
    pct = 100.0 * has / total if total else 0
    out = [
        Check(
            "facility.coordinates_present",
            "ok" if pct > 50 else "warn",
            f"{has:,} / {total:,} ({pct:.1f}%)",
            "facilities with a usable latitude",
        )
    ]
    if has == 0:
        # Reporting "0 bad coordinates" here would read as a clean bill of
        # health for data that does not exist.
        out.append(
            Check(
                "facility.coordinates_outside_us",
                "warn",
                "not applicable",
                "no coordinates in this extract; the range check cannot run. "
                "Geospatial data needs EPA's separate download.",
            )
        )
        return out
    off = con.execute(
        "SELECT count(*) FROM facility WHERE LATITUDE83 IS NOT NULL "
        "AND (LATITUDE83 NOT BETWEEN 17 AND 72 OR LONGITUDE83 NOT BETWEEN -180 AND -64)"
    ).fetchone()[0]
    out.append(
        Check(
            "facility.coordinates_outside_us",
            "ok" if off == 0 else "warn",
            off,
            "coordinates outside a generous US bounding box",
        )
    )
    return out


def check_source_mojibake(con, present) -> list[Check]:
    """U+FFFD characters EPA shipped in the source text.

    A replacement character in a published file means the corruption happened
    upstream, in EPA's own extract pipeline, and the original characters are
    unrecoverable from this file. Worth knowing before trusting a name match.
    """
    out = []
    targets = [
        ("facility", "PRIMARY_NAME"),
        ("facility", "LOCATION_ADDRESS"),
        ("alternative_name", "ALTERNATIVE_NAME"),
        ("organization", "ORG_NAME"),
        ("mailing_address", "MAILING_ADDRESS"),
    ]
    total = 0
    rows = []
    for table, col in targets:
        if table not in present:
            continue
        n = con.execute(
            f"SELECT count(*) FROM raw_{table} WHERE contains(\"{col}\", chr(65533))"
        ).fetchone()[0]
        if n:
            rows.append((f"{table}.{col}", n))
        total += n
    out.append(
        Check(
            "source.mojibake_rows",
            "ok" if total == 0 else "warn",
            total,
            "rows whose text already contains U+FFFD as published by EPA; "
            "the original characters are not recoverable from this file",
            rows=rows,
        )
    )
    return out


def check_crosswalk_agreement(con, present) -> list[Check]:
    """Do the two independent representations of the links agree?"""
    if "crosswalk" not in present:
        return []
    rows = con.execute(
        """
        SELECT
          sum(CASE WHEN list_contains(source_tables, 'facility_acrnms')
                    AND NOT list_contains(source_tables, 'program') THEN 1 ELSE 0 END),
          sum(CASE WHEN list_contains(source_tables, 'program')
                    AND NOT list_contains(source_tables, 'facility_acrnms') THEN 1 ELSE 0 END),
          count(*)
        FROM crosswalk
        """
    ).fetchone()
    only_fac, only_prog, total = (r or 0 for r in rows)
    return [
        Check(
            "crosswalk.in_facility_string_not_program_table",
            "ok" if only_fac == 0 else "warn",
            only_fac,
            f"of {total:,} links; in the facility string but absent from the program table",
        ),
        Check(
            "crosswalk.in_program_table_not_facility_string",
            "ok" if only_prog == 0 else "warn",
            only_prog,
            f"of {total:,} links; in the program table but absent from the facility string",
        ),
    ]


def check_single_source_links(con, present) -> list[Check]:
    if "crosswalk" not in present:
        return []
    n, total = con.execute(
        "SELECT sum(CASE WHEN source_table_count = 1 THEN 1 ELSE 0 END), count(*) FROM crosswalk"
    ).fetchone()
    return [
        Check(
            "crosswalk.single_source_links",
            "ok",
            f"{n:,} / {total:,}",
            "links asserted by exactly one table - weakest evidence",
        )
    ]


ALL_CHECKS = (
    check_row_counts,
    check_facility_key_unique,
    check_orphans,
    check_dates,
    check_state_codes,
    check_fips_shapes,
    check_coordinates,
    check_source_mojibake,
    check_crosswalk_agreement,
    check_single_source_links,
)


def run(con: duckdb.DuckDBPyConnection, *, checks=ALL_CHECKS) -> list[Check]:
    present = _views(con)
    out: list[Check] = []
    for fn in checks:
        try:
            out.extend(fn(con, present))
        except duckdb.Error as exc:  # a broken check must not kill the report
            out.append(Check(fn.__name__, "fail", "error", str(exc)[:200]))
    return out


def summarise(checks: list[Check]) -> dict[str, int]:
    out = {"ok": 0, "warn": 0, "fail": 0}
    for c in checks:
        out[c.status] = out.get(c.status, 0) + 1
    return out
