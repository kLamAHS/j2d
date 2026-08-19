"""Data-quality checks over the built database.

The checks *measure*; they never mutate. Anything that would drop or rewrite a
row belongs in :mod:`j2d.frs.normalize`, where it is a visible, testable rule.
The output of a run is a list of :class:`Check` results — a report you can diff
between two monthly FRS extracts to see what EPA changed underneath you.

That diffing use is why the report has a **stable shape**. A check that could
not run emits a ``skipped.*`` entry rather than vanishing, because an absent
line and a passing line are indistinguishable in a diff, and "no news" would
read as good news. For the same reason a failing check costs one line, not the
whole family: the per-table loops catch their own errors.

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
from typing import Any, Callable

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
        mark = {"ok": "ok  ", "warn": "WARN", "fail": "FAIL", "skip": "SKIP"}.get(
            self.status, self.status
        )
        head = f"[{mark}] {self.name}: {self.value}"
        return head + (f"\n         {self.detail}" if self.detail else "")


def requires(*tables: str) -> Callable:
    """Mark the relations a check needs, so a skip is reported rather than silent."""

    def deco(fn):
        fn.requires = tables
        return fn

    return deco


def _relations(con: duckdb.DuckDBPyConnection) -> set[str]:
    """Tables and views in the *current* database's main schema.

    Scoped deliberately. An unscoped ``information_schema.tables`` spans every
    attached catalog, so ATTACHing last month's database — the obvious thing to
    do when diffing two reports — would make this month's checks believe in
    relations they cannot actually query.
    """
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_catalog = current_database() AND table_schema = 'main'"
    ).fetchall()
    return {r[0] for r in rows}


def _safe(fn, *args) -> list[Check]:
    """Run one measurement, turning any failure into a single Check."""
    try:
        return fn(*args)
    except Exception as exc:  # noqa: BLE001 - a broken check must cost one line
        return [Check(getattr(fn, "__name__", "check"), "fail", "error", str(exc)[:200])]


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------


def check_row_counts(con, present) -> list[Check]:
    out = []
    for name in sorted(TABLES):
        if f"raw_{name}" not in present:
            out.append(Check(f"rows.{name}", "warn", 0, "table not ingested"))
            continue
        try:
            n = con.execute(f"SELECT count(*) FROM raw_{name}").fetchone()[0]
        except Exception as exc:  # noqa: BLE001
            out.append(Check(f"rows.{name}", "fail", "error", str(exc)[:150]))
            continue
        out.append(Check(f"rows.{name}", "ok" if n else "fail", n))
    return out


@requires("raw_facility")
def check_facility_key_unique(con, present) -> list[Check]:
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


@requires("raw_facility")
def check_orphans(con, present) -> list[Check]:
    """Child rows whose REGISTRY_ID has no facility record."""
    out = []
    for name in sorted(TABLES):
        if name == "facility" or f"raw_{name}" not in present:
            continue

        def one(name=name):
            n = con.execute(
                f"SELECT count(*) FROM raw_{name} c "
                "WHERE NOT EXISTS (SELECT 1 FROM raw_facility f "
                "                  WHERE f.REGISTRY_ID = c.REGISTRY_ID)"
            ).fetchone()[0]
            return [
                Check(
                    f"orphans.{name}",
                    "ok" if n == 0 else "warn",
                    n,
                    "rows referencing a REGISTRY_ID absent from the facility table",
                )
            ]

        out.extend(_safe(one))
    return out


def check_dates(con, present) -> list[Check]:
    """Unparseable dates, and dates pulled back a century by the pivot rule.

    The adjustment count is reported even when it is large: the century rule is
    a judgement call about ambiguous input, and a silent judgement call over 8
    million rows is how a dataset quietly goes wrong.
    """
    out = []
    for name, table in sorted(TABLES.items()):
        if f"raw_{name}" not in present or not table.date_columns:
            continue
        cols = {d[0] for d in con.execute(f"SELECT * FROM raw_{name} LIMIT 0").description}
        for col in table.date_columns:
            if col not in cols:
                continue

            def one(name=name, col=col):
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
                res = [
                    Check(
                        f"dates.{name}.{col}.unparseable",
                        "ok" if bad == 0 else "warn",
                        bad,
                        f"of {total:,} rows; these become NULL",
                    )
                ]
                if adjusted:
                    res.append(
                        Check(
                            f"dates.{name}.{col}.century_adjusted",
                            "warn",
                            adjusted,
                            "two-digit year resolved to "
                            f"{nz.AMBIGUOUS_CENTURY_FIRST_YEAR}-"
                            f"{nz.AMBIGUOUS_CENTURY_LAST_YEAR} and shifted back a century",
                        )
                    )
                return res

            out.extend(_safe(one))
    return out


@requires("facility")
def check_state_codes(con, present) -> list[Check]:
    # The total is a separate un-limited aggregate. Summing the LIMITed sample
    # would cap the headline at the twenty most common bad codes and hide any
    # growth in the tail - exactly the regression a monthly diff exists to catch.
    total = con.execute(
        "SELECT count(*) FROM facility "
        "WHERE STATE_CODE IS NULL AND STATE_CODE_RAW IS NOT NULL"
    ).fetchone()[0]
    rows = con.execute(
        "SELECT STATE_CODE_RAW, count(*) c FROM facility "
        "WHERE STATE_CODE IS NULL AND STATE_CODE_RAW IS NOT NULL "
        "GROUP BY 1 ORDER BY c DESC LIMIT 20"
    ).fetchall()
    return [
        Check(
            "facility.state_code_out_of_domain",
            "ok" if total == 0 else "warn",
            total,
            "values outside the USPS domain; nulled in the normalised view",
            rows=rows,
        )
    ]


@requires("facility")
def check_fips_shapes(con, present) -> list[Check]:
    """``FIPS_CODE`` mixes four incompatible formats; only one is a county FIPS.

    This replaced an earlier check whose correlated subquery referenced the same
    table it selected from, so the inner ``STATE_CODE = facility.STATE_CODE``
    bound to the *inner* row and was always true. The subquery therefore returned
    every prefix and ``NOT IN (everything)`` was always false: the check reported
    zero disagreements no matter what the data said. A check that structurally
    cannot fail is worse than no check, because it manufactures confidence.
    """
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
    out = [
        Check(
            "facility.fips_code_shapes",
            "ok" if nonnull == usable else "warn",
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


@requires("facility")
def check_coordinates(con, present) -> list[Check]:
    """Coordinate coverage, and range sanity when there is anything to check."""
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
                "facility.coordinates_unusable",
                "warn",
                "not applicable",
                "no coordinates in this extract; the range check cannot run. "
                "Geospatial data needs EPA's separate download.",
            )
        )
        return out
    # `LONGITUDE83 IS NULL` must be explicit: in SQL's three-valued logic a NULL
    # longitude makes the OR evaluate to NULL for any in-range latitude, so a
    # facility with a latitude and no longitude - unmappable - would count as fine.
    off = con.execute(
        "SELECT count(*) FROM facility WHERE LATITUDE83 IS NOT NULL "
        "AND (LONGITUDE83 IS NULL "
        "     OR LATITUDE83 NOT BETWEEN 17 AND 72 "
        "     OR LONGITUDE83 NOT BETWEEN -180 AND -64)"
    ).fetchone()[0]
    out.append(
        Check(
            "facility.coordinates_unusable",
            "ok" if off == 0 else "warn",
            off,
            "latitude present but the point is unusable: no longitude, or "
            "outside a generous US bounding box",
        )
    )
    return out


def check_source_mojibake(con, present) -> list[Check]:
    """U+FFFD characters in the ingested text.

    A replacement character means some byte was already unrecoverable by the
    time it reached this table. It is attributable to EPA when ``j2d frs
    ingest`` reported no repairs of its own — the ingest log prints both
    ``[N U+FFFD already in source]`` and, separately, ``[utf8 repaired]``, and
    on the current extract only the former appears. The two are indistinguishable
    *here*, which is why the ingest counts them at the source.
    """
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
        if f"raw_{table}" not in present:
            continue
        try:
            n = con.execute(
                f'SELECT count(*) FROM raw_{table} WHERE contains("{col}", chr(65533))'
            ).fetchone()[0]
        except Exception:  # noqa: BLE001 - one column must not cost the check
            continue
        if n:
            rows.append((f"{table}.{col}", n))
        total += n
    return [
        Check(
            "text.replacement_characters",
            "ok" if total == 0 else "warn",
            total,
            "rows whose text contains U+FFFD; the original characters are not "
            "recoverable. Attributable to EPA when the ingest log reports no repairs.",
            rows=rows,
        )
    ]


@requires("crosswalk")
def check_crosswalk_agreement(con, present) -> list[Check]:
    """Do the two independent representations of the links agree?"""
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


@requires("crosswalk")
def check_single_source_links(con, present) -> list[Check]:
    n, total = con.execute(
        "SELECT sum(CASE WHEN source_table_count = 1 THEN 1 ELSE 0 END), count(*) FROM crosswalk"
    ).fetchone()
    # sum() over an empty table is NULL, not 0.
    n = n or 0
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
    """Run every check, keeping the report's shape stable."""
    present = _relations(con)
    out: list[Check] = []
    for fn in checks:
        needed = getattr(fn, "requires", ())
        missing = [t for t in needed if t not in present]
        if missing:
            out.append(
                Check(
                    f"skipped.{fn.__name__}",
                    "warn",
                    "not run",
                    f"requires {', '.join(missing)}, which the database does not have",
                )
            )
            continue
        out.extend(_safe(fn, con, present))
    return out


def summarise(checks: list[Check]) -> dict[str, int]:
    out = {"ok": 0, "warn": 0, "fail": 0}
    for c in checks:
        out[c.status] = out.get(c.status, 0) + 1
    return out
