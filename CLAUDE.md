# Can I Swim Here? — Lower American River

Mobile-first swim-safety map for the Lower American River (Sacramento), built on the CyanoSafe phone-demo framework but driven by E. coli bacteria data instead of HABs.

## Project overview
- Static site hosted on GitHub Pages (`docs/` folder), installable PWA
- Main app: `docs/index.html` — all-in-one Leaflet.js map + sidebar
- Data: `docs/stations.json`, built by `build_data.py` from CA Open Data (CKAN)
- All asset/SW URLs are **relative** so it runs under any base path

## Data
- Source: Central Valley Water Board E. coli monitoring, CA Open Data
  - Dataset: https://data.ca.gov/dataset/central-valley-water-board-e-coli-monitoring-results
  - CKAN resource id: `fc450fb6-e997-4bcf-b824-1b3ed0f06045`
- `build_data.py` groups raw samples by `StationCode`, computes latest result,
  recent 6-sample geometric mean, and a swim status; writes `docs/stations.json`.
- The app loads `stations.json` first; if missing it falls back to a live CKAN
  fetch and aggregates client-side (`aggregate()` in index.html).
- `stations.json` shape: `{thresholds, source, stations:[{code,name,lat,lon,
  samples:[{date,result,status}],latest,geomean,geomean_n,n,status,geomean_status}]}`

## Swim-safety thresholds (E. coli, MPN/100 mL)
EPA 2012 recreational criteria. Defined in `THRESH` (JS) and top of `build_data.py`:
- Good ≤126 · Caution 127–235 · Warning 236–410 · Unsafe >410 (STV)

## Status palette (WCAG AA, beach-flag convention)
- Good `#15803D` · Caution `#A16207` · Warning `#C2410C` · Unsafe `#B91C1C` · No Data `#374151`
- CA Blue `#005566` · CA Gold `#FDB913`

## Popular swim spots (heatmap)
- `docs/swim_spots.json` — hand-curated public swim/river-access beaches
  `{note,sources,spots:[{name,lat,lon,intensity,note}]}`. NOT Strava (proprietary),
  NOT from monitoring; approximate + editable. Popularity ≠ safety.
- index.html renders via `L.heatLayer` (leaflet.heat CDN) + small `swimDots`
  circle markers (`buildSwim`/`showSwimTip`, toggle `#swimBtn`). Blue/cyan
  gradient on purpose — never the green/red safety palette.
- Summary card flags `atSwimSpot` (within 0.4 mi) as context only.

## Harmful algal blooms (HABs)
- `build_data.py:build_habs()` fetches the statewide FHAB bloom + lab resources,
  filters to `BBOX` (Sacramento area), writes `docs/blooms.json`
  `{bbox, source, blooms:[{id,name,county,rwb,lat,lon,obs,status,adv,tier,detail,
  size,texture,landmark,drinking_water,illness,lab_verified,lab_toxins}]}`.
- `tier` ∈ Danger/Warning/Caution/Watch/Mat/Other (advisory colors in `ADV`).
- index.html renders blooms as SVG teardrop **pins** (`habIcon`/`drawHabs`/`showHabTip`)
  — distinct from E. coli circles and hazard diamonds. Toggle `#habBtn`.
- FHAB resources: blooms `c6a36b91-ad38-4611-8750-87ee99e497dd`,
  lab `9d4e1df4-0cd6-4165-9e63-effcafd9dccc`.

## Drowning hazards
- `docs/hazards.json` is a hand-curated list of physical hazards (NOT from the
  monitoring data), rendered as red ⚠️ diamond markers via `drawHazards()` /
  `showHazardTip()` in index.html. Coordinates are approximate and editable.
- Independent of E. coli status — surface both; never imply "Good" bacteria = safe to swim.

## Auto-refresh
- `.github/workflows/update-data.yml` runs `build_data.py` daily + on dispatch,
  commits `docs/stations.json` if changed. No pip deps (stdlib only).

## Development
- Rebuild data: `python3 build_data.py`
- Serve locally: `python3 -m http.server 8001 --directory docs`
- Deploy: push to `main` — GitHub Pages serves `docs/`
