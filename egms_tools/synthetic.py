"""Synthetic EGMS-style ground motion for the whole of Germany.

A *clearly-labelled synthetic* persistent-scatterer (PS) field spanning the
German national bounding box, anchored to the real ground-motion regions in
``germany.HOTSPOTS``. It mimics EGMS in two ways that matter:

* a **sparse national field** for country-wide screening, and
* **dense points on each monitored asset** -- because real EGMS is dense on hard
  targets (buildings, rails) and sparse on fields/forest, and per-asset risk
  needs several scatterers per footprint.

It is synthetic so the whole pipeline runs offline against known ground truth.
The analysis / report / dashboard code is identical for real EGMS: replace
``synthetic_germany_*`` with ``load_egms`` (see ``io.py``).
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
import numpy as np

from .germany import GERMANY, HOTSPOTS, lonlat_to_xy, velocity_field

__all__ = ["MotionField", "Assets", "synthetic_germany_field", "synthetic_germany_assets", "synthetic_focus"]


@dataclass
class MotionField:
    """Persistent-scatterer field (EGMS-like), in local metres + lon/lat."""
    x: np.ndarray            # (N,) metres east of AOI centre
    y: np.ndarray            # (N,) metres north of AOI centre
    lon: np.ndarray          # (N,) longitude
    lat: np.ndarray          # (N,) latitude
    coherence: np.ndarray    # (N,) 0..1 quality
    dates: np.ndarray        # (T,) decimal years
    disp: np.ndarray         # (N, T) cumulative vertical displacement, mm (down -)
    extent: tuple            # (xmin, ymin, xmax, ymax) metres


@dataclass
class Assets:
    """Monitored footprints (buildings / rail / pipeline)."""
    ids: list
    kind: list
    polys: list              # list of (M,2) metre polygons
    meta: dict = dc_field(default_factory=dict)


def _xy_to_lonlat(x, y, aoi=GERMANY):
    lon = aoi.clon + x / (111_320.0 * np.cos(np.radians(aoi.clat)))
    lat = aoi.clat + y / 111_320.0
    return lon, lat


def _rect(cx, cy, w, h):
    return np.array([[cx-w/2, cy-h/2], [cx+w/2, cy-h/2],
                     [cx+w/2, cy+h/2], [cx-w/2, cy+h/2]], float)


def _line_buffer(pts, width):
    pts = np.asarray(pts, float); left, right = [], []
    for i in range(len(pts)):
        a = pts[max(0, i-1)]; b = pts[min(len(pts)-1, i+1)]
        d = b - a; n = np.array([-d[1], d[0]]); nn = n / (np.linalg.norm(n) + 1e-9)
        left.append(pts[i] + nn*width/2); right.append(pts[i] - nn*width/2)
    return np.array(left + right[::-1])


def _hot_xy(name):
    h = next(h for h in HOTSPOTS if h["name"].startswith(name))
    return lonlat_to_xy(h["lon"], h["lat"])


def synthetic_germany_assets(seed=0) -> Assets:
    """Monitored assets clustered on real hotspots + scattered nationwide."""
    rng = np.random.default_rng(seed + 1)
    ids, kind, polys = [], [], []
    # building clusters on selected regions (the stories the demo tells)
    clusters = {"Rhenish": 10, "Lusatia": 8, "Staufen": 8, "Stuttgart": 6,
                "Hamburg": 6, "Munich": 6, "Berlin": 6, "Leipzig": 4}
    i = 0
    for region, k in clusters.items():
        hx, hy = _hot_xy(region)
        for _ in range(k):
            cx = hx + rng.normal(0, 3500); cy = hy + rng.normal(0, 3500)
            w, h = rng.uniform(25, 70, 2)
            ids.append(f"B-{i:04d}"); kind.append("building"); polys.append(_rect(cx, cy, w, h)); i += 1
    # scattered "stable" buildings across the country (mostly OK)
    for _ in range(30):
        lon = rng.uniform(GERMANY.lon_min+1, GERMANY.lon_max-1)
        lat = rng.uniform(GERMANY.lat_min+1, GERMANY.lat_max-1)
        cx, cy = lonlat_to_xy(lon, lat); w, h = rng.uniform(25, 70, 2)
        ids.append(f"B-{i:04d}"); kind.append("building"); polys.append(_rect(cx, cy, w, h)); i += 1
    # a rail corridor crossing the Rhenish subsidence gradient
    rhx, rhy = _hot_xy("Rhenish")
    rail = [(rhx-14000, rhy-9000), (rhx-6000, rhy-3000), (rhx+1000, rhy+2000),
            (rhx+9000, rhy+6000), (rhx+16000, rhy+9000)]
    ids.append("RAIL-RHEIN"); kind.append("rail"); polys.append(_line_buffer(rail, 40))
    # a pipeline crossing the Lusatia subsidence
    lux, luy = _hot_xy("Lusatia")
    pipe = [(lux, luy-16000), (lux+2000, luy-6000), (lux-1000, luy+5000), (lux+3000, luy+15000)]
    ids.append("PIPE-LAUSITZ"); kind.append("pipeline"); polys.append(_line_buffer(pipe, 30))
    return Assets(ids, kind, polys)


def _region_disp(x, y, dates):
    """Cumulative displacement (N, T) summed over all regions, each with its own
    temporal shape: linear + acceleration + seasonal + (optional) onset."""
    t0 = dates[0]; tt = dates - t0
    disp = np.zeros((len(x), len(dates)))
    for h in HOTSPOTS:
        hx, hy = lonlat_to_xy(h["lon"], h["lat"])
        r = h["radius_km"] * 1000.0
        w = np.exp(-(((x - hx) ** 2 + (y - hy) ** 2)) / (2 * (r / 2.2) ** 2))
        onset = h.get("onset")
        ttt = np.clip(dates - onset, 0, None) if onset else tt
        shape = h["vel"] * ttt + 0.5 * h.get("accel", 0.0) * ttt ** 2
        shape = shape + h.get("seasonal", 0.0) * np.sin(2 * np.pi * dates)
        disp += np.outer(w, shape)
    return disp


def _make_disp(x, y, dates, coh, rng):
    """Region drift + small background trend + coherence-scaled noise."""
    drift = _region_disp(x, y, dates)
    vbg = rng.normal(0, 0.4, len(x))                      # background linear texture
    drift = drift + np.outer(vbg, dates - dates[0])
    noise = rng.normal(0, 1.0, (len(x), len(dates))) * (1 + (1 - coh) * 4)[:, None]
    disp = drift + noise
    return (disp - disp[:, :1]).astype(np.float32)


def synthetic_germany_field(seed=0, assets: Assets | None = None,
                            n_background=6000, n_dates=73, t0=2018.0, t1=2024.0,
                            points_per_asset=20, coverage_dropout=0.15):
    """National sparse field + dense points on each asset footprint.

    ``coverage_dropout``: fraction of assets that carry *no* usable scatterers
    (vegetated/new/small roofs) — so the demo shows realistic incompleteness."""
    rng = np.random.default_rng(seed)
    dates = np.linspace(t0, t1, n_dates)

    # --- sparse national background ---
    lon = rng.uniform(GERMANY.lon_min, GERMANY.lon_max, n_background)
    lat = rng.uniform(GERMANY.lat_min, GERMANY.lat_max, n_background)
    bx, by = lonlat_to_xy(lon, lat)

    xs, ys = [bx], [by]
    # --- dense points on assets (real EGMS is dense on hard targets) ---
    if assets is not None:
        for poly in assets.polys:
            if rng.random() < coverage_dropout:
                continue                                  # no scatterers on this asset
            cx, cy = poly[:, 0].mean(), poly[:, 1].mean()
            spread = max(40.0, float(np.ptp(poly[:, 0])), float(np.ptp(poly[:, 1])))
            k = rng.integers(max(2, points_per_asset // 2), points_per_asset + 1)
            xs.append(cx + rng.normal(0, spread, k))
            ys.append(cy + rng.normal(0, spread, k))
    x = np.concatenate(xs); y = np.concatenate(ys)
    lon, lat = _xy_to_lonlat(x, y)

    coh = np.clip(rng.normal(0.80, 0.11, len(x)), 0.3, 0.99)
    disp = _make_disp(x, y, dates, coh, rng)
    return MotionField(x, y, lon, lat, coh, dates, disp, GERMANY.bbox_xy())


def synthetic_focus(place="Staufen", seed=0, n_dates=73, t0=2018.0, t1=2024.0,
                    half_lat=0.007, half_lon=0.011, n_buildings=42, bg=1600,
                    points_per_asset=14):
    """A zoomed focus area around a named hotspot: dense scatterers + a grid of
    building footprints (with exact lat/lon) on the real streets. Returns
    (field, assets, bbox). Footprints are illustrative — use osm.fetch_osm_buildings
    for the real ones."""
    h = next(h for h in HOTSPOTS if h["name"].startswith(place))
    clon, clat = h["lon"], h["lat"]
    bbox = (clat - half_lat, clon - half_lon, clat + half_lat, clon + half_lon)
    rng = np.random.default_rng(seed + 7)

    ids, kind, polys, latlon = [], [], [], []
    nx, ny = 7, 6
    for i in range(n_buildings):
        gx, gy = i % nx, i // nx
        lon = clon - half_lon*0.8 + (gx/(nx-1))*1.6*half_lon + rng.normal(0, half_lon*0.04)
        lat = clat - half_lat*0.8 + (gy/(ny-1))*1.6*half_lat + rng.normal(0, half_lat*0.04)
        cx, cy = lonlat_to_xy(lon, lat)
        w, hgt = rng.uniform(12, 26, 2)
        poly = _rect(cx, cy, w, hgt)
        plon, plat = _xy_to_lonlat(poly[:, 0], poly[:, 1])
        polys.append(poly); latlon.append(np.column_stack([plat, plon]))
        ids.append(f"ST-{i:03d}"); kind.append("building")
    assets = Assets(ids, kind, polys, meta={"latlon": latlon, "source": "synthetic-focus"})

    dates = np.linspace(t0, t1, n_dates)
    lon_bg = rng.uniform(bbox[1], bbox[3], bg); lat_bg = rng.uniform(bbox[0], bbox[2], bg)
    bx, by = lonlat_to_xy(lon_bg, lat_bg)
    xs, ys = [bx], [by]
    for poly in polys:
        cx, cy = poly[:, 0].mean(), poly[:, 1].mean()
        xs.append(cx + rng.normal(0, 22, points_per_asset))
        ys.append(cy + rng.normal(0, 22, points_per_asset))
    x = np.concatenate(xs); y = np.concatenate(ys)
    lon, lat = _xy_to_lonlat(x, y)
    coh = np.clip(rng.normal(0.82, 0.10, len(x)), 0.3, 0.99)
    disp = _make_disp(x, y, dates, coh, rng)
    extent = (float(x.min()), float(y.min()), float(x.max()), float(y.max()))
    field = MotionField(x, y, lon, lat, coh, dates, disp, extent)
    return field, assets, bbox


def synthetic_density_points(seed=0, n=50000, urban_frac=0.7):
    """Lightweight national PS cloud (lon, lat, velocity) at realistic density —
    dense on cities, sparse in between. Velocity only (no time series), so it's
    cheap enough to show the *true* data volume EGMS has over Germany."""
    from .germany import CITIES
    rng = np.random.default_rng(seed)
    n_urban = int(n * urban_frac)
    # urban: clustered on cities
    ci = rng.integers(0, len(CITIES), n_urban)
    clon = np.array([CITIES[i][1] for i in ci]); clat = np.array([CITIES[i][2] for i in ci])
    ulon = clon + rng.normal(0, 0.06, n_urban)
    ulat = clat + rng.normal(0, 0.045, n_urban)
    # rural: sparse, uniform across the country
    n_rural = n - n_urban
    rlon = rng.uniform(GERMANY.lon_min, GERMANY.lon_max, n_rural)
    rlat = rng.uniform(GERMANY.lat_min, GERMANY.lat_max, n_rural)
    lon = np.concatenate([ulon, rlon]).clip(GERMANY.lon_min, GERMANY.lon_max)
    lat = np.concatenate([ulat, rlat]).clip(GERMANY.lat_min, GERMANY.lat_max)
    x, y = lonlat_to_xy(lon, lat)
    vel, _ = velocity_field(x, y)
    vel = vel + rng.normal(0, 1.0, len(x))
    return lon, lat, vel.astype(np.float32)


def _micro_anomalies(seed=0, n=170):
    """Many small local ground-motion features near cities (+ some rural), so the
    surface has realistic district-level texture everywhere, not just at hotspots."""
    from .germany import CITIES
    rng = np.random.default_rng(seed + 99)
    out = []
    for _ in range(n):
        if rng.random() < 0.72 and CITIES:
            _, lo, la = CITIES[rng.integers(len(CITIES))]
            lon = lo + rng.normal(0, 0.07); lat = la + rng.normal(0, 0.05)
        else:
            lon = rng.uniform(GERMANY.lon_min, GERMANY.lon_max)
            lat = rng.uniform(GERMANY.lat_min, GERMANY.lat_max)
        vel = rng.normal(-2.2, 3.6)
        if rng.random() < 0.16:
            vel = abs(vel)
        out.append((float(lon), float(lat), float(vel), float(rng.uniform(1.0, 4.5))))
    return out


def _anom_field(x, y, anoms):
    z = np.zeros(len(x), float)
    for lon, lat, vel, rad in anoms:
        hx, hy = lonlat_to_xy(lon, lat); r = rad * 1000.0
        z += vel * np.exp(-(((x - hx) ** 2 + (y - hy) ** 2)) / (2 * (r / 2.0) ** 2))
    return z


def synthetic_density_components(seed=0, n=60000, urban_frac=0.72):
    """Dense national cloud with BOTH vertical and east-west velocities, plus rich
    local texture. Returns (lon, lat, vertical, east_west, anomalies)."""
    from .germany import CITIES
    rng = np.random.default_rng(seed)
    n_urban = int(n * urban_frac)
    ci = rng.integers(0, len(CITIES), n_urban)
    clon = np.array([CITIES[i][1] for i in ci]); clat = np.array([CITIES[i][2] for i in ci])
    ulon = clon + rng.normal(0, 0.06, n_urban); ulat = clat + rng.normal(0, 0.045, n_urban)
    n_rural = n - n_urban
    rlon = rng.uniform(GERMANY.lon_min, GERMANY.lon_max, n_rural)
    rlat = rng.uniform(GERMANY.lat_min, GERMANY.lat_max, n_rural)
    lon = np.concatenate([ulon, rlon]).clip(GERMANY.lon_min, GERMANY.lon_max)
    lat = np.concatenate([ulat, rlat]).clip(GERMANY.lat_min, GERMANY.lat_max)
    x, y = lonlat_to_xy(lon, lat)
    anoms = _micro_anomalies(seed)
    vfield, _ = velocity_field(x, y)
    vert = vfield + _anom_field(x, y, anoms) + rng.normal(0, 0.8, len(x))
    ew = _anom_field(x, y, _micro_anomalies(seed + 5, n=120)) * 0.6 + rng.normal(0, 0.6, len(x))
    return lon, lat, vert.astype(np.float32), ew.astype(np.float32), anoms


def city_risk_stats(seed=0, half_lat=0.06):
    """Per-city planning statistics over each city's metro grid."""
    from .germany import CITIES
    anoms = _micro_anomalies(seed)
    out = []
    for name, lon, lat in CITIES:
        bbox = (lat - half_lat, lon - 1.5 * half_lat, lat + half_lat, lon + 1.5 * half_lat)
        gy = np.linspace(bbox[0], bbox[2], 42); gx = np.linspace(bbox[1], bbox[3], 52)
        GX, GY = np.meshgrid(gx, gy); X, Y = lonlat_to_xy(GX.ravel(), GY.ravel())
        vf, _ = velocity_field(X, Y); v = vf + _anom_field(X, Y, anoms)
        out.append(dict(name=name, lat=lat, lon=lon, bbox=list(bbox),
                        pct_sub=round(100 * float((v < -2).mean()), 1),
                        pct_up=round(100 * float((v > 2).mean()), 1),
                        max_sub=round(float(v.min()), 1), max_up=round(float(v.max()), 1),
                        mean=round(float(v.mean()), 1)))
    out.sort(key=lambda c: c["max_sub"])
    return out
