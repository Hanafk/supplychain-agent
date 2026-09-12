# ─────────────────────────────────────────────────────────────────
#  clusters.py — 20-cluster reference table for the Cluster Request
#  reallocation engine (Wave 1/2).
# ─────────────────────────────────────────────────────────────────

import math

CLUSTERS = {
    "HC1":  ("Hail",      "Hail Health Cluster",            27.52, 41.68),
    "IC1":  ("Taif",      "Taif Health Cluster",            21.27, 40.41),
    "UC1":  ("Najran",    "Najran Health Cluster",          17.49, 44.13),
    "FC1":  ("Hafer",     "Hafer Al Batin Health Cluster",  28.43, 45.96),
    "LC1":  ("Ahsaa",     "Al Ahsa Health Cluster",         25.38, 49.58),
    "TC1":  ("Tabouk",    "Tabouk Health Cluster",          28.38, 36.57),
    "NC1":  ("North",     "Northern Border Health Cluster", 30.98, 41.04),
    "RC1":  ("Riyadh 1",  "Riyadh Health Cluster 1",        24.69, 46.72),
    "RC2":  ("Riyadh 2",  "Riyadh Health Cluster 2",        24.80, 46.82),
    "RC3":  ("Riyadh 3",  "Riyadh Health Cluster 3",        24.60, 46.62),
    "EC1":  ("Dammam",    "Dammam Health Cluster",          26.43, 50.10),
    "JC1":  ("Jeddah",    "Jeddah Health Cluster",          21.49, 39.19),
    "MC1":  ("Makkah",    "Makkah Health Cluster",          21.42, 39.83),
    "DC1":  ("Madinah",   "Madinah Health Cluster",         24.47, 39.61),
    "AC1":  ("Aseer",     "Aseer Health Cluster",           18.22, 42.51),
    "BC1":  ("Al-Bahah",  "Al Bahah Health Cluster",        20.01, 41.47),
    "GC1":  ("Jazan",     "Jazan Health Cluster",           16.89, 42.56),
    "SC1":  ("Joaf",      "Jouf Health Cluster",            29.79, 39.99),
    "YC3":  ("Qassim",    "Qassim Health Cluster",          26.33, 43.97),
    "KAMC": ("KAMC",      "KAMC Cluster",                   24.75, 46.75),
}

NAME_TO_CODE = {name: code for code, (name, *_r) in CLUSTERS.items()}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _build_distance_table() -> dict:
    table = {}
    codes = list(CLUSTERS.keys())
    for a in codes:
        for b in codes:
            if a == b:
                table[(a, b)] = 0.0
            else:
                _, _, lat_a, lon_a = CLUSTERS[a]
                _, _, lat_b, lon_b = CLUSTERS[b]
                table[(a, b)] = round(haversine_km(lat_a, lon_a, lat_b, lon_b), 1)
    return table


CLUSTER_DISTANCE_KM = _build_distance_table()
