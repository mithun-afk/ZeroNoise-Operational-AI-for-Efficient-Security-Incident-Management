# AI SOC Triage Engine — Smart Alert Categorization & Analytics

[![Platform](https://img.shields.io/badge/Platform-Python%203.8%2B-blue.svg)]()
[![Framework](https://img.shields.io/badge/API-Flask-black.svg)]()
[![Dashboard](https://img.shields.io/badge/Dashboard-Streamlit-red.svg)]()
[![ML Model](https://img.shields.io/badge/Model-XGBoost-orange.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-lightgrey.svg)]()

**AI SOC Triage Engine** is an intelligent cybersecurity triage application engineered to reduce Security Operations Center (SOC) alert fatigue. It fuses an **XGBoost machine learning model** with historical telemetry tracking to automatically classify and grade incoming security incidents.

It solves digital alert chaos by processing incident categories, MITRE ATT&CK techniques, and historical false positive rates in real-time, allowing security teams to focus on actual threats while automatically archiving benign alerts.

---

## Key Features

| Feature | Description |
| :--- | :--- |
| **🧠 ML-Powered Threat Triage** | Balanced XGBoost classifier determining if an alert is a True Positive, False Positive, or needs Manual Review. |
| **📉 Automated FP Reduction** | Computes and utilizes historical False Positive rates per Detector ID to intelligently adjust confidence. |
| **⚡ Live REST API** | Flask-based endpoint (`/api/predict`) delivering real-time inference for live SOC queues. |
| **📊 Analytics Dashboard** | Interactive Streamlit dashboard for filtering alerts, tracking daily trends, and analyzing incident grade distributions. |
| **⚖️ Class Imbalance Handling** | Native `compute_sample_weight` integration during training to correct benign-only bias in security datasets. |
| **✨ Intuitive Web UI** | Flask-served HTML interface with color-coded threat statuses (Auto-Archived, Threat Detected). |

### Visual Showcase (Placeholders)

| Live SOC Triage Console | Telemetry Dashboard | Alert Trend Analytics |
| :---: | :---: | :---: |
| <img src="screenshots/console.jpeg" width="260" alt="Live Console" /> | <img src="screenshots/dashboard.jpeg" width="260" alt="Streamlit Dashboard" /> | <img src="screenshots/analytics.jpeg" width="260" alt="Trend Analytics" /> |
| **Real-time Alert Processing & Inference** | **Interactive Streamlit Metrics** | **Daily Incident Trends & Distributions** |

---

## Architecture Overview

The system is built on a clean separation between the offline training pipeline, the real-time inference API, and the analytics presentation layer.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                             PRESENTATION LAYER                              │
│       Streamlit Dashboard (dashboard.py) • Web Console (index.html)         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ REST / HTTP
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                                 API LAYER                                   │
│    Flask App (app.py) • /api/predict • Label Encoders (scikit-learn)        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Features (Numpy)
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                              INFERENCE LAYER                                │
│       XGBoost Multi-class Model (triage_xgboost_model.pkl)                  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
┌──────────────────────────────────────┐    ┌──────────────────────────────────┐
│          DATA & TELEMETRY LAYER      │    │        TRAINING PIPELINE         │
│  • detector_historical_stats.csv     │    │  • train.py                      │
│  • GUIDE_Test.csv (Telemetry Data)   │    │  • Stratified Splits & Weighting │
└──────────────────────────────────────┘    └──────────────────────────────────┘
```

### System Processing Pipeline

```text
[ New Security Alert Received ]
           │
           ▼
[ Flask API (/api/predict) ] ───► Extracts Category & MITRE Technique
           │
           ▼
[ Historical Telemetry ] ───────► Looks up Historical FP Rate by Detector ID
           │
           ▼
[ Feature Encoding ] ───────────► Scikit-learn LabelEncoders (le_cat, le_mitre)
           │
           ▼
[ XGBoost Classifier ] ─────────► Outputs Class Probabilities
           │
           ▼
[ Decision Logic Engine ]
   ├─► Confidence > 0.70 & FP ──────► [ Auto-Archived (Green) ]
   ├─► Confidence > 0.60 & TP ──────► [ THREAT DETECTED (Red) ]
   └─► Otherwise ───────────────────► [ Manual Review (Orange) ]
```

---

## Project Structure

```text
projectvac/
├── app.py                            # Flask REST API & Live Inference Server
├── dashboard.py                      # Streamlit SOC Analytics Interface
├── train.py                          # ML Pipeline & XGBoost Training Script
├── templates/
│   └── index.html                    # Frontend SOC Triage Web UI
├── static/                           # Web assets
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
Start the Flask application to serve the model for predictions:
```bash
python app.py
```
*The API will be available at `http://localhost:5000` with the web console at the root URL.*

### 3. Analytics Dashboard
Launch the Streamlit analytics interface to visualize alert metrics:
```bash
streamlit run dashboard.py
```

---

## License

Copyright 2026. Licensed under the [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0).
