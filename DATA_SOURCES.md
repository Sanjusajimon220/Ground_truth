# Data sources: what to use, what to fuse, and how current it gets

Your three questions — incompleteness, "should we add Sentinel/Landsat?", and "data up to 2026" — all come down to one design decision: **a layered data architecture where InSAR measures the motion and everything else explains, fills, or validates it.**

## The one rule

**Only InSAR measures millimetre vertical ground motion.** Optical satellites (Sentinel-2, Landsat) **cannot** measure mm subsidence — don't let anyone (or any pitch) imply they can. They are invaluable for *context*, not for the motion itself. Keep that line clear; it's part of the honest brand.

## The three tiers

**Tier 1 — Motion (millimetre), the measurement.**
- **EGMS** (free): the validated, GNSS-calibrated, continental baseline. Annual updates that **lag ~1–2 years**. Use it as the trusted reference. Products: Basic (LOS asc/desc), Calibrated (absolute), Ortho (vertical + east-west, 100 m).
- **Your own Sentinel-1 processing** (free data): for any custom area, **6–12-day** cadence, right up to the latest weeks — this is how you get to *today* (see currency below). PSI gives points on hard targets; **SBAS / distributed-scatterer (DS-InSAR)** adds coverage on rural/vegetated/soft ground where PSI is blind. **This is the main answer to incompleteness.**

**Tier 2 — Context & attribution (this is where Sentinel-2 / Landsat belong).**
- **Sentinel-2 / Landsat (optical):** land cover, **new-construction detection**, vegetation (explains *why* a building has no scatterers), surface water, large/fast horizontal motion via pixel-offset (landslides/glaciers — not mm subsidence). They explain the gaps and the causes.
- **Copernicus DEM:** geocoding, terrain correction, slope.
- **Geology / soil (BGR in Germany):** clay, peat, karst, mining — susceptibility; turns "it's moving" into "it's moving *because*", which is what makes a report actionable.
- **Groundwater levels + ERA5 / precipitation:** explain seasonal (reversible) vs structural motion; link subsidence to drought/abstraction → the *intervention*.
- **OSM / cadastre:** footprints, building age, value, owner → exposure and who to call.

**Tier 3 — Validation.**
- **GNSS / levelling:** ground truth, reference frame, calibration (exactly what you did on La Palma). A few validation points massively raise trust.

## Incompleteness — handled honestly

The product already refuses to call unmeasured assets "stable" — the new **coverage report** counts measured vs unmeasured and lists the gaps. The fix ladder for a gap is: PSI (EGMS) → add **DS-InSAR from your own Sentinel-1** → if still blind, recommend **levelling/GNSS**. Never hide a gap.

## Currency — getting to 2026 (verified June 2026)

- **EGMS alone won't be current** — its latest edition trails by a year or more.
- **Your own Sentinel-1 chain gets you to the present.** And the constellation is healthy again: after Sentinel-1B failed (Dec 2021), **Sentinel-1C** launched Dec 2024 and is operational, and **Sentinel-1D** launched Nov 2025 and becomes fully operational around **April 2026**, restoring the full **6-day revisit**. So 2025–2026 data is dense and available within days.
- **Product line to say out loud:** *"EGMS for the validated multi-year baseline; our own Sentinel-1 processing for the latest months and for the assets EGMS can't see."* That single sentence answers incompleteness **and** currency, and it's a real moat (it needs your InSAR skill).

## A note on the competition

**Detektia** (Spain) does almost exactly this — EGMS + civil-engineering focus + external variables (land use, tree cover, slope, temperature, precipitation) + ML time-series clustering, served via API. That **validates the architecture and the market**. You differentiate on: Germany focus, affordability/SME + municipal tier, an **open core** (community adoption), and transparent, honest reporting.

## What this means for the roadmap

1. Now: EGMS + OSM + the analysis/temporal/actionable layers you have.
2. Next: a **Sentinel-1 SBAS/DS-InSAR** pipeline for one AOI (currency + coverage) — your true technical moat.
3. Then: attribution layers (geology, groundwater, ERA5) to explain motion, and a **movers/alert** feed at each update.
