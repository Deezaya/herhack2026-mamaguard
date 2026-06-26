"""
Risk Scoring Engine for MamaGuard

Transparent, rules-based scoring combining:
- Layer 1: rPPG vitals (heart rate, HRV)
- Layer 2: WHO-aligned danger signs checklist
- Output: Risk tier (Low / Watch / Urgent)

This is NOT a diagnostic tool. It's a decision-support aid.
"""
import logging
from enum import Enum
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class RiskTier(str, Enum):
    LOW = "low"
    WATCH = "watch"
    URGENT = "urgent"


class RiskScoringEngine:
    """
    Transparent rules-based risk scoring.
    Every decision is explainable and auditable.
    """
    
    # Vital sign thresholds (postpartum period)
    NORMAL_HR_MIN = 50
    NORMAL_HR_MAX = 100
    ELEVATED_HR_MIN = 101
    ELEVATED_HR_MAX = 120
    CRITICAL_HR_MIN = 121
    
    # HRV thresholds (indication of autonomic nervous system stress)
    NORMAL_HRV_MIN = 20  # ms
    LOW_HRV_THRESHOLD = 20  # ms (concerning in postpartum)
    
    # Danger sign scoring
    DANGER_SIGN_THRESHOLD_URGENT = 3  # 3+ danger signs = Urgent
    DANGER_SIGN_THRESHOLD_WATCH = 1   # 1+ danger signs = Watch (unless vitals are abnormal)
    
    @staticmethod
    def score(
        heart_rate: float = None,
        hrv: float = None,
        danger_sign_count: int = 0,
        known_risk_factors: dict = None
    ) -> Tuple[RiskTier, float, Dict]:
        """
        Score risk based on vitals and danger signs.
        
        Args:
            heart_rate: Heart rate in bpm
            hrv: Heart rate variability in ms
            danger_sign_count: Number of positive danger signs (0-5)
            known_risk_factors: Clinical history (e.g., prior hypertension)
        
        Returns:
            (risk_tier, risk_score_0_100, rules_applied)
        """
        risk_factors = known_risk_factors or {}
        rules_applied = {}
        vital_risk = 0
        danger_sign_risk = 0
        
        # ===== LAYER 1: VITAL SIGNS ANALYSIS =====
        
        # Heart rate assessment
        hr_assessment = RiskScoringEngine._assess_heart_rate(heart_rate)
        vital_risk += hr_assessment["risk_points"]
        rules_applied["hr_status"] = hr_assessment["status"]
        rules_applied["hr_assessment"] = hr_assessment
        
        # HRV assessment
        hrv_assessment = RiskScoringEngine._assess_hrv(hrv)
        vital_risk += hrv_assessment["risk_points"]
        rules_applied["hrv_status"] = hrv_assessment["status"]
        rules_applied["hrv_assessment"] = hrv_assessment
        
        # ===== LAYER 2: DANGER SIGNS ANALYSIS =====
        
        danger_sign_assessment = RiskScoringEngine._assess_danger_signs(danger_sign_count)
        danger_sign_risk = danger_sign_assessment["risk_points"]
        rules_applied["danger_signs_count"] = danger_sign_count
        rules_applied["danger_sign_assessment"] = danger_sign_assessment
        
        # ===== LAYER 3: COMBINED RISK =====
        
        # Prior risk factors (context modifier)
        context_multiplier = 1.0
        if risk_factors.get("prior_preeclampsia"):
            context_multiplier = 1.2
            rules_applied["prior_preeclampsia_modifier"] = 1.2
        
        # Total risk score (0-100)
        total_risk = (vital_risk + danger_sign_risk) * context_multiplier
        risk_score = min(100, total_risk)  # Cap at 100
        
        rules_applied["total_vital_risk_points"] = vital_risk
        rules_applied["total_danger_sign_risk_points"] = danger_sign_risk
        rules_applied["context_multiplier"] = context_multiplier
        rules_applied["final_risk_score"] = risk_score
        
        # ===== TIER DETERMINATION =====
        
        # URGENT: Any critical condition OR 3+ danger signs
        if (vital_risk >= 40) or (danger_sign_count >= RiskScoringEngine.DANGER_SIGN_THRESHOLD_URGENT):
            risk_tier = RiskTier.URGENT
            rules_applied["tier_reason"] = "Urgent due to critical vitals or multiple danger signs"
        
        # WATCH: Elevated vitals OR 1+ danger signs
        elif (vital_risk >= 20) or (danger_sign_count >= RiskScoringEngine.DANGER_SIGN_THRESHOLD_WATCH):
            risk_tier = RiskTier.WATCH
            rules_applied["tier_reason"] = "Watch tier due to elevated vitals or danger signs"
        
        # LOW: Normal vitals and no danger signs
        else:
            risk_tier = RiskTier.LOW
            rules_applied["tier_reason"] = "All vitals and danger signs within normal range"
        
        logger.info(
            f"Risk score calculated: {risk_score:.1f} → {risk_tier} "
            f"(HR={heart_rate}, HRV={hrv}, danger_signs={danger_sign_count})"
        )
        
        return risk_tier, risk_score, rules_applied
    
    @staticmethod
    def _assess_heart_rate(hr: float = None) -> Dict:
        """Assess heart rate in postpartum context"""
        if hr is None:
            return {
                "status": "unknown",
                "risk_points": 5,  # Small risk for missing data
                "message": "Heart rate not available"
            }
        
        # Postpartum context: slightly elevated HR is expected (physical stress, recovery)
        if RiskScoringEngine.NORMAL_HR_MIN <= hr <= RiskScoringEngine.NORMAL_HR_MAX:
            return {
                "status": "normal",
                "risk_points": 0,
                "message": f"Normal heart rate: {hr:.1f} bpm"
            }
        elif RiskScoringEngine.ELEVATED_HR_MIN <= hr <= RiskScoringEngine.ELEVATED_HR_MAX:
            return {
                "status": "elevated",
                "risk_points": 15,
                "message": f"Elevated heart rate: {hr:.1f} bpm (expected in postpartum, monitor)"
            }
        elif hr >= RiskScoringEngine.CRITICAL_HR_MIN:
            return {
                "status": "critical",
                "risk_points": 35,
                "message": f"Critical heart rate: {hr:.1f} bpm (potential tachycardia)"
            }
        else:  # HR < 50
            return {
                "status": "low",
                "risk_points": 25,
                "message": f"Low heart rate: {hr:.1f} bpm (potential bradycardia)"
            }
    
    @staticmethod
    def _assess_hrv(hrv: float = None) -> Dict:
        """Assess heart rate variability (autonomic stress indicator)"""
        if hrv is None:
            return {
                "status": "unknown",
                "risk_points": 0,
                "message": "HRV not available"
            }
        
        # Low HRV suggests autonomic nervous system stress
        if hrv >= RiskScoringEngine.NORMAL_HRV_MIN:
            return {
                "status": "normal",
                "risk_points": 0,
                "message": f"Normal HRV: {hrv:.1f} ms (good autonomic balance)"
            }
        else:
            return {
                "status": "low",
                "risk_points": 10,
                "message": f"Low HRV: {hrv:.1f} ms (autonomic stress, monitor closely)"
            }
    
    @staticmethod
    def _assess_danger_signs(count: int) -> Dict:
        """Assess WHO-aligned danger sign count"""
        if count == 0:
            return {
                "status": "none",
                "risk_points": 0,
                "message": "No danger signs reported"
            }
        elif count == 1:
            return {
                "status": "mild",
                "risk_points": 10,
                "message": f"{count} danger sign reported - monitor"
            }
        elif count == 2:
            return {
                "status": "moderate",
                "risk_points": 25,
                "message": f"{count} danger signs reported - increased vigilance needed"
            }
        else:  # 3+
            return {
                "status": "severe",
                "risk_points": 50,
                "message": f"{count} danger signs reported - immediate escalation needed"
            }


def get_risk_recommendation(risk_tier: RiskTier) -> str:
    """Get actionable recommendation based on risk tier"""
    recommendations = {
        RiskTier.LOW: "✅ All signs look good. Continue daily self-checks and seek care if anything changes.",
        RiskTier.WATCH: "⚠️ Watch carefully over the next 24 hours. Return immediately if symptoms worsen.",
        RiskTier.URGENT: "🚨 Seek immediate medical care. GPS will show nearest hospitals."
    }
    return recommendations.get(risk_tier, "Unknown risk tier")
