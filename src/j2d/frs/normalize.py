"""SQL normalisation for the FRS tables.

Normalisation is expressed as DuckDB views over the raw Parquet rather than as
a second materialised copy of the data. Ten GB of CSV becomes ~1 GB of Parquet;
writing a cleaned duplicate would double storage to buy nothing, because every
rule here is a cheap scalar expression that DuckDB pushes down into the scan.

The rules are deliberately conservative. Anything that would *discard* a value
is left to :mod:`j2d.frs.qa`, which reports rather than deletes.
"""

from __future__ import annotations

#: How far into the future a parsed date may fall before we conclude the
#: two-digit year belongs to the previous century.
#:
#: FRS dates are Oracle ``DD-MON-YY``. C ``strptime`` maps 00-68 to 2000-2068
#: and 69-99 to 1969-1999. That is right for creation dates but wrong for the
#: handful of 1950s and 1960s permit dates, which land in 2050-2068.
#:
#: Permit *expiration* dates legitimately sit in the future, so we cannot simply
#: reject future dates. The window below keeps genuine expirations (a 2035
#: permit stays 2035) while pulling implausible ones back a century. Every
#: adjustment is counted by ``qa.check_date_century_adjustments`` so the rule
#: never operates silently.
FUTURE_YEARS_ALLOWED = 25

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
    cannot abort a scan over 8 million rows. :mod:`j2d.frs.qa` counts them.
    """
    parsed = f"try_strptime(nullif(trim({col}), ''), '%d-%b-%y')"
    return (
        f"CASE WHEN {parsed} IS NULL THEN NULL "
        f"WHEN {parsed} > current_date + INTERVAL {FUTURE_YEARS_ALLOWED} YEAR "
        f"THEN ({parsed} - INTERVAL 100 YEAR)::DATE "
        f"ELSE {parsed}::DATE END"
    )


def sql_text(col: str) -> str:
    """Trim, collapse internal whitespace runs, and empty-to-NULL."""
    return f"nullif(regexp_replace(trim({col}), '\\s+', ' ', 'g'), '')"


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


def sql_coord(col: str) -> str:
    """Parse a coordinate to DOUBLE, nulling values outside a sane range."""
    v = f"try_cast(nullif(trim({col}), '') AS DOUBLE)"
    return f"CASE WHEN {v} BETWEEN -180 AND 180 AND {v} <> 0 THEN {v} ELSE NULL END"
