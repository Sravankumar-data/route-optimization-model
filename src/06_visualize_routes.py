import duckdb
import folium
import pandas as pd

# 1. Load the exact same 26 stops used in 05_optimize_routes.py
con = duckdb.connect("data/logistics.duckdb")
stops_df = con.execute("""
    SELECT
        trip_id,
        end_lat AS lat,
        end_lon AS lon,
        road_type,
        zone_type,
        traffic_level,
        weather_type
    FROM vw_master_shipments
    WHERE trip_hour = 18
      AND traffic_level <> 'unknown'
    ORDER BY trip_id
    LIMIT 26
""").df()

# 2. Load the optimized dispatch sequences saved by 05_optimize_routes.py
routes_df = pd.read_csv("data/optimization_results.csv")

# 3. Initialize Folium map centered at the Depot (Node 0)
depot_lat = stops_df.loc[0, "lat"]
depot_lon = stops_df.loc[0, "lon"]
m = folium.Map(location=[depot_lat, depot_lon], zoom_start=11, tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", attr="Esri")

# Plot Depot Marker (Node 0)
folium.Marker(
    location=[depot_lat, depot_lon],
    popup="<b>Central Dispatch Depot (Node 0)</b>",
    tooltip="Depot (Start / End)",
    icon=folium.Icon(color="black", icon="home", prefix="fa")
).add_to(m)

# Color palette for the 3 delivery trucks
truck_colors = {
    "Truck_1": "#2563EB",  # Blue
    "Truck_2": "#16A34A",  # Green
    "Truck_3": "#DC2626"   # Red
}

# 4. Draw each truck's route path and numbered customer stop markers
for _, row in routes_df.iterrows():
    vehicle = row["vehicle"]
    color = truck_colors.get(vehicle, "#6B7280")
    node_indices = [int(x.strip()) for x in row["route_sequence"].split("->")]
    
    path_coords = []
    for step_num, node_idx in enumerate(node_indices):
        lat = stops_df.loc[node_idx, "lat"]
        lon = stops_df.loc[node_idx, "lon"]
        path_coords.append([lat, lon])
        
        # Add numbered stop markers for customer drops (skip Depot 0)
        if node_idx != 0:
            popup_html = (
                f"<b>{vehicle} - Stop #{step_num} (Node {node_idx})</b><br>"
                f"Road: {stops_df.loc[node_idx, 'road_type']} ({stops_df.loc[node_idx, 'zone_type']})<br>"
                f"Traffic: {stops_df.loc[node_idx, 'traffic_level']} | Weather: {stops_df.loc[node_idx, 'weather_type']}"
            )
            folium.CircleMarker(
                location=[lat, lon],
                radius=7,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{vehicle} | Stop #{step_num} (Node {node_idx})"
            ).add_to(m)

    # Draw polyline connecting the truck's sequence
    folium.PolyLine(
        locations=path_coords,
        color=color,
        weight=4,
        opacity=0.8,
        tooltip=f"{vehicle}: {row['stops_visited']} stops | {row['distance_km']} km | {row['travel_time_min']} min"
    ).add_to(m)

# Add a clean legend box in the bottom-left corner
legend_html = """
<div style="position: fixed; bottom: 30px; left: 30px; width: 230px; z-index:9999;
            background-color: white; border: 2px solid #cbd5e1; border-radius: 8px;
            padding: 12px; font-family: Arial, sans-serif; font-size: 13px; box-shadow: 0 2px 6px rgba(0,0,0,0.15);">
  <b>Optimized Fleet Routes (VRP)</b><br><br>
  <span style="color: black;">&#9632;</span> <b>Depot</b> (Start / Return)<br>
  <span style="color: #2563EB;">&#9679;</span> <b>Truck 1</b> (10 stops | 412.5 min)<br>
  <span style="color: #16A34A;">&#9679;</span> <b>Truck 2</b> (5 stops | 300.9 min)<br>
  <span style="color: #DC2626;">&#9679;</span> <b>Truck 3</b> (10 stops | 471.3 min)
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

output_file = "assets/dispatch_routes_map.html"
m.save(output_file)
print(f"Interactive map saved to {output_file}!")


