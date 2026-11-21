import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

con = duckdb.connect("data/logistics.duckdb")

print("Loading 250,000 verified shipments for ML training...")
df = con.execute("""
    SELECT
        distance_km,
        num_lanes,
        num_signals,
        trip_hour,
        temperature_c,
        visibility_km,
        road_type,
        zone_type,
        traffic_level,
        weather_type,
        travel_time_min
    FROM vw_master_shipments
    WHERE traffic_level <> 'unknown'
    USING SAMPLE 250000
""").df()

feature_cols = [
    "distance_km", "num_lanes", "num_signals", "trip_hour",
    "temperature_c", "visibility_km",
    "road_type", "zone_type", "traffic_level", "weather_type"
]
cat_cols = ["road_type", "zone_type", "traffic_level", "weather_type"]

X = df[feature_cols]
y = df["travel_time_min"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

preprocessor = ColumnTransformer(
    transformers=[
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), cat_cols)
    ],
    remainder="passthrough"
)

model = Pipeline([
    ("prep", preprocessor),
    ("reg", HistGradientBoostingRegressor(max_iter=150, learning_rate=0.08, random_state=42))
])

print("Training Gradient Boosting Travel-Time Model...")
model.fit(X_train, y_train)

preds = model.predict(X_test)
mae = mean_absolute_error(y_test, preds)
r2 = r2_score(y_test, preds)

print("\n--- ML TRAVEL-TIME MODEL EVALUATION ---")
print(f"R2 Score (Variance Explained): {r2:.4f}")
print(f"Mean Absolute Error (MAE)    : {mae:.2f} minutes")

joblib.dump(model, "src/travel_time_model.pkl")
print("Saved trained model to src/travel_time_model.pkl")
