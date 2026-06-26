"""Continuous risk surface.

Sparse InSAR points are interpolated (inverse-distance) onto a fine grid and
rendered as a coloured raster you overlay on the map — so the *whole terrain*
reads as a risk surface (green = stable/safe, yellow→red = subsidence, blue =
uplift), with buildings drawn on top where measurements exist. Cells far from any
measurement are left transparent (we don't invent data where there is none).

The raster is returned as a base64 PNG ready for Leaflet's ``L.imageOverlay``,
so the whole thing stays in one self-contained HTML file.
"""
from __future__ import annotations

import base64
import io
import numpy as np

__all__ = ["interpolate_grid", "surface_png", "surface_png_stops",
           "grid_payload", "RISK_STOPS", "HEAT_STOPS"]

# velocity (mm/yr) -> RGB control points: red(sub) .. green(stable) .. blue(uplift)
RISK_STOPS = np.array([
    [-10, 0.85, 0.18, 0.13],
    [-6,  0.88, 0.42, 0.20],
    [-3,  0.82, 0.70, 0.25],
    [-1,  0.30, 0.72, 0.45],
    [0,   0.27, 0.73, 0.47],
    [1,   0.30, 0.72, 0.45],
    [3,   0.37, 0.70, 0.64],
    [6,   0.34, 0.60, 0.80],
    [10,  0.20, 0.42, 0.88],
])


def _risk_rgb(v):
    vs = RISK_STOPS[:, 0]
    r = np.interp(v, vs, RISK_STOPS[:, 1])
    g = np.interp(v, vs, RISK_STOPS[:, 2])
    b = np.interp(v, vs, RISK_STOPS[:, 3])
    return r, g, b


def interpolate_grid(lon, lat, val, bbox, nx=260, ny=300,
                     power=2.0, k=12, max_dist_deg=0.22, clip_poly=None):
    """Inverse-distance interpolation of ``val`` onto a grid over ``bbox``
    = (south, west, north, east). Returns (Z, gridlon, gridlat) with NaN where
    the nearest measurement is further than ``max_dist_deg`` (no data) or, if
    ``clip_poly`` (list of (lon,lat)) is given, outside that polygon."""
    from scipy.spatial import cKDTree
    s, w, n, e = bbox
    lon = np.asarray(lon); lat = np.asarray(lat); val = np.asarray(val)
    tree = cKDTree(np.c_[lon, lat])
    gx = np.linspace(w, e, nx)
    gy = np.linspace(n, s, ny)              # north first -> image row 0 = north
    GX, GY = np.meshgrid(gx, gy)
    q = np.c_[GX.ravel(), GY.ravel()]
    k = min(k, len(lon))
    d, idx = tree.query(q, k=k)
    if k == 1:
        d = d[:, None]; idx = idx[:, None]
    wts = 1.0 / (d ** power + 1e-12)
    Z = (wts * val[idx]).sum(1) / wts.sum(1)
    Z[d[:, 0] > max_dist_deg] = np.nan
    if clip_poly is not None:
        from matplotlib.path import Path
        inside = Path(np.asarray(clip_poly)).contains_points(q)
        Z[~inside] = np.nan
    return Z.reshape(ny, nx), gx, gy


def surface_png(Z, alpha=0.66, gamma_alpha=False):
    """Colour a velocity grid (NaN = transparent) -> base64 PNG string."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ny, nx = Z.shape
    rgba = np.zeros((ny, nx, 4), float)
    mask = ~np.isnan(Z)
    Zc = np.clip(np.nan_to_num(Z), -10, 10)
    r, g, b = _risk_rgb(Zc)
    rgba[..., 0] = r; rgba[..., 1] = g; rgba[..., 2] = b
    a = np.where(mask, alpha, 0.0)
    if gamma_alpha:                          # stronger where motion is larger
        a = np.where(mask, 0.35 + 0.45 * np.clip(np.abs(Zc) / 8, 0, 1), 0.0)
    rgba[..., 3] = a
    buf = io.BytesIO()
    plt.imsave(buf, rgba, format="png")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


HEAT_STOPS = np.array([
    [-2,  0.23, 0.45, 0.85],
    [0,   0.30, 0.62, 0.74],
    [3,   0.85, 0.80, 0.35],
    [6,   0.90, 0.55, 0.22],
    [9,   0.86, 0.32, 0.18],
    [12,  0.62, 0.10, 0.12],
])


def surface_png_stops(Z, stops, vmin, vmax, alpha=0.7):
    """Colour a grid with an arbitrary colour ramp (NaN = transparent)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ny, nx = Z.shape
    rgba = np.zeros((ny, nx, 4), float)
    mask = ~np.isnan(Z)
    Zc = np.clip(np.nan_to_num(Z), vmin, vmax)
    vs = stops[:, 0]
    rgba[..., 0] = np.interp(Zc, vs, stops[:, 1])
    rgba[..., 1] = np.interp(Zc, vs, stops[:, 2])
    rgba[..., 2] = np.interp(Zc, vs, stops[:, 3])
    rgba[..., 3] = np.where(mask, alpha, 0.0)
    buf = io.BytesIO()
    plt.imsave(buf, rgba, format="png")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def grid_payload(Z, bbox, step=2):
    """Downsample a velocity grid into a JSON-friendly payload for client-side
    click-to-read. Row 0 = north (matches interpolate_grid). NaN -> None."""
    Zs = Z[::step, ::step]
    ny, nx = Zs.shape
    flat = [None if np.isnan(v) else int(round(float(v))) for v in Zs.ravel()]
    return {"z": flat, "nx": int(nx), "ny": int(ny), "bbox": [float(b) for b in bbox]}
