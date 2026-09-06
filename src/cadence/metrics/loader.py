"""cadence.metrics.loader — the one module allowed to name the privileged partition.

CONTRACT: every other module in `cadence.metrics` reads a run directory through
`RunDirectory`, never by constructing a read path of its own. That is what keeps ST-D30
mechanical: an architecture test scans this package for the partition's name and finds
it nowhere, because there is exactly one place a path is built to read the run directory.
The writer builds the one path it writes, to the partition it alone produces.

CONTRACT: an instance reads each table and the manifest from disk once and hands the same
object back on every later call, so a caller must treat what it receives as shared and
never mutate it in place. Every polars operation the package uses returns a new frame.
What that costs is the whole of every table read, held for the life of the instance --
measured at 24-80 MB for an M8 corridor hour of `state/lane` -- so a long-lived process
scores through an instance it drops afterwards rather than one it keeps.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from cadence.simulation.manifest import RunManifest


def _validate_table_name(table: str) -> None:
    # GOTCHA: `table` reaches a path join unescaped. A bare identifier can never contain
    # "/", "\\", or "..", so this refuses the traversal `run.state("../topology/lane")`
    # would otherwise resolve through the accessor below.
    if not table.isidentifier() or "/" in table or "\\" in table:
        raise ValueError(f"table name {table!r} is not a bare identifier")


class RunDirectory:
    """A run directory written by `cadence.cli.run_scenario`, read through the three
    partitions spec §6.1 allows this package to see. No accessor for the fourth
    partition exists here, or anywhere else under this package (ST-D30).
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._tables: dict[tuple[str, str], pl.DataFrame] = {}
        self._manifest: RunManifest | None = None

    @property
    def root(self) -> Path:
        return self._root

    def manifest(self) -> RunManifest:
        if self._manifest is None:
            self._manifest = RunManifest.model_validate_json(
                (self._root / "manifest.json").read_text()
            )
        return self._manifest

    def _table(self, partition: str, table: str) -> pl.DataFrame:
        # One `cadence metrics` run asks for evaluation/tripinfo once per metric that reads
        # it, and for state/lane once per queue metric. Without the memo those are ~16
        # separate Parquet reads of the same bytes.
        _validate_table_name(table)
        key = (partition, table)
        cached = self._tables.get(key)
        if cached is not None:
            return cached
        frame = pl.read_parquet(self._root / partition / f"{table}.parquet")
        self._tables[key] = frame
        return frame

    def topology(self, table: str) -> pl.DataFrame:
        return self._table("topology", table)

    def state(self, table: str) -> pl.DataFrame:
        return self._table("state", table)

    def evaluation(self, table: str) -> pl.DataFrame:
        return self._table("evaluation", table)
