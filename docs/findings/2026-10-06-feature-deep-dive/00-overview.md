# 00 · Overview: what the `ibm_fez` calibration archive is, at root

Written 2026-10-06 on branch `mert/feature-deep-dive`. This is a dated document: append-only
after today; reconcile it later by appending an as-of section, never by editing the text below.
It was revised later the same day, after independent verifiers appended a "Verification
(2026-10-06)" section and inline markers to documents 02 to 06; its first version described
02 to 06 as unverified. Where a verifier weakened or refuted a claim, this overview now uses the
verifier's reading and cites it as, for example, "(02 Verification)".

**Every figure here is provisional.** Ref: `calibration-data`
`7b84b506ef77beb6e6c1b25a7357c574cfaf5117`. Basis: all 1,760 `ibm_fez` snapshot files
(2026-05-13T12:13:22Z to 2026-10-06T02:57:42Z), 156 qubits, 176 undirected couplers and 97
`lf_<N>` names, as described in `01-data-layer.md`; every figure was measured on 2026-10-06 on
the lead's laptop (Windows 11, CPython 3.12), not on the verification desktop. Nothing here is
registered in `docs/numerical-claims.md`. This overview runs no analysis and has no scripts or
results files of its own: every number is quoted from the document and section named next to it
(written "(02 §4.1)" for `02-coherence.md` section 4.1), and the few obtained by trivial
arithmetic on quoted numbers are marked "arithmetic". No new literature was fetched for it; the
sources are those of each document's section 11 and of the verifiers' spot-checks (each
Verification section).

**Open decisions.** The advisor's (Dr. Akba's) answers and decisions A1 to A9 remain open.
Nothing here records or implies an approval, and nothing here is a modelling or strategic
decision. Where this overview recommends an analysis or a measurement, it says "recommendation";
none is adopted.

**State of the scope documents.** Documents 02 to 07 each carry all eleven sections, their
scripts, their results files and an appended independent "Verification (2026-10-06)" section
written by an agent that did not write the document (07 was itself completed by a second
session after its first analyst stopped, 07 §10). Each verifier re-ran every owner script (all
results JSONs reproduced, differing only in `measured_utc`), recomputed a set of headline
numbers with new scripts written from `ddload` alone, challenged the main claims, and inserted
inline "[Verification 2026-10-06: ...]" markers next to claims it weakened or refuted. The
counts below are taken from each document's Verification section. Every figure stays
provisional (same ref, same laptop); verification is a second agent on the same machine, not
the verification desktop.

| Document | Owner scripts re-run, results reproduce | Numbers independently recomputed (rows of the verifier's table) | Claims challenged: upheld / weakened / refuted | Inline markers |
| --- | --- | --- | --- | --- |
| `02-coherence.md` | 7 of 7 | 16: 14 match, 1 new supporting figure (first differences, no level: Pearson 0.714), 1 partial (matched sub-day median ratio 1.05 all and 1.19 after 05-30 against 0.96; method-dependent) | 8: 3 upheld; 2 upheld only as "shared" (the `T1`/`T2` half-shared bound and the dips that `T2` follows; "real" and "contradicted" weakened); 3 weakened (decorrelation below 3.86 h, dip persistence, ADR-027 "mostly"); 0 refuted | 4 |
| `03-readout-measurement.md` | 7 of 7 | 19: 13 match, 5 approximate (record selection or median definition), 1 new placebo (iid binomial ratio 1.005) | 8: 3 upheld; 4 weakened (fresh-P(0\|1) grid test, checkerboard, half-window decay, the 2^-312 parity figure); 1 split (2026-06-08 RO drop upheld, its A part weakened); 0 refuted | 5 |
| `04-single-qubit-gates.md` | 6 of 6 | 21: 21 match | 8: 4 upheld; 4 weakened (same-round coupling as a real hour-scale fluctuation, spike clustering, the 0.111-decade size, `xslow` "copied"); 0 refuted | 4 |
| `05-two-qubit-gates-couplings.md` | 7 of 7 (4,527 numeric leaves, 0 differences) | 23: 18 match, 5 approximate (different reduction, filter or denominator) | 9: 5 upheld; 3 weakened ("three quarters" within hours, `rzz` cadence fall, "`sx` explains"); 1 refuted (the short-against-preceding Wilcoxon p-values, pseudo-replicated) | 4 |
| `06-device-time-topology.md` | 7 of 7 | 27: 26 match, 1 not (footprint "below the smallest of 2,000 draws": minimum 7.62 with another seed) | 9: 5 upheld; 4 weakened (fault footprint, the 2026-06-08 readout "clear exception", `lf` chain re-selection, `lf` offset speculation); 0 refuted | 6 (on 5 points; the EPLG n note leaves the conclusion unchanged) |
| `07-cross-feature-dependency.md` | 7 of 7 | 16: 16 match | 7: 3 upheld; 3 weakened; 1 refuted as worded (the permutation-validity premise; the null result stands) | 5 |

No measured headline value in 02 to 06 was found miscomputed (the one non-matching row, 06's
footprint minimum, is seed-dependent); the corrections concern wording, the validity of tests
(05's pseudo-replicated p-values, 06's qubit-based null for coupler faults, 03's grid test that
cannot fail) and attributions. What each verifier did not re-verify is listed in section 6 item 3.

**Evidence levels used below.**

| Code | Meaning |
| --- | --- |
| A | Identity: a record-by-record arithmetic or duplicate check (01 §5 and the owners' re-checks; re-counted by the verifiers where noted) |
| V | Measured and verified: recomputed independently by the document's verifier (new code from `ddload`) and upheld; "V approx" where the verifier's figure differs slightly by record selection or reduction |
| W | Measured, then weakened by the document's verifier; the weakened reading is the one used here |
| R | Refuted as stated by the document's verifier; the verifier's corrected figure is the one used here |
| M | Measured; the verifier re-ran the owner's script and the results reproduce, but this figure was not independently recomputed |
| I | Interpretation of measured numbers; falsifiers are given where the owner states one |

**Notation.** "p01" names opposite fields in different documents:
`docs/roadmap/2026-10-05-feature-patterns-and-method.md` (P5) uses it for `prob_meas0_prep1`,
while `01-data-layer.md` §5 and `07-cross-feature-dependency.md` use it for `prob_meas1_prep0`
(03, Notation). This overview uses the symbols of `03-readout-measurement.md`:
**P(0|1)** = `q.prob_meas0_prep1` (prepared |1>, read 0), **P(1|0)** = `q.prob_meas1_prep0`
(prepared |0>, read 1), **RO** = `q.readout_error`. When 07 is quoted, its `p10` is P(0|1), its
`p01` is P(1|0), its `init` is `q.init_error` and its `m2` is `g1.measure_2.gate_error`.

## 1. The answer in one paragraph

At root, the archive is a set of per-entity time series sampled by IBM's calibration schedule,
not a set of measurement records: each value carries one number and, at best, the time at which a
batch of results was written (02 §0, 06 §3.3, interpretation), and no value carries an
uncertainty (02 §6, 05 §4.5). The schedule is a daily round on a cycle of 24.7 to 25.3 h that
walks around the clock (readout and `measure_2` first, then `T1` and `T2` seconds apart, then
`sx` about an hour later, then `cz` and `rzz` hours later), intraday readout sessions about every
4.4 h, a device-wide `zz` refresh about every 5 h and a layer-fidelity cycle of its own of 26.5 h
(06 §3.1 and §3.2, 05 §1.4). Of the 33 rows of the data dictionary (01 §3), twelve carry measured
values that are not copies; two record a discriminator setting; the other nineteen are copies,
constants, configuration lengths or an empty field (section 2, arithmetic). Every informative
series has three parts: a per-entity level that is stable for months (which qubit it is explains
0.817 of the variance of log `T2` and 0.744 of log `sx`, but only 0.386 of log `T1`; 02 §2.1,
04 §2), a level that drifts slowly over weeks to months, and a large non-persistent component
that is memoryless from one sampling to the next (lag-1 autocorrelation of log changes between
-0.425 and -0.513 in every per-entity family) and already carries 0.43 to 0.82 of the long-lag
semivariance at the shortest lag each per-entity family offers (0.94 for `lf_10`; section 4.1).
The families are nearly
independent of one another: across qubits, readout quality and coherence-with-gate quality are
two separate axes (07 §7.5, V); within a qubit no nearest-event cross-family correlation in 07's
scope exceeds 0.06 in absolute value (07 §7.2; at most 0.130 in the shortest gap bin, 07 §4.5);
in none of 07's 23 cross-family pairs does one family's recent movement forecast the other's
(07 §7.3; the links owned by 02 to 06 were not tested for lead or lag anywhere); and
the device-wide common mode takes at most 0.130 of a family's residual variance (07 §3.1). What
the non-persistent component is remains open. It is not explained by the one estimation noise the
archive lets us compute (binomial readout shot noise is about a fifth to a quarter of readout's
shortest-lag variability; 03 §4.7, 07 §4.4, upheld against an iid binomial placebo in 03
Verification); part of it is shared between separate experiments on the same qubit or coupler,
at least about half of the deviation variance for `T1` and `T2` of one round (Pearson 0.70,
reproduced with two level definitions and from first differences, 02 Verification) and a small
part elsewhere (04 §7, 05 §4.4, 07 §4.2); the 02 and 04 verifiers read this as "shared between
experiments", which a common input to both (a shared artefact of IBM's procedure, or a shared
SPAM or state-preparation drift) would also produce, not as proof of a real change of the qubit
(02 and 04 Verification); its size changed about twenty-fold device-wide in May 2026 (02 §3.2,
reproduced); and its bulk is attributed by no test the archive allows.

## 2. The feature map

Every field of `01-data-layer.md` §3, with exact duplicates and constants grouped. "Status" is
informative, duplicate, constant, configuration, procedure marker or structural. Levels are
event medians with the 1% and 99% quantiles unless marked "record" (record quantiles repeat each
value until it is re-measured and include placeholders, so they differ; 04 §2). Figures marked
"(V)" were recomputed independently by the owning document's verifier; every other figure comes
from an owner script that the verifier re-ran and reproduced (M).

| Field(s) | Physical meaning | How IBM produces it | Cadence | Date semantics | Status | Key level and spread | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `q.T1` | Energy-relaxation time (us) | Defined by IBM; the fit procedure is not published (02 §1) | Daily round, median gap 24.77 h (02 §2.3) | Measured stamp; a whole device round is stamped within a median 0.05 min, so the stamp reads as a batch write time (02 §0, §2.3; I) | Informative | 126 us (39.5, 261); 0.386 of log variance between qubits (02 §2.1) (V) | 02 |
| `q.T2` | Phase-coherence time (us) | Hahn echo (IBM documentation, 02 §1) | Same round, stamped 1 to 112 s after `T1` (02 §0) | As `T1` | Informative; absent for `q72` in every file (02 §2.2) | 92.9 us (6.46, 234); 0.817 between qubits (02 §2.1) (0.817 V) | 02 |
| Derived: `1/T1`, `Gamma_phi = 1/T2 - 1/(2 T1)`, `s = T2/(2 T1)`, ADR-027 gamma and lambda | Relaxation and pure-dephasing (echo) rates; damping parameters | Arithmetic on `T1`, `T2` (02 §1) | Paired events | As `T1` | Derived, no new information (02 §1) | `Gamma_phi` 5.94 /ms (1.18, 108); `s` 0.405 (0.0431, 0.817); `T2 > 2 T1` in 20 of 19,899 paired events (02 §2.1) (20 of 19,899 V) | 02 |
| `q.readout_error` (RO); `g1.measure.gate_error` is a copy | Assignment error | IBM: average of the two assignment errors, usually their mean (03 §1.1); equals the mean of the published pair whenever all three come from one session (03 §0 item 1, A) | Sessions about every 4.4 h: one even daily session plus intraday ones (03 §1.3, 06 §3.1) | Measured stamp; P(0\|1), P(1\|0) and RO written about 40 s apart in one session (03 §1.3) | Informative; `measure` copy is a duplicate (01 §5, A) | Record 0.0100 (0.00293, 0.238); per-qubit medians 0.00525, 0.00891, 0.0409 at 10, 50, 90% (03 §2.1) | 03 |
| `q.prob_meas0_prep1`, P(0\|1) | Prepared \|1>, read 0 | A count over 4,096 shots (01 §5); daily sessions sit on the 1/2,048 grid and their shot count is open (03 §4.5) | As RO, except a rotating group of 9 qubits that is not republished intraday (03 §0 item 2) | Measured stamp | Informative | Record 0.0137 (0.00439, 0.185) (03 §2.1) | 03 |
| `q.prob_meas1_prep0`, P(1\|0) | Prepared \|0>, read 1 | As P(0\|1); exactly 0 in 2,468 records (03 §2.1) | As RO | Measured stamp | Informative | Record 0.00610 (0.000244, 0.167) (03 §2.1) | 03 |
| `q.readout_length`; `g1.measure.gate_length` is a copy | Readout duration (ns) | IBM definition (03 §1.1) | Device-wide values: 1,560 ns, then 1,700 ns from 2026-06-08T18:56:28Z, 1,660 ns from 2026-07-30T21:09:17Z (01 §5) | Value only; the `measure` copy is assembly-stamped (01 §5) | Configuration; duplicate | n/a | 03 |
| `q.init_error` | Residual \|1> population after initialization (IBM documentation, 03 §1.1); the fetched IBM text adds the condition "when the prior experiment prepared the qubit in the \|1> state", which 03 omits (03 Verification) | Initialization measurement not documented (03 §7.1) | About every 4.7 h (01 §3); schema start 2026-08-04 | Measured stamp, only partly tied to readout sessions (03 §7.1) | Informative on 116 qubits; 40 never carry it (03 §2.2) | Record 0.00185 (0.0002, 0.0106); 540 records below 1e-6 (03 §2.1) | 03 |
| `g1.measure_2.gate_error` | Error of the mid-circuit measurement instruction (1,340 ns) | IBM: the default `MidCircuitMeasure` instruction; calibration not documented (03 §1.2) | Once a day with the even session, 52 rounds (03 §0 item 11) | Measured stamp; placeholder on every qubit in its first two files (03 §6) | Informative from 2026-08-07 | Record 0.0139 (0.00220, 0.299); per qubit a median 1.25 times RO (03 §2.1, §7.1) | 03 |
| Thresholds: `g1.measure.threshold` (= `g1.measure_reset.threshold`), `g1.measure_2.threshold` (= `g1.measure_reset_2.threshold`) | Discriminator threshold, arbitrary IQ units | IBM's hourly monitoring checks the discriminator threshold (03 §1.1) | Device-wide, all-or-none updates in 327 change files (V), mostly with intraday sessions (03 §0 item 12) | Assembly-stamped; value only (01 §4) | Procedure marker, no stable physical meaning on its own (03 §7.1, I); `measure_reset` copies are duplicates (A) | 84.56% negative; 147 of 156 qubits change sign (03 §7.1) | 03 |
| Other measurement lengths: `g1.measure_2.gate_length` (1,340 ns), `g1.reset.gate_length` (t_ro + 24 ns), `g1.measure_reset.gate_length` (= reset), `g1.reset_2.gate_length` and `g1.measure_reset_2.gate_length` (1,364 ns) | Durations | Reset is a measurement followed by a conditional `x` (Qiskit documentation, 03 §1.2) | Follow the readout length | Value only; assembly-stamped | Constant or derived (A, 03 §1.2) | n/a | 03 |
| `g1.sx.gate_error` | Single-qubit gate error from randomized benchmarking (RB), simultaneous on all qubits (IBM documentation, 04 §1) | RB settings not published (04 §1) | Daily, median gap 24.93 h, 135 rounds (04 §2) | Measured stamp, whole seconds; same-stamp batches never hold two coupled qubits (06 §3.3) | Informative | 3.10e-4 (1.42e-4, 2.54e-3); 0.744 between qubits; qubit medians span a factor 34.5 (04 §2) (V) | 04 |
| `g1.x`, `g1.id`, `g1.rx`, `g1.xslow` errors | The same value as `sx` (for `xslow`, "copied" names a mechanism the data do not show; read "reports the same value as", 04 Verification) | IBM: `sx`, `id`, `x` errors assumed equal; the equality of `rx` and `xslow` is an archive observation (04 §1) | As `sx` | Identical to `sx` outside placeholders (04 §0) | Duplicates (A; 0 mismatches re-counted in 04 Verification) | n/a | 04 |
| Lengths of `sx`, `x`, `id`, `rx` (24 ns) and `xslow` (1,000 ns); `g1.rz.*` (0 error, 0 ns) | Durations; virtual Z gate | `rz` is the virtual Z of McKay et al. 2017 (04 §1) | Constant | `rz` assembly-stamped | Constants; `xslow` present 2026-05-14 to 05-29 and from 2026-09-10 (01 §5) | n/a | 04 |
| `g2.cz.gate_error` | Per-edge CZ error from RB in isolation batches (IBM documentation, 05 §1.1) | RB settings not published (05 §4.5) | Daily, median 25.1 h, 132 rounds (05 §2.3) | Measured stamp; the two directions identical in value and date outside placeholders (05 §1.3) | Informative (one canonical column per coupler); 4 couplers permanently at the placeholder (05 §6.1) | 2.75e-3 (1.59e-3, 4.54e-2); coupler medians span a factor 42.5 (05 §2.1) (median V) | 05 |
| `g2.rzz.gate_error` | RZZ error averaged over angles (IBM documentation, 05 §1.1) | RB variant for arbitrary unitaries (05 §1.1) | Daily, median 25.3 h, typically 1.15 h after `cz`; 0.809 then 0.607 events per coupler per day across the coverage split; one 279.8 h device-wide pause (05 §2.3), which accounts for most of the fall: 0.729 from the split if it is excluded (05 Verification, W) | Measured stamp | Informative; equal to `cz` in 0 of 296,321 same-file records (05 §1.1); 5 couplers permanently at the placeholder | 2.66e-3 (1.53e-3, 4.61e-2); span a factor 99.6 (05 §2.1) (median V) | 05 |
| `g2.cz.gate_length`, `g2.rzz.gate_length` | Durations (ns) | Configuration | 68 ns on most couplers; 88 ns on 102-103 and 146-147; `rzz` 116 ns on 68-69, 80-81 and 106-107; 84 ns on 71-72 and 72-73 from 2026-09-05 (01 §5) | Value only | Configuration | n/a | 05 |
| `gen.jq` | Undocumented; the name suggests a coupling strength (05 §1.2, I) | None | n/a | Assembly-stamped | Constant 0 everywhere (01 §5) | n/a | 05 |
| `gen.zz` | Static ZZ, in GHz (05 §1.2); IBM does not document `zz_<ab>` (05 §1.1) | Re-determined device-wide: 484 of 486 value bursts change at least 170 of 176 couplers (05 §1.4, I; counts V) | Bursts, median gap 5.16 h (05 §1.4) (V) | Assembly-stamped: a file time only (01 §3) | Informative at day resolution; exact zeros are a missing marker; 3 couplers frozen since 2026-07-10 (05 §1.4) | Median 6.18 kHz (V approx: 6.23 with the verifier's filter); record 10% 3.05 kHz, 90% 13.8 kHz; 13 couplers ever negative (05 §0, §6.3) | 05 |
| `gen.lf`, `gen.lf_chain` | Layer fidelity of the best N-qubit sub-chain (IBM documentation; McKay et al. 2023) (06 §1.2) | Six pre-selected 100-qubit chains, best sub-chain per N (06 §1.2) | Own cycle, median gap 26.5 h, 83 events; the first value, stamped 2026-05-10, is carried until 2026-07-01 (06 §0, §3.7) | Measured stamp, but later than `last_update_date` in 217 files and later than the filing poll in 49 of 60 checkable live files (06 §6.2 item 1) (V) | Informative (device level); chain re-selected at most events, 59 distinct `lf_100` chains in 83 (06 §4) (V) | `lf_100` median 0.5449 (10% 0.5069, 90% 0.5809); EPLG(100) 0.00489 (06 §2.5) (medians V) | 06 |
| `file.*` arrays and `meta.json` | Document provenance and structure | n/a | 1,760 files; 443 historical fetches from 2026-08-05 (01 §6, 06 §2.1) (V) | `last_update_date` equals the newest measured stamp in only 0.195 of files (06 §2.2) (V) | Structural | 760 qubit-record states (V); 4 target sets; `backend_version` 1.3.37 throughout (01 §6) | 06 |

## 3. The dependency map

A compact picture of what relates to what (ASCII; numbers and sources in the table below):

```
  AXIS 1: READOUT QUALITY (07 §7.5, V)          AXIS 2: COHERENCE AND GATES (07 §7.5, V)
  +----------------------------------------+    +--------------------------------------------+
  | RO = mean of P(0|1) and P(1|0)    (A)  |    | T1 ====== T2      same round 0.70 (02; V)  |
  | P(0|1) --- P(1|0)  0.908 across qubits |    | T1 ------ sx      -0.434 across qubits (04)|
  | init_error --- P(1|0)  0.822 / 0.722   |    | sx(a)+sx(b) --- cz  0.577 across couplers  |
  | measure_2 --- RO   0.852 / 0.382       |    | cz ====== rzz     0.896 across couplers    |
  | thresholds: procedure marker           |    | coherence limit = 0.40 of sx error (04),   |
  | asymmetry A ~ T1 decay  0.423 (03)     |    |   0.33 of cz error (05)                    |
  +----------------------------------------+    | lf_N  = 1.4x the isolated-cz prediction    |
                  ^                             +--------------------------------------------+
                  |   within a qubit, nearest events: |r| <= 0.06 (07 §7.2);    ^
                  +---- no between-qubit level link (07 §7.1, V); no lead or lag -+
                        (07 §7.3); joint large deviations, tail only (07 §7.4, W)

  zz: unrelated to cz and rzz (05 §7.4); -0.043 with RO within a qubit, candidate (07 §7.2)
  device-wide common mode: 0.012 to 0.130 of residual variance (07 §3.1)

  recomputed by a verifier (V): T1-T2 0.70, T1-sx -0.434, sx-cz 0.577, cz-rzz 0.896, lf_N 1.4x
    (02, 04, 05, 06 Verification); A ~ T1 decay 0.423 is 0.394 on fresh-only records and
    init_error--P(1|0) 0.822 is 0.850 per event (03 Verification, V approx); the
    P(0|1)--P(1|0), measure_2--RO and within-qubit init_error links were re-run only (M)
```

Pairs with two numbers give the across-qubit and the within-qubit (same session) correlation.

| Link | Measured strength and form | Direction | Evidence | Source |
| --- | --- | --- | --- | --- |
| RO and the published pair | RO = (P(0\|1) + P(1\|0)) / 2 in every same-session record (188,100 with identical stamps, 72,900 staggered); fails in 11,263 records, 99.956% of them with a stale P(0\|1) | Arithmetic | A (counts re-counted in 03 Verification) | 03 §0 item 1 |
| Aliases and copies | `x`, `id`, `rx`, `xslow` = `sx`; `measure` = RO; the two coupler directions identical; reset = t_ro + 24 ns | Equal values; a copying mechanism is not shown (04 Verification) | A (re-counted in 03, 04 and 05 Verification) | 01 §5, 04 §0, 05 §1.3, 03 §1.2 |
| `T1` and `T2`, same round | Pearson 0.70 (Spearman 0.69), positive on all 155 qubits; robust to the level (0.701 and 0.698 with two level definitions; 0.714 from first differences at 18 to 30 h, no level; 0.69 after removing each round's median deviation; placebos -0.03 and 0.05 to 0.07; 02 Verification); slope of `T2` on `T1` deviations rises with `s` (Spearman 0.92 across qubits); `T1` against `Gamma_phi` -0.32 | None established. A component shared by the two experiments of a round, which a real change of the qubit or an artefact common to both of IBM's experiments would produce (02 Verification); a common defect (TLS) is the literature candidate for the first (Schlör et al. 2019) | Correlation V (02's verifier; 07's control 0.6928); "at least 0.49 of the variance is shared real change" W: at least about half is shared between the two fits, not shown to be real (the Cauchy-Schwarz step is correct and still needs independent fit errors); slope and `Gamma_phi` figures M | 02 §4.2 and Verification; 07 §7.2 and Verification |
| `T1` dips and `T2` | `T2` below its level in 97.9% of 621 paired factor-2 `T1` dips, by more than the dip alone predicts (median -0.234 against -0.194 decades) | `T2` moves with `T1`; upheld as a shared change, with the same limits as the row above (02 Verification) | Dip count V (630 of 19,595 on 151 qubits); 97.9% M; "real drop" W | 02 §4.2 and Verification |
| `T1` and `T2`, across qubits | Spearman 0.30 of per-qubit medians; `T2` and `Gamma_phi` -0.96 | n/a | M | 02 §7 |
| P(0\|1) and P(1\|0) | Across qubits 0.908; P(0\|1) the larger in 87.63% of events | Shared overlap error (I) | M | 03 §7.1 |
| `init_error` and P(1\|0) | Across qubits 0.822 (0.850 per event in 03 Verification); within a qubit, same session, 0.722; P(1\|0) over `init_error` a median 1.95 | Residual population adds to P(1\|0) (I; IBM's definition carries a prior-\|1> condition that 03 omits, so the direct-addition reading is an inference, 03 Verification) | Across V approx; within and ratio M | 03 §7.1 and Verification |
| `init_error` presence and readout | The 40 qubits without it have median RO 0.0331 against 0.0071 (p = 1.3e-20; 0.0314 against 0.0076 with the verifier's median definition) | Withheld where readout is poor (I) | V approx | 03 §7.3 and Verification |
| `measure_2` and RO | Across qubits 0.852; within 0.382; per-qubit ratio median 1.25 (10% 0.79, 90% 2.87) | n/a | M | 03 §7.1 |
| Thresholds and sessions | Threshold changes in 208 of 343 intraday sessions against 20 of 97 daily ones | Procedure link | M | 03 §7.1 |
| Readout and `T1` decay (assigned link) | Across qubits the asymmetry A follows `1 - exp(-t_ro/T1)` (Spearman 0.423, Theil-Sen slope 0.310; 0.394 on fresh-only records in 03 Verification); P(0\|1) alone does not (0.016; 0.034 in 03 Verification); within a qubit `T1` changes do not move P(0\|1) (-0.014; -0.049 within 3 h); `T1` dips leave P(0\|1) unchanged (relative median 0.997, p = 0.28) | `T1` to decay error, visible between qubits only. 03's reading that A matches an effective decay over half the readout window is weakened: the length change gives 1.6 times the full-window and 3.1 times the half-window prediction, and residual excited population also lowers A (03 Verification) | Across-qubit correlations V approx; effective-time reading W; within-qubit and dip figures M (dip claim upheld as reported, not re-run in detail) | 03 §7.2 and Verification |
| Readout length change, 2026-06-08 | Per-qubit RO -0.137 decades over 7 days (1.9% of qubits up); 03's verifier: -0.138, beyond the placebo minimum -0.084 over 70 days; P(1\|0) -0.269, P(0\|1) -0.079; A +0.0016 against +0.00094 predicted from the longer window, but the A change (+0.00146) lies inside the placebo range (maximum +0.00153) | RO drop at the change, confounded with the first `measure.threshold` in the same file and with a schedule restart on 06-08/09; readout's largest drop is on 2026-05-17 (-0.20 decades) with no known event, and the 2026-07-30 length change shows no response, so "one clear exception" is too strong (06 Verification) | RO drop V (06's verifier: -0.105 to -0.116 with window medians; `T1`, `T2`, `sx` show no step); A response W; attribution to the length change W | 03 §7.4, 06 §3.5, both Verification |
| `sx` and `T1` (assigned link) | Across qubits -0.434 (CI -0.558 to -0.291); within, same round -0.062 (-0.060 in 04 Verification) against a shifted null 0.002 +- 0.008; -0.096 within 1 h against -0.024 at 1 to 6 h, near stronger than far in every month; near pairs set against the previous or next `T1` event give -0.021 and -0.003 against -0.091 (04 Verification) | Not established. A component shared between the two experiments; "a real fluctuation on a timescale of hours" is weakened, since near against far also separates the same calibration job from a different one, and a shared SPAM or state-preparation drift would couple both (04 Verification) | Correlations V; timescale and "real" W; near-far by month M | 04 §7 and Verification |
| `sx` spikes and `T1` dips | 16.7% of `sx` spikes coincide with a 1.5-fold `T1` dip against a shifted-null mean 10.9% (max 14.0%); the coherence limit accounts for a median 0.5% of a spike's excess | Not established | M | 04 §7 |
| `sx` and its coherence limit | Limit over reported error: median 0.402 (10% 0.178, 90% 0.992); across qubits 0.199 | Decoherence is a minority share (I) | Ratio quantiles V; 0.199 M | 04 §7 and Verification |
| `cz`, `rzz` and their coherence limit | Limit over error: median 0.333 (`cz`), 0.351 (`rzz`); across couplers 0.334 (0.318 with the verifier's qubit-level reduction) and 0.391 | As above | 0.334 V approx; others M | 05 §7.2, §7.3 and Verification |
| `cz` and its qubits' `sx` | Across couplers 0.577 with `sx_a + sx_b`; 0.539 given the limit (0.542 recomputed); readout adds -0.012 given both (-0.004); within couplers 0.05 or less for changes | Two candidate mechanisms (I): 2Q RB contains 1Q gates (IBM's page, re-fetched by 05's verifier, says the two-qubit benchmark alternates single-qubit Clifford sequences with two-qubit gates), or a qubit-level defect. "`sx` explains more than coherence" is weakened to a correlation statement: the limit is a proxy built from `T1` and `T2` stamped hours apart (05 Verification) | Correlations V (partials approx); "explains" W; within-coupler figure M | 05 §7.3 and Verification |
| `cz` and `rzz` on one coupler | Across couplers 0.896; matched changes 0.137 (null 0.012); local deviations 0.205 within 1 h, 0.078 at 2 to 4 h, 0.099 at 12 to 24 h (not monotone); per `cz` round (104 rounds) the across-coupler Spearman has median 0.159 at offsets up to 2 h and 0.055 beyond and correlates with offset at -0.393 (p 3.8e-5); the 12 to 24 h bump remains unexplained (05 Verification) | Shared coupler state | 0.896 V; decline with offset V (changed test, since 05's proposed stratification is infeasible as written); matched changes and gap bins M | 05 §4.4, §7.1 and Verification |
| Couplers sharing a qubit | Local deviations 0.220 (`cz`), 0.226 (`rzz`), against -0.008 at four or more hops; 90.9% of 230 `cz` pairs positive. 05's verifier: 0.220 and 0.225; hops 2 and 3 between -0.008 and -0.020; cross-round (lag 1, lag 2) correlations -0.035 and -0.050 (`cz`), so not a slow shared shift leaking through the detrending; per shared qubit a median 0.186 (`cz`) and 0.20 (`rzz`), positive for 95% of 43 and 42 qubits | Shared qubit or region (I) | V | 05 §4.4 and Verification |
| `zz` and `cz`, `rzz` | Across couplers 0.010 and -0.027; within -0.020 and -0.014 | None | M | 05 §7.4 |
| Non-68 ns couplers and `zz` | The five couplers with 88 or 116 ns have low `|zz|` (Mann-Whitney p 1.1e-4; 1.09e-4 recomputed), found by inspection | Hypothesis only | V, exploratory (the number of comparisons scanned is unknown) | 05 §7.4 and Verification |
| `lf_N` and its chain's `cz` | `ln(lf_N)` over the isolated prediction has medians 1.36 to 1.41, flat in N (recomputed 1.37, 1.42, 1.42 for N = 10, 50, 100); over events Spearman 0.269 (n = 76) | Layered gates fail about 1.4 times as often (I: crosstalk, idling, value age) | V (upheld as measured; cause open) | 06 §7.2 and Verification |
| Between-qubit levels, 23 cross-family pairs | 0 of 23 survive Benjamini-Hochberg (smallest q 0.514); every 95% interval inside -0.323 to 0.291 | None | V | 07 §7.1 |
| Two quality axes | Readout factor eigenvalue 3.83 (38%), coherence-and-gate factor 2.58 (26%), both above parallel analysis, 154 qubits | n/a | V | 07 §7.5 |
| Archetypes | Ward clusters never beat a correlated-Gaussian null (p 0.154 to 0.965); bootstrap ARI 0.37 to 0.42 | None | M (verifier re-ran the owner's script only) | 07 §7.6 |
| Within-qubit cross-family co-movement | 11 of 23 pairs survive raw, 10 with the common mode removed; largest `sx`-P(0\|1) 0.057 (15,993 events) against controls 0.693 and 0.781 | Worse together, except `zz` and `sx`-P(1\|0) | Value V (0.0574); counts M | 07 §7.2 |
| Gap dependence of that co-movement | `sx`-P(0\|1) 0.108 within 0.5 h, 0.069 at 0.5 to 2 h, 0.028 at 2 to 6 h, then about 0 at a +-7 day level window; at a +-2 day window 0.032, 0.058, 0.005 | A shared component on a timescale between hours and days, window-dependent | W | 07 §4.2, Verification claim 1 |
| Joint large deviations | Same-day qubit-null lifts 1.22 to 1.63 for 11 pairs at 3 robust sd; 3 or more of 7 groups flagged together 1.66 times as often as chance (adverse 2.38); at 2 sd the `sx`-P(0\|1) lift is 1.07 | Extreme tail only | W | 07 §7.4, Verification claim 3 |
| `zz` and readout | -0.043 with RO (166,855 matched events), same sign at qubit-day (-0.061) and device-day level (-0.251, not surviving) | Not placeable in time: `zz` carries a file time | Value V; candidate only (I) | 07 §7.2 |
| Device-day changes | 8 of 55 family pairs survive, 7 inside a family; the cross-family survivor is P(1\|0) against `sx` (-0.341, 113 days) | Candidate shared driver (I) | M | 07 §3.2 |
| Lead and lag | 0 of 45 (or 44) scorable directions survive in each of three models; best out-of-time ratio 0.99854 (`init_error` to `T2`) | None | M (re-run only) | 07 §7.3 |
| Device-wide common mode | Robust share of residual variance 0.012 (`zz`) to 0.130 (`T1`); 5.5% of `T1` deviation variance in 02's form; RO session mean 1.38% against 0.64% expected | Small, largest for coherence | M | 07 §3.1, 02 §5, 03 §4.6 |
| Readout and lattice role | Readout factor score against qubit degree, Spearman 0.420 (07 §5); Moran's I -0.196 (RO; p 0.009 recomputed), -0.430 (`measure_2`). 03's verifier: RO differs by degree class (medians 0.00757 for degree 2, 0.01196 for degree 1, 0.01428 for degree 3; Kruskal-Wallis p = 3.5e-7), and after removing each degree class's median RO's Moran's I is -0.047 (p = 0.59) | Tied to the qubit's degree class; 03's "checkerboard" with a frequency reading is not supported for RO, since on heavy-hex the degree classes alternate (03 Verification); `measure_2` not re-tested | RO Moran's I V; checkerboard reading W; degree-class figures measured once, by the verifier | 07 §5, 03 §5 and Verification |
| `sx` and degree | Degree-3 median 2.69e-4 against 3.22e-4 for degree 2 (p = 0.003, reproduced; within the long rows p = 0.013). 04's verifier: `T1` shows the same degree pattern (p = 0.0037; medians 132, 125, 142 us for degrees 1, 2, 3), `T2` does not (p = 0.38) | Not established; the `sx` effect may run through `T1` (04 Verification, a lead for 02, not a finding) | V; the `T1` lead measured once, by the verifier | 04 §5 and Verification |
| `cz`, `rzz` levels in space | Moran's I 0.263 and 0.383 on the line graph; `|zz|` none (-0.002) but 1.42 times larger on bridges | Clustering of bad couplers, consistent with the qubit-sharing effect, so probably one phenomenon (05 Verification, I) | `cz` V; `rzz` and `zz` M | 05 §5.2 and Verification |
| Daily sequence | Relative to each `T1` round: `init_error` -1.71 h, readout -0.74 h, `measure_2` -0.59 h, `T2` +3 s, `sx` +0.93 h, `cz` +3.14 h, `rzz` +4.25 h; `lf` not locked (+3.05 h, IQR -4.93 to +6.93 h) | Schedule order (dependency order is I) | Readout offset, `T2` stamp lag (1 to 112 s) and the `T1` and `cz` round counts and gaps V (02 and 06 Verification); other offsets M | 06 §3.2, 07 §1.2 |

## 4. Root questions for the paper

### 4.1 The non-persistent component: estimation noise, or aliased fast dynamics?

**The families side by side.** Variogram of log10 values from `ddload.variogram` in every family
(01 §7); "robust" as each owner defines it. Verification status per row: the `T1`, `sx`, `cz`,
`rzz`, `|zz|` and `lf_100` lag-1 values, the `T1` variogram and ratio, the `sx` and `cz`/`rzz`
ratios and RO's 4.252 units were recomputed by the verifiers and match (02, 03, 04, 05, 06
Verification); the sub-day evidence of `T1`, `cz` and `rzz` was weakened or refuted, as marked;
the rest is M.

| Family | Shortest bin used (pairs) | Semivariance there | Long-lag semivariance | Short over long (robust) | Evidence below the shortest bin | Lag-1 of log changes | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `T1` | 18 to 30 h (16,087) | 0.0146 | 0.0179 at 744 to 1,488 h | 0.817 (0.679); after 2026-08-05 0.934 (0.896) | Nine device-wide re-runs down to 3.86 h apart: change a median 0.96 of the adjacent day-lag change (Wilcoxon p = 0.82). W: the verifier's pairing gives 1.05 (all) and 1.19 (after 05-30), so the ratio is method-dependent; only one occasion (2026-06-12, 147 non-independent qubits) is below 6 h and only five fall after 05-30; supported is "no rise from about 4 to 24 h", not a decorrelation lag (02 Verification) | -0.493 (-0.497 recomputed) | 02 §3.3, §4.1 and Verification |
| `T2` | 18 to 30 h (17,002) | 0.0151 | 0.0191 | 0.791 (0.702); after 2026-08-05 0.884 | Same test: 0.89 (p = 0.65); not recomputed, and the same occasion limits apply | -0.496 | 02 §3.3, §4.1 |
| `Gamma_phi` | 18 to 30 h (15,884) | 0.0177 | 0.0218 | 0.813 (0.717); after 2026-08-05 0.987 | n/a | -0.490 | 02 §3.3, §4.1 |
| RO, intraday sessions only | 2 to 4 h | 0.018524, of which shot noise 0.002311 (share 0.125) | 0.042786 | 0.433; in shot-noise units 4.252 at 2 to 4 h (4.253 recomputed; an iid binomial placebo through the same rule gives 1.005, 03 Verification), 4.759 at 18 to 30 h, 10.745 at 744 to 1,488 h | 0.5 to 2 h: 3.467 units pooled over 933 qubit pairs from the 5 intraday session pairs closer than 2 h (session-pair median at 1 to 2 h 3.367); not resolvable | -0.443 (stamp rule) | 03 §3.4, §4.3, §4.4 |
| P(0\|1), intraday | 2 to 4 h | 0.017901, shot share 0.186 | 0.034887 | 0.513; 2.530 units at 2 to 4 h | As RO | -0.469 | 03 §3.4, §4.3 |
| P(1\|0), intraday | 2 to 4 h | 0.067116, shot share 0.184 | 0.123376 | 0.544; 5.794 units at 2 to 4 h | As RO | -0.434 | 03 §3.4, §4.3 |
| `sx` | 18 to 30 h (15,843) | 12.4e-3 | 14.9e-3 at 744 to 1,488 h | 0.81 (0.83) over 744 to 3,624 h; per-qubit median 0.96 | 6 to 9 h (456 pairs) over 18 to 30 h: 0.97 (CI 0.73 to 1.29); the 456 pairs come from May (302) and August (154) only, and within May alone 6 to 9 h (0.0101) is above 18 to 30 h (0.0079), so the conclusion holds (04 Verification) | -0.490 (lag 2 -0.003) | 04 §4 and Verification |
| `cz` | 18 to 30 h (16,737) | 0.0134 | 0.0209, mean of the bins from 744 h | 0.64 (0.62); per-coupler median 0.82 | 11 device-wide re-measurement occasions 3 to 16 h after a round: 0.727 of the 18 to 30 h value on average. W: the fraction rises with the gap (0.33 of the one-round value at 2 to 4 h, 0.64 at 6 to 9 h, 0.73 at 9 to 12 h, 0.89 at 12 to 18 h); "second calibrations" asserts a recalibration that 05 §4.2 cannot show. R: the Wilcoxon p = 0.0011 against the preceding gap was pseudo-replicated over coupler pairs; at occasion level the sign test gives p 0.065 and the signed-rank test 0.10 (05 Verification) | -0.448 | 05 §3.1, §4.1, §4.2 and Verification |
| `rzz` | 18 to 30 h (12,815) | 0.0131 | 0.0242, mean of the bins from 744 h | 0.54 (0.54); per-coupler median 0.73 | 6 occasions: 0.783 on average. W: it rises with the gap (occasion semivariance 0.0076 for gaps under 8 h against 0.0130 for longer; Spearman with the gap 0.37). R: the p = 2.9e-6 becomes 0.69 (sign test) and 0.56 (signed rank) at occasion level, so "short change below the preceding" is not established for `rzz` (05 Verification) | -0.425 | 05 §3.1, §4.1, §4.2 and Verification |
| `|zz|` | 0 to 2 h of file time (2,404) | 0.00371 | 0.00581 at 744 to 1,488 h | 0.60 (0.83), as 05 defines its long-lag level | Rises to 0.00488 at 2 to 4 h, then flat to about 372 h | -0.513 (lag 2 0.016) | 05 §1.4, §4.3 |
| `lf_100` (EPLG, process form) | 18 to 30 h (71) | 0.00138 | 0.00169 at 744 to 1,488 h | 0.82 (0.58); `lf_10` 0.94 (0.91); `lf_50` 0.65 (0.55) | None (one event per cycle) | -0.56 (-0.565 recomputed; -0.36 to -0.56 across N) | 06 §0, §4 |

**Reading the table.** The comparisons are of order of magnitude only. The shortest bins differ
(2 to 4 h for readout because only intraday sessions are used; 0 to 2 h of file time for `zz`;
18 to 30 h elsewhere), the long-lag denominators differ (the 744 to 1,488 h bin in 02, 03 and 06;
744 to 3,624 h in 04; the mean of the bins from 744 h in 05), the robust estimators differ
(Cressie-Hawkins in 05), and 03's standardized units are multiples of each pair's shot-noise
variance, not decades squared. `T1`'s pooled sub-day bins are period-confounded (302 of the 447
pairs at 6 to 9 h fall before 2026-05-30, in the quiet window of section 4.2), which is why 02
replaces them by the matched test (02 §4.1); that matched test was itself weakened by 02's
verifier (one occasion below 6 h; a method-dependent median ratio, 0.96 against 1.05). `sx`'s
pooled short bins also mix periods (May and August only), which its verifier found does not
change the conclusion (04 Verification). The two readout shot-noise shares in this overview
are different quantities: 03 §4.7 gives 0.235 of RO's robust shortest-lag variability (0.125 on
the pooled log10 scale), from intraday sessions at 4,096 shots; 07 §4.4 gives a median 0.202 of
each qubit's residual variance against a +-7 day level, assuming 4,096 shots for every session,
although 03 §4.5 leaves open whether the daily sessions use 2,048.

**What the evidence supports.**

1. *A slowly moving level plus a nugget, in every family.* No variogram is flat (a fixed level
   plus noise) and none grows in proportion to the lag (a random walk); the slow part grows over
   weeks to months at a decelerating rate (02 §4.1, 04 §4, 05 §4.1). Every lag-1 autocorrelation
   sits between -0.36 and -0.56, near the -0.5 of independent scatter around a level (table).
2. *The nugget is about full-size at the shortest lag the archive resolves for `sx` and readout,
   and probably for `T1`:* below 6.3 h for `sx` (upheld, 04 Verification); flat from about 3 h to
   12 h for RO (session pairs: 4.209 shot-noise units at 3 to 4 h, 4.493 at 9 to 12 h,
   interquartile range at 3 to 4 h 3.583 to 4.948; 03 §4.4); for `T1` the verified statement is
   "no rise of the semivariance from about 4 to 24 h", and the matched test's one occasion below
   6 h cannot fix a decorrelation lag (02 Verification). The exception is `cz` and `rzz`, whose
   verifier found that the short-lag semivariance rises with the gap: the pooled bins give 0.33
   of the one-round value at 2 to 4 h, 0.64 at 6 to 9 h, 0.73 at 9 to 12 h and 0.89 at 12 to
   18 h, and the semivariance of the device-wide re-measurement occasions 3 to 16 h after a round
   rises with their gap (Spearman 0.36 `cz`, 0.37 `rzz`) (05 Verification, replacing 05 §4.2's
   "about three quarters within hours"). Apart from `|zz|`, whose lags are file times, and
   readout's 0.5 to 2 h bin, which rests on 5 session pairs and is not resolvable (table; 03
   §4.4), this is the clearest place where the archive shows the component building up over
   hours, on 11 and 6 occasions; whether that is a correlation time of the device or the effect of a
   recalibration between occasions is not separable (05 §4.2), and the occasion-level sign tests
   of "short change below the preceding" give p 0.065 (`cz`) and 0.69 (`rzz`).
3. *Readout's known estimation noise is a minority.* Binomial shot noise explains about a quarter
   of RO's shortest-lag variability (robust 0.235), two fifths for P(0|1) and a sixth for P(1|0);
   the excess over shot noise is 3.252 shot-noise units at 2 to 4 h and is not explained by
   discriminator re-calibration (median |z| ratio 1.023, p = 0.584), a device-wide common mode or
   neighbours (03 §0 items 5 and 6, §4.6). Upheld: an iid binomial placebo through the same
   plug-in rule gives a ratio 1.005 against 4.25 observed, so the excess is not an artefact of
   the rule (03 Verification).
4. *Shot noise is an unlikely source for `T1`:* it would equal the `T1` nugget only if IBM's whole
   `T1` fit used fewer than about 74 to 167 shots under median readout, for the assumed designs
   (02 §4.2). Upheld and reproduced (74.0 to 167.4); it is a lower bound for a correct
   exponential model, so misspecification and change during the experiment are not covered (02
   Verification).
5. *Part of the component is shared between separate experiments,* which independent errors of
   separate experiments cannot produce, but which an input common to both experiments can (02 and
   04 Verification): `T1` and `T2` in the same round 0.70 (02 §4.2); `sx` and same-round `T1`
   -0.062, -0.096 within 1 h (04 §7); couplers sharing a qubit 0.22 (05 §4.4); `cz` and `rzz`
   0.205 within 1 h (05 §4.4); `sx` and P(0|1) 0.057 (07 §7.2). The verifiers tested the first
   four against a slowly moving level, each in its own way: `T1`-`T2` gives 0.70 with two level
   definitions and 0.714 from first differences with no level at all, and 0.69 after removing
   each round's median deviation (02 Verification); `sx`-`T1` near pairs set against the previous
   or next `T1` event of the qubit give -0.021 and -0.003 against -0.091 (04 Verification);
   couplers sharing a qubit have cross-round correlations of -0.035 and -0.050, "so it is not a
   slow shared shift leaking through the detrending" (05 Verification); the `cz`-`rzz` decline
   with offset holds per round (Spearman with offset -0.393, 104 rounds; 05 Verification). Only
   07's `sx`-P(0|1) pair shrinks under a shorter level window (07 Verification claim 1). 02's dip
   analysis points the same way (in 97.9% of 621 paired factor-2 dips `T2` is also below its
   level; 02 §4.2), but its "single round" character is consistent with the data rather than
   demonstrated: consecutive dips are 28 against 21.1 expected (p = 0.10), and at 25 h sampling a
   dwell of a few hours could not produce consecutive dips anyway (02 Verification). 02's own
   caveat remains: a shared artefact that biases both fits in the same round would produce all of
   this (02 §4.2).
6. *Its size is not a fixed property of the device:* the round-to-round robust semivariance of
   log `T1` was 0.000404 to 0.000686 in 13 rounds of 2026-05-15 to 05-27 against 0.0146 typical
   later, with a further step at 2026-06-26/29 (02 §3.2; section 4.2; the steps and round-step
   medians reproduced and the claim upheld in 02 Verification).
7. *Tails are one-sided towards worse values:* `T1` deviations below -0.301 decades 3.19% against
   0.106% above (02 §4.2); `sx` 1.95% of events more than a factor two above the level against
   0.28% below (04 §4); `cz` 3.35% above twice the coupler median against 1.28% below half of it
   (05 §2.1). This fits discrete degrading events (for example a defect moving into resonance)
   and also one-sided fit failures (04 §4, I).
8. *The size is plausible for TLS dynamics sampled daily:* Burnett et al.'s two qubits scatter by
   a log10 variance of 0.0093 and 0.0077 over about 65 h, against 0.0103 (robust) to 0.0146
   (classical) for `T1` here at one day (02 §4.2). That is another device; it makes the reading
   plausible, it does not measure this one.
9. *The device-wide part is small and has no diurnal signature:* robust common-mode shares 0.012
   to 0.130 (07 §3.1); no detected hour-of-day dependence of any device median, while the cycle
   walks through every hour (06 §3.6, §4), which is evidence against a strong device-wide diurnal
   driver and says nothing about local fluctuations; not rejecting uniformity is not proof of it
   (06 Verification, upheld with that caveat).

**What the evidence does not support.**

- *An attribution of the unshared majority.* Outside the `T1`/`T2` pair every shared part is
  small (at most 0.130 in absolute value for 07's cross-family pairs at the shortest gap, 07
  §4.2; 0.22 for couplers sharing a qubit, 05 §4.4, and the unshared part is not characterised
  there, 05 Verification); most of each family's component is shared with nothing the archive
  records. It is consistent with per-experiment estimation error, with fluctuations that affect
  one quantity only, and with fluctuations faster than the gap between two experiments (07 §4.5).
- *A correlation time, except possibly for the two-qubit gates.* For `T1` nothing below about
  4 h is observed and the sub-day test rests on one occasion below 6 h (02 Verification);
  nothing below 6.3 h for `sx`, about 3 h for readout (5 intraday session pairs below 2 h), and
  `zz` lags are file times (02 §4.1, 04 §4, 03 §4.4, 05 §4.3). For `cz` and `rzz` the
  semivariance rises between 2 to 4 h and 12 to 18 h (item 2; 05 Verification), on 11 and 6
  occasions and without a way to tell device dynamics from recalibration.
- *Physical against procedural, even for the shared part.* A real fluctuation of the qubit and a
  calibration input shared by both experiments predict the same cross-experiment correlation (04
  §4, 05 §4.5, 07 §4.5). The verifiers name concrete versions of the second reading: an artefact
  of IBM's procedure common to the `T1` and `T2` experiments of a round (02 Verification); a
  shared SPAM or state-preparation drift, and same-job against different-job membership in
  place of an hour timescale (04 Verification); for `cz` against `sx`, the single-qubit Clifford
  sequences that IBM's two-qubit benchmark alternates with two-qubit gates (05 Verification). 07's
  verifier adds a further reading, a shared level movement over 2 to 7 days (07 Verification
  claim 1); the level controls of item 5 argue against it for the `T1`-`T2` and shared-qubit
  couplings (02 and 05 Verification), but the +-2 d window test itself ran only on 07.
  Re-tuning of the gates at each round (candidate (c) of 05 §4.5) is not excluded by any fetched
  source.
- *02's lower bound as a statement about real change.* The number is verified: the 0.70
  correlation survives two level definitions, first differences without a level (0.714),
  removal of each round's median deviation (0.69) and placebos (-0.03 for the next round's `T2`,
  0.05 to 0.07 for another qubit's), and the Cauchy-Schwarz step is correct (02 Verification).
  What it supports is "at least about half of each `T1`/`T2` deviation's variance is shared
  between the two fits", under independent fit errors (02 §4.2); 02's "real" and "contradicted"
  are weakened, since a same-round artefact common to both experiments is not excluded (02
  Verification). Whether a round's readout or initialisation change moves both `T1` and `T2` was
  not tested by anyone (02 Verification).
- *A noise floor for the RB families.* IBM's RB sequence lengths, counts and shots are not
  published, the aliases report identical values, not replicates, and the documents carry no
  per-value uncertainty (04 §1, §4; 05 §4.5).

**Conclusion, stated precisely.** The evidence excludes two simple readings: that the component
is entirely independent estimation error around a fixed level (contradicted by the slow level and
by cross-experiment correlations, most robustly by the same-round `T1`/`T2` correlation, which
its verifier reproduced with two level definitions and from first differences, unless a
same-round artefact common to both of IBM's experiments biases both fits), and that readout's
component is binomial shot noise (shot noise is a minority; upheld against an iid binomial
placebo). It does not establish that the bulk is physical: apart from `T1`/`T2` the shared parts
are small; their timescale is window-dependent for 07's pairs, confounded with same-job against
different-job membership for `sx`-`T1` (04 Verification), and rising over hours only for `cz`
and `rzz`, where recalibration is not separable (05 Verification); and the unshared majority
has no discriminating test in the archive. This overview therefore does not label the component
as IBM estimation noise, nor as physical.

**What would discriminate.** Recommendations only; hardware time is the team's decision.

| Measurement or analysis | What it would separate | Source of the proposal |
| --- | --- | --- |
| Own back-to-back repeats on a few `ibm_fez` qubits and couplers at minute spacing for several hours: `T1` and Hahn echo (Qiskit Experiments), single- and two-qubit RB, assignment experiments with known shots; fit uncertainties recorded; with and without recalibration between repeats | Estimation noise predicts a variogram flat from the shortest lag at the replicate (fit) variance and equal to the archive's nugget; aliased fast dynamics predict a curve that rises over minutes to hours to the nugget, with replicate variance below it; recalibration variability predicts jumps aligned with the recalibrations | 02 §9, 03 §9 item 1, 04 §9, 05 §9 item 1, 06 §4, 07 §9 |
| IBM metadata: RB settings, per-value fit uncertainties, job identifiers, the daily readout shot count | A computable floor for each RB family; whether near and far pairs come from one job | 04 §9, 05 §9 item 1, 03 §9 item 2 |
| Archive only: repeat 07's level-window test (+-2 d against +-7 d) on 02 §4.2, 04 §7 and 05 §4.4. Partly addressed by other controls: 02's verifier used a 7-day level and first differences, 04's the previous and next `T1` events, 05's cross-round lags (02, 04, 05 Verification); the window test as such has run only on 07 | Whether the same-round and near-in-time couplings survive as hour-scale or are multi-day level movements; for `sx`-`T1` the remaining confound is job membership, which needs job identifiers (row above) | 07 Verification claim 1 (extension by this overview) |
| Archive only: stratify the `cz`-`rzz` decline by round. Done by 05's verifier in a changed form (per-round Spearman against offset -0.393, p 3.8e-5, 104 rounds), since the stratification proposed by 05 is infeasible as written; the non-monotone 12 to 24 h bump remains unexplained | Whether the decline with offset is a controlled decay | 05 §9 item 3; 05 Verification |
| Archive only, later refs: accumulate intraday readout session pairs closer than 2 h | A readout variogram below 2 h; a rise between 0.5 h and 3 h would put a correlation time there | 03 §4.7, §9 item 1 |
| Archive only: whether 07's coincidence days are followed by lasting level shifts or returns | A defect moving away against a transient | 07 §9 |

### 4.2 Is the size of the component stationary, and what happened in May 2026?

**Evidence.** 02 §3.2: device-wide `T1` steps of -0.162 decades at the 2026-05-15T05 round and
+0.132 at the 2026-05-28T06 round (both reproduced, and the quiet-window claim upheld, in 02
Verification), and between them the quiet window of 13 rounds in which a
qubit's `T1` barely changed (robust semivariance 0.000404 to 0.000686 against 0.0146 later; lag-1
autocorrelation of changes -0.33 against -0.486 and -0.501 later; `T1`/`T2` co-movement of changes
0.385 against 0.724 and 0.720). Across the boundary at which `xslow` disappears, per-qubit `T1`
rose 0.167 decades on 99.3% of 153 qubits with the qubit ranking kept. A second step in the size
of round-to-round change falls at 2026-06-26/29 (median 0.0092 before, 0.0146 after, Pettitt
p = 5.5e-12), and a `Gamma_phi` step at 2026-07-15/17. 07 §3.2: operational day 2026-05-14 is the
only day on which coherence and every gate family jumped together (`T1` -5.64, `T2` -3.33, `sx`
+3.32, `cz` +2.74, `rzz` +4.40 robust z). 06 §3.5 places PELT points for `T1` at 2026-05-15T22:25
and 05-28T06:03, for readout at 05-17 and 05-27, and notes that May's points coincide with the
schedule's most frequent restarts (06 §3.1); 06's verifier adds that readout's largest
10-round-window drop of the archive is -0.20 decades on 2026-05-17, with no known event (06
Verification). 04 §3: the `sx` spike rate was 1.0% in May against
2.0% to 2.2% later, and the `sx`-`T1` coupling was strongest in May and June (04 §7). 05 §3.2: all
four `cz` device splits fall in May and June.

**Juxtaposition by this overview (dates only, not a test).** The first `xslow` run, from
2026-05-14T12:32:42Z to 2026-05-29T16:46:42Z (01 §5), contains the multi-family jump day, both
`T1` steps and the whole quiet window; 02 tested only its end boundary and found nothing that
links them causally (02 §3.2). The 2026-06-26/29 step spans the 61.8 h file gap of 2026-06-27 to
06-29 (06 §2.1), so its timing is uncertain to within that gap.

**For a change in how values were produced:** simultaneity on almost every qubit, the multi-family
jump, and the coincidence with the `xslow` run and the restarts. **For a change of the device's
environment:** nothing in the archive excludes a device-wide physical change; 02 concludes that
either the environment or the production of the values changed and that the archive cannot tell
which (02 §0, §3.2).
**Not measured:** whether the quiet window appears in `sx`, `cz`, `rzz` or readout. **What would
settle it:** IBM's release notes or status history for those dates (02 §9); the round-to-round
change-size test of 02 §3.2 applied to the other families over the same windows
(recommendation); re-running on later refs to see whether the post-June size holds (02 §9).

### 4.3 Is part of the component shared across experiments on one qubit, and on what timescale?

**For:** the cross-experiment correlations of section 4.1 item 5, with the level controls the
02, 04 and 05 verifiers ran on them (`T1`-`T2` 0.714 from first differences; `sx`-`T1` -0.021
and -0.003 against previous or next `T1` events; shared-qubit cross-round lags -0.035 and
-0.050); the near-far ordering of 04 §7 in every month (for `T1`, May to September, near -0.179,
-0.122, -0.067, -0.047, -0.078 against far -0.097, -0.025, -0.001, -0.029, -0.006); the
`cz`-`rzz` decline with offset, which holds per round (-0.393, 104 rounds; 05 Verification); and
07's same-day coincidences of large deviations. **Against or limiting:** 07's verifier found that
the `sx`-P(0|1) short-gap correlation falls from 0.108 to 0.032 when the level window shrinks
from +-7 to +-2 days, that raw `T2`-RO has no decay shape (0.018, -0.039, 0.006, 0.020, 0.020),
that `T1`-`init_error` and `T2`-`init_error` rest on about 485 and 496 pairs at about 2.6 to 2.8
standard errors, and that the coincidence lift is a tail effect (07 Verification claims 1 to 3).
04's verifier found that near against far equally separates the same calibration job from a
different one, so the `sx`-`T1` timescale is not established (04 Verification). 05's `cz`-`rzz`
decline is not monotone (0.099 at 12 to 24 h; 05 §4.4, still unexplained in 05 Verification);
each gap bin holds different events (07 §4.2); and the `sx`-P(0|1) size differs by period (0.071
before 2026-08-01, 0.038 after; 07 §3.3). **Reading:** co-movement between experiments on one
qubit or coupler exists and, for `T1`-`T2` and couplers sharing a qubit, is not explained by a
slowly moving level (02 and 05 Verification); its timescale (hours, the duration of one job, or
2 to 7 days for 07's pairs) and origin (qubit, shared calibration input such as SPAM or state
preparation, or shared level step) are open. **What would settle it:** job identifiers from IBM
(section 4.1), the +-2 d level-window test on 02 §4.2, 04 §7 and 05 §4.4, then the hardware
repeats.

### 4.4 Two axes of qubit quality, and the role of the lattice

**For:** two components above parallel analysis, readout fields loading on the first with
intervals above 0.39 and on the second with intervals that include 0 (07 §7.5, V); negative
spatial autocorrelation of readout (Moran's I -0.196 for RO, reproduced at p 0.009, and -0.430
for `measure_2`, surviving rank transformation and removal of `q72`; 03 §5), which 03's verifier
traced to degree class: RO differs by degree (medians 0.00757 for degree 2, 0.01196 for degree
1, 0.01428 for degree 3; Kruskal-Wallis p = 3.5e-7), and after removing each class's median
RO's Moran's I is -0.047 (p = 0.59), so 03's "checkerboard" with a frequency reading is not
supported for RO (03 Verification); the readout factor's score rising with degree (Spearman
0.420; 07 §5), which on a heavy-hex lattice would make neighbours dissimilar (07 §5, I); bridge
qubits with about half the `measure_2` error of row qubits (03 §5); lower `sx` error on degree-3
qubits (04 §5, reproduced at p = 0.0030), with `T1` showing the same degree pattern (p = 0.0037)
and `T2` not (p = 0.38), so the `sx` effect may run through `T1` (04 Verification, a lead, not a
finding); clustering of bad couplers (05 §5.2, reproduced; probably the same phenomenon as the
shared-qubit correlation, 05 Verification, I); stable rankings (RO June against September
0.926, 03 §5; `sx` halves 0.972, 04 §2, reproduced). **Against or limiting:** 03's own
bridge-against-row test found nothing for RO (p = 0.67; 07 §9); `measure_2` was not re-tested by
degree class, and the degree-class figures are a single computation by the verifier; `T1`
against distance from the centre (+0.254) sits exactly at its Bonferroni boundary (02 §5), and
02 finds no neighbour structure in `T1` (Moran's I reproduced; low power, 02 Verification);
there are no archetypes beyond a correlated continuum (07 §7.6); and the cache carries no qubit or resonator frequencies, so a frequency-allocation reading cannot be tested
(03 §5, 04 §5). **What would settle it:** frequencies if the snapshots carry them (03 §9 item 5);
the degree-class test with within-class autocorrelation for `measure_2` and the other readout
fields, now run for RO only (07 §9, 03 Verification); another Heron r2 archive (02 §9, 05 §9
item 7).

### 4.5 What the gate errors contain beyond decoherence

**For "mostly not decoherence":** the coherence limit is a median 0.40 of the `sx` error (04 §7,
reproduced, and the Qiskit Experiments formula confirmed in 04 Verification) and 0.333 and 0.351
of the `cz` and `rzz` errors (05 §7.2); across couplers `cz` correlates with its qubits' `sx`
errors (0.577, reproduced) much more than with its limit (0.334; 0.318 with the verifier's
reduction), and readout adds nothing (05 §7.3); across qubits `sx` follows `T1` (-0.434,
reproduced) more than its limit (0.199) (04 §7); at an `sx` spike the limit accounts for a median
0.5% of the excess (04 §7); layered gates fail about 1.4 times as often as the isolated `cz`
predicts, flat in chain length (06 §7.2; recomputed 1.37, 1.42, 1.42 for N = 10, 50, 100 in 06
Verification). **Limits:** the 13 qubits whose limit exceeds the error all have low `T2`, so the
formula is a proxy rather than a bound where `T2` is poor (04 §7, I); the limit uses `T1`/`T2`
from other rounds, hours away (05 §7.2), so its weaker correlation is partly proxy noise, and
05's "`sx` explains more than coherence" is weakened to a correlation statement (05
Verification). **Open mechanisms:** two-qubit RB contains single-qubit gates unless corrected
(Qiskit Experiments manual, 05 §7.3), and IBM's page, re-fetched by 05's verifier, says the
two-qubit benchmark alternates single-qubit Clifford sequences with two-qubit gates (05
Verification), which would give the observed pattern with no physical coupling; or a qubit-level
defect degrades everything it takes part in. The 1.4 factor mixes crosstalk, idling and the
10.9 h median age of the isolated value (06 §7.2). **What would settle it:** an IBM statement on
whether the reported 2Q error is corrected for its single-qubit part; the shared-qubit
correlation stratified by the shared qubit's `sx` level (05 §9 item 2), which 05's verifier ran
on terciles of 14 to 15 qubits and found stronger for high-`sx` shared qubits (0.228 against
0.186 for `cz`, 0.262 against 0.150 for `rzz`), in line with 05's prediction for the
qubit-defect mechanism but on few qubits (05 Verification); per-component layered fidelities
(06 §9 item 8).

### 4.6 The device's history and its schedule

- *Levels.* `T1` low in May (device median 101.8 us), highest in June (139.4 us), then settling
  near 126 to 131 us (02 §3.1); monthly RO 0.01416 in May, 0.00854 in June, 0.00928 in October,
  most of the change before mid-June (03 §3.1); `sx` flat (slope 0.0008 decades per 30 days; 04
  §3); `cz` and `rzz` flat (05 §3.2); EPLG(100) rising (Spearman 0.456 with time, n = 83; 0.463
  for the 82 in-archive events; 06 §3.7 and Verification).
- *Known events.* Change points align with known events about as often as chance (5 of 17 at the
  most conservative penalty against 3.29 expected; 06 §3.5; upheld in 06 Verification). The
  readout drop after 2026-06-08 is the closest coincidence (03 §7.4, 06 §3.5): the RO drop
  reproduces and exceeds every placebo day (-0.138 against a placebo minimum of -0.084), while
  `T1`, `T2` and `sx` show no step (03 and 06 Verification). It is not a clean attribution:
  readout's largest drop is on 2026-05-17 (-0.20 decades) with no known event, 06-08/09 is also a
  schedule restart date, the 2.6 h proximity is one event, and the asymmetry A did not move
  outside the placebo range (06 and 03 Verification, which weaken 06's "one clear exception").
  The 2026-07-30 length change moved nothing detectable (03 §7.4). A 14-day before-and-after test
  fires on 21% to 23% of placebo dates for `sx`, so `sx`'s known-date shifts are not attributable
  (04 §3); 04's verifier adds that 15.8% of placebo dates reach p at most 6.5e-6 with a shift of at
  least 0.0148 decades (04 Verification).
- *Unexplained episodes.* `init_error` rose 0.225 decades on 2026-08-21 and fell 0.300 on 08-31,
  with readout points on the same dates and no known event (06 §3.5); `rzz` was not re-measured
  device-wide from 2026-08-19T23:02 to 08-31T14:50 (279.8 h) while the other families were (05
  §2.3, 06 §3.1). That the two periods overlap is a juxtaposition by this overview, not a test.
  Device-day P(1|0) and `sx` changes are anti-correlated (-0.341; 07 §3.2).
- *Schedule.* The daily cycle starts 0.7 to 1.2 h later each day and restarts pull it back (06
  §3.1); the sequence behind `T1` lengthened from May to September (`cz` offset 1.99 h to 3.47 h;
  06 §3.2); visible readout rounds fell from 5.62 to 3.67 per day while files per day rose from
  9.25 to 22.77, so the fall is at least partly what IBM runs or publishes (06 §3.4, I; upheld in
  06 Verification: the fall persists at round gaps of 15, 60 and 180 min and already appears in
  the live-only months); the `rzz` rate fell after the coverage split, when coverage improved
  (05 §2.3), but most of that fall is the single 279.8 h pause: excluding it, the rate from the
  split is 0.729 against 0.809 before (05 Verification).
- *No value seasonality* of practical size by hour or weekday in any family (02 §3.4, 03 §3.3,
  04 §3, 05 §3.3, 06 §3.6); the P(1|0) weekday signal at record level was clustering, since at
  session level the test gives p = 0.18 (03 Verification).

### 4.7 How IBM produces the values (inference from the data unless a source is named)

Stamps are batch write times: a device round is stamped within seconds, in batches that are
independent sets for `sx`, `T2` and `xslow` and index-ordered runs for readout, `init_error`,
`measure_2` and `T1` (06 §3.3, I). `last_update_date` behaves like an assembly time (06 §2.2).
`lf` stamps can postdate the poll that filed the document, which no reading of the stamps
reconciles (06 §6.2 item 1). `zz` is re-determined about every 5 h, directly or by formula,
undecidable from the document (05 §1.4). The daily readout shot count is open (03 §4.5). A
rotating group of 9 qubits (index residue 10, then 9, then 16, modulo 17) has its P(0|1) not
republished intraday (03 §0 item 2, dates reproduced); 03's claim that RO is nevertheless computed
from a fresh P(0|1) is not shown, because the 1/4,096 grid test it rests on holds by arithmetic
(a shuffled-P(0|1) placebo also passes 100%), and the implied value is consistent with the stale
one (median ratio 1.01) (03 Verification). `init_error` is withheld for 40 qubits with poor
readout (03 §7.3; median RO 0.0314 against 0.0076 in 03 Verification). The `cz` and `rzz` stamp
groups are not IBM's documented isolation batches (05 §5.4, 06 §3.3). `rx` records exist for an
instruction the archived target never offers (04 §6), and `xslow` reports the same value as the
24 ns `sx` error (equality in every record; that it is copied is not shown, 04 Verification)
although its own coherence limit exceeds that error in 99.67% of 6,033 matched events (04 §0,
reproduced; 99.27% for the `T1`-only limit).

## 5. Data-quality rules every future analysis of this archive must respect

1. **Mask placeholders before forming events.** `gate_error >= 1` is masked first (01 §4);
   placeholder stamps are assembly times later than `last_update_date` (04 §1, 05 §1.3, 06 §2.2).
   A placeholder is a state lasting days to months, not a value (05 §8).
2. **Say which event rule is used.** Measured rule for fields with a measurement stamp, value-only
   rule for assembly-stamped fields and lengths (01 §4). For the quantized readout fields the
   measured rule drops re-measurements that returned an identical value (1,745 RO and 3,180 P(1|0)
   events), which removes exact zero changes; 03 uses stamp events and collapses 257 within-session
   re-stamps (03 §2.3). Event counts differ by convention (for example `T1` 20,063 with carried-in
   first events in 02 and 07, 19,908 without them in 06).
3. **Use one copy of every duplicate:** `sx` for `x`, `id`, `rx`, `xslow`; RO for `measure`; the
   canonical coupler column `[a, b]` with `a < b`, which is lossless after masking (05 §1.3,
   06 §6.2 item 8); one threshold per pair; reset lengths are derived (01 §5, 03 §1.2).
4. **Do not recompute RO from the published pair without checking stamps.** In the rotating
   9-qubit group P(0|1) is stale (11,515 records on 35 qubits, up to 47.8 h old; the count
   reproduced in 03 Verification). `2 RO - P(1|0)` gives the P(0|1) implied by RO (03 §0 item 2,
   §6), but its landing on the 1/4,096 grid cannot fail by arithmetic, so it does not show that
   the implied value is a fresh measurement; it is consistent with the stale value (median ratio
   1.01; 03 Verification). Make noise statements on intraday sessions, since the daily sessions'
   shot count is open (03 §4.5).
5. **Fix the `p01` notation** as in this overview's header before quoting any readout number.
6. **Handle zeros and the log scale explicitly.** P(1|0) is exactly 0 in 2,468 records (03 §2.1;
   07 uses `log10(p + 1/8192)`, 07 §1.1); `init_error` is below 1e-6 in 540 records (03 §2.1);
   20 nonpositive `Gamma_phi` values (02 §4.1); `zz` exact zeros are a missing marker and 13
   couplers are ever negative (05 §1.4, §6.3). `ddload.variogram` drops `y <= 0` without counting
   them, so count them separately (02 §4.1).
7. **Control for coverage by period.** Historical fetches start with
   `20260805T234531000000Z` (443 files; 06 §2.1); before them a missed document hides events, so
   event rates are lower bounds (05 §2.3), and visible readout cadence varies by month (06 §3.4).
   The documents split at different dates (2026-08-05T23:45:31Z in 02 and 05; 2026-08-01 in 04
   and 07): state the split used.
8. **Schema starts are not missingness:** `measure.threshold` from 2026-06-08T18:56:28Z,
   `init_error` from 2026-08-04T00:52:30Z, `measure_2` from 2026-08-07T03:21:59Z, `measure_reset`,
   `measure_reset_2` and `reset_2` from 2026-09-02T04:56:24Z, the two `xslow` runs (01 §3, §5), the
   configuration key `mcps` from 2026-07-16 (06 §6.2 item 6), and the `lf` first value carried from
   2026-05-10 to 2026-07-01 (06 §3.7).
9. **Assembly stamps carry no time.** `zz`, every threshold, `rz` and the `measure` length are
   stamped at assembly (01 §3); read `zz` at day resolution only (07 §6). `last_update_date` equals
   the newest measured stamp in only 0.195 of files: order files by it, do not use it as the time
   of the features (06 §2.2, §6.2 item 2). Do not order `lf` against other fields at the hour scale
   (06 §6.2 item 1).
10. **Stamp groups are not spatial samples.** Same-stamp `sx`, `T2` and `xslow` qubits are never
    neighbours; readout, `T1`, `init_error` and `measure_2` batches follow index order (06 §3.3,
    §5.4); `cz` and `rzz` stamp groups are not isolation batches (05 §5.4).
11. **Drop carried-in first events** for temporal statistics: a first value can predate the
    archive (`q17`'s `T1` stamped 2026-04-13; `lf` 2026-05-10) (02 §2.2, 06 §6.2 item 7).
12. **Flag stale values:** `T1` of `q72` (stale in 1,126 files), `q11` (876), `q17` (482, a frozen
    April value through both of its `sx` placeholder episodes) and `q103` (76); `T2` of `q149`
    (351) (02 §2.2, 04 §6); `init_error` of `q40` and `q117` (one stamp event each; 03 §2.2). Any
    per-file target, ADR-027's included, mixes stale and fresh values unflagged (02 §2.2).
13. **Exclude or list the faulty entities:** `q72` (`sx` placeholder in every file, `T2` absent
    from every file, `T1` absent from the first 36, both couplers permanently faulty, median RO
    0.350); `cz` permanently faulty on 27-28, 32-33, 71-72, 72-73; `rzz` on 32-33, 71-72, 72-73,
    95-99, 99-115; `cz` on 102-103 at the placeholder in 88.8% of files until 2026-09-29, valid
    since at a median record error of 7.41e-2; `zz` zero on 32-33 always and on 13-14, 39-53 and
    109-118 until 2026-07-10, then frozen at one value; extreme `zz` on 72-73, 71-72, 11-12 and
    11-18; `measure_2` placeholder on every qubit in its first two files; 40 qubits without
    `init_error` (01 §5, 03 §5, §6, 05 §6, 06 §6.1).
14. **Treat regimes as regimes.** The quiet window of 2026-05-15 to 05-27 and the 2026-06-26/29
    step must not be pooled into one stationary noise estimate: pooling biases a noise estimate low
    and a persistence estimate high (02 §6).
15. **Read provenance fields for what they are.** The 760 states are qubit-record states, not
    calibrations (01 §6); `is_new_state` marks filing order and only equality of `state_id` is
    meaningful (06 §6.2 items 3 and 4); a historical file's target is not dated at day resolution
    (06 §6.2 item 5).
16. **Account for dependence and multiplicity.** Events of one round or session are not
    independent (02 §3.4, 03 §3.3); Pettitt p-values are optimistic under autocorrelation (02
    §3.2); use Benjamini-Hochberg and placebo dates (04 §3); report the level-window sensitivity of
    any residual-based co-movement (07 Verification claim 1); check spatial autocorrelation of
    both fields before a permutation test (07 §5). Test at the level of the independent unit:
    05's short-gap Wilcoxon p-values (0.0011, 2.9e-6) treated coupler pairs of one occasion as
    independent and become 0.10 and 0.56 over 11 and 6 occasions (05 Verification). Draw a
    spatial null from the entity type tested: 06's fault-footprint null drew random qubits for
    faults that are couplers, and a random-coupler null gives p = 0.042, or 0.16 given the
    adjacent pairs (06 Verification). Give placebo tests for any grid or arithmetic check, since
    a check that cannot fail is not evidence (03 Verification).

**Corrections the scope documents make to the shared layer and to each other** (recorded, not
resolved here):

| Item | Correction | Source |
| --- | --- | --- |
| 01 §5: alias and direction event counts "can differ" because dates differ | All date mismatches are in placeholder records; after masking the series are identical | 04 §0, 05 §1.3, 06 §6.2 item 8 |
| `results/data-layer/profile.json` labels the `g2` gate lengths "measured" | 01 §4 assigns them to value-only; no number changes | 05 §6.4 |
| 01 §6 lists 38 constant configuration keys | `mcps` appears on 2026-07-16 and is not named | 06 §6.2 item 6 |
| 01 §3 `xslow` "present in lifetime" 0.4983 | A share of files between the two runs, not missing records | 04 §2 |
| `ddload.variogram` | Drops `y <= 0` without a count | 02 §4.1 |
| 07 `levels.py` | `init_error` events-per-qubit median counted absent qubits as zeros; fixed to 241 | 07 §10 |
| Roadmap P7: `measure_2` "one device-wide glitch" | Its first two files at the schema start | 03 §6, 06 §6.1 |
| Roadmap §0 and P2: every series "observed through measurement noise" | Not supported as a blanket description for `T1`/`T2`: at least about half of each deviation's variance is shared by the two fits of a round under 02's independence assumption (02 §0); 02's verifier weakens 02's "contradicted" and "real", since a same-round artefact common to both experiments would also produce it | 02 §0 and Verification |
| `q72`'s `T1` level | 9.603 us as an event median (02 §6) against 21.45 us and 21.5 us (04 §6, 05 §6.2); not reconciled, plausibly event against record weighting given 1,126 stale files (I) | 02, 04, 05 |
| May `T1` step date | The 2026-05-15T05 round (02 §3.2) against a PELT point at 2026-05-15T22:25 (06 §3.5): different methods | 02, 06 |
| Lag-1 band | -0.42 to -0.50 at the older ref; at this ref -0.425 (`rzz`) to -0.513 (`zz`) across per-entity families | 02 §3.3, 03 §3.4, 04 §4, 05 §1.4, §3.1 |

The verifiers' corrections to documents 02 to 07 themselves are in each document's Verification
section and inline markers; the status table at the top of this overview counts them, and the
sections above use the corrected readings.

## 6. What remains unknown, ranked by how much it matters for the paper

1. **What the bulk of the non-persistent component is** (estimation error, fluctuations faster
   than the sampling, or round-to-round recalibration). It is the central question of the paper
   and decides whether a forecaster's band is a measurement-precision band or a physical one.
   Settled only by own repeated experiments at minute spacing or by IBM metadata (section 4.1).
2. **Whether the component's size is stationary,** and what changed device-wide in May 2026 and
   at 2026-06-26/29 (section 4.2). Any model fitted across the regimes inherits the change.
3. **What the shared `T1`/`T2` component is, and what verification left open.** The strongest
   attribution claim of the deep dive (02 §4.2) is now verified as a number and as "at least
   about half shared between the two fits", but not as a real change of the qubit; whether a
   round's readout or initialisation change moves both `T1` and `T2` was tested by no one (02
   Verification). Each verifier also lists what it did not re-verify: for 03, the stale group's
   freshness by session kind and Krantz et al. eq. 173; for 04, the 11 per-qubit change points,
   the spatial Moran tests other than the degree test, and most new sources; for 06, the header's
   event counts per family; for 07, the independent re-implementation of lead and lag, the Ward
   archetype nulls and the device-day jump table. Every figure in this overview marked M was
   reproduced only by re-running its owner's script.
4. **The timescale of the shared cross-experiment component** (section 4.3): robustness to a
   slowly moving level is now supported for `T1`-`T2` and for couplers sharing a qubit (02 and 05
   Verification), but the `T1` sub-day test rests on one occasion below 6 h, the `sx`-`T1`
   near-far contrast is confounded with job membership (04 Verification), the `cz`/`rzz`
   rise over hours cannot be separated from recalibration (05 Verification), and the +-2 d
   level-window test has run only on 07.
5. **The daily readout sessions' shot count** (2,048 or 4,096), which sets the readout noise
   floor for about a fifth of the sessions (123 of 589; 03 §0 item 3) and the assumption behind
   07 §4.4 (03 §4.5).
6. **What the gate errors contain beyond decoherence** (section 4.5): the single-qubit share in
   2Q RB (IBM's page says the benchmark alternates single-qubit Cliffords with two-qubit gates,
   05 Verification; whether the reported error is corrected for them is not documented, 05
   §7.3) and the source of the 1.4 layered-to-isolated factor.
7. **The physical origin of the spatial patterns** (readout by degree class, which accounts for
   most of the "checkerboard" of RO (03 Verification); `sx` and `T1` by degree (04
   Verification); coupler clustering; `zz` on bridges; section 4.4), which needs frequencies the
   cache does not carry.
8. **Production semantics** (section 4.7): how `zz` is produced and why it moves against
   readout; what `lf` stamps mean; whether a historical fetch returns the target at document or
   fetch time (06 §9 item 3).
9. **Isolated anomalies:** the permanent fault of 32-33, whose qubits look unremarkable (05 §6.2);
   the late-August `init_error` and readout episode and the overlapping `rzz` pause (section 4.6);
   readout's largest drop, -0.20 decades on 2026-05-17, with no known event (06 Verification);
   the P(1|0)-`sx` device-day anti-correlation (07 §3.2); `q64` never in an `lf_100` chain (06
   §5.3); the purpose of `xslow` and the `rx` records outside the target (04 §9).

## 7. Index

| Item | One line |
| --- | --- |
| `00-overview.md` | This synthesis: feature map, dependency map, root questions, data-quality rules, unknowns |
| `01-data-layer.md` | The data dictionary: every field, its shape, event rule, identities, length changes, file structure, the shared variogram and the scope table |
| `02-coherence.md` | `T1`, `T2` and derived rates: same-round co-movement, dips, the May quiet window, ADR-027 concentration (with an appended independent Verification section and inline markers) |
| `03-readout-measurement.md` | Readout, assignment probabilities, `init_error`, `measure_2`, thresholds, lengths: sessions, shot noise, the 2026-06-08 natural experiment, the `T1`-decay link (with an appended independent Verification section and inline markers) |
| `04-single-qubit-gates.md` | `sx` and its aliases, `xslow`, `rz`: the RB-based error, its variogram, the `T1`/`T2` coupling and coherence limit (with an appended independent Verification section and inline markers) |
| `05-two-qubit-gates-couplings.md` | `cz`, `rzz`, `jq`, `zz`: faults, cadence, shared-qubit correlation, coherence limit and the `sx` link (with an appended independent Verification section and inline markers) |
| `06-device-time-topology.md` | Schedule, documents, states, change points, fault map, heavy-hex layout and layer fidelity (with an appended independent Verification section and inline markers) |
| `07-cross-feature-dependency.md` | Every other relationship between families, with an appended independent Verification section |
| `analysis/ddload.py`, `analysis/extract_cache.py` | The read-only loader and the one-pass cache extraction |
| `analysis/data_layer/`, `results/data-layer/` | Cache profile, identity checks and the loader self-test; `profile.json`, `identities.json` |
| `analysis/coherence/`, `results/coherence/` | Seven scripts (plus `cohlib.py`) and JSONs: profile, temporal, nonpersistent, regime, dips, spatial, adr027 |
| `analysis/readout/`, `results/readout/` | Seven scripts (plus `rocommon.py`) and JSONs: sessions, profiles, noise, length changes, thresholds and `measure_2` and `init_error`, `T1` link, spatial and temporal |
| `analysis/gates_1q/`, `results/gates_1q/` | Six scripts (plus `g1common.py`) and JSONs: aliases and schema, profile, temporal, variogram, coherence, spatial |
| `analysis/gates_2q/`, `results/gates_2q/` | Seven scripts (plus `common2q.py`) and JSONs: profile, `cz` against `rzz`, temporal, variograms, `zz`, spatial, link |
| `analysis/device/`, `results/device/` | Seven scripts (plus `device_common.py`) and JSONs: batches, schedule, documents, states, change points, layout and faults, layer fidelity |
| `analysis/cross/`, `results/cross/` | Seven scripts (plus `xcommon.py`, `xresid.py`) and JSONs: alignment, levels, comovement, common mode, lead and lag, coincidence, summary |
| `analysis/verify/coherence/`, `results/verify/coherence/` | The 02 verifier's independent re-computations: `v_core`, `v_comove`, `v_subday`; `core_check`, `comove_check`, `subday_check` |
| `analysis/verify/readout/`, `results/verify/readout/` | The 03 verifier's: `v_records`, `v_noise`, `v_length_link`, `v_extra`; `records_check`, `noise_check`, `length_link_check`, `extra_check` |
| `analysis/verify/gates_1q/`, `results/verify/gates_1q/` | The 04 verifier's: `verify_core`, `verify_challenges`, `verify_placebo` and their JSONs |
| `analysis/verify/gates_2q/`, `results/verify/gates_2q/` | The 05 verifier's: `compare_reruns`, `v_core`, `v_challenge`, `v_link`; `compare_reruns`, `core_check`, `challenge_check`, `link_check` |
| `analysis/verify/device/`, `results/verify/device/` | The 06 verifier's: `v1_basics` to `v7_lf_late` and their JSONs |
| `analysis/verify/cross/`, `results/verify/cross/` | The 07 verifier's independent re-computations: levels, comovement, coincidence |
| `docs/implementations/2026-10-06-feature-deep-dive.md` | The implementation record of this deep dive (outside this folder) |
