"""Build the cross-program identifier crosswalk.

This is the reason to hold FRS at all. Every EPA program system — and roughly
forty-five state systems — knows a facility by its own identifier. FRS is the
only public artefact that says those identifiers denote the same place.

The crosswalk collapses ``(REGISTRY_ID, PGM_SYS_ACRNM, PGM_SYS_ID)`` from every
table that carries it, and records *which* tables asserted each link. That
provenance is the useful part: a pair asserted by one contact row is far weaker
evidence than one asserted by the program, interest and facility tables
together.

Provenance is only interpretable against a denominator, so the set of tables a
build actually scanned is written to ``crosswalk_sources``. Without it,
``source_table_count`` is a property of the build configuration rather than of
the data: a ``--no-pii`` run excludes ``contact`` and shifts the count on 2.4
million links while adding and removing exactly zero links.
"""

from __future__ import annotations

import duckdb

from . import normalize as nz

#: Tables carrying the program-identity triple directly.
_PAIR_TABLES = (
    "program",
    "environmental_interest",
    "supplemental_interest",
    "organization",
    "contact",
    "mailing_address",
    "alternative_name",
    "naics",
    "sic",
)

#: ``facility.PGM_SYS_ACRNMS`` is a denormalised "ACRNM:ID, ACRNM:ID" string.
#: Exploding it gives an independent assertion of the same links, which is what
#: makes disagreement between the two representations detectable.
#:
#: The separator is comma-*space*, not comma. Splitting on a bare comma breaks
#: ids that contain one — the extract has ``NCDB:D06#MM-06-98-0736,T`` — leaving
#: a truncated head fragment that fabricates a link no source asserts, and a
#: tail fragment that is silently dropped for having no colon.
_FACILITY_EXPLODE = """
SELECT
    REGISTRY_ID,
    upper(trim(regexp_extract(pair, '^([^:]+):', 1)))       AS PGM_SYS_ACRNM,
    trim(regexp_replace(pair, '^[^:]+:', ''))                AS PGM_SYS_ID,
    'facility_acrnms'                                        AS src
FROM (
    SELECT REGISTRY_ID, unnest(string_split(PGM_SYS_ACRNMS, ', ')) AS pair
    FROM facility
    WHERE PGM_SYS_ACRNMS IS NOT NULL
)
WHERE strpos(pair, ':') > 0
"""


def scanned_tables(available: set[str]) -> list[str]:
    """The sources this build can draw on, in a stable order."""
    out = [t for t in _PAIR_TABLES if t in available]
    if "facility" in available:
        out.append("facility_acrnms")
    return out


def _union_sql(available: set[str]) -> str:
    parts = [
        f"SELECT REGISTRY_ID, PGM_SYS_ACRNM, PGM_SYS_ID, '{t}' AS src FROM {t}"
        for t in _PAIR_TABLES
        if t in available
    ]
    if "facility" in available:
        parts.append(_FACILITY_EXPLODE)
    if not parts:
        raise RuntimeError("no tables available to build a crosswalk from")
    return "\nUNION ALL\n".join(parts)


def build(con: duckdb.DuckDBPyConnection, available: set[str]) -> int:
    """Materialise the ``crosswalk`` table. Returns its row count."""
    union = _union_sql(available)
    sources = scanned_tables(available)

    con.execute("DROP TABLE IF EXISTS crosswalk")
    con.execute(
        f"""
        CREATE TABLE crosswalk AS
        SELECT
            REGISTRY_ID,
            PGM_SYS_ACRNM,
            PGM_SYS_ID,
            count(DISTINCT src)                    AS source_table_count,
            list_sort(list(DISTINCT src))          AS source_tables
        FROM ({union})
        WHERE REGISTRY_ID   IS NOT NULL
          AND PGM_SYS_ACRNM IS NOT NULL
          AND PGM_SYS_ID    IS NOT NULL
        GROUP BY 1, 2, 3
        """
    )
    # The denominator for source_table_count. Two builds are only comparable on
    # provenance if they scanned the same sources.
    con.execute("DROP TABLE IF EXISTS crosswalk_sources")
    con.execute("CREATE TABLE crosswalk_sources (source_table VARCHAR, scan_order INTEGER)")
    con.executemany(
        "INSERT INTO crosswalk_sources VALUES (?, ?)",
        [(name, i) for i, name in enumerate(sources)],
    )
    return con.execute("SELECT count(*) FROM crosswalk").fetchone()[0]


def _water_system_sql() -> str:
    """SQL for the ``water_system`` table.

    Drinking-water systems are held under the ``SFDW`` (Safe Drinking Water)
    acronym, not ``SDWIS`` as the program is usually called externally.

    ``PGM_SYS_ID`` carries more than one shape under that acronym::

        AK2340670              a public water system - a bare PWSID
        AK2340670 42614        a facility within that system, e.g. a plant
        MP0000211 0000211TP UV a specific treatment unit within a facility

    The third shape is rare (2 rows) but the suffix is exactly the interesting
    part — ``UV`` and ``RO`` are treatment technologies. Keeping only the second
    token would collapse those two records into byte-identical duplicates, so
    everything after the first space is kept, and the raw id is projected too.

    Driven from ``crosswalk`` rather than ``environmental_interest`` alone:
    8,150 SFDW links are asserted only by other tables and would otherwise be
    invisible. Interest type, status and dates come from a LEFT JOIN, so those
    links appear with null interest fields rather than not at all.
    """
    pwsid = "split_part(x.PGM_SYS_ID, ' ', 1)"
    # The SFDW filter lives in a CTE rather than a trailing WHERE so the joins
    # see ~616k rows instead of the whole 7.6M-row crosswalk. Joining first and
    # filtering afterwards built the join against the entire normalised facility
    # view and was OOM-killed on a 15 GB machine.
    return f"""
    CREATE TABLE water_system AS
    WITH x AS (
        SELECT REGISTRY_ID, PGM_SYS_ID
        FROM crosswalk
        WHERE PGM_SYS_ACRNM = 'SFDW'
    )
    SELECT
        x.REGISTRY_ID,
        x.PGM_SYS_ID                                              AS SFDW_ID,
        {pwsid}                                                   AS PWSID,
        CASE WHEN strpos(x.PGM_SYS_ID, ' ') > 0
             THEN substr(x.PGM_SYS_ID, strpos(x.PGM_SYS_ID, ' ') + 1)
        END                                                       AS SYSTEM_FACILITY_ID,
        {nz.sql_state(f"substr({pwsid}, 1, 2)")}                   AS PWSID_STATE,
        e.INTEREST_TYPE,
        e.ACTIVE_STATUS,
        e.START_DATE,
        e.END_DATE,
        f.PRIMARY_NAME,
        f.CITY_NAME,
        f.COUNTY_NAME,
        f.STATE_CODE,
        f.FIPS_CODE_COUNTY5,
        f.LATITUDE83,
        f.LONGITUDE83
    FROM x
    LEFT JOIN (
        SELECT REGISTRY_ID, PGM_SYS_ID, INTEREST_TYPE, ACTIVE_STATUS,
               START_DATE, END_DATE
        FROM environmental_interest WHERE PGM_SYS_ACRNM = 'SFDW'
    ) e ON e.REGISTRY_ID = x.REGISTRY_ID AND e.PGM_SYS_ID = x.PGM_SYS_ID
    LEFT JOIN facility f ON f.REGISTRY_ID = x.REGISTRY_ID
    """


def build_water_system(con: duckdb.DuckDBPyConnection) -> int:
    """Materialise ``water_system``.

    A table, not a view: the view form re-ran a join against the 5.3M-row
    normalised facility view — every cleaning expression included — on every
    query, and 616k rows are cheap to keep.
    """
    con.execute("DROP TABLE IF EXISTS water_system")
    con.execute(_water_system_sql())
    return con.execute("SELECT count(*) FROM water_system").fetchone()[0]


def pivot_sql(acronyms: list[str]) -> str:
    """A per-facility pivot: one column of IDs per requested program system."""
    cols = ",\n    ".join(
        "list_sort(list(DISTINCT CASE WHEN PGM_SYS_ACRNM = '{a}' THEN PGM_SYS_ID END))"
        ' AS "{c}"'.format(a=a, c=a.replace("/", "_").replace("-", "_").replace(" ", "_"))
        for a in acronyms
    )
    return f"SELECT REGISTRY_ID,\n    {cols}\nFROM crosswalk GROUP BY REGISTRY_ID"
