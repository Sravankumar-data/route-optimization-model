import duckdb

con = duckdb.connect("data/logistics.duckdb")

with open("sql/02_corridor_analysis.sql", "r") as f:
    raw_sql = f.read()

# Split individual SQL statements cleanly
statements = [s.strip() for s in raw_sql.split(";") if s.strip()]

# 1. Create the master view
con.execute(statements[0])
print("Master view 'vw_master_shipments' created successfully!\n")

# 2. Run Query 1: Top Inefficient Corridors
print("=" * 75)
print("REPORT 1: TOP 10 HIGH-CONGESTION / INEFFICIENT CORRIDORS")
print("=" * 75)
df_corridors = con.execute(statements[1]).df()
print(df_corridors.to_string(index=False))
df_corridors.to_csv("data/report_inefficient_corridors.csv", index=False)

# 3. Run Query 2: Peak Hour Bottlenecks
print("\n" + "=" * 75)
print("REPORT 2: TOP 10 WORST RUSH-HOUR WINDOWS (HIGHEST MIN/KM)")
print("=" * 75)
df_hours = con.execute(statements[2]).df()
print(df_hours.to_string(index=False))
df_hours.to_csv("data/report_hourly_congestion.csv", index=False)

# 4. Run Query 3: Weather & Traffic Impact
print("\n" + "=" * 75)
print("REPORT 3: WEATHER & TRAFFIC CONGESTION IMPACT")
print("=" * 75)
df_weather = con.execute(statements[3]).df()
print(df_weather.to_string(index=False))
df_weather.to_csv("data/report_weather_traffic.csv", index=False)
