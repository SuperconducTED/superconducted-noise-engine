"""Read-only loader for the feature deep-dive cache, with the shared event and variogram rules.

The cache is written once by ``extract_cache.py`` (see ``01-data-layer.md`` for every field).
Load only the fields you need: each ``v()``/``d()`` call memory-maps one ``.npy`` file.

Typical use from a scope script at ``analysis/<scope>/<name>.py``::

    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    import ddload

    dd = ddload.DD()
    t1 = ddload.series(dd, "q.T1", rule=ddload.MEASURED)

Two event rules (the data dictionary says which applies to which field):

- ``MEASURED``: the field carries the date IBM measured it. An event is a file where BOTH
  the value and the stamped date are new (the rule of ``scripts/feature_patterns.py``,
  imported, not re-implemented).
- ``ASSEMBLY``: the field's date is re-stamped whenever a document is assembled, so the date
  carries no information. An event is a file where the value differs from the previous one;
  its time is the first file's ``last_update_date``.

Placeholders are masked BEFORE events are formed (pass ``mask=``), never after.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

REF = "7b84b506ef77beb6e6c1b25a7357c574cfaf5117"
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from scripts.feature_patterns import Series  # noqa: E402
from scripts.feature_patterns import events as _fp_events  # noqa: E402

FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
Mask = Callable[[FloatArray], BoolArray]

MEASURED = "measured"
ASSEMBLY = "assembly"
MS_PER_HOUR = 3.6e6

# Default lag bins for variograms, in hours. Chosen so that the readout cadence (~4.5 h) and
# the daily rounds (~24 h and multiples) fall inside separate bins.
VARIOGRAM_EDGES_H: tuple[float, ...] = (
    0.0,
    0.5,
    2.0,
    4.0,
    6.0,
    9.0,
    12.0,
    18.0,
    30.0,
    42.0,
    54.0,
    84.0,
    132.0,
    204.0,
    372.0,
    744.0,
    1488.0,
    3624.0,
)


def placeholder_error(values: FloatArray) -> BoolArray:
    """``gate_error >= 1``: IBM's "not calibrated" placeholder."""
    out: BoolArray = values >= 1.0
    return out


def zero_value(values: FloatArray) -> BoolArray:
    """Exact zero (e.g. ``jq = 0`` on a faulty coupler); a candidate placeholder."""
    out: BoolArray = values == 0.0
    return out


def cache_dir() -> Path:
    env = os.environ.get("DD_CACHE")
    if env:
        return Path(env)
    return Path.home() / ".cache" / "superconducted-feature-deep-dive" / REF[:8]


class DD:
    """One pinned cache. Arrays are ``(n_files, n_entities)``, files in time order."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or cache_dir()
        meta_path = self.path / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(
                f"no cache at {self.path}: run extract_cache.py (01-data-layer.md) or set DD_CACHE"
            )
        self.meta: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
        if self.meta["ref"] != REF:
            raise ValueError(f"cache ref {self.meta['ref']} is not the pinned {REF}")
        self.stems: list[str] = self.meta["stems"]
        self.n_files: int = int(self.meta["n_files"])

    def fields(self) -> list[str]:
        return sorted(self.meta["fields"])

    def v(self, field: str) -> FloatArray:
        """Values of ``field`` (memory-mapped, read-only)."""
        out: FloatArray = np.load(self.path / f"{field}__v.npy", mmap_mode="r")
        return out

    def d(self, field: str) -> FloatArray:
        """Stamped dates of ``field`` in ms since the epoch (memory-mapped, read-only)."""
        out: FloatArray = np.load(self.path / f"{field}__d.npy", mmap_mode="r")
        return out

    def file(self, name: str) -> npt.NDArray[Any]:
        """A per-file array, e.g. ``last_update_ms``, ``has_configuration``, ``config.dt``."""
        out: npt.NDArray[Any] = np.load(self.path / f"file.{name}.npy")
        return out

    @property
    def file_ms(self) -> FloatArray:
        out: FloatArray = self.file("last_update_ms").astype(np.float64)
        return out

    def entities(self, field: str) -> list[Any]:
        """Column labels: qubit index, directed ``[a, b]``, undirected coupler, or lf name."""
        if field.startswith(("q.", "g1.")):
            return list(self.meta["qubits"])
        if field.startswith("g2."):
            return list(self.meta["directed_edges"])
        if field in ("gen.jq", "gen.zz"):
            return list(self.meta["couplers"])
        if field.startswith("gen.lf"):
            return list(self.meta["lf_names"])
        raise KeyError(field)

    def lf_chain(self, file_idx: int, column: int) -> list[int] | None:
        """Qubit chain of ``gen.lf`` column ``column`` in file ``file_idx`` (None if absent)."""
        ids = np.load(self.path / "gen.lf_chain__v.npy", mmap_mode="r")
        k = int(ids[file_idx, column])
        return None if k < 0 else list(self.meta["lf_chains"][k])


def series(
    dd: DD, field: str, *, rule: str, mask: Mask | None = None, transform_ok: bool = False
) -> list[Series]:
    """Re-measurement events of every column of ``field`` under ``rule``.

    ``mask`` marks placeholder values, which are set to NaN before events are formed.
    With ``transform_ok`` True, non-positive values are also dropped (for log transforms).
    """
    values = np.array(dd.v(field), dtype=np.float64)
    dates = np.array(dd.d(field), dtype=np.float64)
    if mask is not None:
        values[mask(values)] = np.nan
    if transform_ok:
        values[values <= 0] = np.nan
    if rule == MEASURED:
        out, _ = _fp_events(values, dates, mask_placeholder=False)
        return out
    if rule != ASSEMBLY:
        raise ValueError(f"unknown rule {rule!r}")
    file_ms = dd.file_ms
    result: list[Series] = []
    for e in range(values.shape[1]):
        col = values[:, e]
        idx = np.flatnonzero(np.isfinite(col))
        if idx.size == 0:
            continue
        keep = [int(idx[0])]
        for i in idx[1:]:
            if col[i] != col[keep[-1]]:
                keep.append(int(i))
        k = np.array(keep, dtype=np.int64)
        result.append(Series(entity=e, t_ms=file_ms[k], file_idx=k, y=col[k]))
    return result


def assembly_share(dd: DD, field: str) -> float:
    """Share of present records whose date equals the file's ``last_update_date``."""
    dates = np.array(dd.d(field))
    file_ms = dd.file_ms[:, None]
    ok = np.isfinite(dates)
    return (
        float(np.mean(dates[ok] == np.broadcast_to(file_ms, dates.shape)[ok]))
        if ok.any()
        else math.nan
    )


def variogram(
    series_list: Sequence[Series],
    *,
    transform: str = "log10",
    edges_h: Sequence[float] = VARIOGRAM_EDGES_H,
    noise_var: Sequence[FloatArray] | None = None,
) -> dict[str, Any]:
    """Empirical semivariogram of event values against the time between events, pooled.

    For every pair of events ``i < j`` of one series, the lag is ``t_j - t_i`` (hours, from
    the stamped dates) and the half squared difference is ``(z_j - z_i)^2 / 2`` with
    ``z = log10(y)`` (or ``y`` itself when ``transform == "none"``). Pairs are binned by lag.

    Reading it: estimation noise around a fixed level gives a FLAT curve at the noise variance
    for every lag; a random-walk level adds a part that grows linearly with lag; fluctuations
    with a correlation time tau rise over lags near tau and then flatten. The value at the
    shortest observed lag (the nugget) is noise plus any dynamics faster than that lag.

    ``noise_var``, when given, is one array per series of the known variance of each event's
    ``z`` (e.g. readout shot noise); each bin then also reports the mean of
    ``(var_i + var_j) / 2``, the part of the semivariance that noise alone explains.
    """
    edges = np.asarray(edges_h, dtype=np.float64)
    nb = edges.size - 1
    sums = np.zeros(nb)
    counts = np.zeros(nb, dtype=np.int64)
    lag_sums = np.zeros(nb)
    noise_sums = np.zeros(nb)
    sqrt_sums = np.zeros(nb)
    series_seen = np.zeros(nb, dtype=np.int64)
    for k, s in enumerate(series_list):
        y = np.asarray(s.y, dtype=np.float64)
        t = np.asarray(s.t_ms, dtype=np.float64) / MS_PER_HOUR
        ok = np.isfinite(y) & np.isfinite(t)
        if transform == "log10":
            ok &= y > 0
        y, t = y[ok], t[ok]
        if y.size < 2:
            continue
        z = np.log10(y) if transform == "log10" else y
        iu, ju = np.triu_indices(z.size, k=1)
        lag = np.abs(t[ju] - t[iu])
        dz = z[ju] - z[iu]
        b = np.searchsorted(edges, lag, side="right") - 1
        inside = (b >= 0) & (b < nb)
        b, lag, dz = b[inside], lag[inside], dz[inside]
        np.add.at(sums, b, 0.5 * dz * dz)
        np.add.at(counts, b, 1)
        np.add.at(lag_sums, b, lag)
        np.add.at(sqrt_sums, b, np.sqrt(np.abs(dz)))
        series_seen[np.unique(b)] += 1
        if noise_var is not None:
            var = np.asarray(noise_var[k], dtype=np.float64)[ok]
            np.add.at(noise_sums, b, 0.5 * (var[iu][inside] + var[ju][inside]))
    bins = []
    for i in range(nb):
        c = int(counts[i])
        row: dict[str, Any] = {
            "lag_h_lo": float(edges[i]),
            "lag_h_hi": float(edges[i + 1]),
            "pairs": c,
            "series": int(series_seen[i]),
            "mean_lag_h": round(float(lag_sums[i] / c), 3) if c else None,
            "semivariance": round(float(sums[i] / c), 6) if c else None,
            "semivariance_robust": (
                round(float((sqrt_sums[i] / c) ** 4 / (2.0 * (0.457 + 0.494 / c))), 6)
                if c
                else None
            ),
        }
        if noise_var is not None:
            row["noise_part"] = round(float(noise_sums[i] / c), 6) if c else None
        bins.append(row)
    return {"transform": transform, "bins": bins}


def result_header(scope: str, script: str) -> dict[str, Any]:
    """Provenance block every results JSON starts with."""
    return {
        "provisional": True,
        "ref": REF,
        "scope": scope,
        "script": script,
        "measured_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "basis": "all ibm_fez snapshot files at the ref (see n_files)",
        "machine": "lead's laptop (provisional until re-run on the verification desktop)",
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, sort_keys=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def log10(values: FloatArray) -> FloatArray:
    out: FloatArray = np.log10(np.where(values > 0, values, np.nan))
    return out


def hours(ms: FloatArray | float) -> FloatArray:
    out: FloatArray = np.asarray(ms, dtype=np.float64) / MS_PER_HOUR
    return out
