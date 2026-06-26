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

__all__ = ["load_egms", "export_results"]


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
