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
import urllib.request

# CKAN datastore resource: "Draft - Lower American River E. coli Monitoring Results"
RESOURCE_ID = "fc450fb6-e997-4bcf-b824-1b3ed0f06045"
PACKAGE_ID = "central-valley-water-board-e-coli-monitoring-results"
BASE = "https://data.ca.gov/api/3/action"

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


def fetch_all():
    """Page through the CKAN datastore and return all records."""
    records = []
    offset = 0
    limit = 1000
    while True:
        url = (f"{BASE}/datastore_search?resource_id={RESOURCE_ID}"
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


def fetch_last_modified():
    url = f"{BASE}/resource_show?id={RESOURCE_ID}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            d = json.load(resp)
        return d.get("result", {}).get("last_modified")
    except Exception:
        return None


def geomean(values):
    vals = [v for v in values if v and v > 0]
    if not vals:
        return None
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def main():
    records = fetch_all()
    print(f"Fetched {len(records)} records")

    stations = {}
    for row in records:
        if (row.get("Analyte") or "").strip().lower() != "e. coli":
            continue
        code = (row.get("StationCode") or "").strip()
        try:
            lat = float(row["Latitude"])
            lon = float(row["Longitude"])
            result = float(row["Result"])
        except (TypeError, ValueError, KeyError):
            continue
        date = (row.get("SampleDate") or "").strip()[:10]
        if not code or not date:
            continue
        st = stations.setdefault(code, {
            "code": code,
            "name": (row.get("StationName") or code).strip(),
            "lat": lat,
            "lon": lon,
            "unit": (row.get("Unit") or "MPN/100 mL").strip(),
            "program": (row.get("Program") or "").strip(),
            "samples": [],
        })
        st["samples"].append({"date": date, "result": round(result, 1)})

    out = []
    for st in stations.values():
        # newest first
        st["samples"].sort(key=lambda s: s["date"], reverse=True)
        for s in st["samples"]:
            s["status"] = status_for(s["result"])
        latest = st["samples"][0]
        # geometric mean of the 6 most recent samples (EPA uses a rolling window)
        recent = [s["result"] for s in st["samples"][:6]]
        gm = geomean(recent)
        st["latest"] = latest
        st["geomean"] = round(gm, 1) if gm is not None else None
        st["geomean_n"] = len(recent)
        st["n"] = len(st["samples"])
        st["status"] = status_for(latest["result"])
        st["geomean_status"] = "Good" if (gm is not None and gm <= GM_CRITERION) else (
            status_for(gm) if gm is not None else "Unknown")
        out.append(st)

    out.sort(key=lambda s: s["name"])

    payload = {
        "thresholds": {
            "gm_criterion": GM_CRITERION,
            "single_caution": SINGLE_CAUTION,
            "stv": STV,
            "unit": "MPN/100 mL",
        },
        "source": {
            "name": "Central Valley Water Board — Lower American River E. coli Monitoring",
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


if __name__ == "__main__":
    main()
