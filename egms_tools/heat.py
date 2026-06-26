"""Urban heat — the thermal hazard layer.

Land-surface-temperature (LST) anomaly relative to the rural baseline: urban
heat islands run hotter than their surroundings, which is a regulated climate-
adaptation concern for cities (EU). In production this comes from **Landsat
thermal bands** (LST), optionally fused with land cover and Sentinel-2 NDVI;
here it is synthetic and clearly labelled.

Shares the same core as the other layers (grid, surface PNG, click-readout,
per-city stats, map UI).
"""
from __future__ import annotations

import numpy as np

from .germany import GERMANY, CITIES

__all__ = ["synthetic_heat_components", "city_heat_stats"]


def _city_peaks(seed):
    rng = np.random.default_rng(seed + 7)
    # bigger/denser cities run hotter; deterministic per city
    return {name: float(rng.uniform(4.0, 9.0)) for name, _, _ in CITIES}


def synthetic_heat_components(seed=0, n=45000, urban_frac=0.72):
    """Return (lon, lat, lst) where lst = °C above the rural baseline."""
    rng = np.random.default_rng(seed + 3)
    peaks = _city_peaks(seed)
    n_urban = int(n * urban_frac)
    ci = rng.integers(0, len(CITIES), n_urban)
    clon = np.array([CITIES[i][1] for i in ci]); clat = np.array([CITIES[i][2] for i in ci])
    pk = np.array([peaks[CITIES[i][0]] for i in ci])
    ulon = clon + rng.normal(0, 0.05, n_urban); ulat = clat + rng.normal(0, 0.04, n_urban)
    r2 = ((ulon - clon) * np.cos(np.radians(ulat))) ** 2 + (ulat - clat) ** 2
    ulst = pk * np.exp(-r2 / (2 * 0.035 ** 2)) + rng.normal(0, 0.7, n_urban)
    n_rural = n - n_urban
    rlon = rng.uniform(GERMANY.lon_min, GERMANY.lon_max, n_rural)
    rlat = rng.uniform(GERMANY.lat_min, GERMANY.lat_max, n_rural)
    rlst = rng.normal(0.0, 0.6, n_rural)
    cool = rng.random(n_rural) < 0.15                    # green / water patches run cooler
    rlst[cool] -= rng.uniform(0.5, 2.0, int(cool.sum()))
    lon = np.concatenate([ulon, rlon]).clip(GERMANY.lon_min, GERMANY.lon_max)
    lat = np.concatenate([ulat, rlat]).clip(GERMANY.lat_min, GERMANY.lat_max)
    lst = np.concatenate([ulst, rlst])
    return lon, lat, lst.astype(np.float32)


def city_heat_stats(lon, lat, lst, half_lat=0.07):
    lon = np.asarray(lon); lat = np.asarray(lat); lst = np.asarray(lst)
    out = []
    for name, clo, cla in CITIES:
        m = (lat >= cla - half_lat) & (lat <= cla + half_lat) & \
            (lon >= clo - 1.4 * half_lat) & (lon <= clo + 1.4 * half_lat)
        v = lst[m]
        if len(v) < 25:
            continue
        out.append(dict(name=name, lat=cla, lon=clo,
                        bbox=[cla - half_lat, clo - 1.4 * half_lat, cla + half_lat, clo + 1.4 * half_lat],
                        mean=round(float(v.mean()), 1), max=round(float(np.percentile(v, 98)), 1),
                        pct_hot=round(100 * float((v > 3).mean()), 1), n=int(len(v))))
    out.sort(key=lambda c: -c["max"])
    return out


# ---------------------------------------------------------------------------
# REAL DATA — Landsat 8/9 land-surface temperature via Google Earth Engine.
# Runs in YOUR environment:  pip install earthengine-api ; earthengine authenticate
# Output matches synthetic_heat_components(): (lon, lat, lst_celsius) point cloud,
# so it drops straight into build_app's heat layer.
# ---------------------------------------------------------------------------

def landsat_lst_image(bbox, start, end, max_cloud=20):
    """Return an ee.Image of land-surface temperature in °C over bbox
    (south, west, north, east) for the date window [start, end].

    Uses Landsat 8 & 9 Collection-2 Level-2, which ships a calibrated
    surface-temperature band (ST_B10). Scaling per USGS C2L2:
        Kelvin  = ST_B10 * 0.00341802 + 149.0
        Celsius = Kelvin - 273.15
    (If you must start from raw Band 10 radiance instead, the chain is
    radiance -> brightness temperature -> emissivity-corrected LST, with
    emissivity from NDVI using Bands 4 & 5 — but C2L2 ST_B10 already did this.)
    """
    import ee
    s, w, n, e = bbox
    region = ee.Geometry.Rectangle([w, s, e, n])

    def prep(img):
        qa = img.select("QA_PIXEL")
        cloud = qa.bitwiseAnd(1 << 3).Or(qa.bitwiseAnd(1 << 4))   # cloud + shadow
        lst_c = img.select("ST_B10").multiply(0.00341802).add(149.0).subtract(273.15)
        return lst_c.updateMask(cloud.Not()).rename("LST").clip(region)

    col = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
           .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"))
           .filterBounds(region).filterDate(start, end)
           .filter(ee.Filter.lt("CLOUD_COVER", max_cloud))
           .map(prep))
    return col.median().rename("LST"), region


def landsat_lst_points(bbox, start, end, scale=200, max_pixels=60000, max_cloud=20):
    """Sample the real LST image to a (lon, lat, lst_celsius) point cloud —
    same signature shape as synthetic_heat_components(), ready for the app."""
    import ee
    img, region = landsat_lst_image(bbox, start, end, max_cloud)
    fc = img.sample(region=region, scale=scale, numPixels=max_pixels,
                    geometries=True).getInfo()
    lon, lat, lst = [], [], []
    for f in fc["features"]:
        c = f["geometry"]["coordinates"]; v = f["properties"].get("LST")
        if v is None:
            continue
        lon.append(c[0]); lat.append(c[1]); lst.append(float(v))
    return np.array(lon), np.array(lat), np.array(lst, dtype=np.float32)
