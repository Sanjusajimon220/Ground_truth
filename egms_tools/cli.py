"""Command line: `egms demo` (synthetic Germany) and `egms run` (real EGMS).

`egms demo`  -- runs the whole pipeline on a synthetic, Germany-wide field with
                no data and no network; writes the dashboard, reports and
                figures into the output folder.
`egms run`   -- entry point for real EGMS tiles (see README for the few lines
                that load tiles + your asset footprints, then call analyse()).
"""
from __future__ import annotations
import argparse
from pathlib import Path

from .synthetic import synthetic_germany_field, synthetic_germany_assets
from .analysis import analyse
from .io import export_results
from .report import write_reports, plot_asset_timeseries, portfolio_summary
from .dashboard import build_dashboard


def _pipeline(field, assets, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    cfg, results = analyse(field, assets)
    write_reports(field, results, out)
    export_results(results, out / "results.csv")
    build_dashboard(field, results, assets, out / "dashboard.html")
    top = sorted([r for r in results if r.n_points >= 4],
                 key=lambda r: r.score, reverse=True)[:3]
    for r in top:
        plot_asset_timeseries(field, r, out / f"timeseries_{r.id}.png")
    print(portfolio_summary(results))
    print(f"wrote dashboard + reports to {out}/")
    return results


def main(argv=None):
    p = argparse.ArgumentParser(prog="egms", description="EGMS ground-motion risk (Germany)")
    sub = p.add_subparsers(required=True)
    d = sub.add_parser("demo", help="synthetic Germany-wide end-to-end demo")
    d.add_argument("--out", default="results"); d.add_argument("--seed", type=int, default=0)
    d.set_defaults(func=lambda a: _pipeline(
        synthetic_germany_field(seed=a.seed, assets=synthetic_germany_assets(seed=a.seed)),
        synthetic_germany_assets(seed=a.seed), a.out))
    r = sub.add_parser("run", help="run on real EGMS tiles + your asset footprints")
    r.add_argument("--egms", required=True, help="EGMS tile CSV (or folder)")
    r.add_argument("--out", default="results")
    r.set_defaults(func=lambda a: print(
        "Load your footprints (OSM/cadastre) into an Assets object, then:\n"
        "  from egms_tools import load_egms, analyse\n"
        "  field = load_egms(a.egms); cfg, results = analyse(field, assets)\n"
        "See README -> 'On real EGMS (Germany)'."))
    ap = sub.add_parser("app", help="build the single-file combined app (all views)")
    ap.add_argument("--out", default="results/app.html"); ap.add_argument("--seed", type=int, default=0)
    ap.set_defaults(func=lambda a: (
        Path(a.out).parent.mkdir(parents=True, exist_ok=True),
        print("wrote", __import__("egms_tools").build_app(a.out, seed=a.seed))))
    a = p.parse_args(argv); a.func(a)


if __name__ == "__main__":
    main()
