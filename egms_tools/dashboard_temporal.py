"""Interactive time-slider dashboard — watch the ground move through time.

Each scatterer carries a full displacement time series. This view colours every
point by its *cumulative* displacement at the selected date and gives a slider +
play button, so you can watch subsidence bowls deepen and the Stuttgart onset
appear mid-record. This is the temporal-pattern view: the same data the static
map shows, but as change over time. Real OSM basemap (needs internet for tiles).
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np


def timeslider_data(field, focus_bbox=None, n_epochs=13, max_points=1800):
    lat, lon = field.lat, field.lon
    keep = np.ones(len(lat), bool)
    if focus_bbox:
        s, w, n, e = focus_bbox
        keep = (lat >= s) & (lat <= n) & (lon >= w) & (lon <= e)
    idx = np.where(keep)[0]
    rng = np.random.default_rng(0)
    if len(idx) > max_points:
        idx = rng.permutation(idx)[:max_points]
    T = len(field.dates)
    ei = np.linspace(0, T - 1, n_epochs).round().astype(int)
    dates = [round(float(field.dates[i]), 2) for i in ei]
    disp = field.disp[np.ix_(idx, ei)]
    pts = [[round(float(lat[i]), 5), round(float(lon[i]), 5)] for i in idx]
    return {"pts": pts, "disp": np.round(disp).astype(int).tolist(),
            "dates": dates, "focus": focus_bbox, "scale": 60}


def build_timeslider(field, out_path,
                     title="Germany — ground motion over time (synthetic demo)",
                     focus_bbox=None, n_epochs=13, max_points=1800):
    data = timeslider_data(field, focus_bbox, n_epochs, max_points)
    data["title"] = title
    Path(out_path).write_text(TEMPLATE.replace("__DATA__", json.dumps(data)))
    return out_path


TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GroundTruth — ground motion over time</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
 :root{--bg:#0c0e0f;--bg2:#131718;--line:#252b2c;--ink:#ededE6;--muted:#878e8a;--ochre:#e0a64e;--red:#d8694e;--sage:#7fb4ab;
   --d:'Space Grotesk',sans-serif;--b:'Inter',sans-serif;--m:'JetBrains Mono',monospace;}
 *{box-sizing:border-box}html,body{margin:0;height:100%}
 body{background:var(--bg);color:var(--ink);font-family:var(--b);display:flex;flex-direction:column}
 .top{display:flex;align-items:center;justify-content:space-between;padding:12px 18px;border-bottom:1px solid var(--line);flex-wrap:wrap;gap:10px}
 .brand{font-family:var(--m);font-size:13px}.brand b{color:var(--ochre);font-weight:500}
 .tag{font-family:var(--m);font-size:11px;color:var(--muted)}
 #map{flex:1;min-height:480px}
 .ctrl{display:flex;align-items:center;gap:14px;padding:12px 18px;border-top:1px solid var(--line);background:var(--bg2)}
 .play{font-family:var(--m);font-size:13px;background:var(--ochre);color:#170f02;border:none;border-radius:8px;padding:8px 16px;cursor:pointer;font-weight:600}
 input[type=range]{flex:1;accent-color:var(--ochre)}
 .date{font-family:var(--d);font-size:22px;min-width:96px;text-align:right;color:var(--ochre)}
 .legend{font-family:var(--m);font-size:11px;background:rgba(19,23,24,.92);border:1px solid var(--line);border-radius:8px;padding:8px 10px;color:var(--muted);line-height:1.7}
 .note{font-family:var(--m);font-size:10.5px;color:var(--muted);padding:7px 18px;border-top:1px solid var(--line)}
</style></head><body>
<div class="top">
  <div><span class="brand">GroundTruth <b>// ground motion over time</b></span>
       <div class="tag" id="sub"></div></div>
  <div class="tag">cumulative displacement (mm) · red = down, blue = up</div>
</div>
<div id="map"></div>
<div class="ctrl">
  <button class="play" id="play">▶ Play</button>
  <input type="range" id="slider" min="0" value="0"/>
  <div class="date" id="date"></div>
</div>
<div class="note">Map tiles © OpenStreetMap contributors. Synthetic demo (not real EGMS). Watch the Stuttgart onset appear ~2021 and the lignite bowls deepen.</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const D=__DATA__;document.getElementById('sub').textContent=D.title;
function col(v){const t=Math.max(-D.scale,Math.min(D.scale,v))/D.scale;
 const g=[135,142,138],r=[216,105,78],c=[127,180,171];const k=Math.abs(t);
 const a=t<0?r:c;return `rgb(${Math.round(g[0]+(a[0]-g[0])*k)},${Math.round(g[1]+(a[1]-g[1])*k)},${Math.round(g[2]+(a[2]-g[2])*k)})`;}
const map=L.map('map',{preferCanvas:true});
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);
map.getPane('tilePane').style.filter='grayscale(0.6) brightness(0.55) contrast(1.05)';
const canvas=L.canvas({padding:0.5});
const markers=D.pts.map(p=>L.circleMarker([p[0],p[1]],{renderer:canvas,radius:2.6,stroke:false,fillOpacity:0.9,fillColor:'#878e8a'}).addTo(map));
const las=D.pts.map(p=>p[0]),los=D.pts.map(p=>p[1]);
if(D.focus){map.fitBounds([[D.focus[0],D.focus[1]],[D.focus[2],D.focus[3]]]);}
else{map.fitBounds([[Math.min(...las),Math.min(...los)],[Math.max(...las),Math.max(...los)]]);}
const slider=document.getElementById('slider'),dateEl=document.getElementById('date');
slider.max=D.dates.length-1;
function render(e){for(let i=0;i<markers.length;i++){markers[i].setStyle({fillColor:col(D.disp[i][e])});}
  dateEl.textContent=Math.floor(D.dates[e]);}
slider.addEventListener('input',()=>render(+slider.value));
render(0);
let playing=false,timer=null;const btn=document.getElementById('play');
btn.addEventListener('click',()=>{playing=!playing;btn.textContent=playing?'❚❚ Pause':'▶ Play';
 if(playing){timer=setInterval(()=>{let v=(+slider.value+1)%D.dates.length;slider.value=v;render(v);
   if(v===D.dates.length-1){/*loop*/}},650);}else{clearInterval(timer);}});
const lg=L.control({position:'bottomright'});
lg.onAdd=function(){const d=L.DomUtil.create('div','legend');
 d.innerHTML='<b>cumulative mm</b><br><span style="color:#d8694e">●</span> subsidence  '+
  '<span style="color:#878e8a">●</span> ~0  <span style="color:#7fb4ab">●</span> uplift';return d;};
lg.addTo(map);
</script></body></html>"""
