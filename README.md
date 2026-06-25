# Can I Swim Here? — Lower American River

A mobile-first web app that answers a simple question for the Lower American River near Sacramento: **is it safe to get in the water right now?**

It maps **E. coli** bacteria monitoring results to a plain-language swim-safety status for each monitoring station, using EPA recreational water-quality criteria.

**Live app:** https://ggearheart.github.io/CanISwimHere/

Built on the [CyanoSafe](https://github.com/ggearheart/CyanoSafe_phone_demo) phone-demo framework.

## Data source

E. coli monitoring results from the **Central Valley Regional Water Quality Control Board**, published on the California Open Data portal:

- Dataset: https://data.ca.gov/dataset/central-valley-water-board-e-coli-monitoring-results
- River map: https://arcg.is/0ea0zq (Lower American River Recreational Water Quality)

E. coli is a bacteria used to indicate **fecal pollution** and the possible presence of disease-causing organisms. All data are **draft** unless otherwise noted.

## Swim-safety thresholds

Each station's status reflects its **most recent sample**, classified using EPA 2012 recreational water-quality criteria for E. coli (MPN/100 mL):

| Status | E. coli (MPN/100 mL) | Basis |
|--------|----------------------|-------|
| 🟢 **Good** | ≤ 126 | At/below the geometric-mean health criterion |
| 🟡 **Caution** | 127 – 235 | Above the safe criterion |
| 🟠 **Warning** | 236 – 410 | Above the single-sample advisory threshold |
| 🔴 **Unsafe** | > 410 | Exceeds the Statistical Threshold Value (STV) — posting threshold |

A recent **geometric mean** (last 6 samples) is shown alongside the single-sample verdict, since EPA criteria are based on a rolling geomean.

> ⚠️ Bacteria levels change quickly with rain, runoff, and flow. A single result is a snapshot, not a guarantee. This is a demonstration app — always check official sources before recreating in any water body.

## Features

- Full-screen interactive map of monitoring stations, color-coded by swim status
- **Swim summary** anywhere: tap **📍 Near Me** for your location, or **tap any spot on the map** to check it. Gives one "Safe to swim / Use caution / Avoid water contact" verdict with a tri-slice status icon (bacteria · algal blooms · physical hazards) and a one-line readout of each category — naming the specific site and the date of the last water-quality data. Only *recent* blooms (within 120 days, 1.5 mi) count as an active advisory; older reports are shown as historical context
- Per-station detail: latest result, recent geomean, full sample-history sparkline with threshold lines, and a sortable recent-sample table
- **Live river flow** from USGS gage 11446500 (American River at Fair Oaks): current discharge (cfs), gage height, trend, and a 7-day sparkline
- **Harmful algal bloom (HAB) layer** (cyanobacteria-cluster markers) for the Sacramento / American & Sacramento River area — colored by advisory level and faded by how recently the bloom was observed
- **Drowning-hazard markers** (red diamonds) for locally-known dangerous spots
- Printable bilingual (English / Spanish) advisory signs per status level
- Download stations or a single station's history as CSV
- Installable PWA with offline caching of the last-loaded data
- Loads a pre-built `stations.json` for speed, with a live CA Open Data (CKAN) fallback

## River flow

Live streamflow is read client-side from the **USGS Instantaneous Values** service for gage **11446500 — American River at Fair Oaks** (`parameterCd=00060` discharge, `00065` gage height, `period=P7D`). The on-map chip shows current discharge in cfs, a coarse safety category, gage height, short-term trend, a 7-day sparkline, and the downstream direction (water flows east→west, from Folsom/Lake Natoma to the Sacramento River). Flow also feeds the swim summary — *swift* nudges the verdict to caution, *high* to avoid.

Flow categories (cfs, general Lower-American-River guidance, not an official standard): Low/calm < 1,500 · Moderate < 3,500 · Swift < 6,000 · High ≥ 6,000. Releases from Nimbus Dam can change flow quickly.

> Note: popular-swim-spot data was removed pending a higher-quality source (the previous list was approximate and not all points sat on the water).

## Harmful algal blooms

A second hazard layer maps **harmful algal bloom (HAB)** reports from the CA State Water Board **FHAB program** ([dataset](https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms)), filtered to a Sacramento-area bounding box covering the Lower American River, the Sacramento River, Folsom Lake / Lake Natoma, and local park lakes. Blooms show as **cyanobacteria-cluster markers** (`docs/hab-marker.png`, a filamentous-cyanobacteria starburst silhouette used as a CSS mask) filled by advisory level (Danger / Warning / Caution / Watch / Algal Mat / Reported) and **faded by age** (bold = recently observed, faint = older report), with lab-confirmed cyanotoxins and illness reports flagged.

`build_data.py` builds `docs/blooms.json` (fetched statewide, filtered to the bbox) alongside `stations.json`. Edit `BBOX` in `build_data.py` to change the area.

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
