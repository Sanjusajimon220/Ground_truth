"""Plain-language reports -- the artifact a customer actually pays for."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .analysis import AssetResult
from .synthetic import MotionField

BG, PANEL, INK, MUTED, GRID, OCHRE, SAGE, RED = (
    "#0c0e0f", "#131718", "#ededE6", "#878e8a", "#252b2c", "#e0a64e", "#7fb4ab", "#d8694e")
LEVEL_COLOR = {"OK": SAGE, "Monitor": "#cdb24a", "Investigate": OCHRE, "Act": RED}
KIND_WORD = {"building": "building", "rail": "rail corridor", "pipeline": "pipeline"}

VERDICT = {
    "OK": "No action. Motion is within stable limits.",
    "Monitor": "Keep under observation; re-check at the next EGMS update.",
    "Investigate": "Schedule a site inspection / levelling survey to confirm.",
    "Act": "Prioritise a structural / geotechnical inspection now.",
}


def asset_report(r: AssetResult) -> str:
    if r.n_points < 4:
        return (f"{r.id} ({KIND_WORD.get(r.kind, r.kind)}): too few scatterers "
                f"({r.n_points}) for a reliable estimate — no verdict.")
    direction = "subsiding" if r.velocity < 0 else "rising"
    worsening = (r.velocity * r.acceleration > 0 and abs(r.acceleration) >= 0.8)
    trend = " and the rate is accelerating" if worsening else ""
    if r.archetype == "recent onset" and r.onset_year:
        pattern = f"  Pattern: motion began around {r.onset_year:.0f} (recent onset).\n"
    elif r.archetype == "seasonal (reversible)":
        pattern = (f"  Pattern: seasonal / reversible (±{r.seasonal_amp:.1f} mm annual) "
                   f"— usually not structural.\n")
    elif r.archetype:
        pattern = f"  Pattern: {r.archetype}.\n"
    else:
        pattern = ""
    lines = [
        f"{r.id} — {KIND_WORD.get(r.kind, r.kind)}",
        f"  {direction} at {abs(r.velocity):.1f} mm/yr "
        f"(95% CI {abs(r.velocity_hi):.1f}–{abs(r.velocity_lo):.1f}){trend}.",
        pattern.rstrip("\n") if pattern else None,
        f"  Differential motion across the footprint: {r.differential:.1f} mm/yr "
        f"(distortion proxy).",
        f"  Evidence: {r.n_points} scatterers, mean coherence {r.coherence:.2f} "
        f"→ {r.confidence} confidence.",
        f"  RISK: {r.level.upper()} — {VERDICT[r.level]}",
    ]
    return "\n".join(l for l in lines if l)


def portfolio_summary(results) -> str:
    counts = {k: 0 for k in LEVEL_COLOR}
    for r in results:
        counts[r.level] += 1
    top = sorted([r for r in results if r.n_points >= 4],
                 key=lambda r: r.score, reverse=True)[:5]
    lines = ["# Portfolio ground-motion summary\n",
             f"- Assets assessed: {len(results)}",
             f"- Act: {counts['Act']} · Investigate: {counts['Investigate']} · "
             f"Monitor: {counts['Monitor']} · OK: {counts['OK']}\n",
             "## Highest-priority assets\n"]
    for r in top:
        lines.append(f"- **{r.id}** ({r.kind}) — {r.level}: "
                     f"{r.velocity:+.1f} mm/yr, differential {r.differential:.1f} mm/yr")
    return "\n".join(lines) + "\n"


def _ax(fig):
    ax = fig.add_subplot(111); ax.set_facecolor(PANEL)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9); ax.grid(True, color=GRID, lw=0.6, alpha=0.7)
    return ax


def asset_series(field: MotionField, centroid, radius=40.0):
    cx, cy = centroid
    m = ((field.x - cx) ** 2 + (field.y - cy) ** 2) <= radius ** 2
    if m.sum() == 0:
        m = ((field.x - cx) ** 2 + (field.y - cy) ** 2) <= (radius * 2) ** 2
    w = field.coherence[m]
    return field.dates, np.average(field.disp[m], axis=0, weights=w) if m.sum() else field.dates * 0


def plot_asset_timeseries(field: MotionField, r: AssetResult, path):
    t, s = asset_series(field, r.centroid)
    fig = plt.figure(figsize=(6.6, 3.4), facecolor=BG); ax = _ax(fig)
    ax.plot(t, s, "-o", color=LEVEL_COLOR[r.level], lw=2, ms=3)
    ax.plot(t, r.velocity * (t - t[0]) + s[0], "--", color=INK, lw=1, alpha=0.6)
    ax.set_xlabel("Year", color=MUTED); ax.set_ylabel("Vertical displacement (mm)", color=MUTED)
    ax.set_title(f"{r.id} — {r.velocity:+.1f} mm/yr · {r.level}", color=INK, fontsize=11)
    fig.tight_layout(); fig.savefig(path, dpi=150, facecolor=BG); plt.close(fig)


def plot_pattern(field: MotionField, r: AssetResult, path):
    """Temporal pattern figure: series + trend, with onset / seasonal annotated."""
    t, s = asset_series(field, r.centroid)
    fig = plt.figure(figsize=(7.0, 3.6), facecolor=BG); ax = _ax(fig)
    ax.plot(t, s, "-o", color=OCHRE, lw=2, ms=3, label="displacement")
    ax.plot(t, r.velocity * (t - t[0]) + s[0], "--", color=INK, lw=1, alpha=0.6, label="linear trend")
    if r.onset_year:
        ax.axvline(r.onset_year, color=RED, lw=1.6, ls=":")
        ax.text(r.onset_year, ax.get_ylim()[1], f" onset ~{r.onset_year:.0f}", color=RED,
                fontsize=9, va="top")
    ax.set_xlabel("Year", color=MUTED); ax.set_ylabel("Vertical displacement (mm)", color=MUTED)
    ax.set_title(f"{r.id} — pattern: {r.archetype}", color=INK, fontsize=11.5)
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=MUTED, fontsize=8, loc="lower left")
    fig.tight_layout(); fig.savefig(path, dpi=150, facecolor=BG); plt.close(fig)


def write_reports(field, results, out_dir):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    (out / "portfolio_summary.md").write_text(portfolio_summary(results))
    text = "\n\n".join(asset_report(r) for r in
                       sorted(results, key=lambda r: r.score, reverse=True)
                       if r.n_points >= 4)
    (out / "asset_reports.txt").write_text(text)
    return out / "asset_reports.txt"
