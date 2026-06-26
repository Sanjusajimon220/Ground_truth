"""From a motion field + assets to per-asset risk.

The chain is deliberately transparent (the brand is honest evaluation):

1. **attach** the persistent scatterers that fall on/near each asset,
2. **fit** a robust velocity (Theil-Sen, with a confidence interval) and an
   acceleration (is the motion getting worse?),
3. **differential** motion across the footprint -- the spread of velocities,
   a proxy for tilt / angular distortion, which is what actually cracks
   structures,
4. **score** these into a level (OK / Monitor / Investigate / Act) with a
   confidence that reflects data quality.

Thresholds are *illustrative engineering defaults*, exposed in ``RiskConfig`` so
they are calibrated with a geotechnical/structural engineer per asset class --
the tool surfaces evidence and uncertainty, it does not replace an inspection.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import numpy as np
from scipy.stats import theilslopes

from .synthetic import MotionField, Assets
from . import temporal

__all__ = ["RiskConfig", "AssetResult", "analyse"]

LEVELS = ["OK", "Monitor", "Investigate", "Act"]


@dataclass
class RiskConfig:
    # |velocity| mm/yr thresholds (illustrative serviceability-style defaults)
    v_monitor: float = 2.0
    v_investigate: float = 6.0
    v_act: float = 10.0
    # differential velocity across footprint, mm/yr (distortion proxy)
    diff_investigate: float = 3.0
    diff_act: float = 6.0
    # acceleration that escalates the level, mm/yr^2 (magnitude)
    accel_flag: float = 0.8
    # data sufficiency
    min_points: int = 4
    search_radius_m: float = 55.0


@dataclass
class AssetResult:
    id: str
    kind: str
    n_points: int
    coherence: float
    velocity: float            # mm/yr (negative = subsidence)
    velocity_lo: float
    velocity_hi: float
    acceleration: float        # mm/yr^2
    differential: float        # mm/yr across footprint
    score: float               # 0..100
    level: str
    confidence: str            # low/medium/high
    centroid: tuple
    archetype: str = ""        # temporal pattern (see temporal.classify)
    seasonal_amp: float = 0.0  # reversible annual amplitude, mm
    onset_year: float | None = None  # when motion began, if it began mid-record
    recent_change: float = 0.0       # last-third minus first-third rate, mm/yr


def _poly_centroid(poly):
    return (float(poly[:, 0].mean()), float(poly[:, 1].mean()))


def _bbox(poly, pad):
    return (poly[:, 0].min() - pad, poly[:, 1].min() - pad,
            poly[:, 0].max() + pad, poly[:, 1].max() + pad)


def _attach(field: MotionField, poly, radius):
    """Indices of PS points within the asset's padded bounding box.

    A bbox+radius gate is enough for footprints this size and keeps it fast and
    dependency-free; swap for a true point-in-polygon (shapely) on real data.
    """
    xmin, ymin, xmax, ymax = _bbox(poly, radius)
    m = (field.x >= xmin) & (field.x <= xmax) & (field.y >= ymin) & (field.y <= ymax)
    return np.where(m)[0]


def _robust_velocity(t, d):
    """Theil-Sen slope (mm/yr) + 95% CI."""
    res = theilslopes(d, t)
    return float(res[0]), float(res[2]), float(res[3])


def _acceleration(t, d):
    if len(t) < 5:
        return 0.0
    a = np.polyfit(t - t[0], d, 2)[0]
    return float(2 * a)        # d2/dt2 of a t^2 + b t + c


def _score(vel, diff, accel, cfg: RiskConfig):
    av = abs(vel)
    lvl = 0
    if av >= cfg.v_monitor: lvl = 1
    if av >= cfg.v_investigate: lvl = 2
    if av >= cfg.v_act: lvl = 3
    if diff >= cfg.diff_investigate: lvl = max(lvl, 2)
    if diff >= cfg.diff_act: lvl = max(lvl, 3)
    worsening = abs(accel) >= cfg.accel_flag and vel * accel > 0   # same sign = speeding up
    if worsening:
        lvl = min(3, lvl + 1)
    # 0..100 score for sorting/colour
    s = min(100.0, 12 * av + 9 * diff + 18 * (abs(accel) if worsening else 0.0))
    return float(s), LEVELS[lvl]


def analyse(field: MotionField, assets: Assets, cfg: RiskConfig | None = None):
    cfg = cfg or RiskConfig()
    t = field.dates
    out = []
    for aid, kind, poly in zip(assets.ids, assets.kind, assets.polys):
        idx = _attach(field, poly, cfg.search_radius_m)
        if len(idx) < cfg.min_points:
            out.append(AssetResult(aid, kind, len(idx), float("nan"), float("nan"),
                                   float("nan"), float("nan"), 0.0, 0.0, 0.0,
                                   "OK", "low", _poly_centroid(poly)))
            continue
        # weight by coherence; use the coherence-weighted mean series for the asset
        w = field.coherence[idx]
        series = np.average(field.disp[idx], axis=0, weights=w)
        vel, vlo, vhi = _robust_velocity(t, series)
        accel = _acceleration(t, series)
        # differential = spread of per-point velocities across the footprint
        pv = np.array([theilslopes(field.disp[i], t)[0] for i in idx])
        differential = float(np.percentile(pv, 90) - np.percentile(pv, 10))
        score, level = _score(vel, differential, accel, cfg)
        conf = "high" if (len(idx) >= 12 and w.mean() > 0.7) else \
               "medium" if len(idx) >= 6 else "low"
        tinfo = temporal.decompose(series, t)
        archetype = temporal.classify(tinfo)
        out.append(AssetResult(aid, kind, len(idx), float(w.mean()), vel, vlo, vhi,
                               accel, differential, score, level, conf,
                               _poly_centroid(poly), archetype=archetype,
                               seasonal_amp=tinfo["seasonal_amp"],
                               onset_year=tinfo["onset_year"],
                               recent_change=tinfo["recent_change"]))
    return cfg, out


def to_dicts(results):
    return [asdict(r) for r in results]
