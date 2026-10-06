"""Tallies and ratios over the other cross-scope results, so that every count in the document
traces to a field.

Reads only ``results/cross/*.json`` (never the cache); run it after the six analysis scripts.
For each test it lists the pairs that survive Benjamini-Hochberg at 0.05 (in this scope's
family of 23 pairs or 45/44 scorable directions), their number, the largest effect, and where
a period split exists, whether the surviving effects keep their direction in both periods.
It also divides each family's device-to-entity semivariance ratio at the shortest lag by the
``pi / (2N)`` that independent entity components would give (``common_mode.json``).

Writes ``results/cross/summary.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import xcommon as xc

OUT = xc.RESULTS / "summary.json"
SOURCES = ("alignment", "levels", "comovement", "common_mode", "leadlag", "coincidence")


def load(name: str) -> dict[str, Any]:
    out: dict[str, Any] = json.loads((xc.RESULTS / f"{name}.json").read_text(encoding="utf-8"))
    return out


def label(a: str, b: str) -> str:
    return f"{a}-{b}"


def comovement(cm: dict[str, Any]) -> dict[str, Any]:
    mine = [p for p in cm["pairs"] if not p["control"]]
    out: dict[str, Any] = {"pairs_tested": len(mine)}
    for lab in ("raw", "cm_removed"):
        surv = [p for p in mine if p[lab].get("r_bh_reject_q05")]
        surv_mi = [p for p in mine if p[lab].get("mi_bh_reject_q05")]
        big = max(mine, key=lambda p: abs(p[lab]["r"]) if p[lab]["r"] is not None else -1.0)
        both = [
            p for p in surv if p[lab]["n_before_2026_08_01"] > 0 and p[lab]["n_from_2026_08_01"] > 0
        ]
        same = [
            p
            for p in both
            if (p[lab]["r_before_2026_08_01"] > 0) == (p[lab]["r_from_2026_08_01"] > 0)
        ]
        out[lab] = {
            "r_bh_survivors": [label(p["anchor"], p["other"]) for p in surv],
            "n_r_bh_survivors": len(surv),
            "mi_bh_survivors": [label(p["anchor"], p["other"]) for p in surv_mi],
            "n_mi_bh_survivors": len(surv_mi),
            "max_abs_r": big[lab]["r"],
            "max_abs_r_pair": label(big["anchor"], big["other"]),
            "survivors_with_both_periods": len(both),
            "survivors_same_sign_both_periods": len(same),
        }
    shortest: dict[str, Any] = {}
    for p in cm["pairs"]:
        cell = next((c for c in p["by_gap"] if "raw" in c), None)
        if cell is not None:
            shortest[label(p["anchor"], p["other"])] = {
                "gap_h_lo": cell["gap_h_lo"],
                "gap_h_hi": cell["gap_h_hi"],
                "pairs": cell["pairs_used"],
                "r_raw": cell["raw"]["r"],
                "p_shift_raw": cell["raw"]["p_shift"],
                "r_cm_removed": cell["cm_removed"]["r"],
                "p_shift_cm_removed": cell["cm_removed"]["p_shift"],
                "control": bool(p["control"]),
            }
    out["shortest_populated_gap_bin"] = shortest
    scope = {k: v for k, v in shortest.items() if not v["control"] and "zz" not in k}
    for lab in ("raw", "cm_removed"):
        sig = [
            k
            for k, v in scope.items()
            if v[f"p_shift_{lab}"] is not None and v[f"p_shift_{lab}"] < 0.05
        ]
        out[f"shortest_bin_p_below_0_05_uncorrected_excluding_zz_{lab}"] = sig
        top = max(scope, key=lambda k: abs(scope[k][f"r_{lab}"]))
        out[f"shortest_bin_max_abs_r_excluding_zz_{lab}"] = scope[top][f"r_{lab}"]
        out[f"shortest_bin_max_abs_r_excluding_zz_{lab}_pair"] = top
    return out


def levels(lv: dict[str, Any]) -> dict[str, Any]:
    mine = [p for p in lv["pairs"] if p["owner"] == "07"]
    big = max(mine, key=lambda p: abs(p["spearman"]))
    out: dict[str, Any] = {
        "pairs_tested": len(mine),
        "n_spearman_bh_survivors": sum(bool(p["bh_reject_q05"]) for p in mine),
        "min_spearman_bh_q": min(p["bh_q"] for p in mine),
        "n_mi_bh_survivors": sum(bool(p["mi_bh_reject_q05"]) for p in mine),
        "max_abs_spearman": big["spearman"],
        "max_abs_spearman_pair": label(big["a"], big["b"]),
        "n_ci95_excluding_zero": sum(
            (p["spearman_ci95"][0] > 0) or (p["spearman_ci95"][1] < 0) for p in mine
        ),
        "ci95_lowest_lower": min(p["spearman_ci95"][0] for p in mine),
        "ci95_highest_upper": max(p["spearman_ci95"][1] for p in mine),
        "max_mi_excess_over_null": max(p["mi_excess_over_null"] for p in mine),
        "min_mi_p_perm": min(p["mi_p_perm"] for p in mine),
    }
    partial: dict[str, Any] = {}
    for name, m in lv["multivariate"].items():
        rows = [r for r in m["partial_correlations"] if r["owner"] == "07"]
        partial[name] = {
            "pairs_tested": len(rows),
            "n_bh_survivors": sum(bool(r["bh_reject_q05"]) for r in rows),
            "min_bh_q": min(r["bh_q"] for r in rows),
        }
    out["partial_correlations"] = partial
    return out


def leadlag(ll: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for model in ("lag1_all", "lags123_linear", "strict_all"):
        scored = [r for r in ll["pairs"] if r[model].get("ratio") is not None]
        lo = min(scored, key=lambda r: r[model]["ratio"])
        hi = max(scored, key=lambda r: r[model]["ratio"])
        minp = min(scored, key=lambda r: r[model]["wilcoxon_p_greater"])
        out[model] = {
            "directions_scored": len(scored),
            "n_bh_survivors": sum(bool(r[model].get("bh_reject_q05")) for r in scored),
            "min_ratio": lo[model]["ratio"],
            "min_ratio_direction": f"{lo['predictor']}->{lo['target']}",
            "max_ratio": hi[model]["ratio"],
            "max_ratio_direction": f"{hi['predictor']}->{hi['target']}",
            "n_ci95_entirely_below_1": sum(r[model]["ratio_ci95"][1] < 1.0 for r in scored),
            "n_ci95_entirely_above_1": sum(r[model]["ratio_ci95"][0] > 1.0 for r in scored),
            "min_wilcoxon_p": minp[model]["wilcoxon_p_greater"],
            "min_wilcoxon_p_direction": f"{minp['predictor']}->{minp['target']}",
            "max_abs_test_spearman_lag1": max(abs(r["test_spearman_lag1"]) for r in scored),
        }
    return out


def coincidence(co: dict[str, Any]) -> dict[str, Any]:
    mine = [p for p in co["pairs"] if not p["control"]]
    out: dict[str, Any] = {"pairs_tested": len(mine)}
    for key in ("big_lag0", "adv_lag0", "big_lag1", "adv_lag1"):
        row: dict[str, Any] = {}
        for null in ("time", "qubit"):
            surv = [p for p in mine if p[key].get(f"bh_{null}_reject_q05")]
            row[f"{null}_bh_survivors"] = [label(p["a"], p["b"]) for p in surv]
            row[f"n_{null}_bh_survivors"] = len(surv)
        surv_q = [p for p in mine if p[key].get("bh_qubit_reject_q05")]
        both = [p for p in surv_q if p[key]["both_flagged_before_2026_08_01"] > 0]
        above = [
            p
            for p in both
            if (p[key]["lift_time_before_2026_08_01"] or 0) > 1
            and (p[key]["lift_time_from_2026_08_01"] or 0) > 1
        ]
        row["qubit_survivors_with_early_coincidences"] = len(both)
        row["of_which_lift_time_above_1_in_both_periods"] = len(above)
        out[key] = row
    return out


def common_mode(cmj: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    dd_pairs = [r for r in cmj["device_daily"]["pairs"] if r.get("spearman") is not None]
    out["device_daily_bh_survivors"] = [
        label(r["a"], r["b"]) for r in dd_pairs if r.get("bh_reject_q05")
    ]
    out["device_daily_pairs_tested"] = len(dd_pairs)
    cmx: dict[str, Any] = {}
    for lab, m in cmj["change_matrix"].items():
        mine = [r for r in m["pairs"] if r["owner"] == "07"]
        surv = [r for r in mine if r.get("bh_reject_q05")]
        big = max(mine, key=lambda r: abs(r["r"]))
        cmx[lab] = {
            "pairs_tested": len(mine),
            "bh_survivors": [label(r["a"], r["b"]) for r in surv],
            "n_bh_survivors": len(surv),
            "max_abs_r": big["r"],
            "max_abs_r_pair": label(big["a"], big["b"]),
            "components_exceeding_null": sum(bool(c["exceeds_null"]) for c in m["pca"]),
            "components_reported": len(m["pca"]),
        }
    out["change_matrix"] = cmx
    vg: dict[str, Any] = {}
    for f, v in cmj["variograms"].items():
        short = v["matched_bins"]["shortest"]
        long = v["matched_bins"]["long"]
        pred = v["independent_noise_prediction_pi_over_2N"]
        ratio = short["device_to_entity_ratio"] if short else None
        vg[f] = {
            "shortest_bin_h": [short["lag_h_lo"], short["lag_h_hi"]] if short else None,
            "shortest_device_pairs": short["device_pairs"] if short else None,
            "shortest_device_to_entity_ratio": ratio,
            "independent_prediction_pi_over_2N": pred,
            "shortest_ratio_over_prediction": (
                xc.r6(ratio / pred) if ratio is not None and pred else None
            ),
            "long_device_to_entity_ratio": long["device_to_entity_ratio"] if long else None,
            "long_ratio_over_prediction": (
                xc.r6(long["device_to_entity_ratio"] / pred) if long and pred else None
            ),
        }
    out["variogram_vs_independence"] = vg
    return out


def main() -> int:
    data = {name: load(name) for name in SOURCES}
    payload: dict[str, Any] = ddload.result_header(xc.SCOPE, "analysis/cross/summary.py")
    payload["inputs_measured_utc"] = {k: v["measured_utc"] for k, v in data.items()}
    payload["comovement"] = comovement(data["comovement"])
    payload["levels"] = levels(data["levels"])
    payload["leadlag"] = leadlag(data["leadlag"])
    payload["coincidence"] = coincidence(data["coincidence"])
    payload["common_mode"] = common_mode(data["common_mode"])
    ddload.write_json(OUT, payload)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
