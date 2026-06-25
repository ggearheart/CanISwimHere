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

## River flow (live USGS)
- `index.html` fetches USGS IV service client-side (`USGS_URL`, gage `11446500`
  American R at Fair Oaks, params 00060 discharge + 00065 gage, P7D). `parseUSGS`
  → `FLOW={cfs,gageFt,time,trend,series}`. CORS-enabled, so no build step.
- On-map chip `#flow-chip` (`renderFlowChip`) + `flowCat()` categories
  (low/moderate/swift/high) + `flowSpark` 7-day sparkline.
- Flow feeds the swim summary (`flowOnRiver` when nearest station ≤2 mi): swift→caution, high→avoid.
- Downstream is east→west (Folsom/Lake Natoma → Sacramento River).
- NOTE: popular-swim-spot heatmap was removed (awaiting better data); no swim_spots.json.

## Harmful algal blooms (HABs)
- `build_data.py:build_habs()` fetches the statewide FHAB bloom + lab resources,
  filters to `BBOX` (Sacramento area), writes `docs/blooms.json`
  `{bbox, source, blooms:[{id,name,county,rwb,lat,lon,obs,status,adv,tier,detail,
  size,texture,landmark,drinking_water,illness,lab_verified,lab_toxins}]}`.
- `tier` ∈ Danger/Warning/Caution/Watch/Mat/Other (advisory colors in `ADV`).
- index.html renders blooms as organic cell-cluster **splotches** (`habIcon`/`drawHabs`/
  `showHabTip`) — filled by advisory color, overall opacity from `habOpacity(obs)`
  (recent=bold ~0.92, old=faint ~0.22). Distinct from E. coli circles / hazard diamonds. Toggle `#habBtn`.
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
