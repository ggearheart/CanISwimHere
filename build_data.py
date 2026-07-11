#!/usr/bin/env python3
"""Build stations.json for the "Can I swim here?" app.

Fetches Lower American River E. coli monitoring results from the California
Open Data portal (Central Valley Water Board), groups samples by monitoring
station, and computes a current swim-safety status for each station based on
EPA recreational water-quality criteria for E. coli.

Output: docs/stations.json

Source dataset:
  https://data.ca.gov/dataset/central-valley-water-board-e-coli-monitoring-results
"""
import json
import math
import os
import re
import urllib.request


def clean(v):
    s = str(v if v is not None else "").strip()
    return None if s in ("", "None", "null", "nan") else s


def num(v):
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None

# CKAN datastore resource: statewide "Surface Water - Fecal Indicator Bacteria
# Monitoring Results" (2020 to present). We pull E. coli within the American River
# bounding box and consolidate to ongoing swim-monitoring stations.
RESOURCE_ID = "15a63495-8d9f-4a49-b43a-3092ef3106b9"
PACKAGE_ID = "surface-water-fecal-indicator-bacteria-results"
BASE = "https://data.ca.gov/api/3/action"

# American River corridor + Lake Natoma bounding box (for E. coli stations).
STATION_BBOX = {"lat_min": 38.55, "lat_max": 38.72, "lon_min": -121.53, "lon_max": -121.15}
# Only keep river/lake swim sites with monitoring since this date (drops one-off
# study points, stormwater sumps, and discontinued sites).
STATION_MIN_LATEST = "2024-01-01"

# ── HAB (harmful algal bloom) sources — statewide FHAB program ──────────────────
# We fetch statewide and filter to the Sacramento / American & Sacramento River area.
BLOOM_RES = "c6a36b91-ad38-4611-8750-87ee99e497dd"   # FHAB bloom reports
LAB_RES = "9d4e1df4-0cd6-4165-9e63-effcafd9dccc"      # FHAB lab results (toxins)
# Sacramento-area bounding box (Lower American River, Sacramento River, local lakes)
BBOX = {"lat_min": 38.3, "lat_max": 38.85, "lon_min": -121.9, "lon_max": -121.0}

HABS_OUT = os.path.join(os.path.dirname(__file__), "docs", "blooms.json")

# ── EPA / CA recreational water-quality thresholds for E. coli (MPN/100 mL) ──
# 2012 EPA RWQC: geometric-mean criterion 126, statistical threshold value 410.
# 235 is the long-standing single-sample beach-posting threshold (1986 criteria).
GM_CRITERION = 126.0   # below this = good
SINGLE_CAUTION = 235.0  # single-sample advisory threshold
STV = 410.0            # statistical threshold value — posting/closure threshold

OUT = os.path.join(os.path.dirname(__file__), "docs", "stations.json")


def status_for(result):
    """Map a single E. coli result to a swim-safety tier."""
    if result is None:
        return "Unknown"
    if result <= GM_CRITERION:
        return "Good"
    if result <= SINGLE_CAUTION:
        return "Caution"
    if result <= STV:
        return "Warning"
    return "Unsafe"


def fetch_all(resource_id=RESOURCE_ID):
    """Page through the CKAN datastore and return all records for a resource."""
    records = []
    offset = 0
    limit = 1000
    while True:
        url = (f"{BASE}/datastore_search?resource_id={resource_id}"
               f"&limit={limit}&offset={offset}")
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = json.load(resp)
        batch = data["result"]["records"]
        records.extend(batch)
        total = data["result"]["total"]
        offset += len(batch)
        if offset >= total or not batch:
            break
    return records


def fetch_last_modified(resource_id=RESOURCE_ID):
    url = f"{BASE}/resource_show?id={resource_id}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            d = json.load(resp)
        return d.get("result", {}).get("last_modified")
    except Exception:
        return None


def fetch_sql(sql):
    """Run a CKAN datastore SQL query and return the record list."""
    import urllib.parse
    url = f"{BASE}/datastore_search_sql?" + urllib.parse.urlencode({"sql": sql})
    with urllib.request.urlopen(url, timeout=120) as resp:
        return json.load(resp)["result"]["records"]


def fetch_ecoli_stations():
    """Fetch E. coli records within the American River bounding box (paged)."""
    b = STATION_BBOX
    cols = ('"StationCode" c,"StationName" n,"TargetLatitude" lat,"TargetLongitude" lon,'
            '"SampleDate" d,"Result" r,"Unit" u,"6WeekGeoMean" gm,"6WeekCount" gmn')
    where = (f"\"Analyte\"='E. coli' "
             f"AND CAST(\"TargetLatitude\" AS FLOAT) BETWEEN {b['lat_min']} AND {b['lat_max']} "
             f"AND CAST(\"TargetLongitude\" AS FLOAT) BETWEEN {b['lon_min']} AND {b['lon_max']}")
    records, offset, page = [], 0, 20000
    while True:
        rows = fetch_sql(f'SELECT {cols} FROM "{RESOURCE_ID}" WHERE {where} '
                         f'LIMIT {page} OFFSET {offset}')
        records.extend(rows)
        offset += len(rows)
        if len(rows) < page:
            break
    return records


def geomean(values):
    vals = [v for v in values if v and v > 0]
    if not vals:
        return None
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def in_bbox(lat, lon):
    return (BBOX["lat_min"] <= lat <= BBOX["lat_max"]
            and BBOX["lon_min"] <= lon <= BBOX["lon_max"])


def classify_adv(adv):
    """Map an FHAB advisory string to a tier used by the app."""
    a = (adv or "").lower()
    if "danger" in a:
        return "Danger"
    if "warning" in a:
        return "Warning"
    if "caution" in a:
        return "Caution"
    if "mat" in a or "benthic" in a:
        return "Mat"
    if "awareness" in a or "watch" in a:
        return "Watch"
    return "Other"


def build_habs():
    """Fetch statewide FHAB blooms + lab toxins, filter to the Sacramento-area
    bounding box, and write docs/blooms.json."""
    print("Fetching FHAB bloom reports…")
    blooms = fetch_all(BLOOM_RES)
    print(f"  {len(blooms)} statewide bloom records")
    try:
        lab = fetch_all(LAB_RES)
    except Exception:
        lab = []
    print(f"  {len(lab)} lab result rows")

    # Lab toxin lookup: Bloom_Report_ID -> sorted list of toxin classes
    lab_by_bloom = {}
    for row in lab:
        bid = row.get("Bloom_Report_ID")
        ac = (row.get("Analyte_Class") or "").strip()
        if not bid or not ac or ac in ("Taxa_Dominance", "Other"):
            continue
        if (row.get("Sample_Type") or "") != "Lab":
            continue
        lab_by_bloom.setdefault(bid, set()).add(ac)

    out = []
    for row in blooms:
        try:
            lat = float(row.get("Bloom_Latitude"))
            lon = float(row.get("Bloom_Longitude") or row.get("Bloom Longitude"))
        except (TypeError, ValueError):
            continue
        if math.isnan(lat) or math.isnan(lon) or not in_bbox(lat, lon):
            continue
        detail = (row.get("Advisory_Detail_Description") or "") + (row.get("AdvisoryDetail") or "")
        bid = row.get("Bloom_Report_ID")
        lab_linked = (row.get("Lab_Data_Linked_to_Bloom") or "").upper() == "YES"
        lab_toxins = sorted(lab_by_bloom.get(bid, set()))
        adv = clean(row.get("Reported_Advisory_Types"))
        out.append({
            "id": clean(row.get("Bloom_Report_ID")),
            "name": clean(row.get("Water_Body_Name")) or clean(row.get("Official_Water_Body_Name")),
            "county": clean(row.get("County")),
            "rwb": clean(row.get("Regional_Water_Board")),
            "lat": lat, "lon": lon,
            "obs": clean(row.get("Observation_Date")),
            "status": clean(row.get("Case_Status")),
            "adv": adv,
            "tier": classify_adv(adv if (adv and "refer" not in adv.lower()) else detail),
            "detail": clean(row.get("Advisory_Detail_Description")) or clean(row.get("AdvisoryDetail")),
            "size": clean(row.get("Bloom_Size")),
            "texture": clean(row.get("Bloom_Texture")),
            "landmark": clean(row.get("Landmark")),
            "wtype": clean(row.get("Water_Body_Type")),
            "drinking_water": (row.get("Drinking_Water_Source") or "").strip().lower() == "yes",
            "illness": bool(re.search(r"illness|sick", detail, re.I)),
            "lab_verified": lab_linked or len(lab_toxins) > 0,
            "lab_toxins": lab_toxins,
        })

    out.sort(key=lambda b: (b.get("obs") or ""), reverse=True)
    payload = {
        "bbox": BBOX,
        "source": {
            "name": "CA State Water Board — Freshwater & Estuarine HAB (FHAB) Program",
            "url": "https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms",
            "last_modified": fetch_last_modified(BLOOM_RES),
        },
        "blooms": out,
    }
    os.makedirs(os.path.dirname(HABS_OUT), exist_ok=True)
    with open(HABS_OUT, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    from collections import Counter
    print(f"Wrote {len(out)} blooms -> {HABS_OUT}")
    print("Bloom tiers:", dict(Counter(b["tier"] for b in out)))


def main():
    from collections import Counter, defaultdict
    records = fetch_ecoli_stations()
    print(f"Fetched {len(records)} E. coli records in bbox")

    # Group by station code (a code can appear under bank/name variants + replicates).
    by_code = defaultdict(list)
    for row in records:
        code = (row.get("c") or "").strip()
        lat, lon, result = num(row.get("lat")), num(row.get("lon")), num(row.get("r"))
        date = (row.get("d") or "")[:10]
        if not code or not date or None in (lat, lon, result):
            continue
        row["_lat"], row["_lon"], row["_r"], row["_d"] = lat, lon, result, date
        by_code[code].append(row)

    out, dropped = [], 0
    for code, rows in by_code.items():
        name = Counter((r.get("n") or "").strip() for r in rows).most_common(1)[0][0] or code
        coord_rows = [r for r in rows if (r.get("n") or "").strip() == name] or rows
        rlat = round(sum(r["_lat"] for r in coord_rows) / len(coord_rows), 5)
        rlon = round(sum(r["_lon"] for r in coord_rows) / len(coord_rows), 5)
        # one sample per date (keep the row with the fullest 6-week window)
        by_date = {}
        for r in rows:
            d = r["_d"]
            if d not in by_date or (num(r.get("gmn")) or 0) > (num(by_date[d].get("gmn")) or 0):
                by_date[d] = r
        srows = sorted(by_date.values(), key=lambda r: r["_d"], reverse=True)
        latest = srows[0]
        nm = name.lower()
        # keep only ongoing river/lake swim sites
        if not (latest["_d"] >= STATION_MIN_LATEST and ("american river" in nm or "lake natoma" in nm)):
            dropped += 1
            continue
        samples = [{"date": r["_d"], "result": round(r["_r"], 1), "status": status_for(r["_r"])}
                   for r in srows]
        # geomean: prefer the dataset's official 6-week geomean on the latest sample
        official_gm, official_n = num(latest.get("gm")), num(latest.get("gmn"))
        if official_gm:
            gm, gmn = official_gm, int(official_n or 0)
        else:
            recent = [s["result"] for s in samples[:6]]
            gm, gmn = geomean(recent), len(recent)
        out.append({
            "code": code,
            "name": name,
            "lat": rlat, "lon": rlon,
            "unit": "MPN/100 mL",
            "samples": samples,
            "latest": samples[0],
            "geomean": round(gm, 1) if gm is not None else None,
            "geomean_n": gmn,
            "n": len(samples),
            "status": samples[0]["status"],
            "geomean_status": "Good" if (gm is not None and gm <= GM_CRITERION) else (
                status_for(gm) if gm is not None else "Unknown"),
        })

    out.sort(key=lambda s: s["name"])
    print(f"Consolidated to {len(out)} stations ({dropped} non-swim sites dropped)")

    payload = {
        "thresholds": {
            "gm_criterion": GM_CRITERION,
            "single_caution": SINGLE_CAUTION,
            "stv": STV,
            "unit": "MPN/100 mL",
        },
        "source": {
            "name": "CA State Water Board — Surface Water Fecal Indicator Bacteria (E. coli)",
            "url": "https://data.ca.gov/dataset/" + PACKAGE_ID,
            "last_modified": fetch_last_modified(),
        },
        "stations": out,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"Wrote {len(out)} stations -> {OUT}")
    # quick summary
    from collections import Counter
    c = Counter(s["status"] for s in out)
    print("Current status:", dict(c))

    # Also build the Sacramento-area HAB layer.
    build_habs()


if __name__ == "__main__":
    main()
