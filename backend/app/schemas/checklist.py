from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.core.risk_scoring import RiskTier


class ChecklistRequestBase(BaseModel):
    severe_headache: bool = Field(default=False, description="Severe headache")
    blurred_vision: bool = Field(default=False, description="Blurred or flashing vision")
    abdominal_pain: bool = Field(default=False, description="Upper abdominal pain")
    sudden_swelling: bool = Field(default=False, description="Sudden swelling")
    shortness_of_breath: bool = Field(default=False, description="Shortness of breath")


class ChecklistSubmitRequest(ChecklistRequestBase):
    """Submit checklist responses for a scan session"""
    pass


class ChecklistResponse(ChecklistRequestBase):
    id: int
    scan_session_id: str
    danger_sign_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class RiskScoreResponse(BaseModel):
    """Risk assessment result"""
    session_id: str
    risk_tier: RiskTier
    risk_score: float = Field(description="0-100 risk score")
    heart_rate: Optional[float] = None
    hrv: Optional[float] = None
    danger_signs_count: int
    rules_applied: dict = Field(description="Transparent explanation of scoring")
    recommendation: str = Field(description="Actionable guidance based on risk tier")
    created_at: datetime


class ScanSummaryResponse(BaseModel):
    """Complete scan session summary"""
    session_id: str
    total_frames: int
    heart_rate: Optional[float]
    hrv: Optional[float]
    risk_tier: RiskTier
    risk_score: float
    checklist: Optional[ChecklistResponse]
    recommendation: str
    duration_seconds: float
    created_at: datetime
