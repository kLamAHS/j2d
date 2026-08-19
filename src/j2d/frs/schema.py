"""Table registry for the FRS national combined extract.

Every column is read as UTF-8 string. This is deliberate, not lazy:

* ``FIPS_CODE`` ("02020"), ``POSTAL_CODE`` ("07030") and ``NAICS_CODE`` carry
  meaningful leading zeros that integer inference destroys.
* ``REGISTRY_ID`` is a 12-digit identifier, not a quantity.
* FRS dates are Oracle ``DD-MON-YY`` with a two-digit year, which no CSV type
  inferrer reads correctly.

Typing happens later, explicitly, in :mod:`j2d.frs.normalize`, where the
choices are visible and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Table:
    """One CSV member of the national combined zip."""

    name: str
    member: str
    grain: str
    key: tuple[str, ...] = ()
    notes: str = ""
    #: Columns holding Oracle ``DD-MON-YY`` dates.
    date_columns: tuple[str, ...] = ()


#: The program-identity pair present on nearly every table. ``REGISTRY_ID`` is
#: the FRS master facility key; ``PGM_SYS_ACRNM`` + ``PGM_SYS_ID`` is the
#: identity the *source* program system (SDWIS, NPDES, RCRAINFO, TRIS, ...)
#: knows the facility by. The pair is the cross-program join key.
PROGRAM_KEY = ("PGM_SYS_ACRNM", "PGM_SYS_ID")

TABLES: dict[str, Table] = {
    t.name: t
    for t in [
        Table(
            name="facility",
            member="NATIONAL_FACILITY_FILE.CSV",
            grain="one row per FRS facility",
            key=("REGISTRY_ID",),
            date_columns=("CREATE_DATE", "UPDATE_DATE"),
            notes=(
                "PGM_SYS_ACRNMS is a denormalised 'ACRNM:ID, ACRNM:ID, ...' string "
                "duplicating the program table; normalize.py explodes it so the "
                "two representations can be reconciled."
            ),
        ),
        Table(
            name="program",
            member="NATIONAL_PROGRAM_FILE.CSV",
            grain="one row per program-system record linked to a facility",
            key=PROGRAM_KEY,
            date_columns=(
                "LAST_REPORTED_DATE",
                "CREATE_DATE",
                "UPDATE_DATE",
                "REFRESH_DATE",
            ),
            notes="Carries the STD_* standardised name/address fields used for matching.",
        ),
        Table(
            name="environmental_interest",
            member="NATIONAL_ENVIRONMENTAL_INTEREST_FILE.CSV",
            grain="one row per permit / regulatory programme applying to a facility",
            key=PROGRAM_KEY + ("INTEREST_TYPE",),
            date_columns=(
                "START_DATE",
                "END_DATE",
                "LAST_REPORTED_DATE",
                "CREATE_DATE",
                "UPDATE_DATE",
            ),
            notes="ACTIVE_STATUS drives 'is this permit live', and its domain is dirty.",
        ),
        Table(
            name="supplemental_interest",
            member="NATIONAL_SUPP_INTEREST_FILE.CSV",
            grain="one row per supplemental (state / enforcement) interest",
            key=PROGRAM_KEY + ("SUP_PGM_SYS_ACRNM", "SUP_INTEREST_TYPE"),
            date_columns=(
                "START_DATE",
                "END_DATE",
                "LAST_REPORTED_DATE",
                "CREATE_DATE",
                "UPDATE_DATE",
            ),
        ),
        Table(
            name="organization",
            member="NATIONAL_ORGANIZATION_FILE.CSV",
            grain="one row per organisation affiliated with a facility",
            key=PROGRAM_KEY + ("AFFILIATION_TYPE", "ORG_NAME"),
            date_columns=("START_DATE", "END_DATE"),
            notes="AFFILIATION_TYPE separates OWNER / OPERATOR / PARENT COMPANY.",
        ),
        Table(
            name="contact",
            member="NATIONAL_CONTACT_FILE.CSV",
            grain="one row per named contact person affiliated with a facility",
            key=PROGRAM_KEY + ("AFFILIATION_TYPE", "FULL_NAME"),
            date_columns=("START_DATE", "END_DATE"),
            notes="Contains personal names, phone numbers and email addresses.",
        ),
        Table(
            name="mailing_address",
            member="NATIONAL_MAILING_ADDRESS_FILE.CSV",
            grain="one row per mailing address affiliated with a facility",
            key=PROGRAM_KEY + ("AFFILIATION_TYPE",),
            date_columns=("START_DATE", "END_DATE"),
        ),
        Table(
            name="alternative_name",
            member="NATIONAL_ALTERNATIVE_NAME_FILE.CSV",
            grain="one row per alternative / historic / program-specific name",
            key=PROGRAM_KEY + ("ALTERNATIVE_NAME",),
            notes="The highest-value table for name-based entity resolution.",
        ),
        Table(
            name="naics",
            member="NATIONAL_NAICS_FILE.CSV",
            grain="one row per NAICS industry code asserted for a facility",
            key=PROGRAM_KEY + ("NAICS_CODE",),
            notes="NAICS_CODE mixes 2-6 digit levels; keep as string.",
        ),
        Table(
            name="sic",
            member="NATIONAL_SIC_FILE.CSV",
            grain="one row per SIC industry code asserted for a facility",
            key=PROGRAM_KEY + ("SIC_CODE",),
        ),
    ]
}

#: Tables carrying personal contact information, for the ``--no-pii`` switch.
PII_TABLES = frozenset({"contact"})

#: Columns within otherwise-public tables that carry personal information.
PII_COLUMNS: dict[str, tuple[str, ...]] = {
    "contact": ("FULL_NAME", "PHONE_NUMBER", "ALTERNATE_PHONE", "FAX_NUMBER", "EMAIL_ADDRESS"),
    "organization": ("EMAIL_ADDRESS", "PHONE_NUMBER", "ALTERNATE_PHONE", "FAX_NUMBER"),
}


def member_to_table() -> dict[str, Table]:
    """Map zip member filename -> :class:`Table`."""
    return {t.member: t for t in TABLES.values()}


def table_names() -> list[str]:
    return sorted(TABLES)
