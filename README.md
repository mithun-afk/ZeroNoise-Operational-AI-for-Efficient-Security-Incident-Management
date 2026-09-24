# ZeroNoise: Operational AI for Efficient Security Incident Management

[![Platform](https://img.shields.io/badge/Platform-Python%203.8%2B-blue.svg)]()
[![Framework](https://img.shields.io/badge/API-FastAPI-black.svg)]()
[![Dashboard](https://img.shields.io/badge/Dashboard-Streamlit-red.svg)]()
[![ML Model](https://img.shields.io/badge/Model-XGBoost-orange.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-lightgrey.svg)]()

**ZeroNoise** is an intelligent cybersecurity triage application engineered to reduce Security Operations Center (SOC) alert fatigue. It fuses an **XGBoost machine learning model** with historical telemetry tracking to automatically classify and grade incoming security incidents.

It solves digital alert chaos by processing incident categories, MITRE ATT&CK techniques, and historical false positive rates in real-time, allowing security teams to focus on actual threats while automatically archiving benign alerts.

---

## Key Features

| Feature | Description |
| :--- | :--- |
| **🧠 ML-Powered Threat Triage** | Balanced XGBoost classifier determining if an alert is a True Positive, False Positive, or needs Manual Review. |
| **📉 Automated FP Reduction** | Computes and utilizes historical False Positive rates per Detector ID to intelligently adjust confidence. |
| **⚡ Live REST API** | FastAPI endpoint (`/api/ingest`) delivering real-time inference for live SOC queues using Common Alert Schema. |
| **📊 Analytics Dashboard** | Interactive Streamlit dashboard for filtering alerts, tracking daily trends, and analyzing incident grade distributions. |
| **⚖️ Class Imbalance Handling** | Native `compute_sample_weight` integration during training to correct benign-only bias in security datasets. |
| **✨ Intuitive Web UI** | Dark theme SOC Workspace interface with Incident Grouping and MITRE Attack Graphs. |

---

## Project Structure

```text
projectvac/
├── app.py                            # FastAPI REST API & Live Inference Server
├── dashboard.py                      # Streamlit Enterprise SOC UI
├── train.py                          # ML Pipeline (Optuna) & XGBoost Training Script
├── database.py                       # SQLAlchemy SQLite Database Engine
├── requirements.txt                  # Python dependencies
├── le_*.pkl                          # Label Encoders (Category, MITRE, Target)
├── triage_xgboost_model.pkl          # Serialized XGBoost Model Weights
├── detector_historical_stats.csv     # Pre-computed temporal detector metrics
├── GUIDE_Test.csv                    # Raw Telemetry Dataset
└── README.md                         # Project documentation
```

---

## Setup & Execution

### 1. Model Training
To train the XGBoost model and generate the required LabelEncoders and historical stats from your telemetry data:
```bash
python train.py
```
*Note: This will process `GUIDE_Test.csv`, compute historical False Positive rates, balance class weights, and export `.pkl` files.*

### 2. Live Inference API
Start the FastAPI application to serve the model for predictions:
```bash
python app.py
```
*The API will be available at `http://localhost:5053`.*

### 3. Analytics Dashboard
Launch the Streamlit analytics interface to visualize alert metrics:
```bash
streamlit run dashboard.py
```

---

## License

Copyright 2026. Licensed under the [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0).
