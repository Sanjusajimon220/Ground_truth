"""Land-use change & compliance — the optical hazard layer.

Detects parcels where land cover changed between two dates (new construction,
sealed-surface growth, vegetation loss, water change) and flags compliance
(permitted / review / violation, e.g. building or clearing inside a protected or
non-permitted zone).

This is the optical counterpart to the InSAR ground-motion layer, sharing the
same core (grid, map UI, ranked queue export). In production the change map comes
from **Sentinel-2 / Landsat + a land-cover classifier** (the SegFormer model,
89.4% mIoU) differenced across two epochs; here it is synthetic and clearly
labelled.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import numpy as np

from .germany import GERMANY, CITIES, GERMANY_OUTLINE

__all__ = ["synthetic_land_changes", "landuse_summary", "compliance_queue",
           "export_compliance"]


def _in_germany(lon, lat):
    """Ray-cast point-in-polygon against the coarse Germany outline (lon,lat)."""
    inside = False
    n = len(GERMANY_OUTLINE)
    j = n - 1
    for i in range(n):
        xi, yi = GERMANY_OUTLINE[i]
        xj, yj = GERMANY_OUTLINE[j]
        if ((yi > lat) != (yj > lat)) and \
           (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside

TYPES = ["new_construction", "sealed_surface", "vegetation_loss", "water_change"]
TYPE_LABEL = {"new_construction": "New construction",
              "sealed_surface": "Sealed / paved surface",
              "vegetation_loss": "Vegetation cleared",
              "water_change": "Water extent change"}
TYPE_NOTE = {"new_construction": "Built structure on previously non-built land.",
             "sealed_surface": "Impervious surface growth (paving).",
             "vegetation_loss": "Vegetation / tree cover removed.",
             "water_change": "Surface-water extent changed."}


def _area_ha(w_deg, h_deg, lat):
    mx = 2 * w_deg * 111_320.0 * np.cos(np.radians(lat))
    my = 2 * h_deg * 111_320.0
    return mx * my / 10_000.0


def synthetic_land_changes(seed=0, per_city=5, rural=20, t0=2019, t1=2024):
    """Return a list of land-cover change parcels with a compliance flag."""
    rng = np.random.default_rng(seed + 21)
    out = []

    def parcel(lon, lat, typ, protected):
        w = rng.uniform(0.0006, 0.0024); h = rng.uniform(0.0005, 0.0020)
        ring = [[lat - h, lon - w], [lat - h, lon + w], [lat + h, lon + w],
                [lat + h, lon - w], [lat - h, lon - w]]
        area = _area_ha(w, h, lat)
        year = int(rng.integers(t0, t1 + 1))
        if protected and typ in ("new_construction", "vegetation_loss"):
            comp = "violation"
        elif typ == "sealed_surface" and area > 4:
            comp = "review"
        else:
            comp = rng.choice(["permitted", "review"], p=[0.72, 0.28])
        note = TYPE_NOTE[typ] + (" Inside protected / non-permitted zone." if protected else "")
        return dict(id=f"LC-{len(out):04d}", type=typ, compliance=comp,
                    area_ha=round(float(area), 2), year=year,
                    ring=[[round(a, 6), round(b, 6)] for a, b in ring],
                    lat=round(float(lat), 6), lon=round(float(lon), 6),
                    protected=bool(protected), note=note)

    for _, clon, clat in CITIES:
        for _ in range(per_city):
            typ = rng.choice(TYPES, p=[0.4, 0.3, 0.2, 0.1])
            out.append(parcel(clon + rng.normal(0, 0.05), clat + rng.normal(0, 0.04),
                              typ, protected=False))
    for _ in range(rural):
        for _try in range(40):
            lon = rng.uniform(GERMANY.lon_min, GERMANY.lon_max)
            lat = rng.uniform(GERMANY.lat_min, GERMANY.lat_max)
            if _in_germany(lon, lat):
                break
        typ = rng.choice(["vegetation_loss", "new_construction"], p=[0.6, 0.4])
        out.append(parcel(lon, lat, typ, protected=True))
    return out


def landuse_summary(changes):
    by_type = {t: 0 for t in TYPES}
    by_comp = {"permitted": 0, "review": 0, "violation": 0}
    for c in changes:
        by_type[c["type"]] += 1
        by_comp[c["compliance"]] += 1
    return {"total": len(changes), "by_type": by_type, "by_compliance": by_comp,
            "area_ha": round(sum(c["area_ha"] for c in changes), 1),
            "violations": by_comp["violation"]}


_ORDER = {"violation": 0, "review": 1, "permitted": 2}


def compliance_queue(changes):
    q = [c for c in changes if c["compliance"] in ("violation", "review")]
    q.sort(key=lambda c: (_ORDER[c["compliance"]], -c["area_ha"]))
    rows = []
    for rank, c in enumerate(q, 1):
        rows.append(dict(priority=rank, id=c["id"], change=TYPE_LABEL[c["type"]],
                         compliance=c["compliance"], area_ha=c["area_ha"],
                         year=c["year"], lat=c["lat"], lon=c["lon"], note=c["note"]))
    return rows


def export_compliance(changes, out_dir):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    rows = compliance_queue(changes)
    if rows:
        with open(out / "compliance_queue.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    feats = [{"type": "Feature",
              "properties": {"id": c["id"], "change": c["type"], "compliance": c["compliance"],
                             "area_ha": c["area_ha"], "year": c["year"]},
              "geometry": {"type": "Polygon",
                           "coordinates": [[[p[1], p[0]] for p in c["ring"]]]}}
             for c in changes]
    (out / "land_changes.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}))
    return rows
