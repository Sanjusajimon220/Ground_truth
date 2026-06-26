"""National density + velocity map.

The honest way to view a country's worth of EGMS: you never plot raw points at
national zoom (there are tens of millions). You **aggregate** into a grid and
show (a) how much data there is — point density — and (b) the mean ground
velocity per cell. Drill to individual buildings only at city zoom. This view
answers "is there enough data over Germany?" — there is an enormous amount.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np


def density_data(lon, lat, vel, deg=0.15,
                 title="Germany — EGMS data density & mean ground velocity (synthetic demo)"):
    lon = np.asarray(lon); lat = np.asarray(lat); vel = np.asarray(vel)
    gx = np.floor(lon / deg).astype(int)
    gy = np.floor(lat / deg).astype(int)
    cells, inv = np.unique(np.stack([gx, gy], 1), axis=0, return_inverse=True)
    count = np.bincount(inv).astype(float)
    meanvel = np.bincount(inv, weights=vel) / count
    cmax = float(np.log10(count.max()))
    feats = [[round(cx * deg, 4), round(cy * deg, 4), round(float(v), 1), int(c)]
             for (cx, cy), c, v in zip(cells, count, meanvel)]
    return {"deg": deg, "cells": feats, "title": title,
            "total": int(count.sum()), "ncells": len(cells), "cmax": cmax,
            "subsiding_pct": round(100 * float((meanvel < -2).sum()) / len(cells), 1)}


def build_density_map(lon, lat, vel, out_path, deg=0.15,
                      title="Germany — EGMS data density & mean ground velocity (synthetic demo)"):
    data = density_data(lon, lat, vel, deg, title)
    Path(out_path).write_text(TEMPLATE.replace("__DATA__", json.dumps(data)))
    return out_path


TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GroundTruth — Germany data density</title>
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
 .stats{display:flex;gap:7px;flex-wrap:wrap}
 .chip{font-family:var(--m);font-size:12px;border:1px solid var(--line);border-radius:999px;padding:4px 10px}
 .chip b{color:var(--ochre)}
 #map{flex:1;min-height:520px}
 .leaflet-popup-content-wrapper,.leaflet-popup-tip{background:var(--bg2);color:var(--ink);border:1px solid var(--line)}
 .leaflet-popup-content{font-family:var(--m);font-size:12px}
 .legend{font-family:var(--m);font-size:11px;background:rgba(19,23,24,.92);border:1px solid var(--line);border-radius:8px;padding:8px 10px;color:var(--muted);line-height:1.7}
 .legend b{color:var(--ink)}
 .note{font-family:var(--m);font-size:10.5px;color:var(--muted);padding:7px 18px;border-top:1px solid var(--line)}
</style></head><body>
<div class="top">
  <div><span class="brand">GroundTruth <b>// data density</b></span>
       <div class="tag" id="sub"></div></div>
  <div class="stats" id="stats"></div>
</div>
<div id="map"></div>
<div class="note">Map tiles © OpenStreetMap. Synthetic demo — but this is how a country's EGMS is actually viewed: aggregate to a grid at national zoom (tens of millions of points), drill to individual buildings at city zoom. Cell colour = mean velocity; opacity = how many measurement points fall in the cell.</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const D=__DATA__;
document.getElementById('sub').textContent=D.title;
const st=document.getElementById('stats');
st.innerHTML=`<span class="chip">points: <b>${D.total.toLocaleString()}</b></span>`+
 `<span class="chip">grid cells: <b>${D.ncells}</b></span>`+
 `<span class="chip">cells subsiding: <b>${D.subsiding_pct}%</b></span>`;
function velColor(v){const t=Math.max(-12,Math.min(12,v))/12;
 const g=[135,142,138],r=[216,105,78],c=[127,180,171];const k=Math.abs(t);
 const a=t<0?r:c;return `rgb(${Math.round(g[0]+(a[0]-g[0])*k)},${Math.round(g[1]+(a[1]-g[1])*k)},${Math.round(g[2]+(a[2]-g[2])*k)})`;}
const map=L.map('map');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);
map.getPane('tilePane').style.filter='grayscale(0.6) brightness(0.5) contrast(1.05)';
const d=D.deg;const lats=[],lons=[];
for(const c of D.cells){const[lo,la,v,n]=c;lats.push(la);lons.push(lo);
 const op=0.25+0.6*(Math.log10(n)/D.cmax);
 const rect=L.rectangle([[la,lo],[la+d,lo+d]],{stroke:false,fillColor:velColor(v),fillOpacity:op}).addTo(map);
 rect.bindPopup(`<b>cell</b><br>mean velocity: ${v} mm/yr<br>points: ${n.toLocaleString()}`);
}
map.fitBounds([[Math.min(...lats),Math.min(...lons)],[Math.max(...lats)+d,Math.max(...lons)+d]]);
const lg=L.control({position:'bottomright'});
lg.onAdd=function(){const x=L.DomUtil.create('div','legend');
 x.innerHTML='<b>mean velocity</b><br><span style="color:#d8694e">■</span> subsidence  '+
  '<span style="color:#878e8a">■</span> stable  <span style="color:#7fb4ab">■</span> uplift<br>'+
  '<b>opacity</b> = measurement-point density';return x;};
lg.addTo(map);
</script></body></html>"""
