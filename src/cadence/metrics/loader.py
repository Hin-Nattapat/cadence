"""cadence.metrics.loader — the one module allowed to name the privileged partition.

CONTRACT: every other module in `cadence.metrics` reads a run directory through
`RunDirectory`, never by constructing a path of its own. That is what keeps ST-D30
mechanical: an architecture test scans this package for the partition's name and finds
it nowhere, because there is exactly one place a path into the run directory is built.
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

    @property
    def root(self) -> Path:
        return self._root

    def manifest(self) -> RunManifest:
        return RunManifest.model_validate_json((self._root / "manifest.json").read_text())

    def topology(self, table: str) -> pl.DataFrame:
        _validate_table_name(table)
        return pl.read_parquet(self._root / "topology" / f"{table}.parquet")

    def state(self, table: str) -> pl.DataFrame:
        _validate_table_name(table)
        return pl.read_parquet(self._root / "state" / f"{table}.parquet")

    def evaluation(self, table: str) -> pl.DataFrame:
        _validate_table_name(table)
        return pl.read_parquet(self._root / "evaluation" / f"{table}.parquet")
