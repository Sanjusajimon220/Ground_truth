"""Temporal change patterns.

EGMS gives a full displacement time series per scatterer, so the most valuable
question is usually not "how fast?" but "*what kind* of motion, and did it
change?". This module decomposes a series into:

* **velocity** — robust linear rate (Theil-Sen),
* **acceleration** — is the rate increasing? (quadratic term),
* **seasonal amplitude** — reversible annual cycle (clay swell/shrink,
  groundwater), which is usually *not* a structural threat,
* **onset** — did motion start partway through the record (a step change in
  rate, e.g. tunnelling, new dewatering)?
* **recent change** — last-third rate minus first-third rate (an early-warning
  signal between EGMS updates),

and classifies an **archetype** that drives how a human should read it. A
seasonal, reversible signal and a recent-onset subsidence have the same average
velocity but completely different meaning — that distinction is the product.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import theilslopes

__all__ = ["decompose", "classify", "ARCHETYPES"]

ARCHETYPES = ["stable", "linear subsidence", "linear uplift",
              "accelerating subsidence", "accelerating uplift",
              "seasonal (reversible)", "recent onset"]


def decompose(series: np.ndarray, dates: np.ndarray) -> dict:
    series = np.asarray(series, float); dates = np.asarray(dates, float)
    t0 = dates[0]; tt = dates - t0
    vel = float(theilslopes(series, dates)[0])
    accel = float(np.polyfit(tt, series, 2)[0] * 2) if len(tt) >= 5 else 0.0

    # seasonal amplitude: detrend, fit an annual sin/cos
    detr = series - (vel * tt + series[0])
    A = np.column_stack([np.cos(2 * np.pi * dates), np.sin(2 * np.pi * dates),
                         np.ones_like(dates)])
    coef, *_ = np.linalg.lstsq(A, detr, rcond=None)
    seasonal_amp = float(np.hypot(coef[0], coef[1]))

    # onset / recent change: compare first-third vs last-third rate
    n = len(dates); k = max(3, n // 3)
    v1 = float(theilslopes(series[:k], dates[:k])[0])
    v2 = float(theilslopes(series[-k:], dates[-k:])[0])
    recent_change = v2 - v1
    onset_year = None
    if abs(v1) < 1.2 and abs(v2) > 3.0:           # quiet, then clearly moving
        # locate onset: where the running deviation from the early-flat line starts
        flat = series[:k].mean()
        dev = np.abs(series - flat)
        thresh = 3 * (np.std(series[:k]) + 1e-6)
        idx = np.argmax(dev > thresh)
        onset_year = float(dates[idx]) if dev[idx] > thresh else float(dates[k])

    return dict(velocity=vel, accel=accel, seasonal_amp=seasonal_amp,
                recent_change=float(recent_change), onset_year=onset_year)


def classify(d: dict) -> str:
    v, a, sa, onset = d["velocity"], d["accel"], d["seasonal_amp"], d["onset_year"]
    if onset is not None:
        return "recent onset"
    if sa > 2.5 and abs(v) < 2.5:
        return "seasonal (reversible)"
    if abs(v) < 1.5:
        return "stable"
    worsening = (v * a > 0) and (abs(a) >= 0.6)
    if v < 0:
        return "accelerating subsidence" if worsening else "linear subsidence"
    return "accelerating uplift" if worsening else "linear uplift"
