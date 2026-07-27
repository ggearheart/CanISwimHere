#!/usr/bin/env python3
"""Build access_points.json + river_line.json for the Float & Shuttle Planner.

Models a connected river NETWORK (a downstream tree) so floats can cross confluences:
  Feather River  ─┐
                  ├─► Sacramento River ─► (system mouth, near Sacramento)
  American River ─┘

For each reach we fetch the OpenStreetMap centerline (best visual fit), order it
downstream(mile 0)->upstream, and compute a cumulative reach mile per vertex. Each
tributary also gets a `flow_offset` = the Sacramento mile at its confluence, so every
point has a unified `flow_mi` = reach_mi + flow_offset (miles to the system mouth).
Access points snap to their own reach's centerline.

Lakes (lake-natoma, folsom-lake) are flatwater above a dam — no reach mile.

Outputs:
  docs/river_line.json    — {unit, reaches:{seg:{name,source,downstream,flow_offset,
                             junction_mi,line:[[lat,lon,reach_mi],...]}}}
  docs/access_points.json — {note, speed_mph, access:[{id,name,segment,lat,lon,
                             river_mi(reach mile),flow_mi(network mile),...}]}
"""
import csv, json, math, os, re, urllib.request, urllib.parse

M2MI = 1/1609.344
DOCS = os.path.join(os.path.dirname(__file__), "docs")
SOURCE_CSV = os.path.join(os.path.dirname(__file__), "access_points_source.csv")
# Multiple Overpass mirrors — the main endpoint is often rate-limited (504).
OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

STR_FIELDS = ["parking_fee", "parking_info", "walk_to_water", "amenities", "cautions", "note"]

# Flowing-river reaches (each a centerline with its own mile system). Lakes are handled
# separately (flatwater, no centerline). Process the trunk (Sacramento) FIRST so tributary
# flow_offsets can snap their confluence onto it. Overpass bbox is (S, W, N, E).
REACHES = {
    "sacramento-river": {               # trunk — from just below Broderick up to Knights Landing
        "name": "Sacramento River", "osm": "Sacramento River",
        "bbox": (38.57, -121.76, 38.83, -121.48),
        "mouth": (38.578, -121.509),    # below Broderick = mile 0 (so Broderick sits just
                                        # downstream of the American confluence — a universal take-out)
        "downstream": None, "junction": None, "gap": 12000,  # big-river centerline is fragmented
    },
    "river": {                          # Lower American River
        "name": "American River", "osm": "American River",
        "bbox": (38.55, -121.52, 38.67, -121.21),
        "mouth": (38.600, -121.510),    # American–Sacramento confluence = mile 0
        "downstream": "sacramento-river", "junction": (38.600, -121.506), "gap": 1500,
    },
    "feather-river": {
        "name": "Feather River", "osm": "Feather River",
        "bbox": (38.78, -121.72, 39.18, -121.50),
        "mouth": (38.792, -121.627),    # Feather–Sacramento confluence at Verona = mile 0
        "downstream": "sacramento-river", "junction": (38.790, -121.622), "gap": 12000,
    },
}
LAKE_SEGS = {"lake-natoma", "folsom-lake"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def read_seeds():
    """Curated access points from access_points_source.csv (the file the user edits)."""
    seeds = []
    with open(SOURCE_CSV, newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            alat, alon = num(row.get("access_lat")), num(row.get("access_lon"))
            if not name or alat is None or alon is None:
                continue
            seeds.append({
                "id": slug(row.get("id") or name),
                "name": name,
                # segment: a flowing reach in REACHES (float + shuttle across the network)
                # or a lake in LAKE_SEGS (flatwater above a dam — paddle, no shuttle).
                "segment": (row.get("segment") or "river").strip().lower() or "river",
                "lat": alat, "lon": alon,
                "parking_lat": num(row.get("parking_lat")),
                "parking_lon": num(row.get("parking_lon")),
                **{k: ((row.get(k) or "").strip() or None) for k in STR_FIELDS},
            })
    return seeds


def hav(a, b, c, d):
    R = 6371000.0
    p1, p2 = math.radians(a), math.radians(c)
    dp = math.radians(c-a); dl = math.radians(d-b)
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R*2*math.atan2(math.sqrt(x), math.sqrt(1-x))


def overpass(query):
    import time
    last = None
    for ep in OVERPASS_ENDPOINTS:
        for _ in range(2):
            try:
                req = urllib.request.Request(ep, data=urllib.parse.urlencode({"data": query}).encode(),
                                             headers={"User-Agent": "CanISwimHere-build/1.0"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    return json.load(r)
            except Exception as e:            # 504/timeout/rate-limit — try next mirror
                last = e; time.sleep(3)
    raise RuntimeError(f"all Overpass endpoints failed: {last}")


def fetch_centerline(osm_name, bbox, pad=0.01):
    # Overpass `out geom` returns each matching way's FULL geometry (a big river way can
    # run far outside the bbox, e.g. to Oroville/Red Bluff). Clip vertices to the bbox.
    s, w, n, e = bbox
    d = overpass('[out:json][timeout:180];'
                 f'way["waterway"="river"]["name"="{osm_name}"]({s},{w},{n},{e});out geom;')
    pts, seen = [], set()
    for el in d.get("elements", []):
        for g in el.get("geometry", []) or []:
            la, lo = g["lat"], g["lon"]
            if not (s-pad <= la <= n+pad and w-pad <= lo <= e+pad):
                continue                                     # clip to corridor
            k = (round(la, 6), round(lo, 6))
            if k not in seen:
                seen.add(k); pts.append((la, lo))
    return pts


def order_path(P, mouth, gap=1500):
    """Nearest-neighbor order from the vertex closest to `mouth` (the downstream end).
    `gap` bridges breaks between fragmented OSM ways (big rivers are coarsely mapped)."""
    start = min(range(len(P)), key=lambda i: hav(P[i][0], P[i][1], mouth[0], mouth[1]))
    path, used, cur = [P[start]], {start}, start
    while len(used) < len(P):
        best, bd = None, 1e18
        for j, (la, lo) in enumerate(P):
            if j in used:
                continue
            dd = hav(P[cur][0], P[cur][1], la, lo)
            if dd < bd:
                bd, best = dd, j
        if best is None or bd > gap:
            break
        used.add(best); path.append(P[best]); cur = best
    cum = [0.0]
    for i in range(1, len(path)):
        cum.append(cum[-1] + hav(path[i-1][0], path[i-1][1], path[i][0], path[i][1]))
    return path, cum


def station_mi(plat, plon, path, cum):
    """Snap (plat,plon) to `path`; return (reach mile, offset metres)."""
    bestd, beststat = 1e18, 0.0
    latref = math.radians(plat); m = 111320.0
    def xy(la, lo): return (lo*m*math.cos(latref), la*m)
    px, py = xy(plat, plon)
    for i in range(len(path)-1):
        (la1, lo1), (la2, lo2) = path[i], path[i+1]
        x1, y1 = xy(la1, lo1); x2, y2 = xy(la2, lo2)
        dx, dy = x2-x1, y2-y1; L2 = dx*dx + dy*dy
        t = 0 if L2 == 0 else max(0, min(1, ((px-x1)*dx + (py-y1)*dy)/L2))
        cx, cy = x1+t*dx, y1+t*dy
        la, lo = cy/m, cx/(m*math.cos(latref))
        dd = hav(plat, plon, la, lo)
        if dd < bestd:
            bestd = dd
            beststat = cum[i] + t*hav(la1, lo1, la2, lo2)
    return beststat*M2MI, bestd


def main():
    # 1) Build each reach centerline (trunk first — dict preserves insertion order).
    built = {}
    for seg, cfg in REACHES.items():
        pts = fetch_centerline(cfg["osm"], cfg["bbox"])
        path, cum = order_path(pts, cfg["mouth"], cfg.get("gap", 1500))
        built[seg] = {"path": path, "cum": cum}
        print(f"{cfg['name']:<18} {len(path):>4}/{len(pts)} vertices used, {cum[-1]*M2MI:5.1f} mi")

    # 2) flow_offset: Sacramento is the trunk (0); each tributary enters the Sacramento
    #    at its junction -> flow_offset = Sacramento mile there. junction_mi = same.
    sac = built["sacramento-river"]
    for seg, cfg in REACHES.items():
        if cfg["downstream"] is None:
            built[seg]["flow_offset"] = 0.0
            built[seg]["junction_mi"] = None
        else:
            assert cfg["downstream"] == "sacramento-river"
            jmi, joff = station_mi(cfg["junction"][0], cfg["junction"][1], sac["path"], sac["cum"])
            built[seg]["flow_offset"] = round(jmi, 3)
            built[seg]["junction_mi"] = round(jmi, 3)
            print(f"  {cfg['name']} joins Sacramento at mile {jmi:.2f} (snap {joff:.0f} m)")

    # 3) write river_line.json (all reaches)
    reaches_out = {}
    for seg, cfg in REACHES.items():
        b = built[seg]
        line = [[round(la, 6), round(lo, 6), round(c*M2MI, 3)]
                for (la, lo), c in zip(b["path"], b["cum"])]
        reaches_out[seg] = {
            "name": cfg["name"], "source": "OpenStreetMap",
            "downstream": cfg["downstream"], "flow_offset": b["flow_offset"],
            "junction_mi": b["junction_mi"], "line": line,
        }
    with open(os.path.join(DOCS, "river_line.json"), "w") as f:
        json.dump({"unit": "mi",
                   "note": "River-network centerlines (OSM). reach_mi = miles from each "
                   "reach's downstream end (mile 0). flow_offset = the Sacramento mile "
                   "where a tributary joins; flow_mi = reach_mi + flow_offset (miles to "
                   "the system mouth). Feather & American join the Sacramento (no dams).",
                   "reaches": reaches_out}, f, separators=(",", ":"))

    # 4) snap access points -> reach_mi + flow_mi
    access = []
    for s in read_seeds():
        seg = s["segment"]
        walk_ft = None
        if s["parking_lat"] is not None and s["parking_lon"] is not None:
            walk_ft = round(hav(s["lat"], s["lon"], s["parking_lat"], s["parking_lon"]) * 3.28084)
        entry = {"id": s["id"], "name": s["name"], "segment": seg,
                 "lat": s["lat"], "lon": s["lon"],
                 "parking_lat": s["parking_lat"], "parking_lon": s["parking_lon"], "walk_ft": walk_ft}
        if seg in REACHES:
            b = built[seg]
            mi, off = station_mi(s["lat"], s["lon"], b["path"], b["cum"])
            entry["river_mi"] = round(mi, 2)
            entry["flow_mi"] = round(mi + b["flow_offset"], 2)
            entry["snap_off_m"] = round(off)
        else:                                   # lake — flatwater, no reach mile
            entry["river_mi"] = None
            entry["flow_mi"] = None
        for k in STR_FIELDS:
            if s.get(k):
                entry[k] = s[k]
        access.append(entry)
    # order: flowing reaches by flow_mi (downstream->upstream), lakes after
    access.sort(key=lambda a: (a["flow_mi"] is None, a.get("segment"),
                               a["flow_mi"] if a["flow_mi"] is not None else 0, a["name"]))
    with open(os.path.join(DOCS, "access_points.json"), "w") as f:
        json.dump({
            "note": "Access points for the float/shuttle planner. Source of truth: "
                    "access_points_source.csv (edit that, then re-run build_access.py). "
                    "segment = a flowing reach (river=American, sacramento-river, "
                    "feather-river — float + shuttle, connected as a downstream network) or "
                    "a lake (lake-natoma/folsom-lake — flatwater above a dam, paddle). "
                    "river_mi = miles along the reach centerline from its downstream end; "
                    "flow_mi = miles to the system mouth (crosses confluences). "
                    "lat/lon = water's edge; parking_lat/lon = the lot.",
            "speed_mph": {"min": 2, "max": 4, "note": "typical float/paddle speed at regular flows"},
            "access": access,
        }, f, indent=2)
    print(f"wrote {len(access)} access points + river_line.json ({len(REACHES)} reaches)")
    for a in access:
        if a["flow_mi"] is not None:
            print(f"  flow {a['flow_mi']:6.2f}  reach {a['river_mi']:6.2f}  {a['segment']:<16} {a['name']}")
        else:
            print(f"   (lake) {a['segment']:<16} {a['name']}")


if __name__ == "__main__":
    main()
