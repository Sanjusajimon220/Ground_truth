"""Fetch real building footprints from OpenStreetMap (Overpass API).

Run this in your own environment to pull the real footprints for any area, then
feed them straight into the pipeline as ``Assets``:

    from egms_tools.osm import fetch_osm_buildings
    from egms_tools import load_egms, analyse
    assets = fetch_osm_buildings(47.8765, 7.7255, 47.8815, 7.7325)   # Staufen core
    field  = load_egms("EGMS_tile.csv")
    cfg, results = analyse(field, assets)

Notes
-----
* Overpass serves a normal HTTP client fine; use POST and an explicit
  ``Accept: application/json`` + a descriptive ``User-Agent``. (A headless
  *browser* fetch can be refused with HTTP 406 — that's a browser header quirk,
  not a problem with this code.)
* Be polite: small bounding boxes, cache to GeoJSON, don't hammer the API.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np

from .germany import lonlat_to_xy
from .synthetic import Assets

__all__ = ["fetch_osm_buildings", "buildings_to_geojson", "load_buildings_geojson"]

OVERPASS = "https://overpass-api.de/api/interpreter"


def _ways_to_assets(elements) -> Assets:
    ids, kind, polys, latlon = [], [], [], []
    for el in elements:
        if el.get("type") != "way" or "geometry" not in el:
            continue
        geom = el["geometry"]
        if len(geom) < 3:
            continue
        lon = np.array([p["lon"] for p in geom]); lat = np.array([p["lat"] for p in geom])
        x, y = lonlat_to_xy(lon, lat)
        polys.append(np.column_stack([x, y]))
        latlon.append(np.column_stack([lat, lon]))
        ids.append(f"OSM-{el['id']}")
        tags = el.get("tags", {})
        kind.append("rail" if tags.get("railway") else
                    "pipeline" if tags.get("man_made") == "pipeline" else "building")
    return Assets(ids, kind, polys, meta={"latlon": latlon, "source": "osm"})


def fetch_osm_buildings(south, west, north, east, timeout=60,
                        user_agent="egms-tools/0.2 (https://github.com/Sanjusajimon220)") -> Assets:
    """Return building footprints in a bbox as an ``Assets`` object."""
    import requests
    q = (f'[out:json][timeout:25];'
         f'(way["building"]({south},{west},{north},{east}););out geom;')
    r = requests.post(OVERPASS, data={"data": q},
                      headers={"Accept": "application/json", "User-Agent": user_agent},
                      timeout=timeout)
    r.raise_for_status()
    return _ways_to_assets(r.json().get("elements", []))


def buildings_to_geojson(assets: Assets, path):
    """Save asset footprints (lon/lat) as GeoJSON for caching / the dashboard."""
    feats = []
    latlon = assets.meta.get("latlon")
    for i, (aid, kind, poly) in enumerate(zip(assets.ids, assets.kind, assets.polys)):
        if latlon is not None:
            ring = [[float(lo), float(la)] for la, lo in latlon[i]]
        else:
            from .germany import GERMANY
            import numpy as _np
            lon = GERMANY.clon + poly[:, 0] / (111_320.0 * _np.cos(_np.radians(GERMANY.clat)))
            lat = GERMANY.clat + poly[:, 1] / 111_320.0
            ring = [[float(a), float(b)] for a, b in zip(lon, lat)]
        feats.append({"type": "Feature", "properties": {"id": aid, "kind": kind},
                      "geometry": {"type": "Polygon", "coordinates": [ring]}})
    Path(path).write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    return path


def load_buildings_geojson(path) -> Assets:
    gj = json.loads(Path(path).read_text())
    ids, kind, polys, latlon = [], [], [], []
    for f in gj["features"]:
        ring = np.array(f["geometry"]["coordinates"][0])        # [lon, lat]
        lon, lat = ring[:, 0], ring[:, 1]
        x, y = lonlat_to_xy(lon, lat)
        polys.append(np.column_stack([x, y])); latlon.append(np.column_stack([lat, lon]))
        ids.append(f["properties"].get("id", f"OSM-{len(ids)}"))
        kind.append(f["properties"].get("kind", "building"))
    return Assets(ids, kind, polys, meta={"latlon": latlon, "source": "geojson"})
