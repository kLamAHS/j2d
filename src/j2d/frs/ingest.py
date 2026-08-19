"""Stream the FRS national combined zip straight into Parquet.

The archive is ~1.2 GB compressed and ~10 GB expanded. Nothing here ever
materialises that 10 GB on disk: each CSV member is read as a stream of Arrow
record batches straight out of the zip and written incrementally to Parquet.
Peak memory is one batch, not one table.
"""

from __future__ import annotations

import codecs
import io
import itertools
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.parquet as pq

from .schema import PII_COLUMNS, PII_TABLES, Table, member_to_table

#: 64 MiB CSV read blocks: large enough to amortise per-batch overhead, small
#: enough that peak RSS stays well under a GB per worker.
BLOCK_SIZE = 1 << 26

#: Parquet row group size. Chosen so DuckDB can skip whole groups on the
#: predicates that matter here (STATE_CODE, PGM_SYS_ACRNM).
ROW_GROUP_SIZE = 256_000


@dataclass
class IngestResult:
    table: str
    member: str
    rows: int
    columns: int
    path: Path
    bytes_out: int
    seconds: float
    encoding_fallback: bool = False
    control_bytes_removed: int = 0

    @property
    def rows_per_second(self) -> float:
        return self.rows / self.seconds if self.seconds else 0.0


#: C0 control bytes deleted from the stream. Tab, LF and CR are kept because
#: they are structural. Everything else is corruption: EPA's extract carries
#: runs of NUL inside quoted address fields (216 bytes in the mailing-address
#: file, 1,755 in the organization file), plus a scattering of other control
#: characters in free-text name fields.
#:
#: Deleting them bytewise is safe on UTF-8: every byte of a multi-byte sequence
#: has the high bit set, so no control byte can appear inside one.
_CONTROL_BYTES = bytes(b for b in range(0x20) if b not in (0x09, 0x0A, 0x0D))


class _ReplaceCounter:
    """A codec error handler that counts the bytes it replaces.

    Kept separate from the sanitiser because ``codecs.register_error`` holds its
    handler forever; registering a bound method would pin the whole sanitiser,
    and with it the stream it wraps. This object is a few bytes.
    """

    __slots__ = ("count",)

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, exc: UnicodeDecodeError):
        self.count += exc.end - exc.start
        return ("\ufffd", exc.end)


#: Distinguishes the error-handler name registered per sanitiser instance.
_HANDLER_SEQ = itertools.count()


class _TextSanitiser(io.RawIOBase):
    """Wrap a binary stream, removing control bytes and repairing bad UTF-8.

    Two distinct problems, both present in the real archive:

    1. **Embedded NULs.** Arrow's CSV parser treats a NUL as a field terminator
       and silently emits a short row, which then fails the column-count check
       and aborts the whole 2 GB table. Python's own ``csv`` module reads the
       same row correctly at 14 fields, so this is a parser limitation rather
       than malformed CSV. Deleting the NULs keeps the row and costs only the
       junk that was in the field.

    2. **Invalid UTF-8.** Arrow rejects an entire batch on the first bad byte.
       Decoding with ``errors="replace"`` keeps the row.

    Decoding uses an *incremental* decoder, so a multi-byte character split
    across two reads is carried in the decoder's own state. That matters for
    more than tidiness: an earlier hand-rolled version held the partial
    sequence back in a buffer and could return 0 bytes while data remained,
    which ``io.RawIOBase`` defines as EOF — silently truncating the stream.
    The incremental decoder also makes the repaired output independent of where
    the read boundaries fall, so re-ingesting at a different block size cannot
    produce different strings.

    ``readinto`` never returns 0 unless the underlying stream is genuinely
    exhausted; it keeps pulling until it has at least one byte to hand back.
    """

    #: Fallback read size when a caller passes a zero-length buffer.
    _MIN_READ = 1 << 16

    def __init__(self, raw: io.BufferedIOBase) -> None:
        self._raw = raw
        self._pending = b""
        self._eof = False
        self.control_bytes_removed = 0
        #: Source bytes this instance actually replaced with U+FFFD.
        #:
        #: Counted by a private error handler rather than by looking for U+FFFD
        #: in the output, because EPA's own extract already contains 1,228
        #: encoded U+FFFD characters - mojibake produced upstream, before the
        #: file was published. Counting output characters would report those as
        #: our repairs and make the diagnostic useless.
        self.invalid_bytes_replaced = 0
        self._handler = _ReplaceCounter()
        name = f"j2d.frs.replace.{next(_HANDLER_SEQ)}"
        codecs.register_error(name, self._handler)
        self._decoder = codecs.getincrementaldecoder("utf-8")(name)

    @property
    def utf8_repaired(self) -> bool:
        """True if this instance replaced any invalid byte."""
        return self.invalid_bytes_replaced > 0

    def readable(self) -> bool:  # pragma: no cover - trivial
        return True

    def _fill(self, size: int) -> None:
        """Pull from the raw stream until ``_pending`` has bytes, or EOF."""
        while not self._pending and not self._eof:
            chunk = self._raw.read(size)
            if chunk:
                stripped = chunk.translate(None, _CONTROL_BYTES)
                self.control_bytes_removed += len(chunk) - len(stripped)
                text = self._decoder.decode(stripped)
            else:
                self._eof = True
                text = self._decoder.decode(b"", final=True)
            self.invalid_bytes_replaced = self._handler.count
            self._pending = text.encode("utf-8")

    def readinto(self, buf) -> int:
        want = len(buf)
        if want == 0:
            return 0
        self._fill(max(want, self._MIN_READ))
        out = self._pending[:want]
        self._pending = self._pending[len(out):]
        buf[: len(out)] = out
        return len(out)


def _all_string_types(names: list[str]) -> dict[str, pa.DataType]:
    return {name: pa.string() for name in names}


def read_header(zf: zipfile.ZipFile, member: str) -> list[str]:
    """Return the column names of a zip member without decompressing it all."""
    with zf.open(member) as fh:
        buf = fh.read(1 << 20)
    text = buf.decode("utf-8", errors="replace").lstrip("﻿")
    first = text.split("\n", 1)[0].rstrip("\r")
    tbl = pcsv.read_csv(io.BytesIO((first + "\n").encode("utf-8")))
    return tbl.column_names


def ingest_table(
    zip_path: Path,
    table: Table,
    out_dir: Path,
    *,
    force: bool = False,
    drop_pii: bool = False,
) -> IngestResult:
    """Convert one CSV member of the archive to Parquet.

    Returns an :class:`IngestResult`; raises nothing on an already-present
    output unless ``force`` is set, in which case it is rewritten.
    """
    if drop_pii and table.name in PII_TABLES:
        # Dropping every column would leave include_columns empty, and an empty
        # list is falsy: `[] or None` hands Arrow None, which means "all
        # columns". The table would be written in full, PII included. Refuse
        # instead - an entirely-personal table must be excluded, not filtered.
        raise ValueError(
            f"{table.name} is entirely personal data; exclude the table rather "
            f"than filtering its columns"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{table.name}.parquet"
    if out_path.exists() and not force:
        md = pq.read_metadata(out_path)
        return IngestResult(
            table=table.name,
            member=table.member,
            rows=md.num_rows,
            columns=md.num_columns,
            path=out_path,
            bytes_out=out_path.stat().st_size,
            seconds=0.0,
        )

    started = time.time()
    tmp_path = out_path.with_suffix(".parquet.tmp")

    with zipfile.ZipFile(zip_path) as zf:
        names = read_header(zf, table.member)
        drop: set[str] = set()
        if drop_pii:
            if table.name in PII_TABLES:
                drop.update(names)
            drop.update(c for c in PII_COLUMNS.get(table.name, ()) if c in names)

        keep = [n for n in names if n not in drop]
        if not keep:
            raise ValueError(f"{table.member}: every column was dropped")

        with zf.open(table.member) as raw:
            sanitiser = _TextSanitiser(raw)
            stream = io.BufferedReader(sanitiser, buffer_size=BLOCK_SIZE)
            reader = pcsv.open_csv(
                stream,
                read_options=pcsv.ReadOptions(block_size=BLOCK_SIZE),
                parse_options=pcsv.ParseOptions(newlines_in_values=True),
                convert_options=pcsv.ConvertOptions(
                    column_types=_all_string_types(names),
                    strings_can_be_null=True,
                    include_columns=keep,
                ),
            )
            writer: pq.ParquetWriter | None = None
            rows = 0
            ncols = 0
            try:
                for batch in reader:
                    if writer is None:
                        writer = pq.ParquetWriter(
                            tmp_path,
                            batch.schema,
                            compression="zstd",
                            compression_level=3,
                            use_dictionary=True,
                        )
                        ncols = batch.num_columns
                    writer.write_batch(batch, row_group_size=ROW_GROUP_SIZE)
                    rows += batch.num_rows
            finally:
                if writer is not None:
                    writer.close()
            repaired = sanitiser.utf8_repaired
            removed = sanitiser.control_bytes_removed

    if rows == 0 and not tmp_path.exists():
        raise RuntimeError(f"{table.member}: produced no rows")
    tmp_path.replace(out_path)

    return IngestResult(
        table=table.name,
        member=table.member,
        rows=rows,
        columns=ncols,
        path=out_path,
        bytes_out=out_path.stat().st_size,
        seconds=time.time() - started,
        encoding_fallback=repaired,
        control_bytes_removed=removed,
    )


def ingest_all(
    zip_path: Path,
    out_dir: Path,
    *,
    force: bool = False,
    drop_pii: bool = False,
    only: list[str] | None = None,
    progress=None,
) -> list[IngestResult]:
    """Convert every CSV member of the archive to Parquet, smallest first."""
    with zipfile.ZipFile(zip_path) as zf:
        sizes = {i.filename: i.file_size for i in zf.infolist()}
    lookup = member_to_table()
    wanted = [t for t in lookup.values() if only is None or t.name in only]
    if drop_pii:
        excluded = [t.name for t in wanted if t.name in PII_TABLES]
        if excluded and progress:
            for name in excluded:
                progress(f"skip   {name:<24} (entirely personal data; --no-pii)")
        wanted = [t for t in wanted if t.name not in PII_TABLES]
    wanted.sort(key=lambda t: sizes.get(t.member, 0))

    results = []
    for table in wanted:
        if progress:
            progress(f"ingest {table.name:<24} ({sizes.get(table.member, 0) / 1e6:,.0f} MB csv)")
        res = ingest_table(zip_path, table, out_dir, force=force, drop_pii=drop_pii)
        if progress:
            progress(
                f"  -> {res.rows:>10,} rows  {res.bytes_out / 1e6:>7,.0f} MB parquet"
                f"  {res.seconds:>6.1f}s"
                + ("  [utf8 repaired]" if res.encoding_fallback else "")
                + (f"  [{res.control_bytes_removed} control bytes removed]" if res.control_bytes_removed else "")
            )
        results.append(res)
    return results


def missing_members(zip_path: Path) -> list[str]:
    """Zip members the registry does not know about (schema drift check)."""
    with zipfile.ZipFile(zip_path) as zf:
        members = {i.filename for i in zf.infolist() if i.filename.upper().endswith(".CSV")}
    return sorted(members - set(member_to_table()))
