import numpy as np
from egms_tools import (synthetic_germany_field, synthetic_germany_assets,
                        analyse, export_results, velocity_field, GERMANY, HOTSPOTS)


def _demo(seed=0):
    a = synthetic_germany_assets(seed=seed)
    f = synthetic_germany_field(seed=seed, assets=a)
    return f, a


def test_field_spans_germany():
    f, a = _demo()
    assert f.lon.min() >= GERMANY.lon_min - 0.1 and f.lon.max() <= GERMANY.lon_max + 0.1
    assert "RAIL-RHEIN" in a.ids and "PIPE-LAUSITZ" in a.ids


def test_velocity_field_has_hotspots():
    # at a known subsidence hotspot the field is strongly negative
    from egms_tools.germany import lonlat_to_xy
    hx, hy = lonlat_to_xy(6.50, 50.95)            # Rhenish lignite
    v, _ = velocity_field(np.array([hx]), np.array([hy]))
    assert v[0] < -7.0


def test_subsidence_and_act_detected():
    f, a = _demo()
    _, res = analyse(f, a)
    assert any(r.level == "Act" for r in res)
    assert min(r.velocity for r in res if r.n_points >= 4) < -7.0


def test_staufen_accelerating_uplift_flagged():
    f, a = _demo()
    _, res = analyse(f, a)
    # an asset that is rising (vel>0) AND accelerating (accel>0) -> Act
    worsening_uplift = [r for r in res if r.velocity > 4 and r.acceleration > 0.3]
    assert any(r.level == "Act" for r in worsening_uplift)


def test_export(tmp_path):
    f, a = _demo()
    _, res = analyse(f, a)
    assert export_results(res, tmp_path / "r.csv").exists()


def test_focus_has_gradient_and_act():
    from egms_tools import synthetic_focus
    f, a, bbox = synthetic_focus("Staufen", seed=0)
    _, res = analyse(f, a)
    levels = {r.level for r in res}
    assert "Act" in levels and len(levels) >= 2          # centre Act, edges taper
    assert max(r.velocity for r in res) > 6              # uplift (heave)


def test_geojson_roundtrip(tmp_path):
    from egms_tools import synthetic_focus, buildings_to_geojson, load_buildings_geojson
    _, a, _ = synthetic_focus("Staufen", seed=0)
    p = buildings_to_geojson(a, tmp_path / "b.geojson")
    a2 = load_buildings_geojson(p)
    assert len(a2.ids) == len(a.ids) and a2.meta["latlon"] is not None


def test_temporal_archetypes_detected():
    a = synthetic_germany_assets(seed=0)
    f = synthetic_germany_field(seed=0, assets=a)
    _, res = analyse(f, a)
    arch = {r.archetype for r in res if r.n_points >= 4}
    # the synthetic regions include an onset (Stuttgart 2021) and seasonal (Berlin/Munich)
    assert "recent onset" in arch
    assert "seasonal (reversible)" in arch
    # a seasonal, reversible asset should not be escalated to Act
    seasonal = [r for r in res if r.archetype == "seasonal (reversible)"]
    assert all(r.level != "Act" for r in seasonal)


def test_actionable_outputs(tmp_path):
    from egms_tools import coverage_report, inspection_queue, truncate_field, movers
    a = synthetic_germany_assets(seed=0)
    f = synthetic_germany_field(seed=0, assets=a)   # has coverage dropout
    _, res = analyse(f, a)
    cov = coverage_report(res, tmp_path / "cov.md")
    assert cov["unmeasured"] > 0 and cov["coverage_pct"] < 100   # incompleteness shown
    q = inspection_queue(res, tmp_path)
    assert len(q) > 0 and (tmp_path / "inspection_queue.geojson").exists()
    prev_field = truncate_field(f, 2023.5)
    _, prev = analyse(prev_field, a)
    chg = movers(prev, res, tmp_path / "movers.md")
    assert isinstance(chg, list)


def test_density_map(tmp_path):
    from egms_tools import synthetic_density_points, build_density_map
    lon, lat, vel = synthetic_density_points(seed=0, n=8000)
    p = build_density_map(lon, lat, vel, tmp_path / "d.html")
    assert p.exists() and (tmp_path / "d.html").stat().st_size > 1000
    assert len(lon) == 8000


def test_build_app(tmp_path):
    from egms_tools import build_app
    p = build_app(tmp_path / "app.html")
    h = p.read_text()
    assert h.stat if False else (tmp_path / "app.html").stat().st_size > 50000
    # all eight views present
    for v in ["overview", "risk", "cities", "corridor", "staufen", "timelapse", "coverage", "queue", "concepts"]:
        assert f'id="v-{v}"' in h


def test_landuse(tmp_path):
    from egms_tools import synthetic_land_changes, landuse_summary, compliance_queue, export_compliance
    ch = synthetic_land_changes(seed=0)
    assert len(ch) > 50
    s = landuse_summary(ch)
    assert s["violations"] >= 1 and s["total"] == len(ch)
    q = compliance_queue(ch)
    assert q and q[0]["compliance"] == "violation"
    export_compliance(ch, tmp_path)
    assert (tmp_path / "land_changes.geojson").exists()
