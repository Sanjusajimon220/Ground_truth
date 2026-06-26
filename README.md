# egms-tools — the open core of **GroundTruth**

**Multi-hazard ground-and-land risk intelligence for Germany, built entirely from free satellite data.**

Germany is covered, for free, by three of the most valuable open Earth-observation datasets in existence — and almost nobody who needs them can use them, because they ship as raw scatterer tables, thermal rasters and multi-band imagery that take remote-sensing expertise to read. `egms-tools` is the bridge: it fuses them into **queryable, map-based risk layers** for the people who own things that crack, tilt, sink, overheat, or change use.

> **This is the main project** — the open core of **GroundTruth**. Study area: **Germany**. By Sanju Sajimon (M.Sc. Remote Sensing, KIT; ex-surveyor & civil engineer).

---

## Three real hazard layers, one engine

| Layer | Source (free) | Signal | Status |
|---|---|---|---|
| **Ground deformation** | Copernicus **EGMS** (Sentinel-1 InSAR, L3 Ortho) | mm/yr vertical velocity + displacement time series | ✅ **Real** — loads real EGMS tiles; per-region now, scaling to national |
| **Urban heat** | **Landsat** Collection-2 thermal (ST_B10) | land-surface temperature °C + heat-island anomaly | ✅ **Real** — national, **10-year** median + yearly time-lapse (2016–2025) |
| **Land-use change** | **Sentinel-2** optical | change parcels + compliance flags | ◻️ Pipeline built; classifier in progress |

All three render in **one single-file app** on a real basemap (OpenStreetMap / Sentinel-2 / Esri satellite / terrain), with per-layer on/off toggles, click-to-read values, and a **dual time-lapse** that switches between *ground motion over time* and *urban heat over time*.

```
Free satellite data (Germany)
   EGMS InSAR  ──►  real vertical velocity surface + displacement time-lapse  (mm/yr)
   Landsat     ──►  real LST: absolute °C  +  heat-island anomaly  +  10-yr time-lapse
   Sentinel-2  ──►  land-use change parcels + compliance queue
        └──────────►  ONE app: toggle layers, click any point, watch a decade evolve
```

It surfaces evidence and uncertainty; it does not replace a geotechnical inspection or a site survey. Risk thresholds are explicit, documented defaults to calibrate per asset class.

---

## What's real today (honest status)

- **Urban heat — real & national.** 10-year summer-median land-surface temperature across all of Germany from Landsat thermal, clipped to the national outline, with an **Absolute °C / vs-10-yr-mean** toggle and a **2016→2025 yearly time-lapse**. Click anywhere reads the real temperature.
- **Ground deformation — real, scaling.** Loads real **EGMS L3 Ortho Vertical** tiles (100 × 100 km, EPSG:3035) into a velocity surface + a **2020→2024 displacement time-lapse**. Click reads real **mm/yr**. Currently rendered per downloaded tile (e.g. a single subsidence region); national coverage is a matter of loading the full tile set — same code, more tiles.
- **Land-use change — pipeline built.** Sentinel-2 composite → rule-based land-cover → change parcels → compliance queue. Real classifier (SegFormer) is a separate track.

The **deformation point cloud is naturally dense on stable targets (cities, infrastructure, bare ground) and absent over forest/water** — that is the physics of InSAR, not missing data, and it is why the layer is valuable: the measurements sit exactly where the assets are.

---

## Quickstart

```bash
pip install -e .
egms app --out results/app.html      # synthetic, Germany-wide demo (real basemap, no data needed)
egms demo --out results              # full synthetic demo bundle
pytest -q                            # CPU-only test suite
```

### Real data — the way GroundTruth actually runs

**Urban heat (Landsat, via Google Earth Engine in Colab):**
```python
from egms_tools.surface import surface_png_stops, HEAT_STOPS, ANOM_STOPS
from egms_tools.heat import grid_from_array
from egms_tools import build_app
# read a 10-yr LST GeoTIFF (exported from Earth Engine), clip to Germany,
# build absolute + anomaly PNGs + a yearly time-lapse, then:
build_app("groundtruth_real.html", heat_override={...}, heat_timelapse={...})
```

**Ground deformation (real EGMS L3 tile):**
```python
from egms_tools.io import load_egms_l3, egms_deformation_override
from egms_tools import build_app

eg   = load_egms_l3("EGMS_L3_E45N31_100km_U_2020_2024_1.csv")  # free Copernicus tile
defo = egms_deformation_override(eg)        # auto-fits to the tile; real velocity + time-lapse
build_app("groundtruth_real.html", deformation_override=defo)
```

**Both layers in one app:**
```python
build_app("groundtruth_real.html",
          heat_override=heat_override, heat_timelapse=heat_timelapse,
          deformation_override=defo)
```

`load_egms_l3` parses the real EGMS L3 CSV (easting/northing in EPSG:3035 → lon/lat, `mean_velocity`, dated `YYYYMMDD` columns). EGMS tiles are free (registration) from the Copernicus EGMS portal; Landsat thermal is free via Earth Engine. For real data: `pip install -e ".[real]"` (pandas, shapely, pyproj, rasterio, earthengine-api).

---

## What every module does

| File | Purpose |
|---|---|
| `germany.py` | Study area: Germany bbox, outline (for clipping), hotspots, cities, velocity field. |
| `io.py` | **Real EGMS**: `load_egms` (L2), `load_egms_l3` (L3 Ortho, EPSG:3035 reprojection), `egms_deformation_override` (real velocity surface + time-lapse for the app). |
| `heat.py` | **Real Landsat LST** loaders + `grid_from_array` (real-°C click readout) + per-city heat stats. |
| `change.py` | **Real Sentinel-2** land-use change pipeline (composite → land-cover → change parcels). |
| `surface.py` | Interpolation + colour ramps: `RISK_STOPS` (motion), `HEAT_STOPS` (absolute °C), `ANOM_STOPS` (diverging anomaly). |
| `analysis.py` / `temporal.py` | Robust velocity (+CI), acceleration, differential motion, risk levels, temporal archetypes. |
| `actionable.py` | Coverage/incompleteness report, ranked inspection queue (CSV + GeoJSON), movers. |
| `landuse.py` | Change parcels + compliance queue (CSV + GeoJSON). |
| `osm.py` | Real OSM building footprints (Overpass) for any area. |
| `report.py` | Plain-language per-asset reports, portfolio summary, displacement figures. |
| `dashboard_app.py` | **The combined single-file app**: per-layer toggles, basemaps, risk surface (+ City planning / Corridor sub-nav), land-use, urban heat (absolute/anomaly), Staufen, dual time-lapse (motion ⇄ heat), coverage, queue, concepts. |
| `cli.py` | `egms app` / `egms demo`. |

---

## Honest scope

The offline demo runs on **clearly-labelled synthetic data** so the whole pipeline works with known ground truth. The **real product** is the loaders + renderers fed with real data: **urban heat is real and national over 10 years today; ground deformation is real per EGMS tile and scales to national with the full tile set; land-use change is a built pipeline pending its classifier.** Only `synthetic.py` (and the illustrative regions in `germany.py`) are synthetic — `io`, `heat`, `change`, `analysis`, `surface` and `dashboard_app` are the real engine.

## License
Apache-2.0 © 2026 Sanju Sajimon
