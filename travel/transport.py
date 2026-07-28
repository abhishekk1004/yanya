from __future__ import annotations


W_COST, W_TIME, W_COMFORT = 0.5, 0.3, 0.2


def recommend_transport(modes, distance_km: float):

    usable = [m for m in modes if distance_km >= m.min_km]
    if not usable:
        return []

    rows = []
    for m in usable:
        cost = m.base_fare_npr + m.per_km_npr * distance_km
        hours = distance_km / m.speed_kmph if m.speed_kmph else 0.0
        rows.append({"mode": m, "cost_npr": round(cost), "hours": round(hours, 1),
                     "comfort": m.comfort})

    costs = [r["cost_npr"] for r in rows]
    times = [r["hours"] for r in rows]
    c_lo, c_hi = min(costs), max(costs)
    t_lo, t_hi = min(times), max(times)

    def norm(v, lo, hi):
        return 0.0 if hi == lo else (v - lo) / (hi - lo)

    for r in rows:
        cost_n = norm(r["cost_npr"], c_lo, c_hi)      
        time_n = norm(r["hours"], t_lo, t_hi)         
        comfort_n = (r["comfort"] - 1) / 4.0          
        utility = W_COST * (1 - cost_n) + W_TIME * (1 - time_n) + W_COMFORT * comfort_n
        r["score"] = round(100 * utility, 1)

    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows
