# FRS national combined pipeline

Turns EPA's Facility Registry Service "national combined" extract — a 1.26 GB zip
holding ten CSVs, ~10 GB expanded, 47.6 million rows — into a queryable DuckDB
database with a cross-program identifier crosswalk.

FRS matters here because it is the only public artefact that says *these
identifiers denote the same place*. Every EPA program system, and roughly
forty-five state systems, knows a facility by its own ID. FRS is the join.

## Quick start

```bash
pip install -e .
j2d frs all                       # ingest + build, ~5 minutes
j2d frs qa --only-problems        # what is wrong with the source data
j2d frs query "SELECT count(*) FROM crosswalk"
```

Everything lands in `work/` (gitignored): `work/parquet/*.parquet` and
`work/frs.duckdb`.

## Commands

| Command | Does |
|---|---|
| `j2d frs ingest` | zip → Parquet, streaming. `--only`, `--force`, `--no-pii` |
| `j2d frs build` | Parquet → DuckDB views + materialised crosswalk |
| `j2d frs all` | both |
| `j2d frs qa` | data-quality report. `--json`, `--only-problems` |
| `j2d frs query SQL` | run SQL (`-` reads stdin). `--csv` |
| `j2d frs export` | a table or query → Parquet/CSV |
| `j2d frs info` | tables and row counts |

## Layers

```
data/national_combined.zip        1.26 GB, as EPA ships it
  └─ work/parquet/*.parquet       1.1 GB, all columns text, nothing cleaned
       └─ raw_<table>             DuckDB view, exactly what EPA said
            └─ <table>            normalised view: dates, whitespace, codes
                 └─ crosswalk     materialised, 7.6M links with provenance
                    water_system  SFDW parsed into PWSID + plant id
```

The raw layer is kept deliberately. When a normalised value looks wrong, the
question "what did EPA actually say?" must be answerable without re-ingesting.

### Everything is text on ingest

Type inference is off. `FIPS_CODE` `"02020"`, `POSTAL_CODE` `"07030"` and
`NAICS_CODE` all carry meaningful leading zeros that integer inference destroys,
and `REGISTRY_ID` is a 12-digit identifier rather than a quantity. Typing happens
later, in SQL, where the rules are visible and tested.

## What the ingest survives

Two defects in the real extract, both of which abort a naive pyarrow read:

**NUL bytes inside quoted fields.** 216 in the mailing-address file, 1,755 in the
organization file, plus scattered other control characters elsewhere. Arrow treats
a NUL as a field terminator and emits a short row, which fails the column-count
check and kills the whole 2 GB table. Python's own `csv` module reads the same row
correctly at 14 fields, so this is a parser limitation rather than malformed CSV.
The sanitiser deletes C0 control bytes (keeping tab, CR, LF) before Arrow sees
them, so the row survives and only the junk field is emptied. Every removal is
counted and reported.

**Invalid UTF-8.** Arrow rejects an entire batch on the first bad byte. The
sanitiser decodes with replacement, re-aligning chunk boundaries so a multi-byte
character split across two reads survives.

Deleting control bytes bytewise is safe on UTF-8: every byte of a multi-byte
sequence has the high bit set, so a control byte can never appear inside one.

## Normalisation rules

| Rule | What it does |
|---|---|
| dates | Oracle `DD-MON-YY` → `DATE`, unparseable → `NULL` |
| text | trim, collapse internal whitespace runs, empty → `NULL` |
| country | `USA` / `UNITED STATES` / `UNITED STATES OF AMERICA` → `US` |
| state | uppercase; outside the USPS domain → `NULL`, kept in `STATE_CODE_RAW` |
| postal | `POSTAL_CODE_ZIP5` derived from the first five digits |
| fips | `FIPS_CODE_COUNTY5` derived, populated only when genuinely a county FIPS |
| coords | cast to `DOUBLE`; zero and out-of-range → `NULL` |

### The two-digit year problem

FRS dates are Oracle `DD-MON-YY`. C `strptime` maps `00`–`68` to 2000–2068 and
`69`–`99` to 1969–1999. That is right for creation dates and wrong for mid-century
permit and affiliation dates, which land a century in the future.

Simply rejecting future dates does not work: permit *expiration* dates are
legitimately in the future. So a parsed date more than **25 years** ahead of today
is pulled back a century, and everything else is left alone. A 2035 permit expiry
stays 2035; a `01-JAN-60` start date becomes 1960 rather than 2060.

The rule is load-bearing. On the real extract it corrects **~54,000 dates**, and
every value it touches is a genuine 1954–1968 date — the exact range where
`strptime`'s pivot is wrong. `j2d frs qa` counts each adjustment, so the rule can
never operate silently.

## The crosswalk

One row per `(REGISTRY_ID, PGM_SYS_ACRNM, PGM_SYS_ID)`, unioned from every table
carrying the triple plus the denormalised `facility.PGM_SYS_ACRNMS` string, with
`source_tables` recording which tables asserted each link.

That provenance is the useful part. A link asserted by one contact row is far
weaker evidence than one asserted by the program, interest and facility tables
together, and the two representations *disagree* often enough to matter — see the
`crosswalk.*` checks in the QA report.

```sql
-- everything EPA knows this facility as
SELECT PGM_SYS_ACRNM, PGM_SYS_ID, source_tables
FROM crosswalk WHERE REGISTRY_ID = '110000491735';
```

## Drinking water

Drinking-water systems are held under **`SFDW`** (Safe Drinking Water), not
`SDWIS` as the program is usually called externally. This trips people up.

`PGM_SYS_ID` carries two shapes under the one acronym:

| Shape | Meaning |
|---|---|
| `OH1234567` | a public water system — a bare PWSID |
| `AK2340670 42614` | a facility *within* that system, e.g. a treatment plant |

The `water_system` view splits them, which is what makes SFDW joinable to SDWIS
and ECHO — both of which key on the bare PWSID.

In this extract: 608,487 SFDW interests over 392,724 facilities, of which

| Interest type | Rows |
|---|---|
| Transient non-community water system | 241,571 |
| Water treatment plant | 235,288 |
| Community water system | 89,871 |
| Non-transient non-community water system | 41,731 |

Community and non-transient non-community systems are the population subject to
the PFAS MCLs and the LCRI: 131,602 interest rows resolving to **131,598 distinct
PWSIDs**, out of 380,410 distinct PWSIDs in the extract overall. That is the
addressable universe for the water dataset in
`ideas/03-water-treatment-buying-signal.md`.

Two caveats on the ID parsing, both tiny but real: 2 of the 608,487 SFDW ids
contain more than one space, so their plant id is truncated by the split; and 2
program ids elsewhere in the extract contain a comma, which the
`facility.PGM_SYS_ACRNMS` explode mis-splits. No id anywhere contains a colon, so
the acronym split is safe.

## Known defects in the source data

Measured by `j2d frs qa` on the current extract. These are EPA's, not the
pipeline's — the point of the report is that you model around them knowingly.

**Geospatial columns are entirely empty.** All 5,319,139 facility rows have NULL
`LATITUDE83` and `LONGITUDE83`, and NULL `COLLECT_DESC`, `ACCURACY_VALUE` and
`REF_POINT_DESC`. Only `HDATUM_DESC` is populated, with the constant `NAD83`. The
columns exist in the schema and carry no data. **You cannot map anything from this
file** — coordinates need EPA's separate geospatial download or the FRS API. This
is the single most consequential thing to know before planning work on it.

**`FIPS_CODE` mixes four incompatible formats.** Only 3,594,816 of the 4,249,460
non-null values are a real 5-digit county FIPS:

| Shape | Rows | Example |
|---|---:|---|
| 5-digit numeric county FIPS | 3,594,816 | `39155` |
| null | 1,069,679 | |
| USPS prefix + 3 digits | 498,920 | `AK090` — not a FIPS code at all |
| numeric, wrong length | 154,962 | `04` — state only |
| other | 762 | |

A further **43,126** rows pass the shape test but contradict their own
`STATE_CODE`: they are county codes zero-padded to five digits with the state
prefix missing, so Seattle appears as `00033` where King County, WA is `53033`.
These look valid and join to the wrong county, which is worse than not joining.

Net: **3,551,689 trustworthy county FIPS out of 5,319,139 facilities — 67%.**
Joining census or ACS data on the raw column silently drops about a third of the
rows and silently mis-joins another 43,126. Use the derived `FIPS_CODE_COUNTY5`,
which is populated only when the value is five numeric digits *and* its state
prefix agrees with `STATE_CODE`.

This one is worth dwelling on because the check that was supposed to catch it
originally reported a clean zero. Its correlated subquery selected from the same
table it filtered, so `STATE_CODE = facility.STATE_CODE` bound to the inner row
and was always true; the subquery returned every prefix and `NOT IN (everything)`
was always false. A check that structurally cannot fail is worse than no check.

**Referential integrity is not guaranteed.** 8,415 program rows, 1,062
supplemental-interest rows and 101 environmental-interest rows reference a
`REGISTRY_ID` with no facility record. Inner-joining to `facility` silently drops
them.

**Obsolete state codes.** `TT` (Trust Territory of the Pacific Islands, dissolved
1994) appears on 15 facilities and is rejected. `FM`, `MH` and `PW` also appear
and *are* valid USPS codes for the freely associated states, so they are accepted.

**The bundled documentation is stale.** `Facility State File Documentation
11132012_new.pdf` is version 1.1.1 from November 2012. It documents 28 columns for
the facility file where the current extract has 34, and 51 for the program file
where the extract has 55. It also describes a `GIS_program` file that this archive
does not contain. Treat it as a starting point, not as authority — the registry it
describes had "over 2.5 million" facilities; this one has 5.3 million.

## Personal data

The `contact` table is entirely personal data — names, direct phone numbers and
email addresses for 4,656,542 facility contacts. `organization` carries some too.

`--no-pii` excludes the `contact` table outright and drops the personal columns
from `organization`:

```bash
j2d frs ingest --no-pii
```

It refuses to "filter" an all-personal table rather than quietly writing a
column-less one, because an empty column list is falsy and would otherwise be
handed to Arrow as `None`, meaning *all columns* — writing the full table with
the personal data intact. There is a regression test for exactly that.

## Scale

Measured on 4 cores / 15 GB RAM:

| Stage | Time | Output |
|---|---|---|
| ingest (10 GB CSV → Parquet) | 3.3 min | 1.1 GB |
| build views + crosswalk | 1.7 min | 128 MB DuckDB |
| QA (full scans) | ~2 min | — |

Peak memory is one 64 MiB batch per table, not one table. The 10 GB expansion is
never written to disk.

## Extending to another dataset

`src/j2d/frs/` is one dataset package. The shape generalises: a `schema.py`
registry of source files, an `ingest.py` that streams to Parquet without trusting
the source, `normalize.py` rules as SQL, and `qa.py` checks that measure rather
than mutate. Add `src/j2d/<dataset>/` and a subparser in `cli.py`.
