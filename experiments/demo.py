#!/usr/bin/env python3
"""Synthetic Germany demo:
   - national risk dashboard (real OSM basemap)
   - national time-slider (watch the ground move 2018->2024)
   - Staufen building-scale focus
   - temporal-pattern figures (onset / seasonal / accelerating)
"""
from pathlib import Path
from egms_tools.cli import _pipeline
from egms_tools import (synthetic_germany_field, synthetic_germany_assets,
                        synthetic_focus, analyse, build_timeslider)
from egms_tools.dashboard import build_dashboard
from egms_tools.report import plot_pattern
from egms_tools.actionable import coverage_report, inspection_queue, truncate_field, movers
from egms_tools import synthetic_density_points, build_density_map, build_app
from egms_tools import synthetic_land_changes, export_compliance

if __name__ == "__main__":
    out = Path("results"); out.mkdir(exist_ok=True)

    assets = synthetic_germany_assets(seed=0)
    field = synthetic_germany_field(seed=0, assets=assets)
    results = _pipeline(field, assets, out)

    # actionable outputs: coverage (incompleteness), inspection queue, movers
    coverage_report(results, out / "coverage_report.md")
    queue = inspection_queue(results, out)
    print(f"inspection queue: {len(queue)} assets need action")
    # simulate an earlier EGMS release (cut series at mid-2023) and diff
    prev_field = truncate_field(field, 2023.5)
    _, prev_res = analyse(prev_field, assets)
    chg = movers(prev_res, results, out / "movers_since_last_release.md")
    print(f"movers since simulated previous release: {len(chg)}")

    # NATIONAL DATA DENSITY — aggregate tens of thousands of points (answers
    # "is there enough data over Germany?")
    dlon, dlat, dvel = synthetic_density_points(seed=0, n=60000)
    build_density_map(dlon, dlat, dvel, out / "dashboard_density.html")
    print(f"density map: {len(dlon):,} points aggregated")

    # temporal: national time-slider
    build_timeslider(field, out / "dashboard_timelapse.html")

    # temporal-pattern figures — one of each archetype if present
    seen = {}
    for r in results:
        if r.archetype and r.archetype not in seen and r.n_points >= 4:
            seen[r.archetype] = r
    for arche, r in seen.items():
        plot_pattern(field, r, out / f"pattern_{arche.split()[0]}_{r.id}.png")
    print("archetypes found:", sorted(seen))

    # Staufen focus
    f, a, bbox = synthetic_focus("Staufen", seed=0)
    cfg, res = analyse(f, a)
    build_dashboard(f, res, a, out / "dashboard_staufen.html",
                    title="Staufen im Breisgau — building-scale ground motion (synthetic demo)",
                    focus_bbox=bbox)
    # one combined single-file app with nav across every view
    # land-use change / compliance (optical hazard layer)
    export_compliance(synthetic_land_changes(seed=0), out)
    build_app(out / "app.html")
    print("wrote national dashboard, time-lapse, Staufen focus, pattern figures, and app.html")
