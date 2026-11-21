import duckdb

con = duckdb.connect()

files = ["roads.csv", "traffic.csv", "trips.csv", "weather.csv"]

for f in files:
    print("=" * 60)
    print(f"FILE: {f}")
    count = con.execute(f"SELECT COUNT(*) FROM 'data/{f}'").fetchone()[0]
    print(f"Total Rows: {count:,}")
    df = con.execute(f"SELECT * FROM 'data/{f}' LIMIT 3").df()
    print("\nColumns & Sample Rows:")
    print(df.to_string())
    print("\nNull Counts:")
    nulls = con.execute(f"""
        SELECT COLUMNS(*) IS NULL FROM 'data/{f}'
    """).df().sum()
    print(nulls[nulls > 0].to_string())
