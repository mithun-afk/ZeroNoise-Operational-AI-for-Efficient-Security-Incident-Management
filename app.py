import logging
import json
import asyncio
import uuid
from datetime import datetime, timedelta
import pandas as pd
import joblib
import numpy as np
import shap

from fastapi import FastAPI, Depends, Request
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from database import SessionLocal, init_db, Alert, Incident, engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Drop and recreate for schema changes
import database
# database.Base.metadata.drop_all(bind=engine)  # don't drop to keep P1 data
init_db()

app = FastAPI(title="ZeroNoise Enterprise API")

try:
    model = joblib.load("triage_xgboost_model.pkl")
    detector_stats = pd.read_csv("detector_historical_stats.csv").set_index("DetectorId")
    le_cat = joblib.load("le_cat.pkl")
    le_mitre = joblib.load("le_mitre.pkl")
    le_target = joblib.load("le_target.pkl")
    
    # Initialize SHAP Explainer
    explainer = shap.TreeExplainer(model)
except Exception as e:
    logger.error(f"ML init error: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class IngestAlertSchema(BaseModel):
    event_id: str
    timestamp: str
    source: str
    detector_id: str
    category: str
    severity: str
    mitre_techniques: List[str] = []
    device_id: Optional[str] = None
    user: Optional[str] = None
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    asset_criticality: Optional[str] = "Normal"
    raw_message: Optional[str] = None

class FeedbackSchema(BaseModel):
    status: str
    note: Optional[str] = None

def calculate_risk(detector_id: str, category_str: str, mitre_techniques: List[str]):
    mitre_str = mitre_techniques[0] if mitre_techniques else "None"
    try:
        det_id_int = int(detector_id)
    except ValueError:
        det_id_int = 0

    hist_fp_rate = 0.5
    if det_id_int in detector_stats.index:
        hist_fp_rate = float(detector_stats.loc[det_id_int, 'historical_fp_rate'])

    try:
        cat_encoded = le_cat.transform([category_str])[0] if category_str in le_cat.classes_ else -1
    except ValueError:
        cat_encoded = -1
        
    try:
        mitre_encoded = le_mitre.transform([mitre_str])[0] if mitre_str in le_mitre.classes_ else -1
    except ValueError:
        mitre_encoded = -1

    features = np.array([[cat_encoded, mitre_encoded, hist_fp_rate]])
    probs = model.predict_proba(features)[0]
    pred_idx = np.argmax(probs)
    
    predicted_grade = le_target.inverse_transform([pred_idx])[0]
    confidence = float(probs[pred_idx])
    
    # Calculate SHAP values
    shap_vals = explainer.shap_values(features)
    # shap_vals is a list of arrays if multi-class, or one array.
    if isinstance(shap_vals, list):
        target_shap = shap_vals[pred_idx][0]
    else:
        target_shap = shap_vals[0]
        
    shap_explanation = {
        "Category": float(target_shap[0]),
        "MitreTechniques": float(target_shap[1]),
        "Historical FPR": float(target_shap[2])
    }

    if predicted_grade == 'TruePositive':
        risk_score = 60 + (confidence * 40)
    elif predicted_grade == 'FalsePositive':
        risk_score = 40 - (confidence * 40)
    else:
        risk_score = 40 + (confidence * 20)

    if risk_score >= 80:
        action = "ESCALATE"
    elif risk_score >= 60:
        action = "INVESTIGATE"
    elif risk_score >= 30:
        action = "REVIEW"
    else:
        action = "SUPPRESS"

    return predicted_grade, confidence, risk_score, action, shap_explanation

def group_into_incident(db: Session, alert: Alert):
    """
    Groups an alert into an existing incident based on User or Device within the last 2 hours.
    Otherwise creates a new incident if Risk Score >= 60.
    """
    time_window = datetime.utcnow() - timedelta(hours=2)
    
    # Try to find a recent open incident for the same asset or user
    existing_incident = db.query(Incident).join(Alert).filter(
        Incident.status == "OPEN",
        Alert.timestamp >= time_window,
        ((Alert.device_id == alert.device_id) & (alert.device_id != "Unknown")) |
        ((Alert.user == alert.user) & (alert.user != "Unknown"))
    ).first()

    if existing_incident:
        alert.incident_id = existing_incident.incident_id
        # Update incident risk score if this alert is higher
        if alert.risk_score > existing_incident.risk_score:
            existing_incident.risk_score = alert.risk_score
            existing_incident.severity = alert.severity
        existing_incident.updated_at = datetime.utcnow()
    elif alert.risk_score >= 60:
        # Create new incident
        inc_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        new_inc = Incident(
            incident_id=inc_id,
            title=f"Suspicious Activity: {alert.category}",
            status="OPEN",
            severity=alert.severity,
            risk_score=alert.risk_score
        )
        db.add(new_inc)
        alert.incident_id = inc_id

@app.post("/api/ingest")
async def ingest_alert(alert_in: IngestAlertSchema, db: Session = Depends(get_db)):
    grade, conf, risk, action, shap_exp = calculate_risk(
        alert_in.detector_id, alert_in.category, alert_in.mitre_techniques
    )
    
    raw = alert_in.model_dump()
    raw["shap_explanation"] = shap_exp
    
    new_alert = Alert(
        event_id=alert_in.event_id,
        timestamp=datetime.fromisoformat(alert_in.timestamp.replace("Z", "+00:00")) if "T" in alert_in.timestamp else datetime.utcnow(),
        source=alert_in.source,
        detector_id=alert_in.detector_id,
        category=alert_in.category,
        severity=alert_in.severity,
        mitre_techniques=",".join(alert_in.mitre_techniques),
        device_id=alert_in.device_id,
        user=alert_in.user,
        source_ip=alert_in.source_ip,
        destination_ip=alert_in.destination_ip,
        asset_criticality=alert_in.asset_criticality,
        raw_message=json.dumps(raw),
        incident_grade=grade,
        risk_score=risk,
        confidence=conf,
        action=action,
        status="OPEN"
    )
    
    # Run P1 Incident Grouping
    group_into_incident(db, new_alert)
    
    db.add(new_alert)
    db.commit()
    return {"status": "success", "event_id": alert_in.event_id}

@app.post("/api/alerts/{event_id}/feedback")
async def submit_feedback(event_id: str, feedback: FeedbackSchema, db: Session = Depends(get_db)):
    """
    P1: Analyst Feedback Loop
    """
    alert = db.query(Alert).filter(Alert.event_id == event_id).first()
    if alert:
        alert.status = feedback.status
        if feedback.note:
            alert.analyst_note = feedback.note
        db.commit()
        return {"status": "success", "event_id": event_id, "new_status": feedback.status}
    return {"status": "not_found"}

# --- Demo Generator ---
STREAMING = False

class ToggleRequest(BaseModel):
    streaming: bool

@app.post("/api/toggle_stream")
async def toggle_stream(req: ToggleRequest):
    global STREAMING
    STREAMING = req.streaming
    return {"status": "ok"}

try:
    df_pool = pd.read_csv("GUIDE_Test.csv", nrows=5000).fillna("None")
except Exception:
    df_pool = pd.DataFrame()

@app.get("/api/stream")
async def stream(request: Request, db: Session = Depends(get_db)):
    async def event_generator():
        global STREAMING
        while True:
            if await request.is_disconnected():
                break

            if STREAMING and not df_pool.empty:
                row = df_pool.sample(1).iloc[0].to_dict()
                mitre_str = str(row.get("MitreTechniques", "None"))
                
                # To demonstrate grouping, occasionally reuse a specific device
                device = "WIN-023" if np.random.rand() > 0.8 else str(row.get("DeviceId", "Unknown"))
                
                mock_payload = IngestAlertSchema(
                    event_id=f"evt-{uuid.uuid4().hex[:8]}",
                    timestamp=datetime.utcnow().isoformat(),
                    source="Microsoft Defender" if np.random.rand() > 0.3 else "Microsoft Sentinel",
                    detector_id=str(row.get("DetectorId", "0")),
                    category=str(row.get("Category", "Other")),
                    severity=np.random.choice(["Low", "Medium", "High", "Critical"], p=[0.5, 0.3, 0.15, 0.05]),
                    mitre_techniques=[mitre_str] if mitre_str != "None" else [],
                    device_id=device,
                    user=str(row.get("AccountName", "Unknown")),
                    asset_criticality=np.random.choice(["Normal", "High", "Critical"], p=[0.7, 0.2, 0.1]),
                )
                
                grade, conf, risk, action, shap_exp = calculate_risk(
                    mock_payload.detector_id, mock_payload.category, mock_payload.mitre_techniques
                )
                
                raw = mock_payload.model_dump()
                raw["shap_explanation"] = shap_exp
                
                new_alert = Alert(
                    event_id=mock_payload.event_id,
                    timestamp=datetime.utcnow(),
                    source=mock_payload.source,
                    detector_id=mock_payload.detector_id,
                    category=mock_payload.category,
                    severity=mock_payload.severity,
                    mitre_techniques=",".join(mock_payload.mitre_techniques),
                    device_id=mock_payload.device_id,
                    user=mock_payload.user,
                    asset_criticality=mock_payload.asset_criticality,
                    raw_message=json.dumps(raw),
                    incident_grade=grade,
                    risk_score=risk,
                    confidence=conf,
                    action=action,
                    status="OPEN"
                )
                
                try:
                    group_into_incident(db, new_alert)
                    db.add(new_alert)
                    db.commit()
                except Exception:
                    db.rollback()
                
                yield {"data": json.dumps({"event_id": mock_payload.event_id})}
                await asyncio.sleep(2.0)
            else:
                await asyncio.sleep(1.0)

    return EventSourceResponse(event_generator())

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5053)