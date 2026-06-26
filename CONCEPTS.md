# Understanding EGMS: points, accuracy, and time

Three questions every customer (and grant panel) will ask. Short, honest answers you can reuse.

## 1. Why is it scattered points, not a continuous map?

InSAR only produces a measurement where there is a **persistent scatterer** — a hard, radar-stable object: a roof, a façade, a rail, a rock, a lamp post. Vegetation, water and bare fields *decorrelate* between satellite passes (their radar phase becomes random), so there is simply **no reliable measurement** there. The points are dense on cities and infrastructure and sparse on farmland and forest. **Each dot is a real reflector on the ground — the scatter is the physics, not a sampling choice.**

## 2. You said millimetre accuracy — why can't we get every building?

Two different things:

- **Precision** ≈ 1 mm/yr on velocity — how *accurately* the motion is measured *at a scatterer*.
- **Spatial sampling** — *where* scatterers exist. Sentinel-1's resolution is ~5 × 20 m; EGMS **L3** is resampled to a 100 m grid, while EGMS **L2** keeps full persistent-scatterer density.

So **building level is achievable for buildings that carry scatterers** — and most masonry/concrete buildings in a city carry several (roof corners, façade), enough to estimate the building's motion *and* its differential motion. Buildings that are new, small, or vegetated may carry none. Use **L2** (full PS density) for building scale; **L3 Ortho** (vertical + east-west on 100 m) for regional screening.

> Caveat to state plainly: a façade scatterer can be geolocated onto a neighbouring building, so attribution needs good footprints (that's why the OSM step matters).

## 3. How do scattered points become valuable information?

The value is the **transformation**, not the dots. `egms-tools` does this chain:

1. **Attach** scatterers to each asset footprint.
2. **Trend** — robust velocity with a confidence interval.
3. **Differential** motion across the footprint — uneven settlement, which is what cracks structures.
4. **Temporal pattern** (see below) — *what kind* of motion, and did it change?
5. **Risk** — an honest level (OK / Monitor / Investigate / Act) with confidence.
6. **Prioritise & alert** — rank by risk; at each EGMS update, flag what changed.

## 4. Temporal change patterns (yes — this is the highest-value layer)

EGMS gives a full displacement **time series** per scatterer, so we classify *how* something moves, not just *how fast*. `temporal.py` decomposes each series into velocity, acceleration, **seasonal amplitude**, and **onset**, then labels an archetype:

| Archetype | Meaning | How to read it |
|---|---|---|
| stable | within noise | no action |
| linear subsidence / uplift | steady rate | watch / investigate by rate |
| **accelerating** | rate increasing | escalate — getting worse |
| **seasonal (reversible)** | annual swell/shrink (clay, groundwater) | usually **not** structural — don't false-alarm |
| **recent onset** | motion *began* mid-record (new tunnel, dewatering) | investigate — something changed |

Why this matters: a seasonal signal and a recent-onset subsidence can have the **same average velocity** but completely different meaning. Telling them apart — and catching an onset early — is the product. The demo shows all of these (e.g. the synthetic *Stuttgart tunnelling onset 2021* and *Berlin/Munich seasonal groundwater*), and the **time-lapse dashboard** lets you watch the ground move and the onset appear.

---
*Part of GroundTruth / egms-tools. Study area: Germany.*
