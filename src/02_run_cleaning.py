import duckdb
import time

start = time.time()
con = duckdb.connect("data/logistics.duckdb")

with open("sql/01_clean_data.sql", "r") as f:
    sql_script = f.read()

print("Running SQL cleaning pipeline on 2M+ rows...")
con.execute(sql_script)

tables = ["clean_roads", "clean_traffic", "clean_weather", "clean_trips"]
print("\n--- CLEAN DATABASE SUMMARY ---")
for t in tables:
    cnt = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"{t:<15}: {cnt:,} clean rows")

print(f"\nCompleted in {time.time() - start:.2f} seconds! Saved to data/logistics.duckdb")
