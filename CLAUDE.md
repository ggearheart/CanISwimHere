# Can I Swim Here? — Lower American River

Mobile-first swim-safety map for the Lower American River (Sacramento), built on the CyanoSafe phone-demo framework but driven by E. coli bacteria data instead of HABs.

## Project overview
- Static site hosted on GitHub Pages (`docs/` folder), installable PWA
- Main app: `docs/index.html` — all-in-one Leaflet.js map + sidebar
- Data: `docs/stations.json`, built by `build_data.py` from CA Open Data (CKAN)
- All asset/SW URLs are **relative** so it runs under any base path

## Data
- Source: statewide "Surface Water — Fecal Indicator Bacteria Monitoring Results", CA Open Data
  - Dataset: https://data.ca.gov/dataset/surface-water-fecal-indicator-bacteria-results
  - CKAN resource id: `15a63495-8d9f-4a49-b43a-3092ef3106b9` (2020-present); datastore-active (SQL).
- `build_data.py` (`fetch_ecoli_stations`) pulls E. coli within `STATION_BBOX` via
  `datastore_search_sql`, groups by `StationCode` (dedup by date, keep fullest
  6-week window; representative name/coords), keeps ongoing river/lake swim sites
  (`STATION_MIN_LATEST` 2024-01-01 + name contains "american river"/"lake natoma"),
  uses the dataset's official `6WeekGeoMean` (fallback computes). Writes `docs/stations.json`.
- The app loads `stations.json` first; if missing it falls back to a live CKAN
  SQL fetch and aggregates client-side (`aggregate()` in index.html, mirrors the pipeline).
- `stations.json` shape: `{thresholds, source, stations:[{code,name,lat,lon,
  samples:[{date,result,status}],latest,geomean,geomean_n,n,status,geomean_status}]}`

## Swim-safety thresholds (E. coli, MPN/100 mL)
EPA 2012 recreational criteria. Defined in `THRESH` (JS) and top of `build_data.py`:
- Good ≤126 · Caution 127–235 · Warning 236–410 · Unsafe >410 (STV)

## Status palette (WCAG AA, beach-flag convention)
- Good `#15803D` · Caution `#A16207` · Warning `#C2410C` · Unsafe `#B91C1C` · No Data `#374151`
- CA Blue `#005566` · CA Gold `#FDB913`

## Fecal-risk assessment (`riskAssess`/`assessAll` in index.html)
- Do NOT color stations by the last single sample. `riskAssess(r)`: if latest ≤14 days
  → measured `statusFor(latest)`; else estimate from full history — Unsafe if
  all-time geomean >235 or ≥50% > advisory (235) or ≥33% > STV (410); Caution if
  geomean >126 or ≥20%>adv or ≥12%>STV; else Good; <4 samples → Unknown.
- `r._status` = risk key (drives all colors); `r._measured` = raw latest status.
- Flow is a transparent modifier only (`riskFlowNote`, American River stations):
  ≥3500 cfs "higher flow lowers risk", <1500 "lower flow raises risk". NOT a silent recolor.
- `assessAll()` runs on load AND when USGS flow arrives (re-`applyFilters`). `riskLabel`/
  `riskSummary` are lang-aware, computed at render time. Summary: nearest station within
  3 mi else Unknown; tooltip/summary show the history basis. Keep chronic sites (Tiscornia) red.

## Float & Shuttle Planner (`docs/float.html`)
- Separate self-contained page (linked from index.html header). CanISwimHere stays
  focused on swim safety; this answers float/shuttle planning.
- `docs/access_points.json` `{note,river,speed_mph,access:[{name,lat,lon,river_mi,snap_off_m,note}]}`.
  `river_mi` = miles along the OSM river centerline from the confluence (mile 0),
  precomputed by snapping each point (ad-hoc: fetch OSM American River via Overpass,
  order downstream→upstream by nearest-neighbor from the westernmost vertex, cumulative
  arc length, project each access point). NHD+ is the intended upgrade.
- Source of truth = **`access_points_source.csv`** (repo root; the user edits this — I round-trip
  it to/from an xlsx). Columns: id,name,access_lat/lon (water's edge),parking_lat/lon,parking_fee,
  parking_info,walk_to_water,amenities,cautions,note. `build_access.py` reads it (`read_seeds`),
  fetches the LAR centerline from **OpenStreetMap** (Overpass, best visual fit),
  orders confluence→upstream, snaps `access_*` → `river_mi`, computes `walk_ft`
  (parking↔access), writes `docs/river_line.json` + `docs/access_points.json` (with parking fields).
- float.html: `addParkingWalk` draws a 🅿️ marker + dashed walk line; `accDetail` shows fee/walk/
  amenities/cautions per put-in/take-out. Access marker = water's edge.
- Float map also shows a live flow chip (`loadFlow`/`renderFlowChip`, USGS 11446500) and all
  drowning hazards (`drawSafety` shows hazards even with no trip). `⌄ Inspect map`
  (`minimizeTrip`) collapses the panel to a shaded `#plan-chip` (`renderPlanChip`), `expandTrip` reopens.
- Flow: pick access (marker/map-click/Near Me) → Float FROM here (downstream) / Float TO
  here (upstream) → pick a connection → `buildTrip(putInIdx,takeOutIdx,timeMode,timeISO)`
  draws the route (`routeVerts` slices river_line by river mile), shows float/shuttle
  timing, overlays Can I Swim Here? safety data (`drawSafety`, corridor-filtered station
  risk via compact `stationRisk`, blooms, hazards), optional start/take-out time.
- **Share = stateless URL** (`planURL`: `?from=<id>&to=<id>&start|end=<iso>`); `loadFromURL`
  reconstructs on boot. NO backend/DB needed.
- SW serves float.html network-first (v9). River line = OSM (best fit to the mapped river;
  user preferred it over the NHDPlus line for how the route draws).

## HAB risk communication
- A reported bloom is likely over after ~2 weeks. Summary uses `HAB_ACTIVE_DAYS=14`:
  reports within 14 days = *active* (drive verdict); older = site *history*
  ("blooms have occurred here", does NOT force the verdict). `habActive`/`habActiveAdv`
  in `showSwimSummary`. A **recurring** advisory history (`habRecurring`: ≥3 advisory
  blooms, or ≥2 across ≥2 years) → "recurring bloom site", nudges verdict to caution.
- Always lead with **"when in doubt, stay out"** + look for planktonic scum / benthic mats.
  Helpers `habWatchHTML()` + `habAgeNote()`; link `HAB_GUIDE_URL`
  (mywaterquality.ca.gov field guide). Shown in `showHabTip` and the summary.
- Remote-sensing bloom prediction noted as a future direction (About panel).

## Life-vest loaner sites (Kids Don't Float)
- `docs/pfd_stations.json` — curated free life-jacket loaner boards (Sacramento
  County Regional Parks) `{note,program_url,program_name,sites:[{name,lat,lon,
  sizes,note,approx}]}`. Rendered as orange-ringed 🦺 markers (`pfdIcon`/`drawPfd`/
  `showPfdTip`, toggle `#pfdBtn`); tooltip links to `PFD_URL` (Kids Don't Float
  program page). Coords approximate (access points). Independent overlay, not from monitoring.

## Report a hazard (FHAB intake)
- Sidebar form `#hazardForm` → `submitHazardReport()` POSTs JSON to the FHAB
  Modernized public intake API `${FHAB_INTAKE_URL}/api/public/reports` (default
  `https://fhab-web.onrender.com`, overridable via window/localStorage; optional
  `X-API-Key`). Same pattern as the CyanoSafe demo. Payload: water_body_name,
  county, landmark, lat/lon, observation_date, hazard_type, description (type
  prepended), reporter_name/email, honeypot `website`, `source:'caniswimhere'`,
  optional photo_base64. Verify with a stubbed `fetch` — do NOT POST test data to the live API.

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
- index.html renders blooms as cyanobacteria-cluster markers (`habIcon`/`drawHabs`/
  `showHabTip`): `docs/hab-marker.png` silhouette used as a CSS mask, filled by
  advisory color, overall opacity from `habOpacity(obs)` (recent=bold ~0.92,
  old=faint ~0.22). `hab-marker.png` is a downscaled/cropped 256px RGBA of the
  source vecteezy cyanobacteria art. Distinct from E. coli circles / hazard diamonds. Toggle `#habBtn`.
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
