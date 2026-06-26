# Architecture — what each file does

`egms-tools` is deliberately small and readable. This is the map: read it once
and you can explain any part of the codebase. The study area is **the whole of
Germany**.

## How the data flows (one picture)

```
                 germany.py                      synthetic.py                 io.py
            (study area + the real        (a synthetic Germany-wide      (the same thing
             regions + velocity field)     PS field, for the demo)        from REAL EGMS)
                       │                            │                          │
                       └──────────────► MotionField (PS points + time series) ◄┘
                                                    │
                                            analysis.py
                       attach scatterers → robust velocity (+CI) → acceleration
                       → differential motion → honest risk level
                                                    │
                                          AssetResult (per asset)
                                          /            │            \
                                  report.py        dashboard.py     io.py
                              (plain-language     (interactive      (results.csv /
                               reports + figs)     national map)      .json export)
                                                    │
                                                  cli.py  (`egms demo`, `egms run`)
```

## The files, one by one

**`egms_tools/germany.py` — the study area.**
Defines Germany as the national bounding box and a catalogue of *real* German
ground-motion regions (Rhenish & Lusatian lignite, Ruhr mine-water rebound, East
Frisia peat, the famous Staufen anhydrite heave, Munich/Berlin/Hamburg). Provides
the lon/lat ↔ metres helper and `velocity_field(x, y)`, which returns the ground
velocity and acceleration anywhere in the country. On real data you'd clip to the
official German boundaries (BKG) instead; the regions here just anchor the demo.

**`egms_tools/synthetic.py` — the demo data.**
Builds a *clearly-labelled synthetic* EGMS field over Germany: a sparse national
layer of scatterers for screening, plus dense points on each monitored asset
(real EGMS is dense on buildings/rails, sparse on fields). Also builds the
monitored assets (building clusters on the hotspots, a rail corridor across the
Rhenish subsidence, a pipeline across Lusatia). This is the only "fake" part —
everything downstream is production code.

**`egms_tools/io.py` — real EGMS in, results out.**
`load_egms()` parses a real EGMS tile CSV (one row per scatterer; one
displacement column per acquisition date) into the *same* `MotionField` the
synthetic generator produces — so switching from demo to real data is a one-line
change. `export_results()` writes the per-asset results to CSV or JSON.

**`egms_tools/osm.py` — real building footprints.**
`fetch_osm_buildings(bbox)` pulls real building outlines from OpenStreetMap
(Overpass API) and returns them as `Assets`, so you monitor *real* buildings.
`buildings_to_geojson()` / `load_buildings_geojson()` cache them. Run it in your
own environment (a normal HTTP client works; a headless browser can be refused
with HTTP 406 — a browser quirk, not a code issue).

**`egms_tools/analysis.py` — the brain.**
Turns a motion field + assets into per-asset risk, transparently: attach the
scatterers on each footprint → fit a robust **velocity** (Theil-Sen, with a 95%
confidence interval) → fit **acceleration** (is it getting worse?) → measure
**differential** motion across the footprint (uneven settlement = distortion,
what actually cracks things) → combine into an honest level (OK / Monitor /
Investigate / Act) with a confidence from data quality. Thresholds live in
`RiskConfig` so they're calibrated per asset class, not hidden.

**`egms_tools/temporal.py` — what kind of motion, and did it change?**
Decomposes each displacement time series into velocity, acceleration, seasonal
amplitude and onset, and classifies an archetype (stable / linear / accelerating
/ seasonal-reversible / recent-onset). This is the temporal-pattern layer — it
separates a harmless reversible seasonal signal from a real recent-onset
subsidence that share the same average velocity.

**`egms_tools/report.py` — the deliverable.**
Writes the plain-language per-asset reports ("subsiding at 8.3 mm/yr (95% CI …),
the rate is accelerating … RISK: ACT"), the portfolio summary, and the per-asset
displacement figures. This is the artifact a customer actually pays for.

**`egms_tools/dashboard.py` — the interactive map (real OSM basemap).**
Builds the dashboard on a **real OpenStreetMap basemap** (Leaflet): scatterers
coloured by velocity and assets coloured by risk, drawn at their true
latitude/longitude on real streets; click a footprint for its report and time
series. National screening view + a building-scale focus view (`focus_bbox`).
Needs internet to load the map tiles.

**`egms_tools/dashboard_temporal.py` — the time-slider.**
Colours every scatterer by its cumulative displacement at the selected date, with
a slider + play button, so you can watch subsidence bowls deepen and the onset
appear mid-record. The temporal view of the same data.

**`egms_tools/cli.py` — how you run it.**
`egms demo` runs the whole synthetic Germany pipeline with no data and no network.
`egms run --egms <tile>` is the entry point for real EGMS tiles.

## Supporting files

- **`experiments/demo.py`** — the same Germany demo as `egms demo`, as a script.
- **`tests/test_egms.py`** — 5 fast tests: the field spans Germany, hotspots are
  present, subsidence and the accelerating Staufen heave are flagged, export works.
- **`configs/demo.yaml`** — the demo + risk parameters in one place.
- **`README.md`** — overview and how to run on real EGMS.
- **`EXPLAINER.md`** — "what is EGMS and why can't you use it" (the community on-ramp).
- **`Dockerfile`, `.github/workflows/ci.yml`, `pyproject.toml`, `LICENSE`** — packaging, CI, install, licence.

## The one rule to remember

Synthetic data is only in `germany.py` (the illustrative region velocities) and
`synthetic.py` (the demo field). Everything else — `analysis`, `report`,
`dashboard`, `io` — is the real product, and runs unchanged on real EGMS the
moment you call `load_egms()`.
