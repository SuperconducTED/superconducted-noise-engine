# Pipeline-health fixture archive

The committed archive behind issue #48 section 9.2, "end to end over a fixture
archive committed under `tests/fixtures/`, `metrics.json` and `progress.svg`
both asserted whole". Driven by `TestEndToEndFixture` in
`tests/test_pipeline_health.py`.

```
archive/
  snapshots/2026-09/ibm_fez/*.json   four documents, two device states
  ledger/2026-09.tsv                 seven ADR-025 poll events
expected/
  metrics.json                       golden, regenerated not hand-edited
  progress.svg                       golden, regenerated not hand-edited
```

## What the four documents are chosen to exercise

| Document | Measurements | Why it is here |
| --- | --- | --- |
| `20260901T000000000000Z` | T1 91.5 | The first sighting of state A. |
| `20260901T060000000000Z` | T1 91.5, later parameter `date` | **The load-bearing one.** Identical measurements, re-stamped the way the history endpoint re-stamps the records it synthesises. One state, not two. |
| `20260901T120000000000Z` | T1 87.0 | The first sighting of state B. |
| `20260902T000000000000Z` | T1 87.0, same `date` | A plain duplicate, the ordinary case. |

Four documents, two distinct states, 50% duplication.

The ledger has a deliberate gap through most of 09-01 so the 72-hour strip has
something to show rather than being uniformly filled.

## Two values sit exactly on a boundary, deliberately

Rendered at `--now 2026-09-02T12:00:00Z`, state B was first seen exactly 24 h
earlier. That pins two strict comparisons that would otherwise go untested:

- `hours_since_last_new_state` is `24.0` and the band is `24 h to 3 days`, because
  `staleness_band` tests `hours < limit`.
- `states_added_24h` is `0`, because the window test is `timestamp > window24`.

If either boundary is ever meant to be inclusive, this fixture is what will say so.

## Regenerating

Never hand-edit the files under `expected/`. When a rendering or metrics change
is intended:

```bash
PIPELINE_HEALTH_REGOLD=1 python -m pytest tests/test_pipeline_health.py \
    -k test_the_fixture_renders_the_committed_artifacts
```

Then read the diff before committing it. That diff is the point: it is the only
place an unintended change to a *published* graphic shows up as a reviewable
change rather than as a quiet redraw on the branch README.

The fixture supplies its own candidate floor (`sample=8`) rather than the
workflow's, so re-pointing a real floor at a new NC row does not churn these
artifacts.
