"""The distinct-state structure of ``health/state-index.tsv`` as carried in the cache.

``file.state_id`` numbers the archive's qubit digests (one per state-index row matched to a
file by name), ``file.is_new_state`` is the row's flag. This script measures:

- files per state, and whether a state ever recurs after another state intervened;
- what ``is_new_state`` agrees with: "the digest differs from the previous file's" or "the
  digest has not been seen before";
- the digest's scope, checked against the values: inside a run of files with one state, do
  any qubit-record values differ, and between consecutive files of different states, do they
  always differ; which other families change inside a same-state run;
- the one file without a state row.

Writes ``results/device/states.json``.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import device_common as dc

QUBIT_FIELDS = (
    "q.T1",
    "q.T2",
    "q.readout_error",
    "q.prob_meas0_prep1",
    "q.prob_meas1_prep0",
    "q.readout_length",
    "q.init_error",
)
OTHER_FIELDS = (
    "g1.sx.gate_error",
    "g1.measure_2.gate_error",
    "g1.xslow.gate_error",
    "g2.cz.gate_error",
    "g2.rzz.gate_error",
    "gen.lf",
    "gen.zz",
    "g1.measure.threshold",
)


def changed(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Per row pair: any column whose value differs (NaN against a value counts as a change)."""
    both_nan = np.isnan(a) & np.isnan(b)
    diff = (a != b) & ~both_nan
    out: np.ndarray = diff.any(axis=1)
    return out


def main() -> int:
    dd = ddload.DD()
    sid = dd.file("state_id").astype(np.int64)
    new = dd.file("is_new_state").astype(np.int64)
    n = dd.n_files
    has = sid >= 0
    counts = Counter(int(s) for s in sid[has])
    # Runs and recurrences, over files that have a state row.
    idx = np.flatnonzero(has)
    seq = sid[idx]
    run_start = np.r_[True, seq[1:] != seq[:-1]]
    runs = seq[run_start]
    recurring = [s for s, c in Counter(runs.tolist()).items() if c > 1]
    first_seen = np.zeros(idx.size, dtype=bool)
    seen: set[int] = set()
    for k, s in enumerate(seq):
        first_seen[k] = int(s) not in seen
        seen.add(int(s))
    flag = new[idx] == 1
    diff_prev = run_start.copy()
    # Value checks between consecutive files (both with a state row, adjacent in time).
    q_change = np.zeros(n - 1, dtype=bool)
    for field in QUBIT_FIELDS:
        v = np.array(dd.v(field))
        q_change |= changed(v[1:], v[:-1])
    other_change: dict[str, np.ndarray] = {}
    for field in OTHER_FIELDS:
        v = np.array(dd.v(field))
        other_change[field] = changed(v[1:], v[:-1])
    pair_ok = has[1:] & has[:-1]
    same = pair_ok & (sid[1:] == sid[:-1])
    different = pair_ok & (sid[1:] != sid[:-1])
    # Where the flag is not on the state's first file in time: who carries it instead.
    live = dd.file("has_configuration").astype(bool)
    mism_states = sorted(
        {int(s) for s, f, fs in zip(seq, flag, first_seen, strict=True) if f != fs}
    )
    first_in_time_hist = flagged_later = flagged_live = 0
    flag_lag_h: list[float] = []
    for s in mism_states:
        files_s = idx[seq == s]
        first_file = int(files_s[0])
        flagged = [int(i) for i in files_s if new[i] == 1]
        first_in_time_hist += int(not live[first_file])
        if flagged:
            flagged_later += int(flagged[0] > first_file)
            flagged_live += int(live[flagged[0]])
            flag_lag_h.append(float((dd.file_ms[flagged[0]] - dd.file_ms[first_file]) / 3.6e6))
    states_without_flag = sum(1 for s in counts if not np.any(new[idx[seq == s]] == 1))
    states_with_two_flags = sum(1 for s in counts if np.sum(new[idx[seq == s]] == 1) > 1)
    id_order = np.array([int(seq[run_start][k]) for k in range(int(run_start.sum()))])
    mismatch_info = {
        "states_where_flag_is_not_on_first_file_in_time": len(mism_states),
        "of_those_first_file_in_time_is_historical": first_in_time_hist,
        "of_those_flagged_file_is_later": flagged_later,
        "of_those_flagged_file_is_live": flagged_live,
        "flagged_minus_first_file_h_q": dc.quantiles(flag_lag_h),
        "states_without_a_flag": int(states_without_flag),
        "states_with_more_than_one_flag": int(states_with_two_flags),
        "state_ids_in_time_order_are_increasing": bool(np.all(np.diff(id_order) > 0)),
        "state_id_order_inversions": int(np.sum(np.diff(id_order) < 0)),
    }
    no_row = np.flatnonzero(~has)
    no_row_info = []
    for i in no_row:
        info: dict[str, Any] = {"file": dd.stems[int(i)]}
        if 0 < i < n - 1:
            info["qubit_values_equal_previous_file"] = bool(not q_change[i - 1])
            info["qubit_values_equal_next_file"] = bool(not q_change[i])
            info["previous_state"] = int(sid[i - 1])
            info["next_state"] = int(sid[i + 1])
            info["next_file_is_new_state"] = int(new[i + 1])
        no_row_info.append(info)
    payload = {
        **dc.header("states.py"),
        "n_files": n,
        "state_index_rows": dd.meta["state_index_rows"],
        "files_with_state": int(has.sum()),
        "files_without_state_row": no_row_info,
        "distinct_states": len(counts),
        "files_per_state_q": dc.quantiles(list(counts.values())),
        "states_with_one_file": int(sum(1 for c in counts.values() if c == 1)),
        "max_files_per_state": int(max(counts.values())),
        "runs": int(runs.size),
        "states_recurring_after_another_state": len(recurring),
        "is_new_state_ones": int(flag.sum()),
        "is_new_equals_first_seen": int(np.sum(flag == first_seen)),
        "is_new_equals_differs_from_previous": int(np.sum(flag == diff_prev)),
        "files_compared": int(idx.size),
        "flag_mismatch": mismatch_info,
        "consecutive_pairs_same_state": int(same.sum()),
        "same_state_pairs_with_any_qubit_value_change": int(np.sum(same & q_change)),
        "consecutive_pairs_different_state": int(different.sum()),
        "different_state_pairs_without_qubit_value_change": int(np.sum(different & ~q_change)),
        "same_state_pairs_with_change_by_field": {
            f: int(np.sum(same & c)) for f, c in other_change.items()
        },
        "same_state_pairs_with_any_listed_change": int(
            np.sum(same & np.any(np.stack(list(other_change.values())), axis=0))
        ),
        "qubit_fields_compared": list(QUBIT_FIELDS),
    }
    ddload.write_json(dc.RESULTS / "states.json", payload)
    print("wrote", dc.RESULTS / "states.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
