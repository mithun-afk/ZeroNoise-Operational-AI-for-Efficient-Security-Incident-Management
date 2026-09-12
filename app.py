# app.py
from flask import Flask, render_template, request, jsonify, Response
import pandas as pd
import joblib
import numpy as np
import time
import random
import json
import csv
from datetime import datetime
import os

app = Flask(__name__)

model = joblib.load("triage_xgboost_model.pkl")
detector_stats = pd.read_csv("detector_historical_stats.csv").set_index("DetectorId")
le_cat = joblib.load("le_cat.pkl")
le_mitre = joblib.load("le_mitre.pkl")
le_target = joblib.load("le_target.pkl")

# Load sample data for simulation
print("Loading telemetry data pool...")
df_pool = pd.read_csv("GUIDE_Test.csv", nrows=5000)
# Fill NaNs with a string "None" to avoid JSON serialization issues
df_pool = df_pool.fillna("None")
print("Pool loaded.")

STREAMING = False

@app.route('/')
def live_queue_page():
    return render_template('index.html')

@app.route('/api/predict', methods=['POST'])
def run_triage_inference():
    data = request.json
    detector_id = int(data.get("DetectorId", 0))
    category_str = str(data.get("Category", "Other"))
    mitre_str = str(data.get("MitreTechniques", "None"))

    hist_fp_rate = 0.5
    if detector_id in detector_stats.index:
        hist_fp_rate = float(detector_stats.loc[detector_id, 'historical_fp_rate'])

    try:
        cat_encoded = le_cat.transform([category_str])[0]
    except ValueError:
        cat_encoded = 0
        
    try:
        mitre_encoded = le_mitre.transform([mitre_str])[0]
    except ValueError:
        mitre_encoded = 0

    features = np.array([[cat_encoded, mitre_encoded, hist_fp_rate]])
    probabilities = model.predict_proba(features)[0]
    pred_idx = np.argmax(probabilities)
    
    predicted_grade = le_target.inverse_transform([pred_idx])[0]
    confidence = float(probabilities[pred_idx])

    if predicted_grade == 'FalsePositive' and confidence > 0.70:
        status = "Auto-Archived"
        color = "green"
    elif predicted_grade == 'TruePositive' and confidence > 0.60:
        status = "THREAT DETECTED"
        color = "red"
    else:
        status = f"Manual Review ({confidence:.1%})"
        color = "orange"

    return jsonify({
        "Predicted_Grade": predicted_grade,
        "Confidence_Score": confidence,
        "Historical_FP_Rate": hist_fp_rate,
        "status": status,
        "color": color
    })

@app.route('/api/toggle_stream', methods=['POST'])
def toggle_stream():
    global STREAMING
    data = request.json
    STREAMING = data.get('streaming', False)
    return jsonify({"status": "ok", "streaming": STREAMING})

@app.route('/api/stream')
def stream():
    def event_generator():
        global STREAMING
        while True:
            if STREAMING:
                # Pick a random row
                row = df_pool.sample(1).iloc[0].to_dict()
                
                # Predict
                detector_id = row.get("DetectorId", 0)
                detector_id = int(detector_id) if detector_id != "None" else 0
                
                category_str = str(row.get("Category", "Other"))
                mitre_str = str(row.get("MitreTechniques", "None"))
                
                hist_fp_rate = 0.5
                if detector_id in detector_stats.index:
                    hist_fp_rate = float(detector_stats.loc[detector_id, 'historical_fp_rate'])
                    
                try:
                    cat_encoded = le_cat.transform([category_str])[0]
                except ValueError:
                    cat_encoded = 0
                try:
                    mitre_encoded = le_mitre.transform([mitre_str])[0]
                except ValueError:
                    mitre_encoded = 0
                    
                features = np.array([[cat_encoded, mitre_encoded, hist_fp_rate]])
                probs = model.predict_proba(features)[0]
                pred_idx = np.argmax(probs)
                
                confidence = float(probs[pred_idx])
                label = le_target.inverse_transform([pred_idx])[0]
                
                if label == 'FalsePositive' and confidence > 0.70:
                    status = "Auto-Archived"
                    color = "green"
                elif label == 'TruePositive' and confidence > 0.60:
                    status = "THREAT DETECTED"
                    color = "red"
                else:
                    status = f"Manual Review ({confidence:.1%})"
                    color = "orange"
                    
                # Update row with fresh timestamp and predicted label
                row["Timestamp"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
                row["IncidentGrade"] = label
                
                # Convert back to list for CSV appending
                try:
                    with open('live_alerts.csv', 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(list(row.values()))
                except Exception as e:
                    print(f"Error writing to live_alerts.csv: {e}")
                    
                # Yield to frontend
                event_data = {
                    "alertId": str(row.get("AlertId", "UNKNOWN")),
                    "detectorId": str(detector_id),
                    "category": category_str,
                    "mitre": mitre_str,
                    "status": status,
                    "color": color,
                    "confidence": confidence
                }
                
                yield f"data: {json.dumps(event_data)}\n\n"
                
                time.sleep(random.uniform(1.0, 3.0)) # Random interval
            else:
                time.sleep(1.0)
    return Response(event_generator(), mimetype="text/event-stream")

if __name__ == '__main__':
    # Use threaded=True to support SSE
    app.run(port=5000, debug=True, use_reloader=False, threaded=True)