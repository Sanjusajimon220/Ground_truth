"""Turn risk results into *actionable* data.

Three outputs an asset owner can act on directly:

* **coverage report** — honest accounting of where we *can* and *cannot* measure
  (the incompleteness problem), so nobody mistakes "no data" for "no movement".
* **inspection queue** — a ranked, exportable work list (CSV + GeoJSON) of the
  assets that need a survey, with a recommended action per asset.
* **movers** — what *changed* between two EGMS releases (newly escalated assets,
  new onsets): the monitoring/early-warning signal.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import numpy as np

from .germany import GERMANY
from .analysis import LEVELS, AssetResult
from .report import VERDICT

__all__ = ["coverage_report", "inspection_queue", "truncate_field", "movers"]


def _centroid_lonlat(c):
    x, y = c
    lon = GERMANY.clon + x / (111_320.0 * np.cos(np.radians(GERMANY.clat)))
    lat = GERMANY.clat + y / 111_320.0
    return float(lon), float(lat)


# ---------------------------------------------------------------- coverage
def coverage_report(results, out_path=None) -> dict:
    """Account for incompleteness: which assets have enough scatterers to judge."""
    total = len(results)
    measured = [r for r in results if r.n_points >= 4]
    unmeasured = [r for r in results if r.n_points < 4]
    by_kind = {}
    for r in results:
        d = by_kind.setdefault(r.kind, [0, 0])
        d[0] += 1
        if r.n_points >= 4:
            d[1] += 1
    summary = dict(
        assets=total,
        measured=len(measured),
        unmeasured=len(unmeasured),
        coverage_pct=round(100 * len(measured) / total, 1) if total else 0.0,
        by_kind={k: {"total": v[0], "measured": v[1]} for k, v in by_kind.items()},
        unmeasured_ids=[r.id for r in unmeasured],
    )
    if out_path:
        L = ["# Coverage / completeness report\n",
             f"- Assets: **{total}** · measured: **{len(measured)}** "
             f"({summary['coverage_pct']}%) · no reliable measurement: **{len(unmeasured)}**\n",
             "Persistent scatterers exist only on radar-stable targets, so some assets "
             "carry too few points to judge. These are **not** 'stable' — they are "
             "**unmeasured**, and need a complementary source (own Sentinel-1 DS-InSAR, "
             "levelling, or GNSS):\n",
             "## Coverage by asset type\n",
             "| Type | Measured / total |", "|---|---|"]
        for k, v in summary["by_kind"].items():
            L.append(f"| {k} | {v['measured']} / {v['total']} |")
        if unmeasured:
            L += ["", "## Unmeasured assets (need ground survey / extra sensor)\n",
                  ", ".join(summary["unmeasured_ids"][:50]) +
                  (" …" if len(summary["unmeasured_ids"]) > 50 else "")]
        Path(out_path).write_text("\n".join(L) + "\n")
    return summary


# ---------------------------------------------------------------- inspection queue
def inspection_rows(results, levels=("Act", "Investigate")):
    """Ranked work list rows (no file I/O)."""
    q = [r for r in results if r.level in levels and r.n_points >= 4]
    q.sort(key=lambda r: (LEVELS.index(r.level), r.score), reverse=True)
    rows = []
    for rank, r in enumerate(q, 1):
        lon, lat = _centroid_lonlat(r.centroid)
        rows.append(dict(priority=rank, id=r.id, kind=r.kind, level=r.level,
                         velocity_mm_yr=round(r.velocity, 1),
                         acceleration=round(r.acceleration, 2),
                         differential_mm_yr=round(r.differential, 1),
                         pattern=r.archetype, confidence=r.confidence,
                         onset_year=("" if r.onset_year is None else round(r.onset_year)),
                         lat=round(lat, 6), lon=round(lon, 6),
                         recommended_action=VERDICT[r.level]))
    return rows


def inspection_queue(results, out_dir, levels=("Act", "Investigate")):
    """Ranked work list of assets needing action -> CSV + GeoJSON."""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    rows = inspection_rows(results, levels)
    feats = [{"type": "Feature",
              "properties": {k: v for k, v in row.items() if k not in ("lat", "lon")},
              "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]}}
             for row in rows]
    if rows:
        with open(out / "inspection_queue.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    (out / "inspection_queue.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}))
    return rows


# ---------------------------------------------------------------- change / movers
def truncate_field(field, t_max):
    """Return a copy of the field with the time series cut at t_max (simulates an
    earlier EGMS release)."""
    from .synthetic import MotionField
    m = field.dates <= t_max
    return MotionField(field.x, field.y, field.lon, field.lat, field.coherence,
                       field.dates[m], field.disp[:, m], field.extent)


def movers(prev_results, curr_results, out_path=None):
    """What changed between two releases: escalations and new onsets."""
    prev = {r.id: r for r in prev_results}
    changes = []
    for r in curr_results:
        p = prev.get(r.id)
        if p is None or r.n_points < 4:
            continue
        escalated = LEVELS.index(r.level) > LEVELS.index(p.level)
        new_onset = r.archetype == "recent onset" and p.archetype != "recent onset"
        accel_up = (r.velocity * (r.velocity - p.velocity) > 0 and
                    abs(r.velocity - p.velocity) > 1.5)   # speeding up in same direction
        if escalated or new_onset or accel_up:
            changes.append(dict(id=r.id, kind=r.kind, from_level=p.level, to_level=r.level,
                                prev_vel=round(p.velocity, 1), now_vel=round(r.velocity, 1),
                                reason=("new onset" if new_onset else
                                        "escalated" if escalated else "rate increased")))
    changes.sort(key=lambda c: LEVELS.index(c["to_level"]), reverse=True)
    if out_path:
        L = ["# What changed since the previous release\n",
             f"- **{len(changes)}** assets changed status.\n",
             "| Asset | Was | Now | Prev mm/yr | Now mm/yr | Why |",
             "|---|---|---|---|---|---|"]
        for c in changes:
            L.append(f"| {c['id']} | {c['from_level']} | **{c['to_level']}** | "
                     f"{c['prev_vel']} | {c['now_vel']} | {c['reason']} |")
        Path(out_path).write_text("\n".join(L) + "\n")
    return changes
