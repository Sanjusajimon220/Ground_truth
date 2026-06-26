# What is EGMS, and why can't you use it?

*A short, plain explainer. If you own buildings, rail, pipelines or land in Europe, this dataset already knows whether your ground is moving — you just can't read it yet.*

## The dataset almost nobody is using

Since 2023 the European Union has published, for free, a map of how the ground is moving across most of Europe — down to **millimetres per year**. It's called the **European Ground Motion Service (EGMS)**, part of Copernicus. It's built from years of **Sentinel-1 radar** passing overhead and a technique called **InSAR**, which compares the radar phase between passes to measure how far the ground rose or sank.

It covers cities, rail, coastlines and farmland. It updates regularly. It is one of the most valuable open datasets on Earth. And it sits almost unused outside a small circle of specialists.

## Why it's locked behind a wall

EGMS doesn't give you a tidy "this building is sinking" answer. It gives you **persistent scatterers**: millions of individual points — corners of roofs, rails, rocks — each with a long table of displacement numbers, one per satellite pass over several years. To turn that into something useful you have to:

- understand what a persistent scatterer is and which ones to trust (coherence),
- know that the measurement is along the satellite's *line of sight*, not simply "up/down,"
- handle the reference frame (motion is always *relative* to something),
- separate real ground motion from atmospheric noise and seasonal wobble,
- and then connect millions of points to *your* assets and decide what matters.

That's persistent-scatterer InSAR expertise. Almost no asset owner, surveyor, municipality or insurer has it. So a free, Europe-wide, millimetre-precision early-warning system for subsidence sits there — unreadable — while subsidence keeps cracking buildings, misaligning rail and rupturing pipes, getting worse as droughts and groundwater extraction destabilise the ground.

## What `egms-tools` does about it

`egms-tools` is the bridge from "millions of points" to "which of my assets are moving, how fast, and should I worry":

- it **attaches** the right scatterers to each of your assets,
- fits a **robust trend** (velocity) and asks the question that matters most — **is it accelerating?** — with the uncertainty stated honestly,
- measures **differential** motion across a footprint (uneven settlement, which is what actually causes damage),
- and hands you a **plain-language report** and a **map** instead of a spreadsheet of phase values.

It won't replace a site inspection, and it won't pretend to. It tells you *where to look first* — using data you already paid for as a European taxpayer.

## Why this matters

Subsidence damage is expensive, slow, and almost always visible in the ground motion *years before* it's visible in a wall. The data to catch it early is free and public. The only thing missing is the last mile — making it readable. That's the whole point of this tool.

---

*Open source. Part of **GroundTruth** — ground-motion intelligence for infrastructure. Built by a civil engineer who got tired of watching free data go unused.*
