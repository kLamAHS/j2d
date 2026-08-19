"""Tests for the FRS pipeline.

Everything runs against the synthetic archive in ``conftest.py``, which
reproduces the two defects present in the real 1.2 GB extract: NUL bytes inside
a quoted field, and an invalid UTF-8 byte in a name field.
"""

from __future__ import annotations

import io
import zipfile

import duckdb
import pytest

from j2d.frs import crosswalk, db, normalize as nz, qa
from j2d.frs.ingest import BLOCK_SIZE, _TextSanitiser, missing_members, read_header
from j2d.frs.schema import TABLES, member_to_table


# --------------------------------------------------------------------------
# sanitiser
# --------------------------------------------------------------------------


def _through(data: bytes, chunk: int = BLOCK_SIZE) -> tuple[bytes, _TextSanitiser]:
    s = _TextSanitiser(io.BytesIO(data))
    return io.BufferedReader(s, buffer_size=chunk).read(), s


def test_sanitiser_is_byte_faithful_on_clean_input():
    data = b"hello,world\n1,2\n" * 1000
    out, s = _through(data)
    assert out == data
    assert s.control_bytes_removed == 0
    assert s.utf8_repaired is False


def test_sanitiser_strips_nul_and_counts_it():
    data = b'"a","' + b"\x00" * 27 + b'","c"\n'
    out, s = _through(data)
    assert out == b'"a","","c"\n'
    assert s.control_bytes_removed == 27


def test_sanitiser_keeps_tab_cr_lf():
    data = b"a\tb\r\nc\n"
    out, s = _through(data)
    assert out == data
    assert s.control_bytes_removed == 0


def test_sanitiser_repairs_invalid_utf8():
    data = b"name\n90\xb0 works\n"
    out, s = _through(data)
    assert s.utf8_repaired is True
    assert out.decode("utf-8") == "name\n90� works\n"


@pytest.mark.parametrize("chunk", [8, 16, 64, 4096])
def test_sanitiser_survives_multibyte_split_across_chunks(chunk):
    """A UTF-8 character straddling two reads must not be corrupted."""
    text = ("café über 中文 " * 40).encode("utf-8")
    s = _TextSanitiser(io.BytesIO(text))
    out = b""
    while True:
        buf = bytearray(chunk)
        n = s.readinto(buf)
        if not n:
            break
        out += bytes(buf[:n])
    assert out == text
    assert s.utf8_repaired is False


def test_sanitiser_handles_replacement_growth_across_reads():
    """Replacement chars are 3 bytes; overflow must be queued, not dropped."""
    data = b"\xff" * 50
    s = _TextSanitiser(io.BytesIO(data))
    out = b""
    while True:
        buf = bytearray(8)
        n = s.readinto(buf)
        if not n:
            break
        out += bytes(buf[:n])
    assert out.decode("utf-8") == "�" * 50


# --------------------------------------------------------------------------
# schema registry
# --------------------------------------------------------------------------


def test_registry_covers_every_member_of_the_archive(mini_zip):
    assert missing_members(mini_zip) == []


def test_registry_member_names_are_unique():
    members = [t.member for t in TABLES.values()]
    assert len(members) == len(set(members))
    assert len(member_to_table()) == len(TABLES)


def test_read_header_does_not_decompress_whole_member(mini_zip):
    with zipfile.ZipFile(mini_zip) as zf:
        cols = read_header(zf, "NATIONAL_SIC_FILE.CSV")
    assert cols[:3] == ["REGISTRY_ID", "PGM_SYS_ACRNM", "PGM_SYS_ID"]


# --------------------------------------------------------------------------
# normalisation SQL
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect()
    yield c
    c.close()


@pytest.mark.parametrize(
    "raw,expected_year",
    [
        ("01-MAR-00", 2000),
        ("23-MAY-25", 2025),
        ("15-JUN-99", 1999),
        ("01-JAN-35", 2035),  # a real permit expiry, must stay in the future
        ("01-JAN-55", 1955),  # implausible as 2055, pulled back a century
        ("01-JAN-68", 1968),
        ("01-JAN-69", 1969),
    ],
)
def test_date_century_pivot(con, raw, expected_year):
    got = con.execute(f"SELECT {nz.sql_date(chr(39) + raw + chr(39))}").fetchone()[0]
    assert got.year == expected_year


@pytest.mark.parametrize("raw", ["", "   ", "garbage", "29-FEB-01", "32-JAN-00"])
def test_bad_dates_become_null_not_an_error(con, raw):
    got = con.execute(f"SELECT {nz.sql_date(chr(39) + raw + chr(39))}").fetchone()[0]
    assert got is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("USA", "US"),
        ("UNITED STATES", "US"),
        ("UNITED STATES OF AMERICA", "US"),
        ("united states", "US"),
        ("CANADA", "CA"),
        ("ATLANTIS", "ATLANTIS"),
    ],
)
def test_country_normalisation(con, raw, expected):
    got = con.execute(f"SELECT {nz.sql_country(chr(39) + raw + chr(39))}").fetchone()[0]
    assert got == expected


def test_state_code_domain(con):
    assert con.execute(f"SELECT {nz.sql_state(chr(39) + 'oh' + chr(39))}").fetchone()[0] == "OH"
    assert con.execute(f"SELECT {nz.sql_state(chr(39) + 'XX' + chr(39))}").fetchone()[0] is None
    assert con.execute(f"SELECT {nz.sql_state(chr(39) + 'PR' + chr(39))}").fetchone()[0] == "PR"


def test_text_collapses_whitespace(con):
    got = con.execute(f"SELECT {nz.sql_text(chr(39) + '  ACME   WORKS  ' + chr(39))}").fetchone()[0]
    assert got == "ACME WORKS"
    assert con.execute(f"SELECT {nz.sql_text(chr(39) + '   ' + chr(39))}").fetchone()[0] is None


def test_zip5(con):
    assert con.execute(f"SELECT {nz.sql_zip5(chr(39) + '44446-1199' + chr(39))}").fetchone()[0] == "44446"
    assert con.execute(f"SELECT {nz.sql_zip5(chr(39) + 'ABCDE' + chr(39))}").fetchone()[0] is None


@pytest.mark.parametrize(
    "fips,state,expected",
    [
        ("39155", "OH", "39155"),   # Trumbull County, Ohio - agrees
        ("02020", "AK", "02020"),   # leading zero preserved
        ("12345", "OH", None),      # 12 is Florida, contradicts STATE_CODE
        ("AK090", "AK", None),      # USPS-prefixed hybrid, not a FIPS code
        ("04", "AZ", None),         # state only, wrong length
        ("39155", "XX", None),      # unknown state, cannot be verified
    ],
)
def test_county_fips_only_accepts_a_real_county_fips(con, fips, state, expected):
    expr = nz.sql_county_fips(chr(39) + fips + chr(39), chr(39) + state + chr(39))
    assert con.execute(f"SELECT {expr}").fetchone()[0] == expected


@pytest.mark.parametrize("code", ["FM", "MH", "PW", "PR", "GU", "AS", "MP", "VI", "UM"])
def test_territory_and_freely_associated_codes_are_valid(con, code):
    """FM/MH/PW are genuine USPS codes and appear in the real extract."""
    assert con.execute(f"SELECT {nz.sql_state(chr(39) + code + chr(39))}").fetchone()[0] == code


def test_trust_territory_is_rejected_as_obsolete(con):
    assert con.execute(f"SELECT {nz.sql_state(chr(39) + 'TT' + chr(39))}").fetchone()[0] is None


def test_every_state_fips_value_is_two_digits():
    assert set(nz.STATE_FIPS) == set(nz.VALID_STATE_CODES)
    assert all(len(v) == 2 and v.isdigit() for v in nz.STATE_FIPS.values())
    assert len(set(nz.STATE_FIPS.values())) == len(nz.STATE_FIPS), "FIPS codes must be unique"


def test_coord_rejects_zero_and_out_of_range(con):
    assert con.execute(f"SELECT {nz.sql_coord(chr(39) + '41.18' + chr(39))}").fetchone()[0] == 41.18
    assert con.execute(f"SELECT {nz.sql_coord(chr(39) + '0' + chr(39))}").fetchone()[0] is None
    assert con.execute(f"SELECT {nz.sql_coord(chr(39) + '999' + chr(39))}").fetchone()[0] is None


# --------------------------------------------------------------------------
# end-to-end
# --------------------------------------------------------------------------


def test_pipeline_ingests_every_table(built):
    names = {r.table for r in built["ingest"]}
    assert names == set(TABLES)
    assert all(r.rows > 0 for r in built["ingest"])


def test_nul_row_is_preserved_not_dropped(built):
    """The NUL row must survive; only the junk field is emptied."""
    res = {r.table: r for r in built["ingest"]}["mailing_address"]
    assert res.rows == 2, "the NUL-bearing row must not be skipped"
    assert res.control_bytes_removed == 27


def test_invalid_utf8_is_repaired_not_fatal(built):
    res = {r.table: r for r in built["ingest"]}["alternative_name"]
    assert res.rows == 1
    assert res.encoding_fallback is True


def test_everything_is_stored_as_text(built):
    con = db.connect(built["db_path"], read_only=True)
    try:
        types = con.execute("SELECT * FROM raw_facility LIMIT 0").description
        assert {str(t[1]) for t in types} == {"VARCHAR"}
    finally:
        con.close()


def test_leading_zeros_survive_ingest(built):
    con = db.connect(built["db_path"], read_only=True)
    try:
        fips = con.execute(
            "SELECT FIPS_CODE FROM facility WHERE REGISTRY_ID = '110000000002'"
        ).fetchone()[0]
        assert fips == "05139", "FIPS leading zero must not be lost to numeric inference"
    finally:
        con.close()


def test_normalised_view_applies_rules(built):
    con = db.connect(built["db_path"], read_only=True)
    try:
        row = con.execute(
            "SELECT PRIMARY_NAME, COUNTRY_NAME, STATE_CODE, POSTAL_CODE_ZIP5, "
            "       LATITUDE83, UPDATE_DATE "
            "FROM facility WHERE REGISTRY_ID = '110000000001'"
        ).fetchone()
        assert row[0] == "ACME WORKS"          # whitespace collapsed
        assert row[1] == "US"                  # country canonicalised
        assert row[2] == "OH"
        assert row[3] == "44446"               # ZIP+4 reduced to ZIP5
        assert row[4] == pytest.approx(41.18)
        assert row[5].year == 2025
    finally:
        con.close()


def test_county_fips_derived_column(built):
    con = db.connect(built["db_path"], read_only=True)
    try:
        good = con.execute(
            "SELECT FIPS_CODE, FIPS_CODE_COUNTY5 FROM facility WHERE REGISTRY_ID='110000000001'"
        ).fetchone()
        assert good == ("39155", "39155")
        # STATE_CODE is 'XX' here, so the FIPS cannot be corroborated.
        bad = con.execute(
            "SELECT FIPS_CODE, FIPS_CODE_COUNTY5 FROM facility WHERE REGISTRY_ID='110000000002'"
        ).fetchone()
        assert bad == ("05139", None)
    finally:
        con.close()


def test_bad_state_code_nulled_but_preserved_raw(built):
    con = db.connect(built["db_path"], read_only=True)
    try:
        code, raw = con.execute(
            "SELECT STATE_CODE, STATE_CODE_RAW FROM facility WHERE REGISTRY_ID='110000000002'"
        ).fetchone()
        assert code is None
        assert raw == "XX"
    finally:
        con.close()


def test_no_pii_excludes_the_contact_table_entirely(mini_zip, tmp_path):
    """An all-PII table must be skipped, not column-filtered.

    Regression: dropping every column left include_columns == [], and `[] or
    None` handed Arrow None, meaning "all columns" - so the table was written
    in full with the personal data intact.
    """
    from j2d.frs.ingest import ingest_all

    results = ingest_all(mini_zip, tmp_path / "pq", drop_pii=True)
    assert "contact" not in {r.table for r in results}
    assert not (tmp_path / "pq" / "contact.parquet").exists()


def test_no_pii_strips_pii_columns_from_mixed_tables(mini_zip, tmp_path):
    import duckdb

    from j2d.frs.ingest import ingest_all
    from j2d.frs.schema import PII_COLUMNS

    ingest_all(mini_zip, tmp_path / "pq", drop_pii=True, only=["organization"])
    con = duckdb.connect()
    path = (tmp_path / "pq" / "organization.parquet").as_posix()
    cols = {d[0] for d in con.execute(f"SELECT * FROM read_parquet('{path}') LIMIT 0").description}
    assert not cols & set(PII_COLUMNS["organization"])
    assert "ORG_NAME" in cols, "non-PII columns must survive"


def test_ingest_table_refuses_to_filter_an_all_pii_table(mini_zip, tmp_path):
    import pytest as _pytest

    from j2d.frs.ingest import ingest_table
    from j2d.frs.schema import TABLES

    with _pytest.raises(ValueError, match="entirely personal data"):
        ingest_table(mini_zip, TABLES["contact"], tmp_path / "pq", drop_pii=True)


# --------------------------------------------------------------------------
# crosswalk
# --------------------------------------------------------------------------


def test_crosswalk_links_have_provenance(built):
    con = db.connect(built["db_path"], read_only=True)
    try:
        rows = con.execute(
            "SELECT PGM_SYS_ACRNM, PGM_SYS_ID, source_table_count, source_tables "
            "FROM crosswalk WHERE REGISTRY_ID='110000000001' ORDER BY PGM_SYS_ACRNM"
        ).fetchall()
        by_acr = {r[0]: r for r in rows}
        assert "SFDW" in by_acr and "NPDES" in by_acr and "RCRAINFO" in by_acr
        # NPDES is asserted by many tables; RCRAINFO only by the facility string.
        assert by_acr["NPDES"][2] > by_acr["RCRAINFO"][2]
        assert by_acr["RCRAINFO"][3] == ["facility_acrnms"]
    finally:
        con.close()


def test_crosswalk_explodes_facility_acronym_string(built):
    con = db.connect(built["db_path"], read_only=True)
    try:
        got = con.execute(
            "SELECT PGM_SYS_ID FROM crosswalk "
            "WHERE REGISTRY_ID='110000000001' AND PGM_SYS_ACRNM='RCRAINFO'"
        ).fetchone()[0]
        assert got == "OHD004228631", "the ':' split must not eat part of the id"
    finally:
        con.close()


def test_water_system_splits_pwsid_from_plant_id(built):
    con = db.connect(built["db_path"], read_only=True)
    try:
        rows = con.execute(
            "SELECT PWSID, SYSTEM_FACILITY_ID, INTEREST_TYPE, PWSID_STATE "
            "FROM water_system ORDER BY PWSID"
        ).fetchall()
        by_pwsid = {r[0]: r for r in rows}
        assert by_pwsid["OH1234567"][1] is None          # a system, no plant id
        assert by_pwsid["AR9876543"][1] == "4242"        # a plant within a system
        assert by_pwsid["OH1234567"][3] == "OH"
    finally:
        con.close()


def test_pivot_sql_sanitises_column_names():
    sql = crosswalk.pivot_sql(["AIRS/AFS", "TX-TCEQ ACR"])
    assert '"AIRS_AFS"' in sql
    assert '"TX_TCEQ_ACR"' in sql


# --------------------------------------------------------------------------
# QA
# --------------------------------------------------------------------------


def test_qa_runs_and_flags_the_planted_defects(built):
    con = db.connect(built["db_path"], read_only=True)
    try:
        checks = qa.run(con)
    finally:
        con.close()
    by_name = {c.name: c for c in checks}
    assert by_name["facility.registry_id_unique"].status == "ok"
    assert by_name["facility.state_code_out_of_domain"].value == 1
    assert "facility.fips_code_shapes" in by_name
    # The env-interest row for 110000000009 has no facility record.
    assert by_name["orphans.environmental_interest"].value == 1
    assert qa.summarise(checks)["fail"] == 0


def test_qa_never_raises_on_a_missing_table():
    con = duckdb.connect()
    checks = qa.run(con)
    assert all(c.status in ("ok", "warn", "fail") for c in checks)
