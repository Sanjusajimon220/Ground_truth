"""Interactive dashboard on a **real OpenStreetMap basemap** (Leaflet).

Scatterers and building footprints are drawn at their true latitude/longitude on
real OSM tiles, coloured by velocity and risk. Click a footprint for its
plain-language report and displacement time series. Works for the whole of
Germany or a single focus town (``focus_bbox``).

The OSM *map tiles* are real; in the demo the *motion* is synthetic (clearly
labelled). Needs an internet connection to load the basemap tiles.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np

from .report import asset_report, asset_series, LEVEL_COLOR
from .germany import HOTSPOTS, GERMANY


def _poly_latlon(poly):
    lon = GERMANY.clon + poly[:, 0] / (111_320.0 * np.cos(np.radians(GERMANY.clat)))
    lat = GERMANY.clat + poly[:, 1] / 111_320.0
    return [[float(a), float(b)] for a, b in zip(lat, lon)]


def _spark(series):
    if not series or len(series) < 2:
        return ""
    w, h, pad = 240, 64, 5
    mn, mx = min(series), max(series); rng = (mx - mn) or 1
    dx = (w - 2 * pad) / (len(series) - 1)
    d = "".join(("M" if i == 0 else "L") + f"{pad+i*dx:.1f} {h-pad-((v-mn)/rng)*(h-2*pad):.1f} "
                for i, v in enumerate(series))
    return (f'<svg viewBox="0 0 {w} {h}" style="width:100%;height:64px;background:#131718;'
            f'border:1px solid #252b2c;border-radius:6px"><path d="{d}" fill="none" '
            f'stroke="#e0a64e" stroke-width="2"/></svg>')


def dashboard_data(field, results, assets,
                   title="Germany — EGMS ground-motion screening (synthetic demo)",
                   focus_bbox=None, max_points=2500):
    """Assemble the dashboard payload (used by build_dashboard and the combined app)."""
    id_to_poly = {aid: poly for aid, poly in zip(assets.ids, assets.polys)}
    latlon_meta = assets.meta.get("latlon")
    id_to_latlon = ({aid: (ll.tolist() if hasattr(ll, "tolist") else ll)
                     for aid, ll in zip(assets.ids, latlon_meta)}
                    if latlon_meta is not None else {})

    lat, lon = field.lat, field.lon
    keep = np.ones(len(lat), bool)
    if focus_bbox:
        s, w, n, e = focus_bbox
        keep = (lat >= s) & (lat <= n) & (lon >= w) & (lon <= e)
    idx = np.where(keep)[0]
    rng = np.random.default_rng(0)
    if len(idx) > max_points:
        idx = rng.permutation(idx)[:max_points]
    span = field.dates[-1] - field.dates[0]
    pvel = (field.disp[idx, -1] - field.disp[idx, 0]) / span
    points = [[round(float(lat[i]), 5), round(float(lon[i]), 5), round(float(v), 1)]
              for i, v in zip(idx, pvel)]

    afeats = []
    for r in results:
        if r.id in id_to_latlon:
            coords = [[round(a, 6), round(b, 6)] for a, b in id_to_latlon[r.id]]
        elif r.id in id_to_poly:
            coords = [[round(a, 6), round(b, 6)] for a, b in _poly_latlon(id_to_poly[r.id])]
        else:
            continue
        if focus_bbox:
            la = float(np.mean([c[0] for c in coords])); lo = float(np.mean([c[1] for c in coords]))
            s, w, n, e = focus_bbox
            if not (s <= la <= n and w <= lo <= e):
                continue
        t, ser = asset_series(field, r.centroid)
        step = max(1, len(t) // 36)
        afeats.append({"id": r.id, "kind": r.kind, "level": r.level,
                       "v": None if np.isnan(r.velocity) else round(float(r.velocity), 1),
                       "coords": coords, "report": asset_report(r),
                       "spark": _spark([round(float(v), 1) for v in ser[::step]])})

    hs = [{"name": h["name"], "lat": h["lat"], "lon": h["lon"]} for h in HOTSPOTS]
    if focus_bbox:
        s, w, n, e = focus_bbox
        hs = [h for h in hs if s <= h["lat"] <= n and w <= h["lon"] <= e]

    counts = {k: sum(1 for r in results if r.level == k) for k in LEVEL_COLOR}
    return {"points": points, "assets": afeats, "hotspots": hs, "counts": counts,
            "title": title, "focus": focus_bbox}


def build_dashboard(field, results, assets, out_path,
                    title="Germany — EGMS ground-motion screening (synthetic demo)",
                    focus_bbox=None, max_points=2500):
    data = dashboard_data(field, results, assets, title, focus_bbox, max_points)
    Path(out_path).write_text(TEMPLATE.replace("__DATA__", json.dumps(data)))
    return out_path


TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GroundTruth — ground-motion on a real map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
 :root{--bg:#0c0e0f;--bg2:#131718;--line:#252b2c;--ink:#ededE6;--muted:#878e8a;
   --ochre:#e0a64e;--sage:#7fb4ab;--red:#d8694e;--yellow:#cdb24a;
   --d:'Space Grotesk',sans-serif;--b:'Inter',sans-serif;--m:'JetBrains Mono',monospace;}
 *{box-sizing:border-box}html,body{margin:0;height:100%}
 body{background:var(--bg);color:var(--ink);font-family:var(--b);display:flex;flex-direction:column}
 .top{display:flex;align-items:center;justify-content:space-between;padding:12px 18px;border-bottom:1px solid var(--line);flex-wrap:wrap;gap:10px}
 .brand{font-family:var(--m);font-size:13px}.brand b{color:var(--ochre);font-weight:500}
 .tag{font-family:var(--m);font-size:11px;color:var(--muted)}
 .stats{display:flex;gap:7px;flex-wrap:wrap}
 .chip{font-family:var(--m);font-size:12px;border:1px solid var(--line);border-radius:999px;padding:4px 10px}
 .chip .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:middle}
 #map{flex:1;min-height:520px;background:#0c0e0f}
 .leaflet-popup-content-wrapper,.leaflet-popup-tip{background:var(--bg2);color:var(--ink);border:1px solid var(--line)}
 .leaflet-popup-content{margin:12px 14px;font-family:var(--b);width:300px!important}
 .pop h3{font-family:var(--d);margin:0 0 2px;font-size:16px}
 .pop .lvl{display:inline-block;font-family:var(--m);font-size:11px;padding:2px 8px;border-radius:5px;margin:6px 0}
 .pop pre{white-space:pre-wrap;font-family:var(--m);font-size:11px;color:#c3c8c4;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:9px;line-height:1.5;margin:6px 0 0}
 .legend{font-family:var(--m);font-size:11px;background:rgba(19,23,24,.92);border:1px solid var(--line);border-radius:8px;padding:8px 10px;color:var(--muted);line-height:1.7}
 .legend b{color:var(--ink)}
 .note{font-family:var(--m);font-size:10.5px;color:var(--muted);padding:7px 18px;border-top:1px solid var(--line)}
 a{color:var(--ochre)}
</style></head><body>
<div class="top">
  <div><span class="brand">GroundTruth <b>// ground-motion intelligence</b></span>
       <div class="tag" id="subtitle"></div></div>
  <div class="stats" id="stats"></div>
</div>
<div id="map"></div>
<div class="note">Map tiles © OpenStreetMap contributors. Ground-motion values are a synthetic demo (not real EGMS); region velocities illustrative; risk thresholds are defaults to calibrate with a geotechnical engineer.</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const D = __DATA__;
const LC={OK:'#7fb4ab',Monitor:'#cdb24a',Investigate:'#e0a64e',Act:'#d8694e'};
document.getElementById('subtitle').textContent=D.title;
function velColor(v){const t=Math.max(-12,Math.min(12,v))/12;
 const g=[135,142,138],r=[216,105,78],c=[127,180,171];const k=Math.abs(t);
 const a=t<0?r:c;return `rgb(${Math.round(g[0]+(a[0]-g[0])*k)},${Math.round(g[1]+(a[1]-g[1])*k)},${Math.round(g[2]+(a[2]-g[2])*k)})`;}
const map=L.map('map',{preferCanvas:true});
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);
map.getPane('tilePane').style.filter='grayscale(0.6) brightness(0.55) contrast(1.05)';
const canvas=L.canvas({padding:0.5});
const allLat=[],allLon=[];
for(const p of D.points){L.circleMarker([p[0],p[1]],{renderer:canvas,radius:2.4,
  stroke:false,fillColor:velColor(p[2]),fillOpacity:0.85}).addTo(map);allLat.push(p[0]);allLon.push(p[1]);}
for(const a of D.assets){
  const poly=L.polygon(a.coords,{color:LC[a.level],weight:2,fillColor:LC[a.level],fillOpacity:0.35}).addTo(map);
  const html=`<div class="pop"><h3>${a.id}</h3>`+
    `<div style="color:#878e8a;font-size:12px">${a.kind}${a.v!=null?` · ${a.v>0?'+':''}${a.v} mm/yr`:''}</div>`+
    `<span class="lvl" style="background:${LC[a.level]}22;color:${LC[a.level]};border:1px solid ${LC[a.level]}">${a.level.toUpperCase()}</span>`+
    a.spark+`<pre>${a.report.replace(/</g,'&lt;')}</pre></div>`;
  poly.bindPopup(html,{maxWidth:330});
  a.coords.forEach(c=>{allLat.push(c[0]);allLon.push(c[1]);});
}
for(const h of D.hotspots){L.circleMarker([h.lat,h.lon],{radius:9,color:'#e0a64e',weight:1.5,
  fill:false,dashArray:'3 3'}).addTo(map).bindTooltip(h.name);}
if(D.focus){map.fitBounds([[D.focus[0],D.focus[1]],[D.focus[2],D.focus[3]]]);}
else if(allLat.length){map.fitBounds([[Math.min(...allLat),Math.min(...allLon)],[Math.max(...allLat),Math.max(...allLon)]]);}
else{map.setView([51.16,10.45],6);}
const lg=L.control({position:'bottomright'});
lg.onAdd=function(){const d=L.DomUtil.create('div','legend');
  d.innerHTML='<b>velocity</b><br><span style="color:#d8694e">●</span> subsidence  '+
    '<span style="color:#878e8a">●</span> stable  <span style="color:#7fb4ab">●</span> uplift<br>'+
    '<b>assets</b> ▢ OK ▢ Monitor ▢ Investigate ▢ Act<br><span style="color:#e0a64e">◌</span> named region';
  return d;};
lg.addTo(map);
const st=document.getElementById('stats');
for(const k of ['Act','Investigate','Monitor','OK'])
  st.innerHTML+=`<span class="chip"><span class="dot" style="background:${LC[k]}"></span>${k}: ${D.counts[k]||0}</span>`;
</script></body></html>"""
