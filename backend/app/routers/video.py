from fastapi import APIRouter, HTTPException, Depends
from app.schemas.video import VideoAnalysisRequest, VideoAnalysisResponse
from app.services.streaming_service import get_streaming_service, StreamingService
from app.services.video_processor import VideoProcessor
from app.core.database import get_db
from app.routers.auth import get_current_user_dependency
from app.models.models import User, ScanSession
from sqlalchemy.orm import Session
import logging
import cv2
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vitallens", tags=["video"])


def get_service() -> StreamingService:
    """Dependency injection for streaming service"""
    return get_streaming_service()


@router.post("/analyze-video", response_model=VideoAnalysisResponse)
async def analyze_video(
    request: VideoAnalysisRequest,
    current_user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
    service: StreamingService = Depends(get_service)
):
    """
    Analyze a recorded video to extract vital signs (heart rate and respiratory rate).
    
    The video is processed frame-by-frame to extract vitals across the entire duration.
    Frontend controls video length - backend processes whatever is provided.
    
    Args:
        request: VideoAnalysisRequest with base64-encoded video
        current_user: Authenticated user
        db: Database session
        service: Streaming service instance
        
    Returns:
        VideoAnalysisResponse with heart_rate, respiratory_rate, and confidence scores
    """
    temp_video_path = None
    
    try:
        # 1. Decode base64 video
        logger.info(f"Analyzing video for user {current_user.email}")
        video_bytes = VideoProcessor.decode_base64_video(request.video)
        
        # 2. Save to temporary file
        temp_video_path = VideoProcessor.save_temp_video(video_bytes)
        logger.info(f"Saved temp video to {temp_video_path}")
        
        # 3. Extract video metadata
        cap = cv2.VideoCapture(temp_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_seconds = total_frames / fps if fps > 0 else 0
        cap.release()
        
        logger.info(f"Video info: {total_frames} frames, {fps} fps, {duration_seconds} seconds")
        
        # 4. Extract frames from video
        frames = VideoProcessor.extract_frames(temp_video_path)
        
        # 5. Get VitalLens instance
        vitallens = service.vitallens if hasattr(service, 'vitallens') else None
        if not vitallens:
            raise ValueError("VitalLens not initialized")
        
        # 6. Process frames through VitalLens
        vitals = VideoProcessor.process_frames_through_vitallens(frames, vitallens, fps=fps)
        
        # 7. Create ScanSession with vitals
        session_id = str(uuid.uuid4())
        scan_session = ScanSession(
            id=session_id,
            user_id=current_user.id,
            heart_rate=vitals.get("heart_rate"),
            hrv=None,  # Will be calculated later if needed
            total_frames=vitals.get("frames_processed", 0),
            status="processing",  # Will be updated to 'completed' after checklist
            started_at=datetime.utcnow(),
        )
        
        db.add(scan_session)
        db.commit()
        db.refresh(scan_session)
        
        logger.info(
            f"Created scan session {session_id} for user {current_user.id}. "
            f"HR: {vitals.get('heart_rate')}, RR: {vitals.get('respiratory_rate')}"
        )
        
        return VideoAnalysisResponse(
            session_id=session_id,
            heart_rate=vitals.get("heart_rate"),
            heart_rate_confidence=vitals.get("heart_rate_confidence", 0.0),
            respiratory_rate=vitals.get("respiratory_rate"),
            respiratory_rate_confidence=vitals.get("respiratory_rate_confidence", 0.0),
            total_frames=vitals.get("frames_processed", 0),
            valid_frames=vitals.get("valid_frames", 0),
            duration_seconds=duration_seconds,
            status="completed",
            message="Video analysis complete. Submit checklist to calculate risk score."
        )
        
    except ValueError as e:
        logger.error(f"Video analysis validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to analyze video: {e}")
        raise HTTPException(status_code=500, detail=f"Video analysis failed: {str(e)}")
    finally:
        # 8. Cleanup temp video file
        if temp_video_path:
            VideoProcessor.cleanup_temp_file(temp_video_path)
