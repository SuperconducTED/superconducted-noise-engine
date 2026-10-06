"""Aliases, constants, placeholders and schema facts of the single-qubit gate fields.

Writes ``results/gates_1q/aliases_and_schema.json``:

- how the ``id``, ``rx``, ``x`` and ``xslow`` error records relate to ``sx`` record by record
  (values, stamps, and where the stamps differ), and whether their re-measurement events are
  identical once placeholders are masked;
- the stamp resolution of placeholder and measured records, and how long after the document's
  ``last_update_date`` a placeholder is stamped;
- every placeholder episode of ``sx`` and ``xslow``;
- the gate lengths and ``rz`` constants;
- when ``xslow`` is present, against the target operation set, ``basis_gates`` and the
  configuration's gate list; whether ``rx`` appears in any of those.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ddload
import g1common as g
from scripts.feature_patterns import events as fp_events  # on sys.path via ddload

SCRIPT = "analysis/gates_1q/aliases_and_schema.py"
ALIASES = ("id", "rx", "x", "xslow")


def runs(idx: np.ndarray) -> list[tuple[int, int]]:
    """Contiguous runs of sorted file indices, as (first, last) pairs."""
    if idx.size == 0:
        return []
    br = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate([[idx[0]], idx[br + 1]])
    ends = np.concatenate([idx[br], [idx[-1]]])
    return [(int(a), int(b)) for a, b in zip(starts, ends, strict=True)]


def placeholder_episodes(dd: ddload.DD, field: str) -> dict[str, Any]:
    v = np.array(dd.v(field))
    ph = v >= 1.0
    out: dict[str, Any] = {}
    for e in np.flatnonzero(ph.any(axis=0)):
        files = np.flatnonzero(ph[:, e])
        present = np.flatnonzero(np.isfinite(v[:, e]))
        rr = runs(files)
        out[f"q{int(e)}"] = {
            "placeholder_records": int(files.size),
            "present_records": int(present.size),
            "always_placeholder_in_lifetime": bool(files.size == present.size),
            "first_file": dd.stems[files[0]],
            "last_file": dd.stems[files[-1]],
            "episodes": len(rr),
            "episodes_detail": [
                {"first": dd.stems[a], "last": dd.stems[b], "files": b - a + 1} for a, b in rr
            ],
        }
    return out


def alias_checks(dd: ddload.DD) -> dict[str, Any]:
    sxv = np.array(dd.v(g.SX_FIELD))
    sxd = np.array(dd.d(g.SX_FIELD))
    ph = sxv >= 1.0
    sx_series = ddload.series(dd, g.SX_FIELD, rule=ddload.MEASURED, mask=ddload.placeholder_error)
    sx_by = {s.entity: s for s in sx_series}
    out: dict[str, Any] = {}
    for a in ALIASES:
        field = f"g1.{a}.gate_error"
        av = np.array(dd.v(field))
        ad = np.array(dd.d(field))
        both = np.isfinite(av) & np.isfinite(sxv)
        dmis = both & (ad != sxd)
        offs = (ad[dmis] - sxd[dmis]).astype(np.int64)
        cnt = Counter(offs.tolist())
        a_series = ddload.series(dd, field, rule=ddload.MEASURED, mask=ddload.placeholder_error)
        ref_by = sx_by
        if a == "xslow":
            # xslow exists only in some files: compare with sx restricted to those files
            keep = np.isfinite(av)
            rv = np.where(keep & ~ph, sxv, np.nan)
            rd = np.where(keep & ~ph, sxd, np.nan)
            ref_by = {s.entity: s for s in fp_events(rv, rd, mask_placeholder=False)[0]}
        identical = 0
        for s in a_series:
            r = ref_by.get(s.entity)
            if (
                r is not None
                and r.y.size == s.y.size
                and np.array_equal(r.y, s.y)
                and np.array_equal(r.t_ms, s.t_ms)
                and np.array_equal(r.file_idx, s.file_idx)
            ):
                identical += 1
        out[a] = {
            "compared": int(both.sum()),
            "value_mismatch": int(np.sum(both & (av != sxv))),
            "date_mismatch": int(dmis.sum()),
            "date_mismatch_in_placeholder_records": int(np.sum(dmis & ph)),
            "date_mismatch_outside_placeholder_records": int(np.sum(dmis & ~ph)),
            "placeholder_records_compared": int(np.sum(both & ph)),
            "date_mismatch_share_of_placeholder_records": g.rnd(
                float(np.sum(dmis & ph)) / max(1, int(np.sum(both & ph))), 4
            ),
            "offset_alias_minus_sx_ms_counts": {str(k): int(v) for k, v in sorted(cnt.items())},
            "qubits_with_date_mismatch": sorted({int(e) for e in np.nonzero(dmis)[1]}),
            "series_after_masking": len(a_series),
            "series_identical_to_sx_after_masking": identical,
        }
    out["sx_series_after_masking"] = len(sx_series)
    out["sx_events_after_masking"] = int(sum(s.y.size for s in sx_series))
    return out


def stamp_facts(dd: ddload.DD) -> dict[str, Any]:
    sxv = np.array(dd.v(g.SX_FIELD))
    sxd = np.array(dd.d(g.SX_FIELD))
    fm = dd.file_ms
    ph = sxv >= 1.0
    real = np.isfinite(sxv) & ~ph
    fi = np.nonzero(ph)[0]
    lag_s = (sxd[ph] - fm[fi]) / 1000.0
    fr = np.nonzero(real)[0]
    return {
        "placeholder_records": int(ph.sum()),
        "placeholder_stamp_whole_second_share": g.rnd(float(np.mean(sxd[ph] % 1000 == 0)), 6),
        "measured_records": int(real.sum()),
        "measured_stamp_whole_second_share": g.rnd(float(np.mean(sxd[real] % 1000 == 0)), 6),
        "placeholder_stamp_after_file_date_s_q_0_1_10_50_90_99_100": g.q(lag_s, nd=1),
        "placeholder_stamp_after_file_date_count": int(np.sum(lag_s > 0)),
        "measured_stamp_after_file_date_count": int(np.sum(sxd[real] > fm[fr])),
        "measured_stamp_age_at_file_h_q_0_1_10_50_90_99_100": g.q(
            (fm[fr] - sxd[real]) / g.HOUR_MS, nd=3
        ),
    }


def constants(dd: ddload.DD) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in (
        "g1.sx.gate_length",
        "g1.x.gate_length",
        "g1.id.gate_length",
        "g1.rx.gate_length",
        "g1.xslow.gate_length",
        "g1.rz.gate_length",
        "g1.rz.gate_error",
    ):
        v = np.array(dd.v(f))
        fin = v[np.isfinite(v)]
        out[f] = {"records": int(fin.size), "unique_values": sorted(set(fin.tolist()))}
    return out


def xslow_schema(dd: ddload.DD) -> dict[str, Any]:
    xv = np.array(dd.v("g1.xslow.gate_error"))
    n_present = np.isfinite(xv).sum(axis=1)
    pres = n_present > 0
    tgt = dd.file("target_ops_id")
    hc = dd.file("has_configuration").astype(bool)
    bg = dd.file("config.basis_gates")
    meta = dd.meta
    target_has_xslow = {
        int(ts["id"]): not any(op[0] == "xslow" for op in ts["missing_from_union"])
        for ts in meta["target_sets"]
    }
    t_x = np.array([target_has_xslow[int(t)] for t in tgt])
    rr = runs(np.flatnonzero(pres))
    table = Counter(
        zip(pres.tolist(), t_x.tolist(), hc.tolist(), bg.tolist(), strict=True),
    )
    mismatch = np.flatnonzero(~pres & t_x)
    first_live_props = np.flatnonzero(pres & hc)
    second_run_start = rr[1][0] if len(rr) > 1 else dd.n_files
    live_second = np.flatnonzero(pres & hc & (np.arange(dd.n_files) >= second_run_start))
    bg_ids = {
        int(v["id"]): {
            "first": v["first"],
            "last": v["last"],
            "files": v["files"],
            "value": v["value"],
        }
        for v in meta["config_values"]["basis_gates"].values()
    }
    bg_x = [i for i, v in bg_ids.items() if "xslow" in str(v["value"])]
    first_bg_x = np.flatnonzero(np.isin(bg, bg_x))
    gate_versions = []
    for v in meta["config_values"]["gates"].values():
        names = [gg.get("name") for gg in v["value"]]
        xs = [gg for gg in v["value"] if gg.get("name") == "xslow"]
        gate_versions.append(
            {
                "id": v["id"],
                "first": v["first"],
                "last": v["last"],
                "files": v["files"],
                "names": names,
                "xslow_qasm_def": xs[0].get("qasm_def") if xs else None,
            }
        )
    return {
        "present_for_all_or_none": bool(np.all((n_present == 0) | (n_present == 156))),
        "files_present": int(pres.sum()),
        "presence_runs": [
            {"first": dd.stems[a], "last": dd.stems[b], "files": int(pres[a : b + 1].sum())}
            for a, b in rr
        ],
        "file_after_first_run": dd.stems[rr[0][1] + 1] if rr else None,
        "files_by_present_targetHasXslow_hasConfiguration_basisId": [
            {
                "xslow_records_present": k[0],
                "target_has_xslow": k[1],
                "has_configuration": k[2],
                "basis_gates_id": k[3],
                "files": v,
            }
            for k, v in sorted(table.items(), key=lambda kv: str(kv[0]))
        ],
        "target_has_xslow_but_no_records": {
            "files": int(mismatch.size),
            "historical_fetches_among_them": int(np.sum(~hc[mismatch])),
            "first": dd.stems[mismatch[0]] if mismatch.size else None,
            "last": dd.stems[mismatch[-1]] if mismatch.size else None,
        },
        "first_live_file_with_xslow_records": dd.stems[first_live_props[0]]
        if first_live_props.size
        else None,
        "first_live_file_with_xslow_records_in_second_run": dd.stems[live_second[0]]
        if live_second.size
        else None,
        "second_run_first_file_is_historical": bool(len(rr) > 1 and not hc[rr[1][0]]),
        "first_file_with_basis_gates_containing_xslow": dd.stems[first_bg_x[0]]
        if first_bg_x.size
        else None,
        "basis_gates_versions": bg_ids,
        "configuration_gate_versions": gate_versions,
        "target_set_has_xslow": {str(k): v for k, v in target_has_xslow.items()},
    }


def rx_schema(dd: ddload.DD) -> dict[str, Any]:
    meta = dd.meta
    union_names = Counter(op[0] for op in meta["target_union"])
    cv = meta["config_values"]

    def any_has(key: str, name: str) -> bool:
        for v in cv[key].values():
            val = v["value"]
            if isinstance(val, list):
                for item in val:
                    if (isinstance(item, dict) and item.get("name") == name) or item == name:
                        return True
            elif f"'{name}'" in str(val) or f'"{name}"' in str(val):
                return True
        return False

    return {
        "target_union_ops_by_name": dict(sorted(union_names.items())),
        "rx_in_target_union": union_names.get("rx", 0) > 0,
        "rx_in_any_basis_gates": any_has("basis_gates", "rx"),
        "rx_in_any_configuration_gates": any_has("gates", "rx"),
        "rx_in_any_supported_instructions": any_has("supported_instructions", "rx"),
        "rx_records_in_properties": int(np.isfinite(np.array(dd.v("g1.rx.gate_error"))).sum()),
    }


def main() -> int:
    dd = ddload.DD()
    payload: dict[str, Any] = ddload.result_header(g.SCOPE, SCRIPT)
    payload["n_files"] = dd.n_files
    payload["aliases"] = alias_checks(dd)
    payload["stamps"] = stamp_facts(dd)
    payload["placeholders"] = {
        "sx": placeholder_episodes(dd, g.SX_FIELD),
        "xslow": placeholder_episodes(dd, "g1.xslow.gate_error"),
    }
    payload["constants"] = constants(dd)
    payload["xslow"] = xslow_schema(dd)
    payload["rx"] = rx_schema(dd)
    ddload.write_json(g.RESULTS / "aliases_and_schema.json", payload)
    print("wrote", g.RESULTS / "aliases_and_schema.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
