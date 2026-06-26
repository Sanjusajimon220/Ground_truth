"""Germany as the study area.

GroundTruth focuses on **Germany**: the Copernicus European Ground Motion
Service (EGMS) covers the whole country, distributed as 100 km x 100 km tiles
(EPSG:3035). This module pins down the national study area and a catalogue of
*real* German ground-motion regions, so the synthetic demo is anchored to places
a German grant panel will recognise. On real data you clip EGMS tiles to the
official German administrative boundaries (BKG VG250) using these same helpers.

Nothing here measures real motion — the velocities in ``HOTSPOTS`` are
*illustrative*, chosen to reflect the *kind* of motion each region is known for
(mining subsidence, mine-water rebound uplift, peat subsidence, anhydrite heave,
groundwater changes). Swap ``synthetic_*`` for ``load_egms`` to use real values.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

__all__ = ["AOI", "GERMANY", "HOTSPOTS", "lonlat_to_xy", "velocity_field"]


@dataclass
class AOI:
    name: str
    lon_min: float; lat_min: float; lon_max: float; lat_max: float
    clon: float; clat: float

    def bbox_xy(self):
        xs, ys = lonlat_to_xy(np.array([self.lon_min, self.lon_max]),
                              np.array([self.lat_min, self.lat_max]), self)
        return (float(xs[0]), float(ys[0]), float(xs[1]), float(ys[1]))


# national bounding box + centroid of Germany
GERMANY = AOI("Germany", 5.87, 47.27, 15.04, 55.06, clon=10.45, clat=51.16)


def lonlat_to_xy(lon, lat, aoi: AOI = GERMANY):
    """Equirectangular lon/lat -> local metres about the AOI centre.

    Good enough for screening and metre-scale attachment over a country; on real
    data use a proper projection (EGMS is already in EPSG:3035 metres)."""
    x = (np.asarray(lon) - aoi.clon) * 111_320.0 * np.cos(np.radians(aoi.clat))
    y = (np.asarray(lat) - aoi.clat) * 111_320.0
    return x, y


# Real German ground-motion regions. vel = mm/yr at the centre (negative =
# subsidence), accel = mm/yr^2 (negative = subsidence speeding up), radius in km.
HOTSPOTS = [
    dict(name="Rhenish lignite (Hambach/Garzweiler)", lon=6.50, lat=50.95,
         radius_km=22, vel=-11.0, accel=0.0),
    dict(name="Ruhr (mine-water rebound)",            lon=7.20, lat=51.50,
         radius_km=20, vel=+6.0,  accel=0.0),
    dict(name="Lusatia lignite (Lausitz)",            lon=14.30, lat=51.60,
         radius_km=24, vel=-8.0,  accel=0.0),
    dict(name="Leipzig/Halle (post-lignite rebound)", lon=12.20, lat=51.40,
         radius_km=18, vel=+5.0,  accel=0.0),
    dict(name="East Frisia peat (Lower Saxony)",      lon=7.80, lat=53.40,
         radius_km=22, vel=-7.0,  accel=0.0),
    dict(name="Staufen (anhydrite heave)",            lon=7.73, lat=47.88,
         radius_km=1.5, vel=+11.0, accel=+1.0),   # famous, very localised, accelerating
    dict(name="Stuttgart (tunnelling onset 2021)",    lon=9.18, lat=48.78,
         radius_km=8,  vel=-9.0,  accel=0.0, onset=2021.0),  # motion starts mid-series
    dict(name="Munich (gravel/groundwater, seasonal)", lon=11.58, lat=48.14,
         radius_km=14, vel=-3.0,  accel=0.0, seasonal=4.0),  # reversible annual cycle
    dict(name="Berlin (groundwater, seasonal)",       lon=13.40, lat=52.52,
         radius_km=14, vel=-2.0,  accel=0.0, seasonal=5.0),
    dict(name="Hamburg/Elbe soft soil",               lon=9.99, lat=53.55,
         radius_km=14, vel=-5.0,  accel=-0.7),   # mild worsening
]


def velocity_field(x, y, aoi: AOI = GERMANY):
    """Vectorised (vel, accel) in mm/yr & mm/yr^2 at metre coords (x, y)."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    vel = np.zeros_like(x); accel = np.zeros_like(x)
    for h in HOTSPOTS:
        hx, hy = lonlat_to_xy(h["lon"], h["lat"], aoi)
        r = h["radius_km"] * 1000.0
        w = np.exp(-(((x - hx) ** 2 + (y - hy) ** 2)) / (2 * (r / 2.2) ** 2))
        vel = vel + h["vel"] * w
        accel = accel + h["accel"] * w
    return vel, accel


# Major German cities (lon, lat) — used only to give the synthetic density map a
# realistic urban concentration of scatterers (EGMS is dense on cities).
CITIES = [
    ("Berlin", 13.40, 52.52), ("Hamburg", 9.99, 53.55), ("Munich", 11.58, 48.14),
    ("Cologne", 6.96, 50.94), ("Frankfurt", 8.68, 50.11), ("Stuttgart", 9.18, 48.78),
    ("Dusseldorf", 6.78, 51.23), ("Dortmund", 7.47, 51.51), ("Essen", 7.01, 51.46),
    ("Leipzig", 12.37, 51.34), ("Dresden", 13.74, 51.05), ("Hannover", 9.73, 52.37),
    ("Nuremberg", 11.08, 49.45), ("Bremen", 8.80, 53.08), ("Karlsruhe", 8.40, 49.01),
    ("Mannheim", 8.47, 49.49), ("Freiburg", 7.85, 47.99), ("Münster", 7.63, 51.96),
]


# Coarse Germany outline (lon, lat) — for clipping the national risk surface to
# land so it reads as the country (approximate; not a survey boundary).
GERMANY_OUTLINE = [
    (9.4, 54.8), (10.0, 54.4), (11.0, 54.4), (12.5, 54.5), (13.4, 54.1), (14.4, 53.9),
    (14.6, 52.5), (14.7, 51.4), (15.0, 51.3), (14.9, 50.9), (14.3, 51.0), (13.3, 50.6),
    (12.5, 50.4), (12.1, 50.3), (12.4, 49.8), (13.0, 49.3), (12.6, 49.0), (13.8, 48.6),
    (13.0, 48.3), (12.8, 48.0), (13.0, 47.7), (12.2, 47.7), (11.6, 47.6), (10.2, 47.4),
    (10.1, 47.3), (9.6, 47.5), (8.6, 47.8), (7.7, 47.6), (7.6, 47.6), (7.6, 48.1),
    (8.2, 49.0), (6.4, 49.2), (6.1, 49.5), (6.1, 50.0), (6.0, 50.3), (6.3, 50.5),
    (6.0, 51.0), (6.2, 51.5), (6.8, 51.9), (7.0, 52.4), (7.2, 53.2), (7.0, 53.3),
    (8.0, 53.6), (8.5, 53.9), (8.9, 53.9), (9.0, 54.5), (8.6, 54.9), (9.4, 54.8),
]
