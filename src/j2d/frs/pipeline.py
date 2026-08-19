"""End-to-end orchestration: zip -> Parquet -> DuckDB -> crosswalk -> QA."""

from __future__ import annotations

from pathlib import Path

from . import crosswalk, db, qa
from .ingest import IngestResult, ingest_all
from .schema import TABLES


def build_database(
    parquet_dir: Path,
    db_path: Path,
    *,
    with_crosswalk: bool = True,
    progress=None,
) -> dict:
    """Create the DuckDB database of views plus the materialised crosswalk."""
    con = db.connect(db_path)
    if progress:
        progress("building views")
    built = db.build_views(con, parquet_dir)
    info: dict = {"views": built, "crosswalk_rows": 0, "water_system_rows": 0}

    if with_crosswalk and built:
        if progress:
            progress("materialising crosswalk")
        info["crosswalk_rows"] = crosswalk.build(con, set(built))
        if "environmental_interest" in built and "facility" in built:
            info["water_system_rows"] = crosswalk.build_water_system(con)
    con.close()
    return info


def run_all(
    zip_path: Path,
    work_dir: Path,
    *,
    db_path: Path | None = None,
    force: bool = False,
    drop_pii: bool = False,
    only: list[str] | None = None,
    progress=None,
) -> dict:
    parquet_dir = work_dir / "parquet"
    db_path = db_path or work_dir / "frs.duckdb"
    results: list[IngestResult] = ingest_all(
        zip_path, parquet_dir, force=force, drop_pii=drop_pii, only=only, progress=progress
    )
    info = build_database(parquet_dir, db_path, progress=progress)
    info["ingest"] = results
    info["db_path"] = db_path
    info["parquet_dir"] = parquet_dir
    return info


def run_qa(db_path: Path) -> list[qa.Check]:
    con = db.connect(db_path, read_only=True)
    try:
        return qa.run(con)
    finally:
        con.close()
