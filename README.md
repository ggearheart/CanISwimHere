# Can I Swim Here? — Lower American River

A mobile-first web app that answers a simple question for the Lower American River near Sacramento: **is it safe to get in the water right now?**

It maps **E. coli** bacteria monitoring results to a plain-language swim-safety status for each monitoring station, using EPA recreational water-quality criteria.

**Live app:** https://ggearheart.github.io/CanISwimHere/

Built on the [CyanoSafe](https://github.com/ggearheart/CyanoSafe_phone_demo) phone-demo framework.

## Data source

E. coli monitoring results from the CA State Water Resources Control Board's statewide **Surface Water — Fecal Indicator Bacteria Monitoring Results** dataset (the maintained, regularly-refreshed source), published on the California Open Data portal:

- Dataset: https://data.ca.gov/dataset/surface-water-fecal-indicator-bacteria-results
  (resource `15a63495-8d9f-4a49-b43a-3092ef3106b9`, "2020 to present")
- River map: https://arcg.is/0ea0zq (Lower American River Recreational Water Quality)

`build_data.py` pulls E. coli records within an American River bounding box, consolidates them by monitoring station (collapsing bank/replicate variants, dropping one-off study points, stormwater sumps, and discontinued sites), and keeps ongoing river/lake swim sites (last sampled since 2024). It uses the dataset's official **6-week geometric mean** where available. This yields the core Lower American River stations plus Howe Ave and the Lake Natoma swim beaches (Nimbus Flat, Black Miners Bar).

E. coli is a bacteria used to indicate **fecal pollution** and the possible presence of disease-causing organisms.

## Swim-risk assessment (not a single reading)

A single sample older than a week or two — especially at a different flow — no longer predicts today's risk. So a station is **not** colored by its last reading. Instead:

- **Recent data (≤ 14 days):** the *measured* status is shown, from EPA 2012 E. coli criteria (≤126 good · 127–235 caution · 236–410 warning · >410 STV unsafe, MPN/100 mL).
- **Older data:** a **probabilistic estimate from the station's whole history** — its all-time geometric mean and how often it exceeded thresholds:
  - 🟢 **Probably safe** — history typically at/below the criterion (all-time geomean ≤126, <20% of samples over the advisory)
  - 🟡 **Uncertain** — sometimes elevated (geomean >126, or ≥20% over advisory / ≥12% over STV)
  - 🔴 **Probably unsafe** — *most* samples and the geomean exceed thresholds (geomean >235, or ≥50% over advisory / ≥33% over STV)
  - ⚪ **Unknown** — too few samples, or no station within 3 miles of the spot
- **Flow modifier:** today's American River flow (USGS Fair Oaks) is surfaced as a transparent note — higher flow (faster, colder, more dilution) generally *lowers* bacteria risk; lower flow *raises* it.

This keeps a lone year-old high reading from painting a chronically-clean site red, while genuinely chronic sites (e.g. the Tiscornia/Discovery confluence) still read unsafe. When you tap a spot or use **Near Me**, the tooltip/summary explains the basis (sample count, span, geomean, % over threshold, latest date + age).

> ⚠️ Estimates, not guarantees — bacteria change quickly with rain and runoff. This is a demonstration app; always check official sources before recreating.

## Features

- Full-screen interactive map of monitoring stations, color-coded by swim status
- **Swim summary** anywhere: tap **📍 Near Me** for your location, or **tap any spot on the map** to check it. Gives one "Safe to swim / Use caution / Avoid water contact" verdict with a tri-slice status icon (bacteria · algal blooms · physical hazards) and a one-line readout of each category — naming the specific site and the date of the last water-quality data. Only *recent* blooms (within 120 days, 1.5 mi) count as an active advisory; older reports are shown as historical context
- Per-station detail: latest result, recent geomean, full sample-history sparkline with threshold lines, and a sortable recent-sample table
- **Live river flow** from USGS gage 11446500 (American River at Fair Oaks): current discharge (cfs), gage height, trend, and a 7-day sparkline
- **Harmful algal bloom (HAB) layer** (cyanobacteria-cluster markers) for the Sacramento / American & Sacramento River area — colored by advisory level and faded by how recently the bloom was observed
- **Drowning-hazard markers** (red diamonds) for locally-known dangerous spots
- **Free life-vest loaner sites** (🦺 markers) from the Sacramento County "Kids Don't Float" program, with borrow info and a link to the program page
- **Report a hazard** — an in-app form (algal bloom, scum, pollution, etc.) that POSTs to the CA State Water Board FHAB Modernized public intake API
- **[🛶 Float & Shuttle Planner](https://ggearheart.github.io/CanISwimHere/float.html)** — a companion page (`docs/float.html`) for planning a river trip (see below)
- Printable bilingual (English / Spanish) advisory signs per status level
- Download stations or a single station's history as CSV
- Installable PWA with offline caching of the last-loaded data
- Loads a pre-built `stations.json` for speed, with a live CA Open Data (CKAN) fallback

## River flow

Live streamflow is read client-side from the **USGS Instantaneous Values** service for gage **11446500 — American River at Fair Oaks** (`parameterCd=00060` discharge, `00065` gage height, `period=P7D`). The on-map chip shows current discharge in cfs, a coarse safety category, gage height, short-term trend, a 7-day sparkline, and the downstream direction (water flows east→west, from Folsom/Lake Natoma to the Sacramento River). Flow also feeds the swim summary — *swift* nudges the verdict to caution, *high* to avoid.

Flow categories (cfs, general Lower-American-River guidance, not an official standard): Low/calm < 1,500 · Moderate < 3,500 · Swift < 6,000 · High ≥ 6,000. Releases from Nimbus Dam can change flow quickly.

> Note: popular-swim-spot data was removed pending a higher-quality source (the previous list was approximate and not all points sat on the water).

## Float & Shuttle Planner (`docs/float.html`)

A separate companion page — the main app stays focused on "can I swim here?", this one answers "how do I plan a float/shuttle trip?"

**Flow:** pick a river-access point (tap a marker, tap the map, or **📍 Near Me**) → choose **Float _from_ here** (downstream take-outs) or **Float _to_ here** (upstream put-ins) → pick a connecting spot. That builds a trip, which:

- **Draws the route** along the river on the map (put-in → take-out) with green/red endpoint markers.
- Shows **river miles**, **float time** (÷ **2–4 mph**, typical LAR speed), and live **shuttle drive time** — routed **parking-lot to parking-lot** (take-out → put-in), and clickable to open **Google Maps driving directions** for the shuttle.
- **Overlays Can I Swim Here? data** — the live **river-flow chip**, **◆ drowning hazards** (always shown), and along the trip corridor station bacteria risk (history-based dots) + 🦠 bloom reports, plus a put-in/take-out water-quality summary.
- Lets you **set a start or take-out time** (optional); it computes the other end from the float duration.
- **⌄ Inspect map** collapses the panel to a shaded plan box (put-in → take-out · miles · time) so you can pan/zoom and read hazards + flow, then tap to reopen.
- **Share** — a "Share this float plan" button produces a **self-contained URL** (`?from=<id>&to=<id>&start=<iso>`). Opening it reconstructs the whole plan. **No database needed** — the plan lives in the URL (stateless, works on static hosting).

Each access point also carries **parking** detail — a separate parking coordinate (🅿️ marker + a dashed **walk line** to the water's edge on the map), **fee**, lot info, **walk-to-water** description, amenities, and cautions — surfaced in the put-in/take-out plan details. The put-in/take-out names and the 🅿️ parking each **link to a Google Maps point** (and the map's P markers pop up a "Directions in Google Maps" link) for navigating the shuttle.

**Data / rebuild:** the source of truth is **`access_points_source.csv`** (columns: `id, name, access_lat, access_lon, parking_lat, parking_lon, parking_fee, parking_info, walk_to_water, amenities, cautions, note`). Edit it, then run `python3 build_access.py`, which fetches the LAR centerline from **OpenStreetMap** (best visual fit to the mapped river), snaps each `access_*` point to it for the `river_mi`, and writes `docs/river_line.json` + `docs/access_points.json`.

## Harmful algal blooms

A second hazard layer maps **harmful algal bloom (HAB)** reports from the CA State Water Board **FHAB program** ([dataset](https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms)), filtered to a Sacramento-area bounding box covering the Lower American River, the Sacramento River, Folsom Lake / Lake Natoma, and local park lakes. Blooms show as **cyanobacteria-cluster markers** (`docs/hab-marker.png`, a filamentous-cyanobacteria starburst silhouette used as a CSS mask) filled by advisory level (Danger / Warning / Caution / Watch / Algal Mat / Reported) and **faded by age** (bold = recently observed, faint = older report), with lab-confirmed cyanotoxins and illness reports flagged.

`build_data.py` builds `docs/blooms.json` (fetched statewide, filtered to the bbox) alongside `stations.json`. Edit `BBOX` in `build_data.py` to change the area.

**Bloom risk, like bacteria, is time-sensitive.** A reported bloom is usually over after ~2 weeks, so the "Near Me" / tap summary treats only reports within **14 days** (`HAB_ACTIVE_DAYS`) as *active*; older ones become **site history** ("blooms have occurred here"). A spot with a **recurring** advisory history (≥3 advisory blooms, or ≥2 across ≥2 seasons) is flagged a "recurring bloom site" and nudges the verdict to *use caution* — "a new bloom is more likely here." Either way the app leads with **"when in doubt, stay out"** and tells people to look before they get in — for floating scum/streaks (planktonic) or brown-black bottom mats (benthic), noting not every green algae or plant is harmful — linking the state's [bloom ID field guide](https://mywaterquality.ca.gov/habs/resources/field-guide.html). (Fine-scale remote-sensing bloom prediction is a hoped-for future addition.)

> HABs and E. coli are **different hazards** — a site can be clear of one and not the other. Most blooms are reported by the public and only some are lab-tested, so cyanotoxins may be present even when not confirmed.

## Drowning hazards

Bacteria status and physical danger are **independent** — water can be bacteriologically "Good" and still be deadly to swim because of cold water, swift current, and sudden depth changes.

`docs/hazards.json` is a **hand-curated** list (not from the monitoring dataset) of known dangerous swimming spots, shown as red ⚠️ diamonds with safety guidance. It currently includes **Clay Banks** and the **Tiscornia Beach / Discovery Park confluence** with the Sacramento River. Coordinates are **approximate** — edit `docs/hazards.json` to refine locations or add hazards; no rebuild step is needed.

## Auto-refresh

`.github/workflows/update-data.yml` runs `build_data.py` daily (and on manual dispatch), regenerating `docs/stations.json` from CA Open Data and committing it if anything changed. `build_data.py` uses only the Python standard library, so no dependencies are installed in CI.

## Project layout

```
build_data.py        # fetches CKAN data, builds docs/stations.json
docs/
  index.html         # the app (all-in-one Leaflet + sidebar)
  stations.json      # pre-built station data (regenerate with build_data.py)
  manifest.json      # PWA manifest
  sw.js              # service worker (offline + data caching)
  icon-192.png, icon-512.png, waterboards-logo.png
```

## Development

Regenerate the data:

```
python3 build_data.py
```

Serve locally:

```
python3 -m http.server 8001 --directory docs
```

Then open http://localhost:8001

Deploy: push to `main` — GitHub Pages serves from `docs/`. URLs are relative, so it works under any base path.

## License

State of California — open data. See CA Water Boards for terms of use.
