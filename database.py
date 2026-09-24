import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./zeronoise.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Incident(Base):
    __tablename__ = "incidents"
    
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String, index=True, unique=True)
    title = Column(String)
    status = Column(String, default="OPEN")       # OPEN, CLOSED
    severity = Column(String)                     # Critical, High, Medium, Low
    risk_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    alerts = relationship("Alert", back_populates="incident")

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, index=True, unique=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    source = Column(String, index=True)
    detector_id = Column(String, index=True)
    category = Column(String, index=True)
    severity = Column(String)
    mitre_techniques = Column(String)
    
    device_id = Column(String, index=True)
    user = Column(String, index=True)
    source_ip = Column(String)
    destination_ip = Column(String)
    asset_criticality = Column(String)
    
    raw_message = Column(Text)
    
    incident_grade = Column(String, index=True)
    risk_score = Column(Float, index=True)
    confidence = Column(Float)
    action = Column(String)
    
    # Analyst Feedback Fields
    status = Column(String, default="OPEN")       # OPEN, CONFIRMED, FALSE_POSITIVE, SUPPRESSED
    analyst_note = Column(Text)
    
    # Incident Grouping
    incident_id = Column(String, ForeignKey("incidents.incident_id"), nullable=True, index=True)
    incident = relationship("Incident", back_populates="alerts")

def init_db():
    Base.metadata.create_all(bind=engine)
