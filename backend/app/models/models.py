from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime
import enum


class RiskTier(str, enum.Enum):
    """Risk tiers as per MamaGuard scoring"""
    LOW = "low"
    WATCH = "watch"
    URGENT = "urgent"


class User(Base):
    """Mother profile"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=False)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    
    # Clinical history
    gestational_history = Column(JSON, nullable=True, comment="e.g., {'previous_preeclampsia': false, 'prior_csection': true}")
    known_risk_factors = Column(JSON, nullable=True, comment="e.g., {'hypertension': false, 'diabetes': true}")
    
    # Emergency contact
    emergency_contact_name = Column(String, nullable=True)
    emergency_contact_phone = Column(String, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    scan_sessions = relationship("ScanSession", back_populates="user", cascade="all, delete-orphan")


class ScanSession(Base):
    """A single rPPG + checklist scan session"""
    __tablename__ = "scan_sessions"

    id = Column(String, primary_key=True, index=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # rPPG vitals (Layer 1)
    heart_rate = Column(Float, nullable=True)
    hrv = Column(Float, nullable=True, comment="Heart rate variability")
    
    # Risk scoring (Layer 2 + 3)
    risk_score = Column(Float, nullable=True, comment="0-100 risk score")
    risk_tier = Column(Enum(RiskTier), nullable=True)
    
    # Escalation data (Layer 3)
    gps_latitude = Column(Float, nullable=True, comment="Captured on Urgent tier")
    gps_longitude = Column(Float, nullable=True, comment="Captured on Urgent tier")
    
    # Processing metadata
    total_frames = Column(Integer, default=0)
    status = Column(String, default="processing")  # processing, completed, error
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="scan_sessions")
    checklist_response = relationship("ChecklistResponse", back_populates="scan_session", uselist=False, cascade="all, delete-orphan")
    risk_audit_log = relationship("RiskAuditLog", back_populates="scan_session", cascade="all, delete-orphan")


class ChecklistResponse(Base):
    """Mother's responses to WHO-aligned danger sign checklist"""
    __tablename__ = "checklist_responses"

    id = Column(Integer, primary_key=True, index=True)
    scan_session_id = Column(String, ForeignKey("scan_sessions.id"), nullable=False, unique=True)
    
    # WHO-aligned danger signs (Layer 2)
    severe_headache = Column(Boolean, default=False, comment="Severe headache")
    blurred_vision = Column(Boolean, default=False, comment="Blurred or flashing vision")
    abdominal_pain = Column(Boolean, default=False, comment="Upper abdominal pain")
    sudden_swelling = Column(Boolean, default=False, comment="Sudden swelling")
    shortness_of_breath = Column(Boolean, default=False, comment="Shortness of breath")
    
    # Count of yes responses
    danger_sign_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    scan_session = relationship("ScanSession", back_populates="checklist_response")


class RiskAuditLog(Base):
    """Transparent audit trail of risk scoring logic"""
    __tablename__ = "risk_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    scan_session_id = Column(String, ForeignKey("scan_sessions.id"), nullable=False, index=True)
    
    # Scoring details for transparency
    risk_tier = Column(Enum(RiskTier), nullable=False)
    risk_score = Column(Float, nullable=False)
    
    # Rules applied (JSON for explainability)
    rules_applied = Column(JSON, nullable=True, comment="e.g., {'hrv_abnormal': true, 'danger_signs': 2}")
    
    # Additional context
    notes = Column(String, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    scan_session = relationship("ScanSession", back_populates="risk_audit_log")
