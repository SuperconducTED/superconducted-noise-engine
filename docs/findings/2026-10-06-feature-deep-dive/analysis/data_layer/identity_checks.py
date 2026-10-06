"""Re-check, at the pinned ref, the identities every scope relies on, and digest the cache.

Writes ``results/data-layer/identities.json``. The checks compare values AND dates record by
record over every file, so a later reader can see exactly which duplicates were collapsed.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload

OUT = Path(__file__).resolve().parents[2] / "results" / "data-layer" / "identities.json"


def compare(dd: ddload.DD, a: str, b: str, ia: Any = None, ib: Any = None) -> dict[str, int]:
    va, vb = np.array(dd.v(a)), np.array(dd.v(b))
    da, db = np.array(dd.d(a)), np.array(dd.d(b))
    if ia is not None:
        va, vb, da, db = va[:, ia], vb[:, ib], da[:, ia], db[:, ib]
    both = np.isfinite(va) & np.isfinite(vb)
    return {
        "compared": int(both.sum()),
        "value_mismatch": int(np.sum((va != vb) & both)),
        "date_mismatch": int(np.sum((da != db) & both)),
        "only_left": int(np.sum(np.isfinite(va) & ~np.isfinite(vb))),
        "only_right": int(np.sum(~np.isfinite(va) & np.isfinite(vb))),
    }


def main() -> int:
    dd = ddload.DD()
    checks: dict[str, Any] = {}
    for alias in ("id", "rx", "x", "xslow"):
        checks[f"sx_vs_{alias}_error"] = compare(dd, "g1.sx.gate_error", f"g1.{alias}.gate_error")
    checks["readout_error_vs_measure_error"] = compare(
        dd, "q.readout_error", "g1.measure.gate_error"
    )
    checks["readout_length_vs_measure_length_values"] = compare(
        dd, "q.readout_length", "g1.measure.gate_length"
    )
    edges = [tuple(e) for e in dd.entities("g2.cz.gate_error")]
    pos = {e: k for k, e in enumerate(edges)}
    fwd = [k for k, (a, b) in enumerate(edges) if a < b and (b, a) in pos]
    rev = [pos[(edges[k][1], edges[k][0])] for k in fwd]
    for gate in ("cz", "rzz"):
        for param in ("gate_error", "gate_length"):
            f = f"g2.{gate}.{param}"
            checks[f"{gate}_{param}_direction"] = compare(dd, f, f, fwd, rev)
    checks["cz_vs_rzz_error_same_coupler"] = compare(dd, "g2.cz.gate_error", "g2.rzz.gate_error")
    # readout_error = (p01 + p10) / 2 when all three carry the same stamp.
    ro = np.array(dd.v("q.readout_error"))
    p01, p10 = np.array(dd.v("q.prob_meas1_prep0")), np.array(dd.v("q.prob_meas0_prep1"))
    d_ro, d01, d10 = (
        np.array(dd.d(f)) for f in ("q.readout_error", "q.prob_meas1_prep0", "q.prob_meas0_prep1")
    )
    same = (d_ro == d01) & (d_ro == d10) & np.isfinite(ro)
    resid = np.abs(ro - (p01 + p10) / 2)
    checks["readout_is_mean_of_p01_p10"] = {
        "same_stamp_records": int(same.sum()),
        "abs_residual_le_1e-12": int(np.sum((resid <= 1e-12) & same)),
        "records_total": int(np.isfinite(ro).sum()),
    }
    grid = np.concatenate([p01[np.isfinite(p01)], p10[np.isfinite(p10)]]) * 4096
    checks["p01_p10_on_1_over_4096_grid"] = {
        "values": int(grid.size),
        "off_grid": int(np.sum(np.abs(grid - np.round(grid)) > 1e-6)),
    }
    h = hashlib.sha256()
    names = sorted(p.name for p in dd.path.glob("*.npy"))
    for name in names:
        h.update(name.encode("utf-8"))
        h.update((dd.path / name).read_bytes())
    payload = {
        **ddload.result_header("data-layer", "analysis/data_layer/identity_checks.py"),
        "n_files": dd.n_files,
        "checks": checks,
        "cache_npy_files": len(names),
        "cache_npy_sha256": h.hexdigest(),
    }
    ddload.write_json(OUT, payload)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
