"""Command-line interface: ``j2d frs <command>``."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

DEFAULT_ZIP = Path("data/national_combined.zip")
DEFAULT_WORK = Path("work")


def _echo(msg: str) -> None:
    print(msg, flush=True)


def _db_path(args) -> Path:
    return args.db or (args.work / "frs.duckdb")


def cmd_ingest(args) -> int:
    from .frs.ingest import ingest_all, missing_members

    unknown = missing_members(args.zip)
    if unknown:
        _echo(f"warning: archive contains unregistered members: {', '.join(unknown)}")
    ingest_all(
        args.zip,
        args.work / "parquet",
        force=args.force,
        drop_pii=args.no_pii,
        only=args.only,
        progress=_echo,
    )
    return 0


def cmd_build(args) -> int:
    from .frs.pipeline import build_database

    info = build_database(args.work / "parquet", _db_path(args), progress=_echo)
    _echo(f"views: {', '.join(info['views'])}")
    _echo(f"crosswalk rows: {info['crosswalk_rows']:,}")
    _echo(f"water_system rows: {info['water_system_rows']:,}")
    return 0


def cmd_all(args) -> int:
    from .frs.pipeline import run_all

    info = run_all(
        args.zip,
        args.work,
        force=args.force,
        drop_pii=args.no_pii,
        only=args.only,
        progress=_echo,
    )
    _echo(f"\ndatabase: {info['db_path']}")
    _echo(f"crosswalk rows: {info['crosswalk_rows']:,}")
    return 0


def cmd_qa(args) -> int:
    from .frs.pipeline import run_qa
    from .frs.qa import summarise

    checks = run_qa(_db_path(args))
    if args.json:
        print(
            json.dumps(
                [
                    {"name": c.name, "status": c.status, "value": c.value, "detail": c.detail}
                    for c in checks
                ],
                indent=1,
                default=str,
            )
        )
    else:
        for c in checks:
            if args.only_problems and c.status == "ok":
                continue
            print(c)
            for row in c.rows[:10]:
                print(f"           {row}")
    s = summarise(checks)
    _echo(f"\n{s['ok']} ok, {s['warn']} warn, {s['fail']} fail")
    return 1 if s["fail"] else 0


def cmd_query(args) -> int:
    from .frs import db

    sql = args.sql
    if sql == "-":
        sql = sys.stdin.read()
    con = db.connect(_db_path(args), read_only=True)
    try:
        rel = con.sql(sql)
        if rel is None:
            return 0
        if args.csv:
            w = csv.writer(sys.stdout)
            w.writerow(rel.columns)
            w.writerows(rel.fetchall())
        else:
            rel.show(max_rows=args.limit)
    finally:
        con.close()
    return 0


def cmd_export(args) -> int:
    from .frs import db

    con = db.connect(_db_path(args), read_only=True)
    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        src = args.table if args.sql is None else f"({args.sql})"
        fmt = args.out.suffix.lstrip(".").lower()
        if fmt == "parquet":
            con.execute(f"COPY (SELECT * FROM {src}) TO '{args.out}' (FORMAT PARQUET)")
        elif fmt in ("csv", "tsv"):
            sep = "\t" if fmt == "tsv" else ","
            con.execute(
                f"COPY (SELECT * FROM {src}) TO '{args.out}' "
                f"(FORMAT CSV, HEADER, DELIMITER '{sep}')"
            )
        else:
            _echo(f"unsupported output format: {args.out.suffix}")
            return 2
    finally:
        con.close()
    _echo(f"wrote {args.out}")
    return 0


def cmd_info(args) -> int:
    from .frs import db
    from .frs.schema import TABLES

    con = db.connect(_db_path(args), read_only=True)
    try:
        counts = db.table_row_counts(con)
    finally:
        con.close()
    width = max(len(n) for n in TABLES)
    for name, t in sorted(TABLES.items()):
        n = counts.get(name)
        _echo(f"{name:<{width}}  {n:>12,}  {t.grain}" if n else f"{name:<{width}}  {'-':>12}")
    _echo(f"\ntotal rows: {sum(counts.values()):,}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="j2d", description=__doc__)
    p.add_argument("--work", type=Path, default=DEFAULT_WORK, help="working directory")
    p.add_argument("--db", type=Path, default=None, help="DuckDB path (default WORK/frs.duckdb)")
    sub = p.add_subparsers(dest="dataset", required=True)

    frs = sub.add_parser("frs", help="EPA Facility Registry Service")
    fsub = frs.add_subparsers(dest="command", required=True)

    def add_ingest_args(sp):
        sp.add_argument("--zip", type=Path, default=DEFAULT_ZIP)
        sp.add_argument("--force", action="store_true", help="rewrite existing Parquet")
        sp.add_argument("--no-pii", action="store_true", help="drop personal contact columns")
        sp.add_argument("--only", nargs="*", default=None, help="limit to these tables")

    sp = fsub.add_parser("ingest", help="zip -> Parquet")
    add_ingest_args(sp)
    sp.set_defaults(func=cmd_ingest)

    sp = fsub.add_parser("build", help="Parquet -> DuckDB views + crosswalk")
    sp.set_defaults(func=cmd_build)

    sp = fsub.add_parser("all", help="ingest + build in one pass")
    add_ingest_args(sp)
    sp.set_defaults(func=cmd_all)

    sp = fsub.add_parser("qa", help="run data-quality checks")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--only-problems", action="store_true")
    sp.set_defaults(func=cmd_qa)

    sp = fsub.add_parser("query", help="run SQL against the database")
    sp.add_argument("sql", help="SQL text, or - to read stdin")
    sp.add_argument("--csv", action="store_true", help="emit CSV instead of a table")
    sp.add_argument("--limit", type=int, default=40)
    sp.set_defaults(func=cmd_query)

    sp = fsub.add_parser("export", help="export a table or query to Parquet/CSV")
    sp.add_argument("--table", default="crosswalk")
    sp.add_argument("--sql", default=None, help="export this query instead of --table")
    sp.add_argument("--out", type=Path, required=True)
    sp.set_defaults(func=cmd_export)

    sp = fsub.add_parser("info", help="show ingested tables and row counts")
    sp.set_defaults(func=cmd_info)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
