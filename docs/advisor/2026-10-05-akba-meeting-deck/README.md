# Meeting deck for Dr. Akba, 2026-10-05

The slide deck @mertefesensoy presented to Dr. Fırat Akba on 2026-10-05: how each of the
three engines turns IBM calibration data into a noise model, and the deep engine's two
candidate designs for him to choose between. It was published as two private Claude Slides
artifacts, one English (`en/`) and one Turkish (`tr/`), with identical slides.

This folder is the dated record of what was shown. It is not a standalone web page:

- `deck.json` is each deck's index (title, slide order, sections, fonts);
- `slides/<id>.html` holds one slide each, a single `<section>` in the Slides format.

**Sources.** Every fact on the slides comes from:

- `docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md` (the plan; decisions A1 to
  A8);
- `docs/roadmap/2026-10-04-deep-engine-architecture-research.md` (the research; Option B is
  its recommendation, documented and not adopted);
- the code on `main` at `110cfad` for the fuzzy pipelines.

The archive figures (1,697 files, 740 states, 132 T1/T2 re-measurements) are provisional
measurements at `calibration-data` ref `43607a2`, registered later by tasks T1, T12 and T13
of Issue #110.

**Decisions it asks for.** The "Decisions We Need From You" slide lists eight questions.
Dr. Akba's answers are recorded in `docs/advisor/2026-09-03-decisions-from-akba.md` (plan
task T0), not here.
