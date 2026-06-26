"""Load real EGMS, and export results.

The European Ground Motion Service distributes per-tile CSVs of persistent
scatterers: one row per point with longitude, latitude, height, a mean velocity
(mm/yr) and one displacement column per acquisition date (``YYYYMMDD``), plus
quality fields. ``load_egms`` parses that shape into the same ``MotionField``
the synthetic generator produces, so the rest of the library is unchanged.

Download EGMS tiles (free, registration required) from the Copernicus EGMS
portal; the L3 "Ortho" product gives vertical + east-west components on a 100 m
grid, which is the easiest starting point.
"""
from __future__ import annotations

from pathlib import Path
import json
import csv
import numpy as np

from .synthetic import MotionField

__all__ = ["load_egms", "load_egms_l3", "egms_deformation_override", "export_results"]


def load_egms(path, lat_col="latitude", lon_col="longitude",
              coh_col="coherence", center_lat=51.16, center_lon=10.45) -> MotionField:  # pragma: no cover
    """Parse an EGMS CSV (one row per PS; date columns named YYYYMMDD)."""
    import pandas as pd
    df = pd.read_csv(path)
    date_cols = [c for c in df.columns if c.isdigit() and len(c) == 8]
    dates = np.array([int(c[:4]) + (int(c[4:6]) - 1) / 12 + (int(c[6:]) - 1) / 365
                      for c in date_cols], float)
    lat = df[lat_col].to_numpy(float); lon = df[lon_col].to_numpy(float)
    clat = center_lat if center_lat is not None else float(np.median(lat))
    clon = center_lon if center_lon is not None else float(np.median(lon))
    x = (lon - clon) * 111_320.0 * np.cos(np.radians(clat))
    y = (lat - clat) * 111_320.0
    disp = df[date_cols].to_numpy(float)
    disp = disp - disp[:, :1]
    coh = df[coh_col].to_numpy(float) if coh_col in df else np.full(len(df), 0.8)
    extent = (float(x.min()), float(y.min()), float(x.max()), float(y.max()))
    return MotionField(x, y, lon, lat, coh, dates, disp.astype(np.float32), extent)


def export_results(results, path):
    rows = [r.__dict__ for r in results]
    p = Path(path)
    if p.suffix == ".json":
        p.write_text(json.dumps(rows, indent=2, default=float))
    else:
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            for r in rows:
                w.writerow({k: (v if not isinstance(v, tuple) else f"{v[0]:.1f},{v[1]:.1f}")
                            for k, v in r.items()})
    return p


def load_egms_l3(path, vel_col="mean_velocity", max_points=None):  # pragma: no cover
    """Parse a real EGMS L3 Ortho CSV (easting/northing in EPSG:3035).

    Returns a dict: lon, lat (arrays), vel (mm/yr), disp (n x t cumulative mm,
    re-zeroed to the first epoch), dates (decimal years), date_cols (YYYYMMDD).
    Reprojects ETRS89-LAEA (EPSG:3035) -> WGS84 lon/lat with pyproj.
    """
    import pandas as pd
    from pyproj import Transformer
    df = pd.read_csv(path)
    if max_points and len(df) > max_points:
        df = df.sample(max_points, random_state=0).reset_index(drop=True)
    date_cols = [c for c in df.columns if str(c).isdigit() and len(str(c)) == 8]
    tr = Transformer.from_crs("EPSG:3035", "EPSG:4326", always_xy=True)
    lon, lat = tr.transform(df["easting"].to_numpy(float),
                            df["northing"].to_numpy(float))
    vel = df[vel_col].to_numpy(float)
    disp = df[date_cols].to_numpy(float)
    disp = disp - disp[:, :1]
    dates = np.array([int(c[:4]) + (int(c[4:6]) - 1) / 12 + (int(c[6:]) - 1) / 365
                      for c in date_cols], float)
    return {"lon": np.asarray(lon), "lat": np.asarray(lat), "vel": vel,
            "disp": disp.astype(np.float32), "dates": dates, "date_cols": date_cols}


def egms_deformation_override(egms, bbox=None, clip_poly=None, nx=360, ny=360,
                              vmin=-10, vmax=10, max_dist_deg=0.03,
                              margin=0.05):  # pragma: no cover
    """Turn parsed EGMS L3 (from load_egms_l3) into a deformation_override dict
    for build_app: real velocity surface + click grid + yearly time-lapse.

    By default the surface is rendered over the DATA's own bounding box (so a
    single 100x100 km tile shows up densely and the map zooms to it), with no
    national clipping. Pass ``bbox`` (south, west, north, east) and/or
    ``clip_poly`` only if you want to force a wider frame or clip to a polygon.
    Mirrors the heat_override shape so build_app handles it the same way.
    """
    from .surface import interpolate_grid, grid_payload, RISK_STOPS, surface_png_stops
    lon, lat, vel = egms["lon"], egms["lat"], egms["vel"]
    if bbox is None:                                  # fit to the tile's real extent
        s = float(np.nanmin(lat)) - margin; n = float(np.nanmax(lat)) + margin
        w = float(np.nanmin(lon)) - margin; e = float(np.nanmax(lon)) + margin
        bbox = (s, w, n, e)
    Z, _, _ = interpolate_grid(lon, lat, vel, bbox, nx=nx, ny=ny,
                               max_dist_deg=max_dist_deg, clip_poly=clip_poly)
    png = surface_png_stops(Z, RISK_STOPS, vmin=vmin, vmax=vmax, alpha=0.85)
    bounds = [[bbox[0], bbox[1]], [bbox[2], bbox[3]]]
    grid = grid_payload(Z, bbox, step=2)
    filled = int(np.isfinite(Z).sum())
    out = {"png": png, "bounds": bounds, "grid": grid,
           "n_points": int(len(vel)), "filled_cells": filled,
           "stats": {"min": float(np.nanmin(vel)), "max": float(np.nanmax(vel)),
                     "mean": float(np.nanmean(vel))}}
    # yearly time-lapse from the cumulative displacement columns
    disp, dates = egms["disp"], egms["dates"]
    years = sorted({int(d) for d in dates})
    frames, fdates = [], []
    for y in years:
        idx = np.where(dates.astype(int) == y)[0]
        if len(idx) == 0:
            continue
        cum = disp[:, idx[-1]]                        # cumulative displacement by year-end
        Zy, _, _ = interpolate_grid(lon, lat, cum, bbox, nx=nx, ny=ny,
                                    max_dist_deg=max_dist_deg, clip_poly=clip_poly)
        frames.append(surface_png_stops(Zy, RISK_STOPS, vmin=-40, vmax=40, alpha=0.85))
        fdates.append(str(y))
    if frames:
        out["timelapse"] = {"frames": frames, "dates": fdates, "bounds": bounds}
    return out


