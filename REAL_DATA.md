# Going to real data — the three pipelines

The app demo is synthetic where noted. Each hazard layer becomes real through a
**different** pipeline. Build them one at a time. All real loaders output the
**same shape** as their synthetic counterpart, so they drop into `build_app`.

| Layer | Real source | Loader (in this repo) | Output shape |
|---|---|---|---|
| Ground deformation | EGMS L2/L3 (real today) | `io.load_egms()` | points → `MotionField` |
| Urban heat | Landsat 8/9 C2L2 `ST_B10` | `heat.landsat_lst_points()` | `(lon, lat, lst_°C)` |
| Land-use change | Sentinel-2 SR + classifier | `change.*` | parcels (app schema) |

Run the optical/thermal loaders in **your** environment (the sandbox can't reach
Earth Engine / USGS):

```bash
pip install earthengine-api
earthengine authenticate
```

---

## 1. Ground deformation — already real

EGMS gives real InSAR. `egms_tools.io.load_egms(csv_path)` parses an EGMS export
into a `MotionField`; everything downstream (velocity, acceleration, temporal
classification, risk surface) already runs on it. Download tiles from the
Copernicus EGMS portal (Basic/Calibrated/L2 = building scale, L3 Ortho = 100 m
Vertical + East-West). For currency past the EGMS lag, process your own
Sentinel-1 (SBAS/DS-InSAR) — that is the moat.

## 2. Urban heat — Landsat 8/9 Band 10 → real °C

You were right that Band 10 is the thermal channel. The clean route uses
Collection-2 **Level-2**, which already ships a calibrated surface-temperature
band `ST_B10`:

```
Kelvin  = ST_B10 * 0.00341802 + 149.0
Celsius = Kelvin - 273.15
```

(The manual route from raw Band 10 is radiance → brightness temperature →
emissivity-corrected LST, with emissivity from NDVI via Bands 4 & 5. C2L2 has
already done this for you.)

```python
from egms_tools.heat import landsat_lst_points
# bbox = (south, west, north, east); summer window for peak heat
lon, lat, lst = landsat_lst_points(
    bbox=(47.3, 5.9, 55.1, 15.0),     # all Germany
    start="2024-06-01", end="2024-09-15", scale=200)
# feed into build_app's heat layer exactly like synthetic_heat_components()
```

Real values vary by scene/date (Karlsruhe in summer ≈ 25–40 °C LST), and
mosaicking the window gives **full-Germany** coverage (many path/rows). For a
clean national map, raise `scale` (e.g. 300–1000 m) or export the image and
tile it; per-pixel 30 m sampling over the whole country is too many points to
pull through `getInfo()` in one call — process per region/UTM zone and merge.

## 3. Land-use change — Sentinel-2 + your classifier (EGMS does NOT provide this)

```python
import ee; ee.Initialize()
from egms_tools.change import s2_composite, classify, detect_change, change_to_parcels

bbox = (48.9, 8.2, 49.1, 8.6)  # one AOI (e.g. Karlsruhe) to start
img0, region = s2_composite(bbox, "2019-05-01", "2019-09-30")
img1, _      = s2_composite(bbox, "2024-05-01", "2024-09-30")

c0 = classify(img0, model=None)   # rule-based fallback; swap in SegFormer
c1 = classify(img1, model=None)

change = detect_change(c0, c1)
parcels = change_to_parcels(change, region, year=2024, scale=20, min_ha=0.2)
# parcels match landuse.synthetic_land_changes() schema -> drop into build_app
```

`classify(img, model=...)` is the hook for your **SegFormer** (NEXUS: 5-channel,
7-class, 89.4% mIoU). Tile the composite, predict, mosaic, and remap the 7
classes to {water, vegetation, built, bare}. Then join the parcels with cadastral
/ zoning / protected-area layers to set `compliance` = permitted / review /
violation (the demo defaults everything to `review`).

---

## Recommended order

1. **One AOI, real EGMS** (deformation) — validate against known damage.
2. **Same AOI, Landsat LST** (heat) — real °C, fast win, few lines.
3. **Same AOI, Sentinel-2 change** with the rule-based classifier, then swap in
   SegFormer — the hardest layer and where your ML is the differentiator.

Land one buyer on the layer they care about, on real data, before widening.
