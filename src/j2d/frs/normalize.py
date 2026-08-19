"""SQL normalisation for the FRS tables.

Normalisation is expressed as DuckDB views over the raw Parquet rather than as
a second materialised copy of the data. Ten GB of CSV becomes ~1 GB of Parquet;
writing a cleaned duplicate would double storage to buy nothing, because every
rule here is a cheap scalar expression that DuckDB pushes down into the scan.

The rules are deliberately conservative. Anything that would *discard* a value
is left to :mod:`j2d.frs.qa`, which reports rather than deletes.
"""

from __future__ import annotations

#: The two-digit years that C ``strptime`` resolves to a century FRS never used.
#:
#: FRS dates are Oracle ``DD-MON-YY``. C ``strptime`` maps ``00``-``68`` to
#: 2000-2068 and ``69``-``99`` to 1969-1999. The second half is right. The first
#: is right for recent dates and wrong for mid-century ones: a 1960 permit date
#: written ``01-JAN-60`` comes back as 2060.
#:
#: Only years landing in **2050-2068** are ambiguous. Below 2050 the modern
#: reading is overwhelmingly more likely (a ``25`` is 2025, not 1925, in a
#: registry that did not exist then), and 2069+ is unreachable from a two-digit
#: year. So exactly that band is pulled back a century.
#:
#: The band is a fixed constant rather than an offset from ``current_date`` on
#: purpose. An earlier version used "more than 25 years in the future", which
#: had two faults: it left ``50`` and ``51`` unadjusted (11,255 rows in this
#: extract kept a 2050/2051 date that is really 1950/1951, while sibling rows
#: dated 1952-1968 were corrected), and it made the output depend on the day the
#: build ran, so the same input Parquet yielded different dates over time.
#:
#: The cost is that a genuine permit expiring in 2050-2068 would be dragged to
#: the 1950s. This extract contains no such row — zero permit-expiration dates
#: fall in the band — and ``qa.check_dates`` counts every adjustment, so the
#: trade is visible rather than assumed.
AMBIGUOUS_CENTURY_FIRST_YEAR = 2050
AMBIGUOUS_CENTURY_LAST_YEAR = 2068

#: Country spellings observed in the extract, mapped to ISO-3166 alpha-2.
COUNTRY_MAP = {
    "USA": "US",
    "US": "US",
    "UNITED STATES": "US",
    "UNITED STATES OF AMERICA": "US",
    "U.S.A.": "US",
    "CANADA": "CA",
    "MEXICO": "MX",
}

#: USPS state / territory code -> two-digit state FIPS.
#:
#: Includes the freely associated states (FM, MH, PW), which are valid USPS
#: codes and do appear in the extract. ``TT`` (Trust Territory of the Pacific
#: Islands) is deliberately absent: it was dissolved in 1994 and any record
#: still carrying it is stale.
STATE_FIPS: dict[str, str] = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15",
    "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56",
    "AS": "60", "FM": "64", "GU": "66", "MH": "68", "MP": "69", "PW": "70",
    "PR": "72", "UM": "74", "VI": "78",
}

#: USPS state / territory codes considered valid for a US facility.
VALID_STATE_CODES = frozenset(STATE_FIPS)


def sql_date(col: str) -> str:
    """SQL expression parsing an Oracle ``DD-MON-YY`` column to ``DATE``.

    Unparseable values become ``NULL`` rather than raising, so one bad string
    cannot abort a scan over 8 million rows. :func:`j2d.frs.qa.check_dates`
    counts both the failures and the century adjustments.

    The result depends only on the input, never on when the build ran.
    """
    parsed = f"try_strptime(nullif(trim({col}), ''), '%d-%b-%y')"
    return (
        f"CASE WHEN {parsed} IS NULL THEN NULL "
        f"WHEN year({parsed}) BETWEEN {AMBIGUOUS_CENTURY_FIRST_YEAR} "
        f"AND {AMBIGUOUS_CENTURY_LAST_YEAR} "
        f"THEN ({parsed} - INTERVAL 100 YEAR)::DATE "
        f"ELSE {parsed}::DATE END"
    )


def sql_text(col: str) -> str:
    """Collapse whitespace runs, trim the edges, and empty-to-NULL.

    Order matters. DuckDB's one-argument ``trim`` strips ASCII spaces only, so
    trimming first would leave a leading tab in place, and the subsequent
    ``\\s+`` collapse would turn it into a leading *space* that nothing removes.
    A field of nothing but a tab would become ``' '`` rather than ``NULL``,
    defeating the empty-to-NULL guard entirely. Collapsing first normalises
    every whitespace character to a space, and the trim then catches all of them.

    This matters because the ingest deliberately preserves tab, CR and LF —
    they are structural in CSV — so they do reach this expression.
    """
    return f"nullif(trim(regexp_replace({col}, '\\s+', ' ', 'g')), '')"


def sql_upper(col: str) -> str:
    return f"upper({sql_text(col)})"


def sql_country(col: str) -> str:
    """Map the observed country spellings to ISO alpha-2, passing others through."""
    whens = "\n        ".join(
        f"WHEN {sql_upper(col)} = '{k}' THEN '{v}'" for k, v in COUNTRY_MAP.items()
    )
    return f"CASE\n        {whens}\n        ELSE {sql_upper(col)}\n    END"


def sql_state(col: str) -> str:
    """Uppercase a state code, nulling values outside the USPS domain.

    The bad values are real: the extract contains records whose city is in one
    state and whose ``STATE_CODE`` is another, and a handful of codes that are
    not states at all. Only the second class is nulled here; the first is a
    cross-field contradiction and is reported by ``qa`` instead.
    """
    codes = ", ".join(f"'{c}'" for c in sorted(VALID_STATE_CODES))
    return f"CASE WHEN {sql_upper(col)} IN ({codes}) THEN {sql_upper(col)} ELSE NULL END"


def sql_zip5(col: str) -> str:
    """First five digits of a postal code, when it looks like a US ZIP."""
    return (
        f"CASE WHEN regexp_matches({sql_text(col)}, '^[0-9]{{5}}') "
        f"THEN substr({sql_text(col)}, 1, 5) ELSE NULL END"
    )


def sql_county_fips(fips_col: str, state_col: str) -> str:
    """A trustworthy 5-digit county FIPS, or NULL.

    ``FIPS_CODE`` in this extract carries four incompatible shapes:

    ===============================  =========  ===================================
    shape                            rows       example
    ===============================  =========  ===================================
    5-digit numeric county FIPS      3,594,816  ``39155``
    NULL                             1,069,679
    USPS prefix + 3 digits             498,920  ``AK090``  (not FIPS at all)
    numeric, wrong length              154,962  ``04``     (state only)
    other                                  762
    ===============================  =========  ===================================

    Only the first shape is a county FIPS. Joining census data on the raw column
    silently drops roughly a third of the rows, so this expression populates a
    separate column only when the value is genuinely 5 numeric digits *and* its
    state prefix agrees with ``STATE_CODE``. Disagreements are counted by
    ``qa.check_fips_shapes`` rather than silently coerced.
    """
    fips = sql_text(fips_col)
    whens = " ".join(
        f"WHEN {sql_upper(state_col)} = '{k}' THEN '{v}'" for k, v in STATE_FIPS.items()
    )
    expected = f"CASE {whens} ELSE NULL END"
    return (
        f"CASE WHEN regexp_matches({fips}, '^[0-9]{{5}}$') "
        f"AND substr({fips}, 1, 2) = {expected} THEN {fips} ELSE NULL END"
    )


def sql_coord(col: str, *, lo: float = -180.0, hi: float = 180.0) -> str:
    """Parse a coordinate to DOUBLE, nulling values outside ``lo``..``hi``.

    Latitude and longitude have different valid ranges, so the bounds are a
    parameter rather than a shared constant: passing ``180`` for a latitude
    would accept a transposed lat/long pair as valid.
    """
    v = f"try_cast(nullif(trim({col}), '') AS DOUBLE)"
    return f"CASE WHEN {v} BETWEEN {lo} AND {hi} AND {v} <> 0 THEN {v} ELSE NULL END"
