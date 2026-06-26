"""Land-use change — REAL pipeline (Sentinel-2 + a land-cover classifier).

EGMS does NOT provide this; it is motion only. This module is the optical
counterpart, run in YOUR environment:
    pip install earthengine-api
    earthengine authenticate

Pipeline:
    1. Build a cloud-free Sentinel-2 surface-reflectance composite at two epochs
       (t0, t1) over the AOI.
    2. Classify land cover at each epoch. Plug in your SegFormer model via the
       `classify` hook; a rule-based fallback (NDVI/NDBI/NDWI thresholds) is
       provided so the pipeline runs end-to-end without a trained model.
    3. Difference the two classifications -> change type per pixel.
    4. Vectorise to parcels with the SAME schema as
       landuse.synthetic_land_changes(), so the output drops into build_app.

Classes: 0 water, 1 vegetation, 2 built, 3 bare/soil.
Change types map to the app: vegetation->built = new_construction,
veg/bare->built or sealed growth = sealed_surface, *->bare from veg =
vegetation_loss, water gain/loss = water_change.
"""
from __future__ import annotations

import numpy as np

__all__ = ["s2_composite", "rule_based_landcover", "classify",
           "detect_change", "change_to_parcels"]

CLASS = {"water": 0, "vegetation": 1, "built": 2, "bare": 3}


def s2_composite(bbox, start, end, max_cloud=20):
    """Cloud-masked median Sentinel-2 SR composite over bbox=(s,w,n,e),
    with NDVI / NDBI / NDWI added. Returns (ee.Image, ee.Geometry)."""
    import ee
    s, w, n, e = bbox
    region = ee.Geometry.Rectangle([w, s, e, n])

    def mask(img):
        scl = img.select("SCL")
        keep = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))  # shadow/cloud/cirrus
        return img.updateMask(keep).divide(10000)

    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(region).filterDate(start, end)
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud)).map(mask))
    img = col.median().clip(region)
    ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndbi = img.normalizedDifference(["B11", "B8"]).rename("NDBI")
    ndwi = img.normalizedDifference(["B3", "B8"]).rename("NDWI")
    return img.addBands([ndvi, ndbi, ndwi]), region


def rule_based_landcover(img):
    """Fallback classifier: ee.Image of class codes from spectral indices.
    Replace with `classify(img, model=...)` once your SegFormer is wired in."""
    import ee
    ndvi = img.select("NDVI"); ndbi = img.select("NDBI"); ndwi = img.select("NDWI")
    water = ndwi.gt(0.2)
    veg = ndvi.gt(0.4)
    built = ndbi.gt(0.0).And(ndvi.lt(0.3))
    cls = ee.Image(CLASS["bare"]).rename("class")
    cls = cls.where(built, CLASS["built"]).where(veg, CLASS["vegetation"]).where(water, CLASS["water"])
    return cls.rename("class")


def classify(img, model=None):
    """Land-cover classification hook.

    model=None -> rule_based_landcover (runs in Earth Engine, no training).
    model=<your SegFormer> -> export S2 patches, run the model client-side,
    and return a class raster aligned to `img`. The SegFormer used in NEXUS
    (5-channel, 7-class, 89.4% mIoU) plugs in here; map its 7 classes down to
    the 4 used for change detection.
    """
    if model is None:
        return rule_based_landcover(img)
    raise NotImplementedError(
        "Wire your SegFormer here: tile `img` to patches, predict, mosaic, "
        "and remap the 7 NEXUS classes to {water,vegetation,built,bare}.")


def detect_change(cls_t0, cls_t1):
    """Return an ee.Image 'change' coded: 0 none, 1 new_construction,
    2 sealed_surface, 3 vegetation_loss, 4 water_change."""
    import ee
    veg_to_built = cls_t0.eq(CLASS["vegetation"]).And(cls_t1.eq(CLASS["built"]))
    bare_to_built = cls_t0.eq(CLASS["bare"]).And(cls_t1.eq(CLASS["built"]))
    veg_loss = cls_t0.eq(CLASS["vegetation"]).And(cls_t1.eq(CLASS["bare"]))
    water_chg = cls_t0.eq(CLASS["water"]).neq(cls_t1.eq(CLASS["water"]))
    chg = ee.Image(0).rename("change")
    chg = (chg.where(water_chg, 4).where(veg_loss, 3)
              .where(bare_to_built, 2).where(veg_to_built, 1))
    return chg.selfMask().rename("change")


_TYPE = {1: "new_construction", 2: "sealed_surface", 3: "vegetation_loss", 4: "water_change"}


def change_to_parcels(change_img, region, year, scale=20, min_ha=0.2, max_parcels=400):
    """Vectorise the change raster to parcels matching the app schema:
    dicts with id/type/compliance/area_ha/year/ring/lat/lon/note. Compliance
    here defaults to 'review'; join with zoning/protected-area layers to set
    'violation' vs 'permitted'."""
    import ee
    vec = change_img.reduceToVectors(
        geometry=region, scale=scale, geometryType="polygon",
        eightConnected=True, labelProperty="change",
        maxPixels=1e9, bestEffort=True).getInfo()
    out = []
    for ft in vec["features"][:max_parcels]:
        code = int(ft["properties"]["change"])
        coords = ft["geometry"]["coordinates"][0]
        ring = [[round(c[1], 6), round(c[0], 6)] for c in coords]   # [lat,lon]
        lats = [p[0] for p in ring]; lons = [p[1] for p in ring]
        # shoelace area in m^2 -> ha
        a = 0.0
        for i in range(len(coords) - 1):
            x1, y1 = coords[i]; x2, y2 = coords[i + 1]
            a += x1 * y2 - x2 * y1
        cy = sum(lats) / len(lats)
        area_ha = abs(a) / 2 * (111_320 ** 2) * np.cos(np.radians(cy)) / 10_000
        if area_ha < min_ha:
            continue
        out.append(dict(id=f"LC-{len(out):04d}", type=_TYPE[code], compliance="review",
                        area_ha=round(float(area_ha), 2), year=int(year), ring=ring,
                        lat=round(cy, 6), lon=round(sum(lons) / len(lons), 6),
                        protected=False, note="Detected land-cover change (review against zoning)."))
    return out
