"""One self-contained HTML app: continuous terrain risk surfaces + buildings.

`build_app(out_path)` generates the synthetic Germany demo and writes a single
HTML file with a nav across every view. The maps now show a **continuous risk
surface** (interpolated from the InSAR points and clipped to land) so the whole
terrain reads as a risk map — green = stable/safe, yellow→red = subsidence,
blue = uplift — with building footprints drawn on top where measurements exist.
Needs internet for the OSM basemap tiles.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np

from .synthetic import (synthetic_germany_assets, synthetic_germany_field,
                        synthetic_focus, synthetic_density_components, city_risk_stats)
from .analysis import analyse
from .dashboard import dashboard_data
from .dashboard_temporal import timeslider_data
from .dashboard_density import density_data
from .actionable import coverage_report, inspection_rows
from .landuse import synthetic_land_changes, landuse_summary, compliance_queue
from .heat import synthetic_heat_components, city_heat_stats
from .surface import (interpolate_grid, surface_png, surface_png_stops,
                      grid_payload, HEAT_STOPS)
from .germany import GERMANY, GERMANY_OUTLINE, HOTSPOTS, CITIES


def _pvel(field):
    span = field.dates[-1] - field.dates[0]
    return (field.disp[:, -1] - field.disp[:, 0]) / span


def _city_stats(lon, lat, vert, half_lat=0.07):
    """Per-city planning stats from the measurement points themselves (same data
    as the surface), so the panel and the click-readout agree."""
    lon = np.asarray(lon); lat = np.asarray(lat); vert = np.asarray(vert)
    out = []
    for name, clo, cla in CITIES:
        bbox = (cla - half_lat, clo - 1.4 * half_lat, cla + half_lat, clo + 1.4 * half_lat)
        m = (lat >= bbox[0]) & (lat <= bbox[2]) & (lon >= bbox[1]) & (lon <= bbox[3])
        v = vert[m]
        if len(v) < 25:
            continue
        out.append(dict(name=name, lat=cla, lon=clo, bbox=list(bbox), n=int(len(v)),
                        pct_sub=round(100 * float((v < -2).mean()), 1),
                        pct_up=round(100 * float((v > 2).mean()), 1),
                        max_sub=round(float(np.percentile(v, 2)), 1),
                        max_up=round(float(np.percentile(v, 98)), 1),
                        mean=round(float(v.mean()), 1)))
    out.sort(key=lambda c: c["max_sub"])
    return out


def build_app(out_path, seed=0):
    assets = synthetic_germany_assets(seed=seed)
    field = synthetic_germany_field(seed=seed, assets=assets)
    _, results = analyse(field, assets)

    risk = dashboard_data(field, results, assets,
                          title="Whole of Germany — terrain risk surface", max_points=10)
    risk["points"] = []                       # surface replaces raw points nationally
    dlon, dlat, dvert, dew, anoms = synthetic_density_components(seed=seed, n=60000)
    dens = density_data(dlon, dlat, dvert, deg=0.15)

    ff, fa, fbbox = synthetic_focus("Staufen", seed=seed)
    _, fres = analyse(ff, fa)
    staufen = dashboard_data(ff, fres, fa, title="Staufen im Breisgau — building scale",
                             focus_bbox=fbbox, max_points=1400)

    nat_bbox = (GERMANY.lat_min, GERMANY.lon_min, GERMANY.lat_max, GERMANY.lon_max)
    Zv, _, _ = interpolate_grid(dlon, dlat, dvert, nat_bbox, nx=300, ny=350,
                                max_dist_deg=0.18, clip_poly=GERMANY_OUTLINE)

    def _mask(Z, band=None, keep_neg=False, keep_pos=False):
        Zc = Z.copy()
        if band is not None:
            Zc[np.abs(np.nan_to_num(Zc)) < band] = np.nan      # hide stable
        if keep_neg:
            Zc[Zc >= -2] = np.nan                               # subsidence only
        if keep_pos:
            Zc[Zc <= 2] = np.nan                                # uplift only
        return Zc

    nat_surface = {"png": surface_png(Zv, alpha=0.72),
                   "png_sig": surface_png(_mask(Zv, band=2), alpha=0.82),
                   "png_sub": surface_png(_mask(Zv, keep_neg=True), alpha=0.85),
                   "png_up": surface_png(_mask(Zv, keep_pos=True), alpha=0.85),
                   "bounds": [[nat_bbox[0], nat_bbox[1]], [nat_bbox[2], nat_bbox[3]]],
                   "grid": grid_payload(Zv, nat_bbox, step=2)}
    Zh, _, _ = interpolate_grid(dlon, dlat, dew, nat_bbox, nx=280, ny=320,
                                max_dist_deg=0.18, clip_poly=GERMANY_OUTLINE)
    nat_surface_ew = {"png": surface_png(Zh, alpha=0.78),
                      "bounds": [[nat_bbox[0], nat_bbox[1]], [nat_bbox[2], nat_bbox[3]]],
                      "grid": grid_payload(Zh, nat_bbox, step=2)}

    Zs, _, _ = interpolate_grid(ff.lon, ff.lat, _pvel(ff), fbbox, nx=220, ny=220,
                                max_dist_deg=0.01)
    st_surface = {"png": surface_png(Zs, alpha=0.6),
                  "bounds": [[fbbox[0], fbbox[1]], [fbbox[2], fbbox[3]]],
                  "grid": grid_payload(Zs, fbbox, step=2)}

    # per-city stats computed from the SAME points that build the surface, so the
    # panel numbers and the click-readout agree
    cities = _city_stats(dlon, dlat, dvert)
    hotspots = [{"name": h["name"], "lat": h["lat"], "lon": h["lon"], "vel": h["vel"]}
                for h in HOTSPOTS]

    # time-lapse surfaces: cumulative displacement at 13 epochs (scaled into the
    # colormap so the deepening is visible)
    T = len(field.dates)
    ei = np.linspace(0, T - 1, 13).round().astype(int)
    frames, dates = [], []
    for e in ei:
        Zt, _, _ = interpolate_grid(field.lon, field.lat, field.disp[:, e] * 0.2,
                                    nat_bbox, nx=150, ny=175, max_dist_deg=0.30,
                                    clip_poly=GERMANY_OUTLINE)
        frames.append(surface_png(Zt, alpha=0.72))
        dates.append(round(float(field.dates[e])))
    timelapse = {"frames": frames, "dates": dates,
                 "bounds": [[nat_bbox[0], nat_bbox[1]], [nat_bbox[2], nat_bbox[3]]]}

    cov = coverage_report(results)
    queue = inspection_rows(results)
    changes = synthetic_land_changes(seed)
    landuse = {"parcels": changes, "summary": landuse_summary(changes),
               "queue": compliance_queue(changes)}
    hlon, hlat, hlst = synthetic_heat_components(seed=seed)
    Zheat, _, _ = interpolate_grid(hlon, hlat, hlst, nat_bbox, nx=300, ny=350,
                                   max_dist_deg=0.18, clip_poly=GERMANY_OUTLINE)
    heat = {"surface": {"png": surface_png_stops(Zheat, HEAT_STOPS, -2, 12, alpha=0.74),
                        "bounds": [[nat_bbox[0], nat_bbox[1]], [nat_bbox[2], nat_bbox[3]]],
                        "grid": grid_payload(Zheat, nat_bbox, step=2)},
            "cities": city_heat_stats(hlon, hlat, hlst)}
    app = {"risk": risk, "staufen": staufen,
           "nat_surface": nat_surface, "nat_surface_ew": nat_surface_ew,
           "st_surface": st_surface, "timelapse": timelapse,
           "hotspots": hotspots, "cities": cities, "landuse": landuse, "heat": heat,
           "coverage": cov, "queue": queue,
           "stats": {"points": dens["total"], "buildings": cov["assets"],
                     "act": risk["counts"].get("Act", 0),
                     "changes": landuse["summary"]["total"],
                     "violations": landuse["summary"]["violations"],
                     "coverage_pct": cov["coverage_pct"], "queue": len(queue)}}
    Path(out_path).write_text(TEMPLATE.replace("__APP__", json.dumps(app)))
    return out_path


TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GroundTruth — ground-motion intelligence</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet-control-geocoder/dist/Control.Geocoder.css"/>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
 :root{--bg:#0c0e0f;--bg2:#131718;--line:#252b2c;--ink:#ededE6;--muted:#878e8a;
   --ochre:#e0a64e;--sage:#7fb4ab;--red:#d8694e;--green:#4cb873;--yellow:#cdb24a;--blue:#3a6fd8;
   --d:'Space Grotesk',sans-serif;--b:'Inter',sans-serif;--m:'JetBrains Mono',monospace;}
 *{box-sizing:border-box}html,body{margin:0;height:100%}
 body{background:var(--bg);color:var(--ink);font-family:var(--b);display:flex;flex-direction:column;height:100vh;overflow:hidden}
 header{display:flex;align-items:center;gap:18px;padding:11px 18px;border-bottom:1px solid var(--line);flex-wrap:wrap}
 .brand{font-family:var(--m);font-size:14px;white-space:nowrap}.brand b{color:var(--ochre);font-weight:500}
 nav{display:flex;gap:4px;flex-wrap:wrap}
 nav button{font-family:var(--m);font-size:12px;background:transparent;color:var(--muted);border:1px solid transparent;border-radius:8px;padding:6px 11px;cursor:pointer}
 nav button:hover{color:var(--ink);border-color:var(--line)}
 nav button.active{color:#170f02;background:var(--ochre);font-weight:600}
 main{flex:1;position:relative;overflow:hidden}
 .view{position:absolute;inset:0;display:none;flex-direction:column}
 .view.show{display:flex}
 .map{flex:1;min-height:0;background:#0c0e0f}
 .bar{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 18px;border-bottom:1px solid var(--line);flex-wrap:wrap}
 .bar h2{font-family:var(--d);font-size:16px;margin:0;font-weight:600}
 .bar .sub{font-family:var(--m);font-size:11px;color:var(--muted)}
 .chips{display:flex;gap:7px;flex-wrap:wrap}
 .chip{font-family:var(--m);font-size:12px;border:1px solid var(--line);border-radius:999px;padding:4px 10px}
 .chip .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:middle}
 .chip b{color:var(--ochre)}
 .scroll{flex:1;overflow:auto;padding:22px 26px}
 .note{font-family:var(--m);font-size:10.5px;color:var(--muted);padding:7px 18px;border-top:1px solid var(--line)}
 .leaflet-popup-content-wrapper,.leaflet-popup-tip{background:var(--bg2);color:var(--ink);border:1px solid var(--line)}
 .leaflet-popup-content{margin:12px 14px;font-family:var(--b);width:300px!important}
 .pop h3{font-family:var(--d);margin:0 0 2px;font-size:16px}
 .pop .lvl{display:inline-block;font-family:var(--m);font-size:11px;padding:2px 8px;border-radius:5px;margin:6px 0}
 .pop pre{white-space:pre-wrap;font-family:var(--m);font-size:11px;color:#c3c8c4;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:9px;line-height:1.5;margin:6px 0 0}
 .legend{font-family:var(--m);font-size:11px;background:rgba(12,14,15,.92);border:1px solid var(--line);border-radius:8px;padding:9px 11px;color:var(--muted);line-height:1.8}
 .legend b{color:var(--ink)}.legend .row{display:flex;align-items:center;gap:6px}
 .legend .sw{width:30px;height:11px;border-radius:3px;display:inline-block}
 .biglegend{background:rgba(12,14,15,.94);border:1px solid var(--line);border-radius:10px;padding:9px 12px;font-family:var(--m);color:var(--ink);min-width:210px}
 .biglegend .ttl{font-size:11px;color:var(--muted);margin-bottom:6px}
 .biglegend .gbar{height:12px;border-radius:6px;background:linear-gradient(90deg,#d92e21,#e06b33,#d1b340,#45b873,#5eb3a3,#3a6fd8)}
 .biglegend .lbl{display:flex;justify-content:space-between;font-size:11px;margin-top:5px}
 .biglegend .lbl b{font-weight:600}
 .biglegend .tk{display:flex;justify-content:space-between;font-size:10px;color:var(--muted);margin-top:2px}
 .leaflet-control-geocoder{border-radius:8px!important}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:6px 0 22px}
 .card{border:1px solid var(--line);border-radius:12px;padding:16px;background:var(--bg2)}
 .card .n{font-family:var(--d);font-size:30px;color:var(--ochre);line-height:1}
 .card .l{font-family:var(--m);font-size:11px;color:var(--muted);margin-top:7px}
 .lead{max-width:760px;line-height:1.65;color:#c9cec9}
 .lead h1{font-family:var(--d);font-size:24px;margin:0 0 6px;color:var(--ink)}
 .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-top:18px;max-width:900px}
 .tile{text-align:left;border:1px solid var(--line);border-radius:12px;padding:15px;background:var(--bg2);cursor:pointer;color:var(--ink)}
 .tile:hover{border-color:var(--ochre)}
 .tile .t{font-family:var(--d);font-size:15px;margin-bottom:4px}
 .tile .dsc{font-family:var(--m);font-size:11px;color:var(--muted);line-height:1.5}
 .cov{max-width:720px}.track{height:14px;border-radius:999px;background:var(--bg2);border:1px solid var(--line);overflow:hidden;margin:10px 0}
 .fill{height:100%;background:var(--green)}
 table{border-collapse:collapse;width:100%;font-size:12.5px}
 th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
 th{font-family:var(--m);font-size:11px;color:var(--muted);position:sticky;top:0;background:var(--bg)}
 td{font-family:var(--b)}tr:hover td{background:var(--bg2)}
 .pill{font-family:var(--m);font-size:11px;padding:2px 8px;border-radius:5px}
 .concepts{max-width:780px;line-height:1.65;color:#c9cec9}
 .concepts h2{font-family:var(--d);color:var(--ink);font-size:18px;margin:22px 0 6px}
 .concepts code{font-family:var(--m);background:var(--bg2);border:1px solid var(--line);border-radius:5px;padding:1px 5px;font-size:12px}
 .ctrl{display:flex;align-items:center;gap:14px;padding:11px 18px;border-top:1px solid var(--line);background:var(--bg2)}
 .play{font-family:var(--m);font-size:13px;background:var(--ochre);color:#170f02;border:none;border-radius:8px;padding:8px 16px;cursor:pointer;font-weight:600}
 input[type=range]{flex:1;accent-color:var(--ochre)}
 .date{font-family:var(--d);font-size:22px;min-width:70px;text-align:right;color:var(--ochre)}
 a{color:var(--ochre)}
</style></head><body>
<header>
 <span class="brand">GroundTruth <b>// ground-motion intelligence</b></span>
 <nav id="nav">
  <button data-v="overview" class="active">Overview</button>
  <button data-v="risk">Risk surface</button>
  <button data-v="cities">City planning</button>
  <button data-v="corridor">Corridor / path</button>
  <button data-v="landuse">Land-use change</button>
  <button data-v="heat">Urban heat</button>
  <button data-v="staufen">Staufen (building)</button>
  <button data-v="timelapse">Time-lapse</button>
  <button data-v="coverage">Coverage</button>
  <button data-v="queue">Inspection queue</button>
  <button data-v="concepts">Concepts</button>
 </nav>
</header>
<main>
 <section class="view show" id="v-overview"><div class="scroll">
   <div class="lead"><h1>From free Copernicus EGMS data to a terrain-wide ground-motion risk surface</h1>
     <p>InSAR measures millimetre vertical ground motion. This tool interpolates those measurements into a continuous risk surface over the whole terrain — green is stable, red is subsiding, blue is rising — and drills down to individual buildings where the data supports it. Motion below is a synthetic demo (clearly labelled); the workflow, surfaces and reports are the real product.</p></div>
   <div class="grid" id="ov-cards"></div>
   <div class="tiles" id="ov-tiles"></div>
 </div></section>

 <section class="view" id="v-risk">
   <div class="bar"><div><h2>Terrain risk surface — whole Germany</h2><div class="sub">continuous interpolated velocity · click a building footprint for its report</div></div><div class="chips" id="risk-chips"></div></div>
   <div class="map" id="map-risk"></div>
   <div class="note">Green = stable, red = sinking, blue = rising. Use <b>show component</b> (top-right) to isolate layers — <b>Hide stable</b> (green off), <b>Subsidence</b> only, <b>Uplift</b> only, or <b>Horizontal</b> (east–west). Switch basemap (Map / Sentinel-2 / hi-res satellite), search your town, or click anywhere to read the motion (with cm-over-a-decade + Safe/Watch/Act).</div>
 </section>

 <section class="view" id="v-cities">
   <div class="bar"><div><h2>City planning</h2><div class="sub">pick a city — district-level subsidence, % of area affected, worst zones</div></div></div>
   <div style="flex:1;display:flex;min-height:0">
     <div id="city-panel" style="width:340px;border-right:1px solid var(--line);overflow:auto;padding:14px 16px"></div>
     <div class="map" id="map-cities" style="flex:1"></div>
   </div>
 </section>

 <section class="view" id="v-corridor">
   <div class="bar"><div><h2>Corridor / path planning</h2><div class="sub">click to add points · click a point to remove it · drag map to pan</div></div><div><button class="play" id="corridor-undo" style="background:transparent;border:1px solid var(--line);color:var(--ink);margin-right:6px">Undo</button><button class="play" id="corridor-clear" style="background:transparent;border:1px solid var(--line);color:var(--ink)">Clear route</button></div></div>
   <div style="flex:1;display:flex;min-height:0">
     <div id="corridor-panel" style="width:340px;border-right:1px solid var(--line);overflow:auto;padding:14px 16px"></div>
     <div class="map" id="map-corridor" style="flex:1"></div>
   </div>
 </section>

 <section class="view" id="v-landuse">
   <div class="bar"><div><h2>Land-use change &amp; compliance</h2><div class="sub">optical change detection (Sentinel-2 + land-cover ML) · click a parcel for details</div></div><div class="chips" id="landuse-chips"></div></div>
   <div style="flex:1;display:flex;min-height:0">
     <div id="landuse-panel" style="width:340px;border-right:1px solid var(--line);overflow:auto;padding:14px 16px"></div>
     <div class="map" id="map-landuse" style="flex:1"></div>
   </div>
 </section>

 <section class="view" id="v-heat">
   <div class="bar"><div><h2>Urban heat</h2><div class="sub">land-surface temperature vs rural (Landsat thermal) · click anywhere to read °C</div></div></div>
   <div style="flex:1;display:flex;min-height:0">
     <div id="heat-panel" style="width:340px;border-right:1px solid var(--line);overflow:auto;padding:14px 16px"></div>
     <div class="map" id="map-heat" style="flex:1"></div>
   </div>
 </section>

 <section class="view" id="v-staufen">
   <div class="bar"><div><h2>Staufen im Breisgau — building scale</h2><div class="sub">risk surface + real building footprints; click a building</div></div><div class="chips" id="staufen-chips"></div></div>
   <div class="map" id="map-staufen"></div>
   <div class="note">Building-scale: the surface plus individual footprints coloured by risk over the real streets. Centre is rising &amp; accelerating (Act); it tapers outward.</div>
 </section>

 <section class="view" id="v-timelapse">
   <div class="bar"><div><h2>Ground motion over time</h2><div class="sub">cumulative displacement surface · red = down, blue = up</div></div></div>
   <div class="map" id="map-timelapse"></div>
   <div class="ctrl"><button class="play" id="tl-play">▶ Play</button>
     <input type="range" id="tl-slider" min="0" value="0"/><div class="date" id="tl-date"></div></div>
 </section>

 <section class="view" id="v-coverage"><div class="scroll"><div class="cov" id="cov-body"></div></div></section>
 <section class="view" id="v-queue"><div class="scroll"><div id="queue-body"></div></div></section>
 <section class="view" id="v-concepts"><div class="scroll"><div class="concepts" id="concepts-body"></div></div></section>
</main>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet-control-geocoder/dist/Control.Geocoder.js"></script>
<script>
const APP = __APP__;
const LC={OK:'#4cb873',Monitor:'#cdb24a',Investigate:'#e0a64e',Act:'#d8694e'};
const STOPS=[[-10,217,46,33],[-6,224,107,51],[-3,209,179,64],[-1,77,184,115],[0,69,186,120],[1,77,184,115],[3,94,179,163],[6,87,153,204],[10,51,107,224]];
function vcol(v){v=Math.max(-10,Math.min(10,v));for(let i=1;i<STOPS.length;i++){if(v<=STOPS[i][0]){const a=STOPS[i-1],b=STOPS[i],t=(v-a[0])/(b[0]-a[0]);
 return `rgb(${Math.round(a[1]+(b[1]-a[1])*t)},${Math.round(a[2]+(b[2]-a[2])*t)},${Math.round(a[3]+(b[3]-a[3])*t)})`;}}const z=STOPS[STOPS.length-1];return `rgb(${z[1]},${z[2]},${z[3]})`;}
function osmLayer(){return L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'});}
function s2Layer(){return L.tileLayer('https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2024_3857/default/g/{z}/{y}/{x}.jpg',{maxZoom:16,attribution:'Sentinel-2 cloudless 2024 © EOX'});}
function esriLayer(){return L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{x}/{y}',{maxZoom:19,attribution:'Imagery © Esri, Maxar, Earthstar Geographics'});}
function terrainLayer(){return L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{x}/{y}',{maxZoom:16,attribution:'Elevation © Esri, USGS, NASA'});}
function dim(m){m.getPane('tilePane').style.filter='grayscale(0.55) brightness(0.55) contrast(1.0)';}
function addBase(m){const osm=osmLayer().addTo(m),s2=s2Layer(),esri=esriLayer(),terr=terrainLayer();
 L.control.layers({'Map (OpenStreetMap)':osm,'Sentinel-2 (10 m optical)':s2,'Satellite hi-res (Esri)':esri,'Terrain / elevation':terr},null,{position:'topright',collapsed:false}).addTo(m);
 m.on('baselayerchange',e=>{m.getPane('tilePane').style.filter=(e.name.indexOf('Map')>=0)?'grayscale(0.55) brightness(0.55) contrast(1.0)':(e.name.indexOf('Terrain')>=0)?'brightness(0.85) contrast(1.1)':'brightness(0.72) contrast(1.05)';});
 dim(m);}
function bigLegend(mode){const c=L.control({position:'bottomleft'});c.onAdd=function(){const d=L.DomUtil.create('div','biglegend');
 const ew=mode==='ew';
 d.innerHTML='<div class="ttl">'+(ew?'horizontal motion (east–west)':'vertical ground motion')+'</div><div class="gbar"></div>'+
  '<div class="lbl"><b style="color:#d8694e">'+(ew?'Westward':'Sinking')+'</b><b style="color:#45b873">Stable</b><b style="color:#3a6fd8">'+(ew?'Eastward':'Rising')+'</b></div>'+
  '<div class="tk"><span>−10</span><span>0</span><span>+10 mm/yr</span></div>'+
  (ew?'':'<div class="tk" style="margin-top:5px;color:#9aa6a0">safe 0–2 · watch 2–6 · act 6+ mm/yr · ≈ cm over 10 yrs</div>');
 L.DomEvent.disableClickPropagation(d);return d;};return c;}
function addSearch(m){try{L.Control.geocoder({defaultMarkGeocode:true,placeholder:'Search your address / town…',position:'topleft'}).addTo(m);}catch(e){}}
function sampleGrid(g,lat,lon){const b=g.bbox,s=b[0],w=b[1],n=b[2],e=b[3];
 if(lat<s||lat>n||lon<w||lon>e)return undefined;
 const col=Math.round((lon-w)/(e-w)*(g.nx-1)),row=Math.round((n-lat)/(n-s)*(g.ny-1));
 return g.z[row*g.nx+col];}
function addReadout(m){m.on('click',e=>{const g=m._grid;if(!g)return;const v=sampleGrid(g,e.latlng.lat,e.latlng.lng);
 const ew=m._mode==='ew';let html;
 if(v===undefined||v===null){html='<div class="pop"><b>Here</b><br><span style="color:#878e8a">no measurement at this spot (outside coverage)</span></div>';}
 else{const word=ew?(v<-2?'moving west':v>2?'moving east':'~stable'):(v<-2?'sinking':v>2?'rising':'stable');
  const col=v<-2?'#d8694e':v>2?'#3a6fd8':'#45b873',cat=Math.abs(v)<2?'Safe':Math.abs(v)<6?'Watch':'Act';
  html=`<div class="pop"><b>${ew?'Horizontal motion':'Ground motion'} here</b><br><span style="font-size:19px;color:${col};font-family:var(--d)">${v>0?'+':''}${v} mm/yr</span> — <b style="color:${col}">${word}</b>`+
   (ew?'':`<br>≈ <b>${Math.abs(v)} cm</b> over 10 years · <b style="color:${col}">${cat}</b>`)+
   `<br><span style="color:#878e8a;font-size:11px">interpolated estimate from nearby InSAR points</span></div>`;}
 L.popup({maxWidth:270}).setLatLng(e.latlng).setContent(html).openOn(m);});}
function addHotspots(m,list){for(const h of (list||[])){const word=h.vel<-2?'sinking':h.vel>2?'rising':'stable',col=h.vel<-2?'#d8694e':h.vel>2?'#3a6fd8':'#45b873';
 L.marker([h.lat,h.lon]).addTo(m).bindPopup(`<div class="pop"><b>${h.name}</b><br><span style="color:${col};font-family:var(--d);font-size:16px">${h.vel>0?'+':''}${h.vel} mm/yr</span> — ${word}</div>`);}}
function componentToggle(m,onChange){const c=L.control({position:'topright'});c.onAdd=function(){const d=L.DomUtil.create('div','biglegend');d.style.minWidth='0';d.style.marginTop='6px';
 const opts=[['vert','Vertical'],['sig','Hide stable'],['sub','Subsidence'],['up','Uplift'],['ew','Horizontal']];
 d.innerHTML='<div class="ttl">show component</div>'+opts.map(o=>`<button class="mt" data-mode="${o[0]}">${o[1]}</button>`).join('');
 d.querySelectorAll('.mt').forEach(b=>{b.style.cssText='font-family:var(--m);font-size:11px;margin:2px 3px 0 0;padding:4px 8px;border-radius:6px;border:1px solid #252b2c;cursor:pointer;background:transparent;color:#ededE6';});
 function act(mode){d.querySelectorAll('.mt').forEach(b=>{const on=b.dataset.mode===mode;b.style.background=on?'#e0a64e':'transparent';b.style.color=on?'#170f02':'#ededE6';});}
 act('vert');d.querySelectorAll('.mt').forEach(b=>b.addEventListener('click',()=>{onChange(b.dataset.mode);act(b.dataset.mode);}));
 L.DomEvent.disableClickPropagation(d);return d;};return c;}

const maps={};
function riskNationalMap(id){
 const m=L.map(id,{preferCanvas:true});addBase(m);
 const ov=L.imageOverlay(APP.nat_surface.png,APP.nat_surface.bounds,{interactive:false}).addTo(m);
 m._grid=APP.nat_surface.grid;m._mode='vert';m._legend=bigLegend('vert').addTo(m);
 addHotspots(m,APP.hotspots);m.fitBounds(APP.nat_surface.bounds);addSearch(m);addReadout(m);
 const S=APP.nat_surface,opts={
  vert:{u:S.png,g:S.grid,l:'vert'},sig:{u:S.png_sig,g:S.grid,l:'vert'},
  sub:{u:S.png_sub,g:S.grid,l:'vert'},up:{u:S.png_up,g:S.grid,l:'vert'},
  ew:{u:APP.nat_surface_ew.png,g:APP.nat_surface_ew.grid,l:'ew'}};
 componentToggle(m,k=>{const o=opts[k];ov.setUrl(o.u);m._grid=o.g;m._mode=o.l;
  m.removeControl(m._legend);m._legend=bigLegend(o.l).addTo(m);}).addTo(m);
 return m;}
function cityMap(id){
 const m=L.map(id,{preferCanvas:true});addBase(m);
 L.imageOverlay(APP.nat_surface.png,APP.nat_surface.bounds,{interactive:false}).addTo(m);
 m._grid=APP.nat_surface.grid;m._mode='vert';bigLegend('vert').addTo(m);addSearch(m);addReadout(m);
 m.fitBounds(APP.nat_surface.bounds);return m;}
function surfaceMap(id,surface,D,opts){opts=opts||{};
 const m=L.map(id,{preferCanvas:true});addBase(m);
 L.imageOverlay(surface.png,surface.bounds,{opacity:1,interactive:false}).addTo(m);
 m._grid=surface.grid;m._mode='vert';
 if(opts.points&&D.points){const cv=L.canvas({padding:0.5});for(const p of D.points)
   L.circleMarker([p[0],p[1]],{renderer:cv,radius:2.2,stroke:false,fillColor:vcol(p[2]),fillOpacity:0.9}).addTo(m);}
 if(D&&D.assets)for(const a of D.assets){const poly=L.polygon(a.coords,{color:'#0c0e0f',weight:1,fillColor:LC[a.level],fillOpacity:0.85}).addTo(m);
  poly.bindPopup(`<div class="pop"><h3>${a.id}</h3><div style="color:#878e8a;font-size:12px">${a.kind}${a.v!=null?` · ${a.v>0?'+':''}${a.v} mm/yr`:''}</div>`+
   `<span class="lvl" style="background:${LC[a.level]}22;color:${LC[a.level]};border:1px solid ${LC[a.level]}">${a.level.toUpperCase()}</span>`+
   a.spark+`<pre>${a.report.replace(/</g,'&lt;')}</pre></div>`,{maxWidth:330});}
 if(opts.hotspots)addHotspots(m,APP.hotspots);
 m.fitBounds(surface.bounds);bigLegend().addTo(m);addSearch(m);addReadout(m);
 return m;}
function corridorBand(v){return (v==null)?'#666':v<-6?'#d8694e':v<-2?'#e0a64e':v>2?'#3a6fd8':'#45b873';}
function corridorMap(id){
 const m=L.map(id,{preferCanvas:true});addBase(m);
 L.imageOverlay(APP.nat_surface.png,APP.nat_surface.bounds,{interactive:false}).addTo(m);
 m._grid=APP.nat_surface.grid;m._mode='vert';bigLegend('vert').addTo(m);addSearch(m);
 m.fitBounds(APP.nat_surface.bounds);
 let pts=[],layer=L.layerGroup().addTo(m);
 function redraw(){layer.clearLayers();
  for(let i=0;i<pts.length-1;i++){const a=pts[i],b=pts[i+1],segs=24;
   for(let s=0;s<segs;s++){const t0=s/segs,t1=(s+1)/segs;
    const p0=[a[0]+(b[0]-a[0])*t0,a[1]+(b[1]-a[1])*t0],p1=[a[0]+(b[0]-a[0])*t1,a[1]+(b[1]-a[1])*t1];
    const v=sampleGrid(m._grid,(p0[0]+p1[0])/2,(p0[1]+p1[1])/2);
    L.polyline([p0,p1],{color:corridorBand(v),weight:5,opacity:0.95}).addTo(layer);}}
  pts.forEach((p,i)=>{const mk=L.circleMarker(p,{radius:5,color:'#e0a64e',weight:2,fill:true,fillColor:'#170f02',fillOpacity:1}).addTo(layer);
   mk.bindTooltip('click to remove',{direction:'top'});
   mk.on('click',ev=>{L.DomEvent.stop(ev);pts.splice(i,1);redraw();});});
  profile();}
 function profile(){const el=document.getElementById('corridor-panel');
  if(pts.length<2){el.innerHTML='<div style="font-family:var(--m);font-size:12px;color:#878e8a;line-height:1.7">Click two or more points on the map to lay out a route (pipeline, rail, road, cycleway…). You\'ll get its ground-motion risk profile — which segments cross sinking ground.</div>';return;}
  let samples=[],cum=0,length=0;
  for(let i=0;i<pts.length-1;i++){const a=pts[i],b=pts[i+1],d=m.distance(a,b),segs=Math.max(6,Math.round(d/300));
   for(let s=0;s<=segs;s++){const t=s/segs,p=[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t];
    const v=sampleGrid(m._grid,p[0],p[1]);samples.push({d:cum+d*t,v:(v==null?0:v),nodata:v==null});}
   cum+=d;}
  length=cum/1000;const valid=samples.filter(s=>!s.nodata);
  const sub=valid.filter(s=>s.v<-2).length, act=valid.filter(s=>s.v<-6).length;
  const worst=valid.length?valid.reduce((a,s)=>s.v<a.v?s:a,valid[0]).v:0;
  const pctsub=valid.length?Math.round(100*sub/valid.length):0;
  // svg profile
  const W=300,H=90,pad=6;const dmax=samples[samples.length-1].d||1;
  let path='';samples.forEach((s,i)=>{const x=pad+(s.d/dmax)*(W-2*pad);const y=H/2-(Math.max(-12,Math.min(12,s.v))/12)*(H/2-pad);path+=(i?'L':'M')+x.toFixed(1)+' '+y.toFixed(1)+' ';});
  let bars='';samples.forEach(s=>{const x=pad+(s.d/dmax)*(W-2*pad);bars+=`<rect x="${x.toFixed(1)}" y="0" width="2" height="${H}" fill="${corridorBand(s.nodata?null:s.v)}" opacity="0.5"/>`;});
  const flag=act>0?['Act','#d8694e']:sub>0?['Watch','#e0a64e']:['OK','#45b873'];
  el.innerHTML=`<div style="border:1px solid ${flag[1]};border-radius:10px;padding:12px;margin-bottom:12px;background:${flag[1]}14">
    <div style="font-family:var(--d);font-size:17px">Route risk: <span style="color:${flag[1]}">${flag[0]}</span></div>
    <div style="font-family:var(--m);font-size:12px;color:#c9cec9;line-height:1.8;margin-top:6px">
     Length: <b>${length.toFixed(1)} km</b><br>
     Over subsiding ground (&gt;2 mm/yr): <b style="color:${pctsub>0?'#e0a64e':'#45b873'}">${pctsub}%</b><br>
     Worst point: <b style="color:${corridorBand(worst)}">${worst.toFixed(1)} mm/yr</b><br>
     High-risk stretch (&gt;6 mm/yr): <b>${act>0?'yes':'no'}</b></div></div>
   <div style="font-family:var(--m);font-size:11px;color:#878e8a;margin-bottom:4px">motion profile along route (start → end)</div>
   <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:90px;background:#131718;border:1px solid #252b2c;border-radius:8px">
     ${bars}<line x1="${pad}" y1="${H/2}" x2="${W-pad}" y2="${H/2}" stroke="#45b873" stroke-width="1" opacity="0.5"/>
     <path d="${path}" fill="none" stroke="#ededE6" stroke-width="1.5"/></svg>
   <div style="font-family:var(--m);font-size:10.5px;color:#878e8a;margin-top:6px">Use this to route pipelines, rail, roads or cycle paths away from sinking ground — or to flag existing corridors for inspection.</div>`;}
 m.on('click',e=>{pts.push([e.latlng.lat,e.latlng.lng]);redraw();});
 const clr=document.getElementById('corridor-clear');if(clr)clr.onclick=()=>{pts=[];layer.clearLayers();profile();};
 const und=document.getElementById('corridor-undo');if(und)und.onclick=()=>{pts.pop();redraw();};
 profile();return m;}
function timelapseMap(id,D){
 const m=L.map(id);addBase(m);
 const ov=L.imageOverlay(D.frames[0],D.bounds,{opacity:1}).addTo(m);m.fitBounds(D.bounds);
 const sl=document.getElementById('tl-slider'),de=document.getElementById('tl-date');sl.max=D.frames.length-1;
 function render(e){ov.setUrl(D.frames[e]);de.textContent=D.dates[e];}render(0);
 sl.oninput=()=>render(+sl.value);
 let playing=false,timer=null;const btn=document.getElementById('tl-play');
 btn.onclick=()=>{playing=!playing;btn.textContent=playing?'❚❚ Pause':'▶ Play';
  if(playing)timer=setInterval(()=>{let v=(+sl.value+1)%D.frames.length;sl.value=v;render(v);},700);else clearInterval(timer);};
 bigLegend().addTo(m);return m;}
function buildCityPanel(){const el=document.getElementById('city-panel');const cs=APP.cities;
 let h='<div style="font-family:var(--m);font-size:11px;color:#878e8a;margin-bottom:8px">Cities ranked by worst local subsidence. Click to zoom in.</div><div id="city-detail"></div>';
 h+=cs.map((c,i)=>`<button class="cityrow" data-i="${i}" style="display:block;width:100%;text-align:left;background:${c.max_sub<-6?'#d8694e16':'transparent'};border:1px solid #252b2c;border-radius:8px;padding:8px 10px;margin-bottom:6px;cursor:pointer;color:#ededE6">
  <div style="font-family:var(--d);font-size:14px">${c.name}</div>
  <div style="font-family:var(--m);font-size:11px;color:#878e8a">worst ${c.max_sub} mm/yr · ${c.pct_sub}% of area subsiding</div></button>`).join('');
 el.innerHTML=h;el.querySelectorAll('.cityrow').forEach(b=>b.onclick=()=>selectCity(+b.dataset.i));}
function selectCity(i){const c=APP.cities[i];if(maps.cities)maps.cities.flyToBounds([[c.bbox[0],c.bbox[1]],[c.bbox[2],c.bbox[3]]],{maxZoom:12});
 const cat=c.max_sub<-6?'Act':c.max_sub<-2?'Watch':'OK',col=c.max_sub<-6?'#d8694e':c.max_sub<-2?'#e0a64e':'#45b873';
 const det=document.getElementById('city-detail');if(det)det.innerHTML=`<div style="border:1px solid ${col};border-radius:10px;padding:12px;margin-bottom:12px;background:${col}14">
  <div style="font-family:var(--d);font-size:17px">${c.name}</div>
  <div style="font-family:var(--m);font-size:12px;color:#c9cec9;line-height:1.8;margin-top:6px">
   Worst subsidence: <b style="color:${col}">${c.max_sub} mm/yr</b> (≈ ${Math.abs(c.max_sub)} cm/decade)<br>
   Area subsiding (&gt;2 mm/yr): <b>${c.pct_sub}%</b><br>
   Area uplifting: <b>${c.pct_up}%</b> · max uplift <b>${c.max_up}</b><br>
   Planning flag: <b style="color:${col}">${cat}</b></div></div>`;}

// overview
const S=APP.stats;
document.getElementById('ov-cards').innerHTML=[
 [S.points.toLocaleString(),'measurement points'],[S.buildings,'assets monitored'],
 [S.act,'need action now (Act)'],[S.changes,'land-use changes'],
 [S.violations,'compliance violations'],[S.queue,'in inspection queue']
].map(c=>`<div class="card"><div class="n">${c[0]}</div><div class="l">${c[1]}</div></div>`).join('');
const TILES=[['risk','Risk surface','Continuous terrain risk over all of Germany; toggle vertical/horizontal, click buildings.'],
 ['cities','City planning','Pick a city → district-level subsidence, % of area affected, worst zones.'],
 ['corridor','Corridor / path','Draw a route — pipeline, rail, road — and read its ground-motion risk profile.'],
 ['landuse','Land-use change','Optical change detection — new build, sealed surface, clearing — with compliance flags.'],
 ['heat','Urban heat','Land-surface temperature vs rural — where the dangerous heat islands are.'],
 ['staufen','Staufen (building)','Building-scale surface + real footprints on a real town.'],
 ['timelapse','Time-lapse','Watch the terrain deform 2018→2024.'],
 ['coverage','Coverage','Where we can and cannot measure — honestly.'],
 ['queue','Inspection queue','Ranked, exportable work list — the actionable output.'],
 ['concepts','Concepts','Ground motion + optical, one core; data, accuracy, currency.']];
document.getElementById('ov-tiles').innerHTML=TILES.map(t=>`<button class="tile" data-go="${t[0]}"><div class="t">${t[1]}</div><div class="dsc">${t[2]}</div></button>`).join('');

function riskChips(el,D){document.getElementById(el).innerHTML=['Act','Investigate','Monitor','OK'].map(k=>`<span class="chip"><span class="dot" style="background:${LC[k]}"></span>${k}: ${D.counts[k]||0}</span>`).join('');}
riskChips('risk-chips',APP.risk);riskChips('staufen-chips',APP.staufen);
(function(){const s=APP.landuse.summary;document.getElementById('landuse-chips').innerHTML=
 `<span class="chip"><span class="dot" style="background:#d8694e"></span>Violations: ${s.by_compliance.violation}</span>`+
 `<span class="chip"><span class="dot" style="background:#cdb24a"></span>Review: ${s.by_compliance.review}</span>`+
 `<span class="chip"><span class="dot" style="background:#45b873"></span>Permitted: ${s.by_compliance.permitted}</span>`;})();

(function(){const c=APP.coverage;let h=`<h2 style="font-family:var(--d);font-size:18px;margin:0 0 4px;color:var(--ink)">Coverage / completeness</h2>`+
 `<p style="color:#c9cec9;line-height:1.6;max-width:680px">Persistent scatterers exist only on radar-stable targets, so some assets carry too few points to judge. These are <b style="color:var(--ink)">not “stable”</b> — they are <b style="color:var(--ink)">unmeasured</b>, and need a complementary source (own Sentinel-1 DS-InSAR, levelling, or GNSS). The terrain surface bridges the gaps with interpolation, shown only where measurements are near.</p>`+
 `<div class="track"><div class="fill" style="width:${c.coverage_pct}%"></div></div>`+
 `<div style="font-family:var(--m);font-size:12px;color:var(--muted)">${c.measured} of ${c.assets} assets measured (${c.coverage_pct}%) · ${c.unmeasured} unmeasured</div>`+
 `<h2 style="font-family:var(--d);font-size:15px;margin:20px 0 6px;color:var(--ink)">By asset type</h2><table><tr><th>Type</th><th>Measured / total</th></tr>`;
 for(const k in c.by_kind)h+=`<tr><td>${k}</td><td>${c.by_kind[k].measured} / ${c.by_kind[k].total}</td></tr>`;h+=`</table>`;
 if(c.unmeasured_ids.length)h+=`<h2 style="font-family:var(--d);font-size:15px;margin:20px 0 6px;color:var(--ink)">Unmeasured (need ground survey / extra sensor)</h2><div style="font-family:var(--m);font-size:12px;color:var(--muted);line-height:1.8">${c.unmeasured_ids.join(', ')}</div>`;
 document.getElementById('cov-body').innerHTML=h;})();

(function(){const q=APP.queue;if(!q.length){document.getElementById('queue-body').innerHTML='<p>No assets currently need action.</p>';return;}
 const cols=['priority','id','kind','level','velocity_mm_yr','differential_mm_yr','pattern','confidence','recommended_action'];
 let h=`<h2 style="font-family:var(--d);font-size:18px;margin:0;color:var(--ink)">Inspection queue</h2><div style="font-family:var(--m);font-size:11px;color:var(--muted);margin-bottom:12px">${q.length} assets ranked by priority · exported as CSV + GeoJSON by the tool</div>`;
 h+='<table><tr>'+cols.map(c=>`<th>${c.replace(/_/g,' ')}</th>`).join('')+'</tr>';
 for(const r of q)h+='<tr>'+cols.map(c=>c==='level'?`<td><span class="pill" style="background:${LC[r.level]}22;color:${LC[r.level]}">${r.level}</span></td>`:`<td>${r[c]}</td>`).join('')+'</tr>';
 h+='</table>';document.getElementById('queue-body').innerHTML=h;})();

document.getElementById('concepts-body').innerHTML=`
 <h2>From points to a terrain surface</h2><p>InSAR measures only at radar-stable reflectors, so raw data is points. We interpolate them into a continuous risk surface (shown only near real measurements) so the <b style="color:var(--ink)">whole terrain</b> reads as risk, then overlay individual buildings where the data supports it.</p>
 <h2>Why not every building, despite mm accuracy?</h2><p>“mm” is the <b style="color:var(--ink)">precision at a point</b>, not the resolution. Building level works where scatterers exist (most masonry/concrete buildings carry several). Use EGMS <code>L2</code> (full density) for building scale; <code>L3</code> is a 100 m grid for regional screening.</p>
 <h2>Temporal patterns</h2><p>Each series is decomposed into velocity, acceleration, <b style="color:var(--ink)">seasonal amplitude</b> and <b style="color:var(--ink)">onset</b>, then classified: stable / linear / accelerating / seasonal-reversible / recent-onset. A reversible seasonal signal and a recent-onset subsidence share an average velocity but mean opposite things.</p>
 <h2>Data sources &amp; currency to 2026</h2><p>Only InSAR measures mm vertical motion; Sentinel-2/Landsat add context (land cover, new construction, vegetation that explains gaps). EGMS is the validated baseline but lags ~1–2 years; your own Sentinel-1 processing reaches the present. Sentinel-1C (2024) is operational and Sentinel-1D (Nov 2025) is fully operational ~April 2026 → full 6-day revisit restored.</p>
 <h2>Two hazards, one core</h2><p>This app combines three satellite hazard layers on one engine: <b style="color:var(--ink)">ground motion</b> from radar (InSAR / EGMS / Sentinel-1), <b style="color:var(--ink)">land-use change &amp; compliance</b> from optical (Sentinel-2 + a land-cover classifier), and <b style="color:var(--ink)">urban heat</b> from thermal (Landsat land-surface temperature). Same grid, same map, same ranked-queue export — sold as separate products to separate buyers, built once. Land-use change detection here is synthetic for the demo; in production it differences a land-cover classification (SegFormer, 89.4% mIoU) across two epochs.</p>
 <h2>Where optical (Sentinel-2 &amp; Landsat) fits — the “complete product”</h2><p>Switch the basemap (top-right) between map, <b style="color:var(--ink)">Sentinel-2</b> (10 m, recent) and <b style="color:var(--ink)">hi-res satellite</b>. Optical does <b style="color:var(--ink)">not</b> measure millimetre motion — but it completes the picture: <b style="color:var(--ink)">Landsat</b> adds a 50-year archive, land-surface temperature (urban heat), and land-cover/change at 30 m, and Sentinel-2 adds recent 10 m detail and new-construction/vegetation context (which explains where InSAR has no points). Motion from radar (Sentinel-1 / EGMS); context and history from optical (Landsat / Sentinel-2) — used honestly, together.</p>
 <h2>What this is for (planning)</h2><p>The same ground-motion layer drives several planning jobs: <b style="color:var(--ink)">city planning</b> (district subsidence, % of area affected), <b style="color:var(--ink)">corridor / path planning</b> (route pipelines, rail, roads and cycleways away from sinking ground — see the Corridor tab), and <b style="color:var(--ink)">asset due-diligence</b> (per-building risk + inspection queue). One honest core measurement, many decisions.</p>`;

const LU_COLOR={new_construction:'#e0a64e',sealed_surface:'#c0664e',vegetation_loss:'#d8694e',water_change:'#3a6fd8'};
const LU_LABEL={new_construction:'New construction',sealed_surface:'Sealed / paved',vegetation_loss:'Vegetation cleared',water_change:'Water change'};
const CMP_COLOR={permitted:'#45b873',review:'#cdb24a',violation:'#d8694e'};
function landuseMap(id){
 const m=L.map(id,{preferCanvas:true});addBase(m);m.fitBounds(APP.nat_surface.bounds);addSearch(m);
 maps._luMarks={};
 for(const p of APP.landuse.parcels){const v=p.compliance==='violation';
  const lats=p.ring.map(r=>r[0]),lons=p.ring.map(r=>r[1]);
  const cy=(Math.min(...lats)+Math.max(...lats))/2,cx=(Math.min(...lons)+Math.max(...lons))/2;
  const popup=`<div class="pop"><h3>${p.id}</h3><div style="color:#878e8a;font-size:12px">${LU_LABEL[p.type]} · ${p.area_ha} ha · ${p.year}</div>`+
    `<span class="lvl" style="background:${CMP_COLOR[p.compliance]}22;color:${CMP_COLOR[p.compliance]};border:1px solid ${CMP_COLOR[p.compliance]}">${p.compliance.toUpperCase()}</span><pre>${p.note}</pre></div>`;
  // polygon (visible when zoomed in) + always-visible marker at centroid
  L.polygon(p.ring,{color:CMP_COLOR[p.compliance],weight:v?2.5:1.2,fillColor:LU_COLOR[p.type],fillOpacity:0.75}).addTo(m).bindPopup(popup,{maxWidth:300});
  const mk=L.circleMarker([cy,cx],{radius:v?7:5,color:CMP_COLOR[p.compliance],weight:v?3:1.6,fillColor:LU_COLOR[p.type],fillOpacity:0.95}).addTo(m).bindPopup(popup,{maxWidth:300});
  maps._luMarks[p.id]=mk;
 }
 const lg=L.control({position:'bottomleft'});lg.onAdd=function(){const d=L.DomUtil.create('div','legend');
  d.innerHTML='<b>change type</b><br><span style="color:#e0a64e">●</span> new build  <span style="color:#c0664e">●</span> sealed<br>'+
   '<span style="color:#d8694e">●</span> veg. cleared  <span style="color:#3a6fd8">●</span> water<br>'+
   '<b>ring</b> = compliance · red = violation';return d;};lg.addTo(m);
 return m;}
function flyParcel(pid,lat,lon){if(!maps.landuse)return;maps.landuse.flyTo([lat,lon],13,{duration:0.6});
 const mk=maps._luMarks&&maps._luMarks[pid];if(mk)setTimeout(()=>mk.openPopup(),650);}
function buildLandusePanel(){const el=document.getElementById('landuse-panel');const s=APP.landuse.summary,q=APP.landuse.queue;
 let h=`<div style="border:1px solid ${s.violations?'#d8694e':'#45b873'};border-radius:10px;padding:12px;margin-bottom:12px;background:${s.violations?'#d8694e14':'#45b87314'}">
   <div style="font-family:var(--d);font-size:17px">${s.violations} compliance violations</div>
   <div style="font-family:var(--m);font-size:12px;color:#c9cec9;line-height:1.8;margin-top:6px">
    ${s.total} change parcels · ${s.area_ha} ha total<br>
    permitted <b>${s.by_compliance.permitted}</b> · review <b style="color:#cdb24a">${s.by_compliance.review}</b> · violation <b style="color:#d8694e">${s.by_compliance.violation}</b></div></div>`;
 h+='<div style="font-family:var(--m);font-size:11px;color:#878e8a;margin-bottom:6px">Compliance queue (violations &amp; reviews) — exported as CSV + GeoJSON by the tool</div>';
 h+='<table><tr><th>#</th><th>change</th><th>flag</th><th>ha</th></tr>';
 for(const r of q.slice(0,40))h+=`<tr class="lurow" data-id="${r.id}" data-lat="${r.lat}" data-lon="${r.lon}" style="cursor:pointer"><td>${r.priority}</td><td>${r.change}</td><td><span class="pill" style="background:${CMP_COLOR[r.compliance]}22;color:${CMP_COLOR[r.compliance]}">${r.compliance}</span></td><td>${r.area_ha}</td></tr>`;
 h+='</table>';el.innerHTML=h;
 el.querySelectorAll('.lurow').forEach(tr=>tr.onclick=()=>flyParcel(tr.dataset.id,+tr.dataset.lat,+tr.dataset.lon));}

function heatLegend(m){const c=L.control({position:'bottomleft'});c.onAdd=function(){const d=L.DomUtil.create('div','biglegend');
 d.innerHTML='<div class="ttl">land-surface temperature (vs rural)</div>'+
  '<div class="gbar" style="background:linear-gradient(90deg,#3a73d8,#4e9fbd,#d9cc59,#e68d38,#dc522e,#9e1a1f)"></div>'+
  '<div class="tk"><span>−2</span><span>+4</span><span>+12 °C</span></div>'+
  '<div class="tk" style="margin-top:5px;color:#9aa6a0">mild &lt;3 · hot 3–6 · severe heat island 6+ °C</div>';
 L.DomEvent.disableClickPropagation(d);return d;};return c;}
function heatReadout(m){m.on('click',e=>{const g=m._grid;if(!g)return;const v=sampleGrid(g,e.latlng.lat,e.latlng.lng);
 let html;if(v===undefined||v===null){html='<div class="pop"><b>Here</b><br><span style="color:#878e8a">outside coverage</span></div>';}
 else{const col=v>6?'#d8694e':v>3?'#e68d38':v>1?'#cdb24a':'#3a86c8',cat=v>6?'Severe heat island':v>3?'Hot':v>1?'Mild':'Near baseline';
  html=`<div class="pop"><b>Land-surface temperature</b><br><span style="font-size:19px;color:${col};font-family:var(--d)">${v>0?'+':''}${v.toFixed(1)} °C</span> vs rural<br><b style="color:${col}">${cat}</b></div>`;}
 L.popup({maxWidth:260}).setLatLng(e.latlng).setContent(html).openOn(m);});}
function heatMap(id){const m=L.map(id,{preferCanvas:true});addBase(m);
 L.imageOverlay(APP.heat.surface.png,APP.heat.surface.bounds,{interactive:false}).addTo(m);
 m._grid=APP.heat.surface.grid;heatLegend(m).addTo(m);addSearch(m);heatReadout(m);
 m.fitBounds(APP.heat.surface.bounds);return m;}
function buildHeatPanel(){const el=document.getElementById('heat-panel');const cs=APP.heat.cities;
 let h='<div style="font-family:var(--m);font-size:11px;color:#878e8a;margin-bottom:8px">Cities ranked by peak heat-island intensity. Click to zoom.</div><div id="heat-detail"></div>';
 h+=cs.map((c,i)=>`<button class="heatrow" data-i="${i}" style="display:block;width:100%;text-align:left;background:${c.max>6?'#d8694e16':'transparent'};border:1px solid #252b2c;border-radius:8px;padding:8px 10px;margin-bottom:6px;cursor:pointer;color:#ededE6">
   <div style="font-family:var(--d);font-size:14px">${c.name}</div>
   <div style="font-family:var(--m);font-size:11px;color:#878e8a">peak +${c.max} °C · ${c.pct_hot}% of area hot</div></button>`).join('');
 el.innerHTML=h;el.querySelectorAll('.heatrow').forEach(b=>b.onclick=()=>selectHeatCity(+b.dataset.i));}
function selectHeatCity(i){const c=APP.heat.cities[i];if(maps.heat)maps.heat.flyToBounds([[c.bbox[0],c.bbox[1]],[c.bbox[2],c.bbox[3]]],{maxZoom:12});
 const col=c.max>6?'#d8694e':c.max>3?'#e68d38':'#3a86c8',det=document.getElementById('heat-detail');
 if(det)det.innerHTML=`<div style="border:1px solid ${col};border-radius:10px;padding:12px;margin-bottom:12px;background:${col}14">
   <div style="font-family:var(--d);font-size:17px">${c.name}</div>
   <div style="font-family:var(--m);font-size:12px;color:#c9cec9;line-height:1.8;margin-top:6px">
    Peak heat island: <b style="color:${col}">+${c.max} °C</b> vs rural<br>
    Mean urban anomaly: <b>+${c.mean} °C</b><br>
    Area running hot (&gt;3 °C): <b>${c.pct_hot}%</b></div></div>`;}

function show(v){
 document.querySelectorAll('.view').forEach(s=>s.classList.remove('show'));
 document.getElementById('v-'+v).classList.add('show');
 document.querySelectorAll('#nav button').forEach(b=>b.classList.toggle('active',b.dataset.v===v));
 setTimeout(()=>{
  if(v==='risk'){maps.risk=maps.risk||riskNationalMap('map-risk');maps.risk.invalidateSize();}
  if(v==='cities'){if(!maps.cities){maps.cities=cityMap('map-cities');buildCityPanel();selectCity(0);}maps.cities.invalidateSize();}
  if(v==='corridor'){maps.corridor=maps.corridor||corridorMap('map-corridor');maps.corridor.invalidateSize();}
  if(v==='landuse'){if(!maps.landuse){maps.landuse=landuseMap('map-landuse');buildLandusePanel();}maps.landuse.invalidateSize();}
  if(v==='heat'){if(!maps.heat){maps.heat=heatMap('map-heat');buildHeatPanel();selectHeatCity(0);}maps.heat.invalidateSize();}
  if(v==='staufen'){maps.staufen=maps.staufen||surfaceMap('map-staufen',APP.st_surface,APP.staufen,{points:true});maps.staufen.invalidateSize();}
  if(v==='timelapse'){maps.timelapse=maps.timelapse||timelapseMap('map-timelapse',APP.timelapse);maps.timelapse.invalidateSize();}
 },60);
}
document.getElementById('nav').addEventListener('click',e=>{if(e.target.dataset.v)show(e.target.dataset.v);});
document.getElementById('ov-tiles').addEventListener('click',e=>{const t=e.target.closest('[data-go]');if(t)show(t.dataset.go);});
</script></body></html>"""
