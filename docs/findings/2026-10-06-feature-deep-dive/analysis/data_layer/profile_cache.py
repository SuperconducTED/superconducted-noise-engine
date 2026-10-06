"""Mechanical profile of every field in the cache: coverage, values, date semantics, events.

Writes ``results/data-layer/profile.json``; ``01-data-layer.md`` is written from it.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload

OUT = Path(__file__).resolve().parents[2] / "results" / "data-layer" / "profile.json"
QS = (0.0, 0.01, 0.1, 0.5, 0.9, 0.99, 1.0)


def quantiles(x: np.ndarray) -> list[float] | None:
    x = x[np.isfinite(x)]
    return [float(f"{v:.6g}") for v in np.quantile(x, QS)] if x.size else None


def field_profile(dd: ddload.DD, field: str) -> dict[str, Any]:
    v = np.array(dd.v(field), dtype=np.float64)
    d = np.array(dd.d(field), dtype=np.float64)
    fms = dd.file_ms[:, None]
    present = np.isfinite(v) | np.isfinite(d)
    rows = np.flatnonzero(present.any(axis=1))
    finite = v[np.isfinite(v)]
    dated = np.isfinite(d)
    same = (d == fms) & dated
    out: dict[str, Any] = {
        "width": int(v.shape[1]),
        "records": int(present.sum()),
        "files_with_any": int(rows.size),
        "first_file": dd.stems[int(rows[0])] if rows.size else None,
        "last_file": dd.stems[int(rows[-1])] if rows.size else None,
        "files_full_width": int(np.sum(present.all(axis=1))),
        "entities_never_present": int(np.sum(~present.any(axis=0))),
        "units": dd.meta["fields"][field]["units"],
        "distinct_values": int(np.unique(finite).size),
        "quantiles_0_1_10_50_90_99_100": quantiles(finite),
        "n_value_ge_1": int(np.sum(finite >= 1.0)),
        "n_value_eq_0": int(np.sum(finite == 0.0)),
        "n_value_lt_0": int(np.sum(finite < 0.0)),
        "date_equals_file_date_share": float(f"{same.sum() / max(dated.sum(), 1):.6f}"),
        "date_after_file_date": int(np.sum((d > fms) & dated)),
        "entity_age_h_median": float(f"{np.nanmedian((fms - d)[dated]) / ddload.MS_PER_HOUR:.4g}")
        if dated.any()
        else None,
    }
    if rows.size:
        # Coverage within the field's own lifetime, so a late schema start is not missingness.
        life = present[rows[0] : rows[-1] + 1]
        out["present_share_within_lifetime"] = float(f"{life.mean():.6f}")
        per_entity = life.mean(axis=0)
        out["entities_partially_present"] = int(np.sum((per_entity > 0) & (per_entity < 1)))
    rule = ddload.ASSEMBLY if out["date_equals_file_date_share"] > 0.99 else ddload.MEASURED
    out["event_rule"] = rule
    mask = ddload.placeholder_error if field.endswith("gate_error") else None
    ser = ddload.series(dd, field, rule=rule, mask=mask)
    n_events = np.array([s.y.size for s in ser], dtype=np.float64)
    gaps = np.concatenate([np.diff(s.t_ms) for s in ser if s.y.size > 1] or [np.array([])])
    out["events_per_entity_q"] = quantiles(n_events)
    out["event_gap_h_q"] = quantiles(gaps / ddload.MS_PER_HOUR)
    if mask is not None:
        ph = v >= 1.0
        out["placeholder_records"] = int(ph.sum())
        out["entities_ever_placeholder"] = int(np.sum(ph.any(axis=0)))
        if rows.size:
            alive = ph[rows[0] : rows[-1] + 1]
            out["entities_always_placeholder"] = [
                dd.entities(field)[k] for k in np.flatnonzero(alive.all(axis=0))
            ]
    if field in ("gen.jq", "gen.zz"):
        z = v == 0.0
        out["entities_ever_zero"] = int(np.sum(z.any(axis=0)))
        out["entities_always_zero"] = [dd.entities(field)[k] for k in np.flatnonzero(z.all(axis=0))]
    if rule == ddload.ASSEMBLY:
        both = np.isfinite(v[1:]) & np.isfinite(v[:-1])
        changes = np.sum((np.diff(v, axis=0) != 0) & both, axis=0)
        out["value_changes_per_entity_q"] = quantiles(changes.astype(np.float64))
    return out


def main() -> int:
    dd = ddload.DD()
    meta = dd.meta
    fields = {f: field_profile(dd, f) for f in dd.fields()}
    has_conf = dd.file("has_configuration").astype(bool)
    fms = dd.file_ms
    ts = dd.file("timestamp_ms").astype(np.float64)
    lag_h = (ts - fms) / ddload.MS_PER_HOUR
    config = {}
    for key, store in meta["config_values"].items():
        config[key] = {
            "distinct": len(store),
            "values": [
                {
                    "id": e["id"],
                    "first": e["first"],
                    "last": e["last"],
                    "files": e["files"],
                    "chars": e["chars"],
                    "value": e["value"] if e["chars"] <= 200 else "(long; see meta.json)",
                }
                for e in store.values()
            ],
        }
    state = dd.file("state_id")
    per_state = Counter(int(s) for s in state if s >= 0)
    chain_ids = np.load(dd.path / "gen.lf_chain__v.npy")
    lf_names = meta["lf_names"]
    chains_per_name = {
        nm: int(np.unique(chain_ids[:, k][chain_ids[:, k] >= 0]).size)
        for k, nm in enumerate(lf_names)
    }
    lengths = Counter(len(c) for c in meta["lf_chains"])
    ledger = Counter(r.get("decision", "") for r in meta["ledger"])
    files = {
        "n_files": dd.n_files,
        "first": dd.stems[0],
        "last": dd.stems[-1],
        "has_configuration": int(has_conf.sum()),
        "no_configuration": int((~has_conf).sum()),
        "timestamp_minus_last_update_h_live_q": quantiles(lag_h[has_conf]),
        "timestamp_minus_last_update_h_historical_q": quantiles(lag_h[~has_conf]),
        "backend_versions": meta["backend_versions"],
        "schema_versions": meta["schema_versions"],
        "top_level_keys": meta["top_level_keys"],
        "target_sets": [
            {
                "id": t["id"],
                "n_ops": t["n_ops"],
                "files": int(np.sum(dd.file("target_ops_id") == t["id"])),
                "missing_from_union": t["missing_from_union"][:40],
                "missing_count": len(t["missing_from_union"]),
            }
            for t in meta["target_sets"]
        ],
        "target_union_size": len(meta["target_union"]),
        "distinct_states": len(per_state),
        "files_without_state_row": int(np.sum(state < 0)),
        "files_per_state_q": quantiles(np.array(list(per_state.values()), dtype=np.float64)),
        "state_index_rows": meta["state_index_rows"],
        "ledger_rows": len(meta["ledger"]),
        "ledger_decisions": dict(ledger),
        "collisions": meta["collisions"],
        "lf_names": len(lf_names),
        "lf_chain_lengths": dict(sorted(lengths.items())),
        "lf_distinct_chains": len(meta["lf_chains"]),
        "lf_chains_per_name_q": quantiles(np.array(list(chains_per_name.values()), dtype=float)),
        "couplers": len(meta["couplers"]),
        "directed_edges": len(meta["directed_edges"]),
        "coupling_map_directed": len(meta["coupling_map"]),
        "checks": meta["checks"],
        "extract_seconds": meta["seconds"],
    }
    payload = {
        **ddload.result_header("data-layer", "analysis/data_layer/profile_cache.py"),
        "n_files": dd.n_files,
        "files": files,
        "config": config,
        "fields": fields,
    }
    ddload.write_json(OUT, payload)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
