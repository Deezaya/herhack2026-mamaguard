from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.routers.auth import get_current_user_dependency
from app.models.models import User, ScanSession, ChecklistResponse, RiskAuditLog, RiskTier
from app.schemas.checklist import ChecklistSubmitRequest, ChecklistResponse as ChecklistResponseSchema, RiskScoreResponse, ScanSummaryResponse
from app.core.risk_scoring import RiskScoringEngine, get_risk_recommendation
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.post("/{session_id}/checklist")
async def submit_checklist(
    session_id: str,
    checklist: ChecklistSubmitRequest,
    current_user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Submit danger sign checklist for a scan session.
    
    This combines with Layer 1 (rPPG vitals) to calculate risk tier.
    """
    # Verify session belongs to current user
    scan_session = db.query(ScanSession).filter(
        ScanSession.id == session_id,
        ScanSession.user_id == current_user.id
    ).first()
    
    if not scan_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan session not found"
        )
    
    # Check if session is still active
    if scan_session.status != "processing":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only submit checklist for active sessions"
        )
    
    try:
        # Count danger signs
        danger_sign_count = sum([
            checklist.severe_headache,
            checklist.blurred_vision,
            checklist.abdominal_pain,
            checklist.sudden_swelling,
            checklist.shortness_of_breath,
        ])
        
        # Save checklist response
        db_checklist = ChecklistResponse(
            scan_session_id=session_id,
            severe_headache=checklist.severe_headache,
            blurred_vision=checklist.blurred_vision,
            abdominal_pain=checklist.abdominal_pain,
            sudden_swelling=checklist.sudden_swelling,
            shortness_of_breath=checklist.shortness_of_breath,
            danger_sign_count=danger_sign_count,
        )
        
        db.add(db_checklist)
        
        # Calculate risk score (Layer 1 + Layer 2)
        risk_tier, risk_score, rules_applied = RiskScoringEngine.score(
            heart_rate=scan_session.heart_rate,
            hrv=scan_session.hrv,
            danger_sign_count=danger_sign_count,
            known_risk_factors=current_user.known_risk_factors
        )
        
        # Update scan session with risk tier
        scan_session.risk_tier = risk_tier
        scan_session.risk_score = risk_score
        scan_session.status = "completed"
        scan_session.ended_at = datetime.utcnow()
        
        # Save audit log for transparency
        db_audit = RiskAuditLog(
            scan_session_id=session_id,
            risk_tier=risk_tier,
            risk_score=risk_score,
            rules_applied=rules_applied,
            notes=f"Danger signs: {danger_sign_count}. HR: {scan_session.heart_rate}. HRV: {scan_session.hrv}"
        )
        
        db.add(db_audit)
        db.commit()
        
        logger.info(
            f"Checklist submitted for session {session_id}: "
            f"risk_tier={risk_tier}, risk_score={risk_score:.1f}, danger_signs={danger_sign_count}"
        )
        
        return {
            "session_id": session_id,
            "danger_sign_count": danger_sign_count,
            "risk_tier": risk_tier,
            "risk_score": risk_score,
            "message": "Checklist submitted. Risk score calculated."
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error submitting checklist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process checklist"
        )


@router.get("/{session_id}/risk-score", response_model=RiskScoreResponse)
async def get_risk_score(
    session_id: str,
    current_user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Get risk assessment for a completed scan session.
    
    Includes transparent rules showing why the risk tier was assigned.
    """
    # Verify session belongs to current user
    scan_session = db.query(ScanSession).filter(
        ScanSession.id == session_id,
        ScanSession.user_id == current_user.id
    ).first()
    
    if not scan_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan session not found"
        )
    
    if scan_session.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Risk score only available for completed sessions"
        )
    
    # Get audit log for transparency
    audit = db.query(RiskAuditLog).filter(
        RiskAuditLog.scan_session_id == session_id
    ).first()
    
    checklist = db.query(ChecklistResponse).filter(
        ChecklistResponse.scan_session_id == session_id
    ).first()
    
    return RiskScoreResponse(
        session_id=session_id,
        risk_tier=scan_session.risk_tier,
        risk_score=scan_session.risk_score,
        heart_rate=scan_session.heart_rate,
        hrv=scan_session.hrv,
        danger_signs_count=checklist.danger_sign_count if checklist else 0,
        rules_applied=audit.rules_applied if audit else {},
        recommendation=get_risk_recommendation(scan_session.risk_tier),
        created_at=scan_session.ended_at
    )


@router.get("/{session_id}/summary", response_model=ScanSummaryResponse)
async def get_scan_summary(
    session_id: str,
    current_user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Get complete scan session summary with all results.
    """
    scan_session = db.query(ScanSession).filter(
        ScanSession.id == session_id,
        ScanSession.user_id == current_user.id
    ).first()
    
    if not scan_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan session not found"
        )
    
    checklist = db.query(ChecklistResponse).filter(
        ChecklistResponse.scan_session_id == session_id
    ).first()
    
    duration = (scan_session.ended_at - scan_session.started_at).total_seconds() if scan_session.ended_at else 0
    
    return ScanSummaryResponse(
        session_id=session_id,
        total_frames=scan_session.total_frames,
        heart_rate=scan_session.heart_rate,
        hrv=scan_session.hrv,
        risk_tier=scan_session.risk_tier,
        risk_score=scan_session.risk_score,
        checklist=ChecklistResponseSchema.from_orm(checklist) if checklist else None,
        recommendation=get_risk_recommendation(scan_session.risk_tier),
        duration_seconds=duration,
        created_at=scan_session.ended_at
    )
