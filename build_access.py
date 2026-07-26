#!/usr/bin/env python3
"""Build access_points.json + river_line.json for the Float & Shuttle Planner.

Fetches the Lower American River centerline from OpenStreetMap, orders it
downstream->upstream, computes a cumulative river mile for every vertex, and
snaps a curated set of river-access points onto it (giving each a `river_mi`
station used to compute float distances between put-ins/take-outs).

Outputs:
  docs/river_line.json   — ordered centerline: {unit, line:[[lat,lon,mi],...]}
  docs/access_points.json — {note, river, speed_mph, access:[{id,name,lat,lon,river_mi,...}]}

NHD+ would give more authoritative river distances; OSM is close for this reach.
"""
import json, math, os, urllib.request, urllib.parse

M2MI = 1/1609.344
DOCS = os.path.join(os.path.dirname(__file__), "docs")
OVERPASS = "https://overpass-api.de/api/interpreter"

# Seed access points (downstream->upstream). Coordinates approximate — edit freely.
SEEDS = [
 ("discovery-park",   "Discovery Park",         38.6015, -121.5045, "Confluence with the Sacramento River; large park, boat ramp, restrooms."),
 ("tiscornia-beach",  "Tiscornia Beach",        38.5980, -121.5070, "Sandy beach at the confluence; life jackets on site."),
 ("sutters-landing",  "Sutter's Landing",       38.5880, -121.4620, "River access near downtown; parking."),
 ("paradise-beach",   "Paradise Beach",         38.5820, -121.4300, "Glen Hall Park / River Park; popular beach."),
 ("howe-ave",         "Howe Avenue Access",     38.5601, -121.4053, "River access off Howe Ave."),
 ("watt-ave",         "Watt Avenue Access",     38.5660, -121.3810, "River access at the Watt Ave bridge."),
 ("river-bend",       "River Bend Park",        38.5875, -121.3255, "Formerly Goethe Park; beaches and parking (Rancho Cordova)."),
 ("rossmoor-bar",     "Rossmoor Bar",           38.6112, -121.3045, "Gravel-bar access, Rancho Cordova."),
 ("ancil-hoffman",    "Ancil Hoffman Park",     38.6228, -121.3050, "Large Carmichael park on a river bend."),
 ("sacramento-bar",   "Sacramento Bar",         38.6275, -121.2891, "Gravel-bar access and rafting take-out."),
 ("el-manto",         "El Manto Access",        38.6180, -121.2820, "River access at the end of El Manto Dr (Gold River)."),
 ("lower-sunrise",    "Lower Sunrise",          38.6330, -121.2710, "Sunrise Recreation Area; sandy beaches, parking, popular put-in."),
 ("sailor-bar",       "Sailor Bar",             38.6330, -121.2330, "Fair Oaks; uppermost Lower American River access below Nimbus Dam."),
]


def hav(a, b, c, d):
    R = 6371000.0
    p1, p2 = math.radians(a), math.radians(c)
    dp = math.radians(c-a); dl = math.radians(d-b)
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R*2*math.atan2(math.sqrt(x), math.sqrt(1-x))


def fetch_centerline():
    q = ('[out:json][timeout:120];'
         'way["waterway"="river"]["name"="American River"]'
         '(38.55,-121.52,38.67,-121.21);out geom;')
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
                                 headers={"User-Agent": "CanISwimHere-build/1.0"})
    with urllib.request.urlopen(req, timeout=150) as r:
        d = json.load(r)
    pts = []
    for e in d.get("elements", []):
        for g in e.get("geometry", []) or []:
            pts.append((g["lat"], g["lon"]))
    # de-dup preserving order
    seen, P = set(), []
    for la, lo in pts:
        k = (round(la, 6), round(lo, 6))
        if k not in seen:
            seen.add(k); P.append((la, lo))
    return P


def order_path(P):
    # nearest-neighbor from the confluence (westernmost vertex), upstream
    start = min(range(len(P)), key=lambda i: P[i][1])
    path, used, cur = [P[start]], {start}, start
    while len(used) < len(P):
        best, bd = None, 1e18
        for j, (la, lo) in enumerate(P):
            if j in used:
                continue
            dd = hav(P[cur][0], P[cur][1], la, lo)
            if dd < bd:
                bd, best = dd, j
        if best is None or bd > 1500:
            break
        used.add(best); path.append(P[best]); cur = best
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
        json.dump({"unit": "mi", "note": "Lower American River centerline (OSM), ordered "
                   "confluence(mi 0)->upstream, with cumulative river mile per vertex.",
                   "line": line}, f, separators=(",", ":"))

    access = []
    for aid, name, la, lo, note in SEEDS:
        mi, off = station_mi(la, lo, path, cum)
        access.append({"id": aid, "name": name, "lat": la, "lon": lo,
                       "river_mi": round(mi, 2), "snap_off_m": round(off), "note": note})
    access.sort(key=lambda a: a["river_mi"])
    with open(os.path.join(DOCS, "access_points.json"), "w") as f:
        json.dump({
            "note": "Lower American River access points for the float/shuttle planner. "
                    "river_mi = miles along the OSM river centerline from the American-"
                    "Sacramento confluence (mile 0). NHD+ would be more authoritative. "
                    "Coordinates approximate — edit freely, then re-run build_access.py.",
            "river": "Lower American River",
            "speed_mph": {"min": 2, "max": 4, "note": "typical float/paddle speed at regular LAR flows"},
            "access": access,
        }, f, indent=2)
    print(f"wrote {len(access)} access points + river_line.json")
    for a in access:
        print(f"  {a['river_mi']:6.2f} mi  {a['snap_off_m']:>4}m  {a['id']:<16} {a['name']}")


if __name__ == "__main__":
    main()
