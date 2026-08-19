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

#: USPS state / territory codes considered valid for a US facility.
VALID_STATE_CODES = frozenset(
    """AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN
    MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV
    WI WY AS GU MP PR VI UM""".split()
)


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


def sql_coord(col: str) -> str:
    """Parse a coordinate to DOUBLE, nulling values outside a sane range."""
    v = f"try_cast(nullif(trim({col}), '') AS DOUBLE)"
    return f"CASE WHEN {v} BETWEEN -180 AND 180 AND {v} <> 0 THEN {v} ELSE NULL END"
