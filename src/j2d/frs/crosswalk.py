"""Build the cross-program identifier crosswalk.

This is the reason to hold FRS at all. Every EPA program system — and roughly
forty-five state systems — knows a facility by its own identifier. FRS is the
only public artefact that says those identifiers denote the same place.

The crosswalk collapses ``(REGISTRY_ID, PGM_SYS_ACRNM, PGM_SYS_ID)`` from every
table that carries it, and records *which* tables asserted each link. That
provenance count is the useful part: a pair asserted by one contact row is far
weaker evidence than one asserted by the program, interest and facility tables
together.
"""

from __future__ import annotations

import duckdb

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
_FACILITY_EXPLODE = """
SELECT
    REGISTRY_ID,
    upper(trim(regexp_extract(pair, '^([^:]+):', 1)))       AS PGM_SYS_ACRNM,
    trim(regexp_replace(pair, '^[^:]+:', ''))                AS PGM_SYS_ID,
    'facility_acrnms'                                        AS src
FROM (
    SELECT REGISTRY_ID, unnest(string_split(PGM_SYS_ACRNMS, ',')) AS pair
    FROM facility
    WHERE PGM_SYS_ACRNMS IS NOT NULL
)
WHERE strpos(pair, ':') > 0
"""


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
    return con.execute("SELECT count(*) FROM crosswalk").fetchone()[0]


#: Drinking-water systems are held under the ``SFDW`` (Safe Drinking Water)
#: acronym, not ``SDWIS`` as the program is usually called externally.
#:
#: Two ID shapes share the acronym:
#:   ``AK2340670``        a public water system, i.e. a bare PWSID
#:   ``AK2340670 42614``  a facility *within* that system (a treatment plant)
#:
#: Splitting them is what turns SFDW into a usable join to SDWIS/ECHO, which key
#: on the bare PWSID.
WATER_SYSTEM_VIEW = """
CREATE OR REPLACE VIEW water_system AS
SELECT
    e.REGISTRY_ID,
    split_part(e.PGM_SYS_ID, ' ', 1)                          AS PWSID,
    CASE WHEN strpos(e.PGM_SYS_ID, ' ') > 0
         THEN split_part(e.PGM_SYS_ID, ' ', 2) END            AS SYSTEM_FACILITY_ID,
    e.INTEREST_TYPE,
    e.ACTIVE_STATUS,
    substr(split_part(e.PGM_SYS_ID, ' ', 1), 1, 2)            AS PWSID_STATE,
    e.START_DATE,
    e.END_DATE,
    f.PRIMARY_NAME,
    f.CITY_NAME,
    f.COUNTY_NAME,
    f.STATE_CODE,
    f.FIPS_CODE,
    f.LATITUDE83,
    f.LONGITUDE83
FROM environmental_interest e
LEFT JOIN facility f USING (REGISTRY_ID)
WHERE e.PGM_SYS_ACRNM = 'SFDW'
"""


def build_water_system(con: duckdb.DuckDBPyConnection) -> int:
    con.execute(WATER_SYSTEM_VIEW)
    return con.execute("SELECT count(*) FROM water_system").fetchone()[0]


def pivot_sql(acronyms: list[str]) -> str:
    """A per-facility pivot: one column of IDs per requested program system."""
    cols = ",\n    ".join(
        "list_sort(list(DISTINCT CASE WHEN PGM_SYS_ACRNM = '{a}' THEN PGM_SYS_ID END))"
        ' AS "{c}"'.format(a=a, c=a.replace("/", "_").replace("-", "_").replace(" ", "_"))
        for a in acronyms
    )
    return f"SELECT REGISTRY_ID,\n    {cols}\nFROM crosswalk GROUP BY REGISTRY_ID"
