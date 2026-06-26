"""egms-tools: make the free European Ground Motion Service usable — for Germany.

Turn Copernicus EGMS persistent-scatterer data into per-asset ground-motion
risk: attach scatterers to buildings / rail / pipelines, fit robust velocity
and acceleration with confidence, score risk honestly, and report it in plain
language. Study area: the whole of Germany. Open core of GroundTruth.
"""
__version__ = "0.23.0"
from .germany import GERMANY, HOTSPOTS, velocity_field, lonlat_to_xy
from .synthetic import (synthetic_germany_field, synthetic_germany_assets,
                        synthetic_focus, MotionField, Assets)
from .analysis import analyse, RiskConfig, AssetResult
from .io import load_egms, load_egms_l3, egms_deformation_override, export_results
from .osm import fetch_osm_buildings, buildings_to_geojson, load_buildings_geojson
from .temporal import decompose, classify, ARCHETYPES
from .dashboard_temporal import build_timeslider
from .actionable import coverage_report, inspection_queue, truncate_field, movers
from .landuse import synthetic_land_changes, landuse_summary, compliance_queue, export_compliance
from .heat import synthetic_heat_components, city_heat_stats, landsat_lst_image, landsat_lst_points, landsat_lst_to_drive, grid_from_array
from .change import s2_composite, classify, detect_change, change_to_parcels
from .synthetic import synthetic_density_points
from .dashboard_density import build_density_map
from .dashboard_app import build_app

__all__ = ["GERMANY", "HOTSPOTS", "velocity_field", "lonlat_to_xy",
           "synthetic_germany_field", "synthetic_germany_assets", "synthetic_focus",
           "MotionField", "Assets", "analyse", "RiskConfig", "AssetResult",
           "load_egms", "load_egms_l3", "egms_deformation_override", "export_results", "fetch_osm_buildings",
           "buildings_to_geojson", "load_buildings_geojson",
           "decompose", "classify", "ARCHETYPES", "build_timeslider",
           "coverage_report", "inspection_queue", "truncate_field", "movers",
           "synthetic_density_points", "build_density_map", "build_app",
           "synthetic_land_changes", "landuse_summary", "compliance_queue", "export_compliance",
           "synthetic_heat_components", "city_heat_stats", "landsat_lst_image", "landsat_lst_points", "landsat_lst_to_drive", "grid_from_array",
           "s2_composite", "classify", "detect_change", "change_to_parcels", "__version__"]
