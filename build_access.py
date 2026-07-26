#!/usr/bin/env python3
"""Build access_points.json + river_line.json for the Float & Shuttle Planner.

Fetches the Lower American River centerline from the USGS NHDPlus network via the
NLDI service (downstream-main flowlines from the American R at Fair Oaks gage),
trims it at the American-Sacramento confluence, orders it confluence->upstream,
computes a cumulative river mile for every vertex, and snaps a curated set of
river-access points onto it (giving each a `river_mi` station used to compute
float distances between put-ins/take-outs).

Outputs:
  docs/river_line.json   — ordered centerline: {unit, source, line:[[lat,lon,mi],...]}
  docs/access_points.json — {note, river, speed_mph, access:[{id,name,lat,lon,river_mi,...}]}
"""
import csv, json, math, os, re, urllib.request

M2MI = 1/1609.344
DOCS = os.path.join(os.path.dirname(__file__), "docs")
SOURCE_CSV = os.path.join(os.path.dirname(__file__), "access_points_source.csv")
# USGS NLDI (Network Linked Data Index) — NHDPlus flowlines, downstream-main from
# the American River at Fair Oaks gage; trimmed at the confluence.
NLDI = ("https://api.water.usgs.gov/nldi/linked-data/nwissite/USGS-11446500/"
        "navigation/DM/flowlines?distance=45&f=json")
CONFLUENCE = (38.6005, -121.5085)   # American x Sacramento River

# String fields carried through from the source CSV into access_points.json.
STR_FIELDS = ["parking_fee", "parking_info", "walk_to_water", "amenities", "cautions", "note"]


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


def fetch_centerline():
    req = urllib.request.Request(NLDI, headers={"User-Agent": "CanISwimHere-build/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    pts = []
    for f in d.get("features", []):
        g = f.get("geometry", {})
        segs = [g["coordinates"]] if g.get("type") == "LineString" else g.get("coordinates", [])
        for ls in segs:
            for c in ls:
                pts.append((c[1], c[0]))  # (lat, lon)
    seen, P = set(), []
    for la, lo in pts:
        k = (round(la, 6), round(lo, 6))
        if k not in seen:
            seen.add(k); P.append((la, lo))
    return P


def order_path(P):
    # order downstream from the gage (easternmost vertex) via nearest-neighbor
    start = max(range(len(P)), key=lambda i: P[i][1])
    path, used, cur = [P[start]], {start}, start
    while len(used) < len(P):
        best, bd = None, 1e18
        for j, (la, lo) in enumerate(P):
            if j in used:
                continue
            dd = hav(P[cur][0], P[cur][1], la, lo)
            if dd < bd:
                bd, best = dd, j
        if best is None or bd > 2000:
            break
        used.add(best); path.append(P[best]); cur = best
    # trim at the confluence and flip so mile 0 = confluence, increasing upstream
    ci = min(range(len(path)), key=lambda i: hav(path[i][0], path[i][1], *CONFLUENCE))
    path = path[:ci+1][::-1]
    cum = [0.0]
    for i in range(1, len(path)):
        cum.append(cum[-1] + hav(path[i-1][0], path[i-1][1], path[i][0], path[i][1]))
    return path, cum


def station_mi(plat, plon, path, cum):
    best, bestd, beststat = None, 1e18, 0.0
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
    P = fetch_centerline()
    path, cum = order_path(P)
    print(f"centerline: {len(path)} ordered vertices, {cum[-1]*M2MI:.1f} river miles")

    line = [[round(la, 6), round(lo, 6), round(c*M2MI, 3)] for (la, lo), c in zip(path, cum)]
    with open(os.path.join(DOCS, "river_line.json"), "w") as f:
        json.dump({"unit": "mi", "source": "USGS NHDPlus via NLDI",
                   "note": "Lower American River centerline (NHDPlus flowlines), ordered "
                   "confluence(mi 0)->upstream, with cumulative river mile per vertex.",
                   "line": line}, f, separators=(",", ":"))

    access = []
    for s in read_seeds():
        mi, off = station_mi(s["lat"], s["lon"], path, cum)
        walk_ft = None
        if s["parking_lat"] is not None and s["parking_lon"] is not None:
            walk_ft = round(hav(s["lat"], s["lon"], s["parking_lat"], s["parking_lon"]) * 3.28084)
        entry = {"id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"],
                 "river_mi": round(mi, 2), "snap_off_m": round(off),
                 "parking_lat": s["parking_lat"], "parking_lon": s["parking_lon"], "walk_ft": walk_ft}
        for k in STR_FIELDS:
            if s.get(k):
                entry[k] = s[k]
        access.append(entry)
    access.sort(key=lambda a: a["river_mi"])
    with open(os.path.join(DOCS, "access_points.json"), "w") as f:
        json.dump({
            "note": "Lower American River access points for the float/shuttle planner. "
                    "Source of truth: access_points_source.csv (edit that, then re-run "
                    "build_access.py). river_mi = miles along the USGS NHDPlus river "
                    "centerline (via NLDI) from the American-Sacramento confluence (mile 0). "
                    "lat/lon = water's edge (put-in/take-out); parking_lat/lon = the lot.",
            "river": "Lower American River",
            "speed_mph": {"min": 2, "max": 4, "note": "typical float/paddle speed at regular LAR flows"},
            "access": access,
        }, f, indent=2)
    print(f"wrote {len(access)} access points + river_line.json")
    for a in access:
        print(f"  {a['river_mi']:6.2f} mi  {a['snap_off_m']:>4}m  {a['id']:<16} {a['name']}")


if __name__ == "__main__":
    main()
