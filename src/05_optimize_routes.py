import duckdb
import joblib
import numpy as np
import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

# 1. Load trained ML model and connect to DuckDB
model = joblib.load("src/travel_time_model.pkl")
con = duckdb.connect("data/logistics.duckdb")

# Pull 26 deterministic delivery coordinates (Index 0 = Depot, 1..25 = Customer Drops)
stops_df = con.execute("""
    SELECT
        trip_id,
        end_lat AS lat,
        end_lon AS lon,
        road_type,
        zone_type,
        num_lanes,
        num_signals,
        traffic_level,
        weather_type,
        temperature_c,
        visibility_km
    FROM vw_master_shipments
    WHERE trip_hour = 18
      AND traffic_level <> 'unknown'
    ORDER BY trip_id
    LIMIT 26
""").df()

n_stops = len(stops_df)

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0)**2
    return 2 * R * np.arcsin(np.sqrt(a)) * 1.35

# 2. Build Distance Matrix & ML-Predicted Travel Time Matrix
dist_matrix = np.zeros((n_stops, n_stops))
pair_features = []

for i in range(n_stops):
    for j in range(n_stops):
        if i == j:
            dist_matrix[i][j] = 0.0
        else:
            d = haversine_km(
                stops_df.loc[i, "lat"], stops_df.loc[i, "lon"],
                stops_df.loc[j, "lat"], stops_df.loc[j, "lon"]
            )
            dist_matrix[i][j] = max(d, 0.8)
        pair_features.append({
            "distance_km": dist_matrix[i][j],
            "num_lanes": stops_df.loc[j, "num_lanes"],
            "num_signals": stops_df.loc[j, "num_signals"],
            "trip_hour": 18,
            "temperature_c": stops_df.loc[j, "temperature_c"],
            "visibility_km": stops_df.loc[j, "visibility_km"],
            "road_type": stops_df.loc[j, "road_type"],
            "zone_type": stops_df.loc[j, "zone_type"],
            "traffic_level": stops_df.loc[j, "traffic_level"],
            "weather_type": stops_df.loc[j, "weather_type"],
        })

pred_times = model.predict(pd.DataFrame(pair_features)).reshape((n_stops, n_stops))
pred_times = np.maximum(pred_times, 2.0)
np.fill_diagonal(pred_times, 0.0)

FUEL_COST_PER_KM = 0.22    # $0.22/km fuel & maintenance
DRIVER_COST_PER_MIN = 0.40 # $24/hr ($0.40/min) driver labor

def solve_fleet_routing(weight_matrix, num_vehicles=3):
    # Scale weights to large integers so OR-Tools preserves full precision
    scaled_matrix = np.round((weight_matrix / np.max(weight_matrix)) * 10000).astype(int)
    np.fill_diagonal(scaled_matrix, 0)

    manager = pywrapcp.RoutingIndexManager(n_stops, num_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def cost_callback(from_idx, to_idx):
        u = manager.IndexToNode(from_idx)
        v = manager.IndexToNode(to_idx)
        return int(scaled_matrix[u][v])

    cb_idx = routing.RegisterTransitCallback(cost_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(cb_idx)

    # Cap each truck at 10 stops so workload balances across all 3 trucks
    def count_callback(from_idx):
        return 1
    cnt_idx = routing.RegisterUnaryTransitCallback(count_callback)
    routing.AddDimensionWithVehicleCapacity(cnt_idx, 0, [11] * num_vehicles, True, "Stops")

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = 3

    solution = routing.SolveWithParameters(params)
    routes = []
    total_dist, total_time, total_cost = 0.0, 0.0, 0.0

    for v in range(num_vehicles):
        idx = routing.Start(v)
        path = []
        v_dist, v_time = 0.0, 0.0
        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            path.append(node)
            next_idx = solution.Value(routing.NextVar(idx))
            next_node = manager.IndexToNode(next_idx)
            v_dist += dist_matrix[node][next_node]
            v_time += pred_times[node][next_node]
            idx = next_idx
        path.append(0)
        v_cost = (v_dist * FUEL_COST_PER_KM) + (v_time * DRIVER_COST_PER_MIN)
        total_dist += v_dist
        total_time += v_time
        total_cost += v_cost
        routes.append({
            "vehicle": f"Truck_{v+1}",
            "stops_visited": len(path) - 2,
            "route_sequence": " -> ".join(map(str, path)),
            "distance_km": round(v_dist, 2),
            "travel_time_min": round(v_time, 1),
            "operational_cost_usd": round(v_cost, 2)
        })
    return pd.DataFrame(routes), total_dist, total_time, total_cost

# Scenario A: Naive Baseline (Optimizes raw distance only, ignoring traffic & weather)
baseline_df, b_dist, b_time, b_cost = solve_fleet_routing(dist_matrix)

# Scenario B: Congestion-Aware Optimization (Balances 65% speed + 35% fuel/labor cost)
monetary_matrix = (dist_matrix * FUEL_COST_PER_KM) + (pred_times * DRIVER_COST_PER_MIN)
norm_time = pred_times / np.max(pred_times)
norm_cost = monetary_matrix / np.max(monetary_matrix)
balanced_matrix = (0.65 * norm_time) + (0.35 * norm_cost)

opt_df, o_dist, o_time, o_cost = solve_fleet_routing(balanced_matrix)

print("=" * 80)
print("OPTIMIZED FLEET DISPATCH PLAN (ML + GOOGLE OR-TOOLS)")
print("=" * 80)
print(opt_df.to_string(index=False))

time_saved_pct = ((b_time - o_time) / b_time) * 100
cost_saved_pct = ((b_cost - o_cost) / b_cost) * 100

print("\n" + "=" * 80)
print("BUSINESS IMPACT: BASELINE (DISTANCE-ONLY) VS. CONGESTION-AWARE MODEL")
print("=" * 80)
print(f"Total Fleet Travel Time : {b_time:.1f} min  -->  {o_time:.1f} min  ({time_saved_pct:+.1f}% change)")
print(f"Total Operational Cost  : ${b_cost:.2f}      -->  ${o_cost:.2f}      ({cost_saved_pct:+.1f}% change)")
print(f"Total Fleet Distance    : {b_dist:.1f} km   -->  {o_dist:.1f} km")

opt_df.to_csv("data/optimization_results.csv", index=False)
print("\nSaved dispatch schedule to data/optimization_results.csv")
