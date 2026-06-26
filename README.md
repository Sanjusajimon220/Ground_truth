# egms-tools

**Make the free European Ground Motion Service usable — across the whole of Germany.**

Germany is covered, for free, by a millimetre-precision map of how the ground is moving: the Copernicus **European Ground Motion Service (EGMS)**, built from Sentinel-1 InSAR. It's one of the most valuable open geospatial datasets in the country — and almost nobody who needs it can use it, because it ships as enormous tables of persistent-scatterer points that take InSAR expertise to read. `egms-tools` is the bridge: it turns EGMS into **per-asset ground-motion risk** for the people who own things that crack, tilt or sink.

> **This is the main project** — the open core of **GroundTruth**, ground-motion intelligence for infrastructure. Study area: **Germany**. By Sanju Sajimon (M.Sc. Remote Sensing, KIT; ex-surveyor & civil engineer). See [`CONCEPTS.md`](CONCEPTS.md) for *why points / what accuracy / temporal patterns*, [`EXPLAINER.md`](EXPLAINER.md) for "what is EGMS," and [`ARCHITECTURE.md`](ARCHITECTURE.md) for what every file does.

## What it does

```
EGMS scatterers (Germany)  ─►  attach to your assets  ─►  robust velocity + acceleration (with CI)
                                                       ─►  differential motion (distortion proxy)
                                                       ─►  honest risk (OK/Monitor/Investigate/Act) + report + dashboard
```

It surfaces evidence and uncertainty; it does not replace a geotechnical inspection. Risk thresholds are explicit, documented defaults to calibrate per asset class.

## Quickstart

```bash
pip install -e .
egms demo --out results          # synthetic, Germany-wide, no data (tiles load in your browser)
#   -> results/dashboard.html          (national screening, real OSM basemap)
#      results/dashboard_staufen.html   (building-scale focus on a real map)
#      results/asset_reports.txt, portfolio_summary.md, results.csv
#      results/dashboard_timelapse.html    (time-slider: watch the ground move)
#      results/pattern_*.png             (temporal archetypes: onset / seasonal / accelerating)
#      results/inspection_queue.csv/.geojson  (ranked work list)
#      results/coverage_report.md         (incompleteness accounting)
#      results/movers_since_last_release.md
#      results/timeseries_*.png
egms app --out results/app.html  # ONE file, click between every view
pytest -q                        # 11 tests, CPU-only
```

The dashboards render on a **real OpenStreetMap basemap** (Leaflet) — your scatterers and building footprints sit at their true coordinates on real streets; click a footprint for its report and displacement history. The national view screens all of Germany; the **Staufen im Breisgau** focus zooms to building scale, where geothermal drilling triggered real ground heave that cracked the historic core (flagged *Act — rising and accelerating*). The map tiles are real OSM; the motion is synthetic for the demo (needs internet to load tiles).

### Real OSM footprints (any area)

```python
from egms_tools import fetch_osm_buildings, analyse, load_egms
assets = fetch_osm_buildings(47.8765, 7.7255, 47.8815, 7.7325)  # bbox: real Staufen footprints
field  = load_egms("EGMS_tile.csv")
cfg, results = analyse(field, assets)                            # real buildings + real motion
```

## On real EGMS (Germany)

```python
from egms_tools import load_egms, analyse
field = load_egms("EGMS_L3_E38N32_100km_U.csv")   # free EGMS tile (vertical product)
cfg, results = analyse(field, my_assets)           # my_assets: footprints from OSM / cadastre
```

`load_egms` parses the EGMS CSV shape (one row per scatterer; one displacement column per date `YYYYMMDD`); everything downstream is identical to the demo. EGMS distributes Germany as 100 km × 100 km tiles (EPSG:3035) — download them free (registration) from the Copernicus EGMS portal, and clip to official German boundaries (BKG VG250). For real data: `pip install -e ".[real]"` (pandas + shapely).

## Purpose of each file (short version — full detail in `ARCHITECTURE.md`)

| File | Purpose |
|---|---|
| `egms_tools/germany.py` | The study area: Germany bbox, real ground-motion regions, the velocity field. |
| `egms_tools/synthetic.py` | The **only synthetic part** — a Germany-wide demo PS field + monitored assets. |
| `egms_tools/io.py` | Load **real** EGMS tile CSVs into the same structure; export results. |
| `egms_tools/osm.py` | Fetch **real** OSM building footprints (Overpass) for any area; GeoJSON cache. |
| `egms_tools/analysis.py` | The brain: attach · robust velocity (+CI) · acceleration · differential · risk. |
| `egms_tools/temporal.py` | Temporal patterns: decompose a time series → trend, seasonal, **onset**; classify archetype. |
| `egms_tools/actionable.py` | Actionable outputs: coverage/incompleteness report, ranked inspection queue (CSV+GeoJSON), movers (what changed). |
| `egms_tools/landuse.py` | **Land-use change & compliance** (optical hazard layer): change parcels + compliance queue (CSV+GeoJSON). |
| `egms_tools/heat.py` | **Urban heat** (thermal hazard layer): land-surface-temperature anomaly + per-city heat stats. |
| `egms_tools/report.py` | Plain-language per-asset reports, portfolio summary, displacement figures. |
| `egms_tools/dashboard.py` | Interactive risk dashboard on a **real OSM basemap** (Leaflet): footprints + scatterers, click-through reports. National + focus. |
| `egms_tools/dashboard_temporal.py` | **Time-slider** dashboard — watch cumulative ground motion evolve over time on the real map. |
| `egms_tools/dashboard_density.py` | **National density map** — aggregate tens of thousands of points into a grid (data-volume + mean-velocity view). |
| `egms_tools/dashboard_app.py` | **Combined single-file app** — one HTML, nav across every view: risk surface (vertical/horizontal toggle, search, click-to-read), **city planning** (per-city stats), **corridor/path risk**, Staufen, time-lapse, coverage, queue, concepts. Optical basemaps (Sentinel-2 + hi-res satellite). |
| `egms_tools/cli.py` | `egms demo` (synthetic Germany) and `egms run` (real tiles). |
| `experiments/demo.py` | The Germany demo as a script. |
| `tests/test_egms.py` | 5 fast tests (Germany coverage, hotspots, subsidence/heave flagged, export). |
| `configs/demo.yaml` | Demo + risk parameters in one place. |

## Honest scope

The demo runs on **clearly-labelled synthetic data** so the whole pipeline works offline with known ground truth — it validates the method, not a real site, and the regional velocities are illustrative. Point it at real EGMS tiles for real measurements; only `germany.py` and `synthetic.py` are synthetic — `analysis`, `report`, `dashboard` and `io` are the real product.

## License
Apache-2.0 © 2026 Sanju Sajimon
