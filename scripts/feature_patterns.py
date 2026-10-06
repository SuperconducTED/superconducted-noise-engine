"""Feature patterns of the calibration archive for the two forecasting targets (Issue #110).

Two targets share this analysis (lead's decision of 2026-10-05, recorded as A9 in
``docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md``):

1. the gate errors themselves (``sx``, ``cz``, ``rzz``, ``measure``, ``measure_2``)
   at a later calibration round;
2. ADR-027's per-qubit ``(gamma, lambda)`` at a later state.

The script has two stages.

``extract`` reads every ``snapshots/<month>/<backend>/*.json`` blob at a pinned
``calibration-data`` ref through one ``git cat-file --batch`` process (the archive is
never checked out, the network is never touched) and writes a compact ``.npz`` cache:
for every file, every qubit and every coupler, each field's value and the date IBM
stamped on it.

``analyze`` reads that cache and writes a JSON report. Its unit is the
**re-measurement event**: for one series (one field on one qubit or coupler), an
event is a file where both the value and the stamped date differ from the series'
previous record. ``gate_error >= 1`` is IBM's "not calibrated" placeholder; its date
is re-stamped whenever a document is assembled, so placeholder records are masked
before any event is counted. Every figure the report carries is provisional until
re-run on the verification desktop.

Usage::

    python -m scripts.feature_patterns extract --repo <path> --ref <sha> --out cache.npz
    python -m scripts.feature_patterns analyze --cache cache.npz --out report.json
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]

N_QUBITS = 156
ONE_Q_ALIASES = ("id", "rx", "x", "xslow")
QUBIT_FIELDS = (
    "T1",
    "T2",
    "readout_error",
    "prob_meas0_prep1",
    "prob_meas1_prep0",
    "readout_length",
    "init_error",
)
QUBIT_GATES = ("sx", "measure", "measure_2")
EDGE_GATES = ("cz", "rzz")
PLACEHOLDER = 1.0
ROUND_GAP_HOURS = 0.25
WARMUP_EVENTS = 5
EWMA_ALPHAS = (0.1, 0.3, 0.5)


# --------------------------------------------------------------------------- extract


def _iso_ms(stamp: str) -> float:
    """Milliseconds since the epoch for an ISO-8601 stamp with an explicit offset."""
    return datetime.fromisoformat(stamp).timestamp() * 1000.0


def list_blobs(repo: Path, ref: str, backend: str) -> list[tuple[str, str]]:
    """``(path, blob sha)`` of every snapshot of ``backend`` at ``ref``, in stem order."""
    out = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", ref, "--", "snapshots"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    rows: list[tuple[str, str]] = []
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        parts = path.split("/")
        if len(parts) == 4 and parts[2] == backend and path.endswith(".json"):
            rows.append((path, meta.split()[2]))
    rows.sort(key=lambda row: row[0].rsplit("/", 1)[1])
    return rows


def iter_blobs(repo: Path, shas: Sequence[str]) -> Iterator[bytes]:
    """Yield blob contents in order through one ``git cat-file --batch`` process.

    One request is written and its answer read before the next, so neither pipe can
    fill while the other side waits on it.
    """
    proc = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    assert proc.stdin is not None and proc.stdout is not None
    for sha in shas:
        proc.stdin.write(f"{sha}\n".encode("ascii"))
        proc.stdin.flush()
        header = proc.stdout.readline().decode("ascii").split()
        if len(header) != 3 or header[1] != "blob":
            raise RuntimeError(f"git cat-file: no blob for {sha}: {header}")
        body = proc.stdout.read(int(header[2]))
        proc.stdout.read(1)
        yield body
    proc.stdin.close()
    proc.wait()


@dataclass
class Cache:
    """Arrays of shape ``(n_files, n_entities)`` per field: value and stamped date."""

    stems: list[str]
    file_ms: FloatArray
    edges: list[tuple[int, int]]
    values: dict[str, FloatArray]
    dates: dict[str, FloatArray]
    checks: dict[str, int]
    inventory: dict[str, dict[str, Any]]


def _new(n_files: int, width: int) -> FloatArray:
    return np.full((n_files, width), np.nan, dtype=np.float64)


def extract(repo: Path, ref: str, backend: str, limit: int | None = None) -> Cache:
    """Read every snapshot blob at ``ref`` into per-field value and date arrays."""
    blobs = list_blobs(repo, ref, backend)[:limit]
    n = len(blobs)
    stems = [path.rsplit("/", 1)[1] for path, _ in blobs]
    file_ms = np.full(n, np.nan)
    edge_index: dict[tuple[int, int], int] = {}
    q_values = {f: _new(n, N_QUBITS) for f in (*QUBIT_FIELDS, *QUBIT_GATES, "sx_length")}
    q_dates = {f: _new(n, N_QUBITS) for f in (*QUBIT_FIELDS, *QUBIT_GATES)}
    raw_edges: dict[str, list[dict[tuple[int, int], tuple[float, float, float]]]] = {
        g: [] for g in EDGE_GATES
    }
    checks = {
        "alias_value_mismatch": 0,
        "alias_compared": 0,
        "edge_direction_value_mismatch": 0,
        "edge_direction_compared": 0,
        "unit_unexpected": 0,
    }
    inventory: dict[str, dict[str, Any]] = {}

    def seen(key: str, stem: str) -> None:
        entry = inventory.setdefault(key, {"files": 0, "first": stem, "last": stem})
        entry["files"] += 1
        entry["last"] = stem

    for i, body in enumerate(iter_blobs(repo, [sha for _, sha in blobs])):
        if i % 250 == 0:
            print(f"  {i}/{n}", file=sys.stderr, flush=True)
        doc = json.loads(body)
        props = doc["properties"]
        file_ms[i] = _iso_ms(props["last_update_date"])
        for q, records in enumerate(props.get("qubits") or []):
            for rec in records:
                name = rec.get("name")
                seen(f"qubit:{name}:{rec.get('unit', '')}", stems[i])
                if name in QUBIT_FIELDS and isinstance(rec.get("value"), (int, float)):
                    q_values[name][i, q] = float(rec["value"])
                    q_dates[name][i, q] = _iso_ms(rec["date"])
                    if name in ("T1", "T2") and rec.get("unit") != "us":
                        checks["unit_unexpected"] += 1
        alias: dict[int, dict[str, float]] = {}
        edges_here: dict[str, dict[tuple[int, int], tuple[float, float, float]]] = {
            g: {} for g in EDGE_GATES
        }
        for gate in props.get("gates") or []:
            kind, qubits = gate.get("gate"), gate.get("qubits") or []
            params = {p["name"]: p for p in gate.get("parameters") or []}
            for pname in params:
                seen(f"gate:{kind}:{pname}", stems[i])
            err = params.get("gate_error")
            if kind in QUBIT_GATES and len(qubits) == 1 and err is not None:
                q_values[kind][i, qubits[0]] = float(err["value"])
                q_dates[kind][i, qubits[0]] = _iso_ms(err["date"])
                if kind == "sx" and "gate_length" in params:
                    q_values["sx_length"][i, qubits[0]] = float(params["gate_length"]["value"])
            if kind in (*ONE_Q_ALIASES, "sx") and len(qubits) == 1 and err is not None:
                alias.setdefault(qubits[0], {})[kind] = float(err["value"])
            if kind in EDGE_GATES and len(qubits) == 2 and err is not None:
                length = params.get("gate_length", {}).get("value", math.nan)
                edges_here[kind][(qubits[0], qubits[1])] = (
                    float(err["value"]),
                    _iso_ms(err["date"]),
                    float(length),
                )
        for per_qubit in alias.values():
            if "sx" in per_qubit:
                for other in ONE_Q_ALIASES:
                    if other in per_qubit:
                        checks["alias_compared"] += 1
                        if per_qubit[other] != per_qubit["sx"]:
                            checks["alias_value_mismatch"] += 1
        for kind in EDGE_GATES:
            merged: dict[tuple[int, int], tuple[float, float, float]] = {}
            for (a, b), rec3 in edges_here[kind].items():
                key = (min(a, b), max(a, b))
                if key in merged:
                    checks["edge_direction_compared"] += 1
                    if merged[key][0] != rec3[0]:
                        checks["edge_direction_value_mismatch"] += 1
                    # keep the later stamp so a re-stamped placeholder never looks older
                    if rec3[1] > merged[key][1]:
                        merged[key] = rec3
                else:
                    merged[key] = rec3
                edge_index.setdefault(key, len(edge_index))
            raw_edges[kind].append(merged)
        for rec in props.get("general") or []:
            seen(f"general:{str(rec.get('name', '')).split('_')[0]}", stems[i])

    edges = sorted(edge_index)
    position = {e: k for k, e in enumerate(edges)}
    values: dict[str, FloatArray] = dict(q_values)
    dates: dict[str, FloatArray] = dict(q_dates)
    for kind in EDGE_GATES:
        vals, stamp, length = _new(n, len(edges)), _new(n, len(edges)), _new(n, len(edges))
        for i, merged in enumerate(raw_edges[kind]):
            for pair, (v, d, g) in merged.items():
                col = position[pair]
                vals[i, col], stamp[i, col], length[i, col] = v, d, g
        values[kind], dates[kind], values[f"{kind}_length"] = vals, stamp, length
    order = np.argsort(file_ms, kind="stable")
    for store in (values, dates):
        for name in store:
            store[name] = store[name][order]
    return Cache(
        stems=[stems[k] for k in order],
        file_ms=file_ms[order],
        edges=edges,
        values=values,
        dates=dates,
        checks=checks,
        inventory=inventory,
    )


def save_cache(cache: Cache, out: Path, ref: str) -> None:
    arrays: dict[str, Any] = {"file_ms": cache.file_ms, "edges": np.array(cache.edges)}
    arrays.update({f"v__{k}": v for k, v in cache.values.items()})
    arrays.update({f"d__{k}": v for k, v in cache.dates.items()})
    meta = {
        "ref": ref,
        "stems": cache.stems,
        "checks": cache.checks,
        "inventory": cache.inventory,
    }
    arrays["meta"] = np.array(json.dumps(meta))
    np.savez_compressed(out, **arrays)


def load_cache(path: Path) -> tuple[Cache, str]:
    with np.load(path) as data:
        meta = json.loads(str(data["meta"]))
        values = {k[3:]: data[k] for k in data.files if k.startswith("v__")}
        dates = {k[3:]: data[k] for k in data.files if k.startswith("d__")}
        cache = Cache(
            stems=meta["stems"],
            file_ms=data["file_ms"],
            edges=[(int(a), int(b)) for a, b in data["edges"]],
            values=values,
            dates=dates,
            checks=meta["checks"],
            inventory=meta["inventory"],
        )
    return cache, str(meta["ref"])


# --------------------------------------------------------------------------- analyze


@dataclass
class Series:
    """Re-measurement events of one entity, in time order (placeholders masked)."""

    entity: int
    t_ms: FloatArray  # stamped calibration date of each event
    file_idx: npt.NDArray[np.int64]  # first file carrying the event
    y: FloatArray  # value at each event


def events(
    values: FloatArray, dates: FloatArray, *, mask_placeholder: bool
) -> tuple[list[Series], dict[str, int]]:
    """Split each column into re-measurement events: value AND stamped date both new."""
    out: list[Series] = []
    counts = {"value_moved_date_kept": 0, "date_moved_value_kept": 0, "date_regressed": 0}
    for e in range(values.shape[1]):
        v, d = values[:, e], dates[:, e]
        ok = np.isfinite(v) & np.isfinite(d)
        if mask_placeholder:
            ok &= v < PLACEHOLDER
        idx = np.flatnonzero(ok)
        keep_t: list[float] = []
        keep_i: list[int] = []
        keep_y: list[float] = []
        last_v, last_d = math.nan, math.nan
        for i in idx:
            vi, di = float(v[i]), float(d[i])
            if not keep_y:
                keep_t, keep_i, keep_y = [di], [int(i)], [vi]
            elif vi != last_v and di != last_d:
                if di < last_d:
                    counts["date_regressed"] += 1
                keep_t.append(di)
                keep_i.append(int(i))
                keep_y.append(vi)
            elif vi != last_v:
                counts["value_moved_date_kept"] += 1
            elif di != last_d:
                counts["date_moved_value_kept"] += 1
            last_v, last_d = vi, di
        if keep_y:
            out.append(
                Series(
                    entity=e,
                    t_ms=np.array(keep_t),
                    file_idx=np.array(keep_i, dtype=np.int64),
                    y=np.array(keep_y),
                )
            )
    return out, counts


def _q(x: FloatArray, qs: Sequence[float] = (0.0, 0.1, 0.5, 0.9, 1.0)) -> list[float] | None:
    x = x[np.isfinite(x)]
    if x.size == 0:
        return None
    return [round(float(v), 6) for v in np.quantile(x, qs)]


def rounds(series: list[Series]) -> dict[str, Any]:
    """Cluster all event dates of a family into device-wide rounds (gap > 15 min splits)."""
    stamps = np.sort(np.concatenate([s.t_ms[1:] for s in series if s.t_ms.size > 1]))
    if stamps.size == 0:
        return {"n_rounds": 0}
    breaks = np.flatnonzero(np.diff(stamps) > ROUND_GAP_HOURS * 3.6e6)
    sizes = np.diff(np.concatenate([[0], breaks + 1, [stamps.size]]))
    starts = stamps[np.concatenate([[0], breaks + 1])]
    gaps_h = np.diff(starts) / 3.6e6
    return {
        "n_rounds": int(sizes.size),
        "entities_per_round_q": _q(sizes.astype(np.float64)),
        "rounds_with_ge_half_device": int(np.sum(sizes >= 0.5 * len(series))),
        "gap_between_rounds_h_q": _q(gaps_h),
    }


def memory(series: list[Series], transform: str = "log10") -> dict[str, Any]:
    """Temporal memory and one-step skill of simple forecasters, pooled over series.

    For every event k >= WARMUP_EVENTS the one-step forecast of ``z_k`` is scored by
    absolute error: persistence ``z_{k-1}``, the expanding mean of ``z_0..z_{k-1}``,
    and EWMA at each alpha. Skill is MAE relative to persistence (1.0 = persistence).
    """

    def tf(a: FloatArray) -> FloatArray:
        out: FloatArray = np.log10(a) if transform == "log10" else a
        return out

    err: dict[str, list[float]] = {"persistence": [], "expanding_mean": []}
    for a in EWMA_ALPHAS:
        err[f"ewma_{a}"] = []
    deltas: list[float] = []
    lag1_pairs: list[tuple[float, float]] = []
    gaps_h: list[float] = []
    for s in series:
        z = tf(s.y)
        if z.size < 2:
            continue
        dz = np.diff(z)
        deltas.extend(dz.tolist())
        gaps_h.extend((np.diff(s.t_ms) / 3.6e6).tolist())
        lag1_pairs.extend(zip(dz[:-1].tolist(), dz[1:].tolist(), strict=True))
        ew = {a: float(z[0]) for a in EWMA_ALPHAS}
        csum = 0.0
        for k in range(1, z.size):
            csum += float(z[k - 1])
            for a in EWMA_ALPHAS:
                ew[a] = a * float(z[k - 1]) + (1 - a) * ew[a] if k > 1 else float(z[0])
            if k >= WARMUP_EVENTS:
                target = float(z[k])
                err["persistence"].append(abs(target - float(z[k - 1])))
                err["expanding_mean"].append(abs(target - csum / k))
                for a in EWMA_ALPHAS:
                    err[f"ewma_{a}"].append(abs(target - ew[a]))
    d = np.array(deltas)
    pairs = np.array(lag1_pairs) if lag1_pairs else np.empty((0, 2))
    mae = {k: float(np.mean(v)) for k, v in err.items() if v}
    base = mae.get("persistence", math.nan)
    lag1 = float(np.corrcoef(pairs[:, 0], pairs[:, 1])[0, 1]) if len(pairs) > 2 else math.nan
    return {
        "n_series": len(series),
        "transitions": int(d.size),
        "events_per_series_q": _q(np.array([s.y.size for s in series], dtype=np.float64)),
        "gap_h_q": _q(np.array(gaps_h)),
        "abs_delta_q": _q(np.abs(d)),
        "share_factor2": float(np.mean(np.abs(d) > math.log10(2))) if d.size else math.nan,
        "lag1_autocorr_of_change": round(lag1, 4),
        "scored_events": len(err["persistence"]),
        "mae": {k: round(v, 5) for k, v in mae.items()},
        "skill_vs_persistence": {k: round(v / base, 4) for k, v in mae.items()},
    }


def coherence_limit_1q(t1_us: FloatArray, t2_us: FloatArray, t_ns: FloatArray) -> FloatArray:
    """Average gate infidelity of an idle of length ``t`` under T1 and T2 alone."""
    t = t_ns * 1e-3
    out: FloatArray = 1.0 - (3.0 + np.exp(-t / t1_us) + 2.0 * np.exp(-t / t2_us)) / 6.0
    return out


def process_fidelity_1q(t1_us: FloatArray, t2_us: FloatArray, t_ns: FloatArray) -> FloatArray:
    t = t_ns * 1e-3
    out: FloatArray = (1.0 + np.exp(-t / t1_us) + 2.0 * np.exp(-t / t2_us)) / 4.0
    return out


def _corr(x: FloatArray, y: FloatArray) -> float:
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3:
        return math.nan
    return round(float(np.corrcoef(x[ok], y[ok])[0, 1]), 4)


def _spearman(x: FloatArray, y: FloatArray) -> float:
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3:
        return math.nan
    rx = np.argsort(np.argsort(x[ok])).astype(np.float64)
    ry = np.argsort(np.argsort(y[ok])).astype(np.float64)
    return round(float(np.corrcoef(rx, ry)[0, 1]), 4)


def coherence_share(cache: Cache) -> dict[str, Any]:
    """How much of each gate error the T1/T2 limit explains, across and within qubits."""
    v = cache.values
    t1, t2 = v["T1"], v["T2"]
    sx = np.where(v["sx"] < PLACEHOLDER, v["sx"], np.nan)
    coh_sx = coherence_limit_1q(t1, t2, v["sx_length"])
    a = np.array([e[0] for e in cache.edges])
    b = np.array([e[1] for e in cache.edges])
    f2 = process_fidelity_1q(t1[:, a], t2[:, a], v["cz_length"]) * process_fidelity_1q(
        t1[:, b], t2[:, b], v["cz_length"]
    )
    coh_cz = 1.0 - (4.0 * f2 + 1.0) / 5.0
    f2r = process_fidelity_1q(t1[:, a], t2[:, a], v["rzz_length"]) * process_fidelity_1q(
        t1[:, b], t2[:, b], v["rzz_length"]
    )
    coh_rzz = 1.0 - (4.0 * f2r + 1.0) / 5.0
    cz = np.where(v["cz"] < PLACEHOLDER, v["cz"], np.nan)
    rzz = np.where(v["rzz"] < PLACEHOLDER, v["rzz"], np.nan)
    out: dict[str, Any] = {}
    for name, err, coh in (("sx", sx, coh_sx), ("cz", cz, coh_cz), ("rzz", rzz, coh_rzz)):
        share = coh / err
        within = [_spearman(np.log10(coh[i]), np.log10(err[i])) for i in range(err.shape[0])]
        # one value per entity: its time-mean of log error vs log limit (between-entity)
        le, lc = np.log10(err), np.log10(coh)
        out[name] = {
            "share_coh_over_err_q": _q(share.ravel()),
            "within_file_spearman_q": _q(np.array(within)),
            "between_entity_pearson_logs": _corr(np.nanmean(lc, axis=0), np.nanmean(le, axis=0)),
            "within_entity_pearson_logs_demeaned": _corr(
                (lc - np.nanmean(lc, axis=0)).ravel(), (le - np.nanmean(le, axis=0)).ravel()
            ),
        }
    return out


def readout_checks(cache: Cache) -> dict[str, Any]:
    v = cache.values
    ro, p01, p10 = v["readout_error"], v["prob_meas0_prep1"], v["prob_meas1_prep0"]
    ok = np.isfinite(ro) & np.isfinite(p01) & np.isfinite(p10)
    mean_rule = np.abs(ro - (p01 + p10) / 2.0) < 1e-12
    meas = v["measure"]
    ok_m = np.isfinite(meas) & np.isfinite(ro)
    grid = ro[np.isfinite(ro)] * 4096.0
    t_ro = v["readout_length"] * 1e-3
    decay = 1.0 - np.exp(-t_ro / v["T1"])
    return {
        "records": int(ok.sum()),
        "readout_eq_mean_of_p01_p10": float(np.mean(mean_rule[ok])),
        "measure_eq_readout_error": float(np.mean(meas[ok_m] == ro[ok_m])),
        "readout_on_1_over_4096_grid": float(np.mean(np.abs(grid - np.round(grid)) < 1e-9)),
        "p01_over_p10_q": _q((p01 / p10).ravel()),
        "p01_vs_readout_decay_spearman": _spearman(decay.ravel(), p01.ravel()),
        "p01_p10_on_1_over_4096_grid": float(
            np.mean(
                (np.abs(p01[ok] * 4096.0 - np.round(p01[ok] * 4096.0)) < 1e-9)
                & (np.abs(p10[ok] * 4096.0 - np.round(p10[ok] * 4096.0)) < 1e-9)
            )
        ),
        "readout_eq_mean_when_dates_equal": float(
            np.mean(
                mean_rule[ok & (cache.dates["readout_error"] == cache.dates["prob_meas0_prep1"])]
            )
        ),
        "shot_noise": shot_noise(cache),
    }


def shot_noise(cache: Cache, shots: float = 4096.0) -> dict[str, Any]:
    """Binomial floor of readout changes: ``p01`` and ``p10`` each come from ``shots`` shots.

    ``readout_error = (p01 + p10) / 2`` so a single estimate has variance
    ``(p01 (1 - p01) + p10 (1 - p10)) / (4 shots)``; the difference of two independent
    estimates has twice that. In log10 units the delta method gives
    ``sd_log = 0.4343 * sd / readout_error``.
    """
    v = cache.values
    series, _ = events(v["readout_error"], cache.dates["readout_error"], mask_placeholder=False)
    ratio: list[float] = []
    sd_single: list[float] = []
    for s in series:
        p01 = v["prob_meas0_prep1"][s.file_idx, s.entity]
        p10 = v["prob_meas1_prep0"][s.file_idx, s.entity]
        var = (p01 * (1 - p01) + p10 * (1 - p10)) / (4.0 * shots)
        sd_log = 0.4343 * np.sqrt(var) / s.y
        sd_single.extend(sd_log.tolist())
        sd_diff = np.sqrt(sd_log[1:] ** 2 + sd_log[:-1] ** 2)
        ratio.extend((np.abs(np.diff(np.log10(s.y))) / sd_diff).tolist())
    r = np.array(ratio)
    r = r[np.isfinite(r)]
    return {
        "sd_log10_single_estimate_q": _q(np.array(sd_single)),
        "abs_change_over_noise_sd_q": _q(r),
        "share_changes_within_2sd": round(float(np.mean(r < 2.0)), 4),
        "share_expected_within_2sd_if_pure_noise": 0.9545,
    }


def level_series(series: list[Series], alpha: float) -> list[FloatArray]:
    """EWMA level after each event (``level[k]`` uses ``z_0..z_k``), log10 units."""
    out: list[FloatArray] = []
    for s in series:
        z = np.log10(s.y)
        lev = np.empty_like(z)
        lev[0] = z[0]
        for k in range(1, z.size):
            lev[k] = alpha * z[k] + (1 - alpha) * lev[k - 1]
        out.append(lev)
    return out


def horizon_skill(series: list[Series], alpha: float) -> dict[str, Any]:
    """MAE (log10) of forecasting ``z_k`` from the state ``h`` events earlier, by method."""
    levels = level_series(series, alpha)
    out: dict[str, Any] = {}
    for h in (1, 2, 4, 8, 16):
        e_p: list[float] = []
        e_l: list[float] = []
        e_m: list[float] = []
        for s, lev in zip(series, levels, strict=True):
            z = np.log10(s.y)
            for k in range(WARMUP_EVENTS + h - 1, z.size):
                e_p.append(abs(z[k] - z[k - h]))
                e_l.append(abs(z[k] - lev[k - h]))
                e_m.append(abs(z[k] - float(np.mean(z[: k - h + 1]))))
        if not e_p:
            continue
        base = float(np.mean(e_p))
        out[f"h{h}"] = {
            "events": len(e_p),
            "persistence_mae": round(base, 5),
            "ewma_vs_persistence": round(float(np.mean(e_l)) / base, 4),
            "expanding_mean_vs_persistence": round(float(np.mean(e_m)) / base, 4),
        }
    return out


def local_level_q(lag1: float) -> dict[str, float]:
    """Signal-to-noise of a local-level model from the lag-1 autocorrelation of changes.

    For ``z_k = mu_k + eps_k`` with ``mu_k = mu_{k-1} + eta_k``, the change has lag-1
    autocorrelation ``-1 / (q + 2)`` with ``q = var(eta) / var(eps)``, and the optimal
    EWMA weight (the steady-state Kalman gain) is ``(-q + sqrt(q^2 + 4 q)) / 2``.
    """
    if not (-0.5 < lag1 < 0.0):
        return {"q": math.nan, "alpha_opt": math.nan}
    q = -1.0 / lag1 - 2.0
    return {"q": round(q, 4), "alpha_opt": round((-q + math.sqrt(q * q + 4 * q)) / 2, 4)}


def forward_fill(
    series: list[Series], levels: list[FloatArray], n_files: int, width: int
) -> tuple[FloatArray, FloatArray]:
    """Per file: the latest event value and its EWMA level (log10), NaN before the first."""
    last = np.full((n_files, width), np.nan)
    lev = np.full((n_files, width), np.nan)
    for s, lv in zip(series, levels, strict=True):
        z = np.log10(s.y)
        bounds = np.concatenate([s.file_idx, [n_files]])
        for k in range(z.size):
            last[bounds[k] : bounds[k + 1], s.entity] = z[k]
            lev[bounds[k] : bounds[k + 1], s.entity] = lv[k]
    return last, lev


def panel_signal(cache: Cache, alpha: dict[str, float]) -> dict[str, Any]:
    """Does any other field at time t move the next value beyond its own EWMA level?

    For each event k of a target family the state at t is the file just before the new
    value arrived. The response is the deviation ``z_k - L_{k-1}`` from the target's own
    EWMA level; predictors are the target's own deviation ``z_{k-1} - L_{k-1}`` and the
    deviations ``z - L`` of other families on the same qubit (both qubits, averaged, for
    a coupler). Ordinary least squares before the 70% time cut, MAE after it, reported
    against persistence and against the EWMA level alone.
    """
    n = cache.file_ms.size
    fams = ("sx", "readout_error", "T1", "T2", "cz", "rzz")
    ser: dict[str, list[Series]] = {}
    dev: dict[str, FloatArray] = {}
    for fam in fams:
        fam_series, _ = events(
            cache.values[fam], cache.dates[fam], mask_placeholder=fam in (*QUBIT_GATES, *EDGE_GATES)
        )
        last, lev_ff = forward_fill(
            fam_series, level_series(fam_series, alpha[fam]), n, cache.values[fam].shape[1]
        )
        ser[fam] = fam_series
        dev[fam] = last - lev_ff
    a = np.array([e[0] for e in cache.edges])
    b = np.array([e[1] for e in cache.edges])
    exo_q = ("sx", "readout_error", "T1", "T2")
    out: dict[str, Any] = {}
    for target in fams:
        is_edge = target in EDGE_GATES
        exo_names = [f for f in exo_q if f != target]
        if is_edge:
            exo_names.append("rzz" if target == "cz" else "cz")
        lv = level_series(ser[target], alpha[target])
        rows: list[list[float]] = []
        for s, lev in zip(ser[target], lv, strict=True):
            z = np.log10(s.y)
            for k in range(WARMUP_EVENTS, z.size):
                f = int(s.file_idx[k]) - 1
                feats = [float(s.t_ms[k]), z[k] - lev[k - 1], z[k - 1] - lev[k - 1]]
                for name in exo_names:
                    if name in EDGE_GATES:
                        feats.append(float(dev[name][f, s.entity]))
                    elif is_edge:
                        pair = (dev[name][f, a[s.entity]], dev[name][f, b[s.entity]])
                        feats.append(float(np.mean(pair)))
                    else:
                        feats.append(float(dev[name][f, s.entity]))
                rows.append(feats)
        arr = np.array(rows)
        arr = arr[np.all(np.isfinite(arr), axis=1)]
        cut = float(np.quantile(arr[:, 0], 0.7))
        tr, te = arr[arr[:, 0] <= cut], arr[arr[:, 0] > cut]
        y_tr, y_te = tr[:, 1], te[:, 1]
        # |z_k - z_{k-1}| = |(z_k - L) - (z_{k-1} - L)| = |y - own_dev|
        persistence = float(np.mean(np.abs(y_te - te[:, 2])))
        level_only = float(np.mean(np.abs(y_te)))
        res: dict[str, Any] = {
            "train_events": len(tr),
            "test_events": len(te),
            "exogenous": exo_names,
            "ewma_level_vs_persistence": round(level_only / persistence, 4),
        }
        for label, cols in (
            ("own_deviation", [2]),
            ("own_plus_exogenous", [2, *range(3, arr.shape[1])]),
        ):
            x_tr = np.column_stack([np.ones(len(tr)), tr[:, cols]])
            x_te = np.column_stack([np.ones(len(te)), te[:, cols]])
            beta, *_ = np.linalg.lstsq(x_tr, y_tr, rcond=None)
            mae = float(np.mean(np.abs(y_te - x_te @ beta)))
            res[label] = {
                "coef": [round(float(c), 4) for c in beta],
                "vs_persistence": round(mae / persistence, 4),
                "vs_ewma_level": round(mae / level_only, 4),
            }
        out[target] = res
    return out


def faults(cache: Cache) -> dict[str, Any]:
    """Placeholder (``gate_error = 1``) episodes per family: entry, duration, offenders."""
    out: dict[str, Any] = {}
    for fam in (*QUBIT_GATES, *EDGE_GATES):
        v = cache.values[fam]
        ph = v >= PLACEHOLDER
        entries = (ph[1:] & ~ph[:-1]).sum(axis=0)
        ever = np.flatnonzero(ph.any(axis=0))
        share_files = ph.mean(axis=0)
        worst = np.argsort(-share_files)[:5]

        def label(k: int, fam: str = fam) -> str:
            if fam in QUBIT_GATES:
                return f"q{k}"
            return f"q{cache.edges[k][0]}-{cache.edges[k][1]}"

        out[fam] = {
            "entities_ever_placeholder": int(ever.size),
            "entries_into_placeholder": int(entries.sum()),
            "share_of_records_placeholder": round(float(ph.mean()), 5),
            "most_affected": [
                {"entity": label(int(k)), "share_of_files": round(float(share_files[k]), 4)}
                for k in worst
                if share_files[k] > 0
            ],
        }
    return out


def neighbours(cache: Cache, sx_series: list[Series]) -> dict[str, Any]:
    """Do changes of coupled qubits move together beyond the device-wide common mode?"""
    n_files = cache.file_ms.size
    delta = np.full((n_files, N_QUBITS), np.nan)
    for s in sx_series:
        z = np.log10(s.y)
        delta[s.file_idx[1:], s.entity] = np.diff(z)
    rows = np.flatnonzero(np.isfinite(delta).sum(axis=1) >= 20)
    d = delta[rows]
    common = np.nanmean(d, axis=1, keepdims=True)
    total_var = float(np.nanvar(d))
    resid = d - common
    adj = set(cache.edges)
    dist = _hop_distance(cache.edges)

    def pair_corr(i: int, j: int) -> float:
        return _corr(resid[:, i], resid[:, j])

    coupled = [pair_corr(i, j) for i, j in adj]
    far = [
        pair_corr(i, j) for i in range(N_QUBITS) for j in range(i + 1, N_QUBITS) if dist[i, j] >= 4
    ]
    return {
        "rounds_used": int(rows.size),
        "common_mode_share_of_variance": round(float(np.nanvar(common)) / total_var, 4),
        "coupled_pairs": len(coupled),
        "coupled_residual_corr_q": _q(np.array(coupled)),
        "far_pairs": len(far),
        "far_residual_corr_q": _q(np.array(far)),
    }


def _hop_distance(edges: list[tuple[int, int]]) -> npt.NDArray[np.int64]:
    dist = np.full((N_QUBITS, N_QUBITS), 10**6, dtype=np.int64)
    nbrs: dict[int, list[int]] = {q: [] for q in range(N_QUBITS)}
    for a, b in edges:
        nbrs[a].append(b)
        nbrs[b].append(a)
    for src in range(N_QUBITS):
        dist[src, src] = 0
        frontier = [src]
        while frontier:
            nxt: list[int] = []
            for u in frontier:
                for w in nbrs[u]:
                    if dist[src, w] > dist[src, u] + 1:
                        dist[src, w] = dist[src, u] + 1
                        nxt.append(w)
            frontier = nxt
    return dist


def lead_lag(cache: Cache, sx_series: list[Series]) -> dict[str, Any]:
    """Out-of-time test: does the T1/T2 limit at the new round add to the gate's own history?

    For each sx event k (k >= WARMUP_EVENTS) regress ``z_k - z_{k-1}`` on
    ``m_{k-1} - z_{k-1}`` (pull toward the series' expanding mean) and on the change in
    the log coherence limit between the two events' files. Ordinary least squares on
    events before the time cut, MAE scored after it, against persistence.
    """
    v = cache.values
    coh = coherence_limit_1q(v["T1"], v["T2"], v["sx_length"])
    rows: list[tuple[float, float, float, float, float]] = []
    for s in sx_series:
        z = np.log10(s.y)
        c = np.log10(coh[s.file_idx, s.entity])
        for k in range(WARMUP_EVENTS, z.size):
            pull = float(np.mean(z[:k]) - z[k - 1])
            rows.append(
                (float(s.t_ms[k]), pull, float(c[k] - c[k - 1]), float(z[k] - z[k - 1]), 0.0)
            )
    arr = np.array(rows)
    arr = arr[np.all(np.isfinite(arr), axis=1)]
    cut = float(np.quantile(arr[:, 0], 0.7))
    train, test = arr[arr[:, 0] <= cut], arr[arr[:, 0] > cut]
    out: dict[str, Any] = {"train_events": len(train), "test_events": len(test)}
    base = float(np.mean(np.abs(test[:, 3])))
    for name, cols in (("pull_only", [1]), ("pull_plus_coherence_change", [1, 2])):
        x_tr = np.column_stack([np.ones(len(train)), train[:, cols]])
        x_te = np.column_stack([np.ones(len(test)), test[:, cols]])
        beta, *_ = np.linalg.lstsq(x_tr, train[:, 3], rcond=None)
        mae = float(np.mean(np.abs(test[:, 3] - x_te @ beta)))
        out[name] = {
            "coef": [round(float(b), 4) for b in beta],
            "test_mae_vs_persistence": round(mae / base, 4),
        }
    return out


def ages(cache: Cache) -> dict[str, Any]:
    """Age of each field at the moment of each file: file time minus its stamped date."""
    out: dict[str, Any] = {}
    for fam in ("T1", "T2", "readout_error", "sx", "measure_2", "cz", "rzz"):
        d = cache.dates[fam]
        v = cache.values[fam]
        ok = np.isfinite(d) & (v < PLACEHOLDER) if fam in (*QUBIT_GATES, *EDGE_GATES) else None
        age_h = (cache.file_ms[:, None] - d) / 3.6e6
        if ok is not None:
            age_h = np.where(ok, age_h, np.nan)
        out[fam] = {"age_h_q": _q(age_h.ravel())}
    return out


def gamma_lambda(cache: Cache) -> tuple[FloatArray, FloatArray]:
    """ADR-027's per-qubit target with the sx gate length, in the archive's own units."""
    v = cache.values
    t = v["sx_length"] * 1e-3
    t1, t2 = v["T1"], v["T2"]
    valid = (t1 > 0) & (t2 > 0) & (t2 <= 2 * t1)
    gamma = np.where(valid, 1.0 - np.exp(-t / t1), np.nan)
    lam = np.where(valid, 1.0 - np.exp(-t * (2.0 / t2 - 1.0 / t1)), np.nan)
    return gamma, lam


def device_mean(cache: Cache, gamma: FloatArray, lam: FloatArray) -> dict[str, Any]:
    """Stage A's view: one device-wide arithmetic mean per file, deduplicated into events.

    The mean moves whenever any entity is re-measured, so its events are files where the
    mean changes. Placeholders are excluded from the gate-error means.
    """
    out: dict[str, Any] = {}
    arrays: dict[str, FloatArray] = {"gamma": gamma, "lambda": lam}
    for fam in ("sx", "cz", "rzz", "readout_error"):
        v = cache.values[fam]
        arrays[fam] = np.where(v < PLACEHOLDER, v, np.nan)
    for name, arr in arrays.items():
        mean = np.nanmean(arr, axis=1)
        ok = np.flatnonzero(np.isfinite(mean))
        keep = ok[np.concatenate([[True], np.diff(mean[ok]) != 0])]
        series = Series(
            entity=0,
            t_ms=cache.file_ms[keep],
            file_idx=keep.astype(np.int64),
            y=mean[keep],
        )
        out[name] = memory([series])
    return out


def analyze(cache: Cache, ref: str) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ref": ref,
        "files": len(cache.stems),
        "first_file": cache.stems[0],
        "last_file": cache.stems[-1],
        "edges": len(cache.edges),
        "extract_checks": cache.checks,
        "inventory": cache.inventory,
    }
    families: dict[str, Any] = {}
    sx_series: list[Series] = []
    for fam in (*QUBIT_GATES, *EDGE_GATES, "readout_error", "T1", "T2"):
        series, counts = events(
            cache.values[fam], cache.dates[fam], mask_placeholder=fam in (*QUBIT_GATES, *EDGE_GATES)
        )
        if fam == "sx":
            sx_series = series
        families[fam] = {
            "event_rule_mismatches": counts,
            "rounds": rounds(series),
            "value_q": _q(np.concatenate([s.y for s in series])),
            "memory_log10": memory(series),
        }
    gamma, lam = gamma_lambda(cache)
    stamp_t1t2 = np.fmax(cache.dates["T1"], cache.dates["T2"])
    for name, arr, stamp in (("gamma", gamma, cache.dates["T1"]), ("lambda", lam, stamp_t1t2)):
        series, counts = events(arr, stamp, mask_placeholder=False)
        families[name] = {
            "event_rule_mismatches": counts,
            "value_q": _q(np.concatenate([s.y for s in series])),
            "memory_log10": memory(series),
        }
    report["families"] = families
    report["coherence_limit"] = coherence_share(cache)
    report["readout"] = readout_checks(cache)
    report["faults"] = faults(cache)
    report["neighbours_sx"] = neighbours(cache, sx_series)
    report["lead_lag_sx"] = lead_lag(cache, sx_series)
    report["ages"] = ages(cache)
    alpha: dict[str, float] = {}
    for fam in ("sx", "readout_error", "T1", "T2", "cz", "rzz", "measure_2"):
        lag1 = families[fam]["memory_log10"]["lag1_autocorr_of_change"]
        families[fam]["local_level"] = local_level_q(lag1)
        a_opt = families[fam]["local_level"]["alpha_opt"]
        alpha[fam] = a_opt if math.isfinite(a_opt) else 0.2
        series, _ = events(
            cache.values[fam], cache.dates[fam], mask_placeholder=fam in (*QUBIT_GATES, *EDGE_GATES)
        )
        families[fam]["horizon_skill"] = horizon_skill(series, alpha[fam])
    report["ewma_alpha_used"] = alpha
    report["device_mean"] = device_mean(cache, gamma, lam)
    report["panel_signal"] = panel_signal(cache, alpha)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("extract")
    ex.add_argument("--repo", type=Path, required=True)
    ex.add_argument("--ref", required=True)
    ex.add_argument("--backend", default="ibm_fez")
    ex.add_argument("--out", type=Path, required=True)
    ex.add_argument("--limit", type=int, default=None, help="first N files only (smoke test)")
    an = sub.add_parser("analyze")
    an.add_argument("--cache", type=Path, required=True)
    an.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.cmd == "extract":
        cache = extract(args.repo, args.ref, args.backend, args.limit)
        save_cache(cache, args.out, args.ref)
        print(f"{len(cache.stems)} files, {len(cache.edges)} edges -> {args.out}")
        return 0
    cache, ref = load_cache(args.cache)
    report = analyze(cache, ref)
    args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"report -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
