from fastapi import APIRouter, HTTPException, Depends
from app.schemas.streaming import (
    StreamStartRequest,
    StreamStartResponse,
    ProcessFrameRequest,
    ProcessFrameResponse,
    StreamStatusRequest,
    StreamStatusResponse,
    StreamStopRequest,
    StreamStopResponse,
)
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

router = APIRouter(prefix="/api/vitallens/stream", tags=["streaming"])


def get_service() -> StreamingService:
    """Dependency injection for streaming service"""
    return get_streaming_service()


@router.post("/start", response_model=StreamStartResponse)
async def start_stream(
    request: StreamStartRequest,
    current_user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
    service: StreamingService = Depends(get_service)
):
    """
    Start a new real-time streaming session.
    
    The frontend will capture frames and send them via /process-frame endpoint.
    """
    try:
        session_id = service.create_session(
            user_id=current_user.id,
            db_session=db,
            process_signals=request.process_signals,
            model=request.model
        )
        
        return StreamStartResponse(
            session_id=session_id,
            status="started",
            message=f"Streaming session {session_id} started"
        )
    except Exception as e:
        logger.error(f"Failed to start streaming: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-frame", response_model=ProcessFrameResponse)
async def process_frame(
    request: ProcessFrameRequest,
    service: StreamingService = Depends(get_service)
):
    """
    Process a single frame from the camera stream.
    
    Expected frame format: base64-encoded RGB24 buffer (40x40x3).
    
    This endpoint is called for each camera frame and returns:
    - Current frame count
    - Real-time heart rate estimate
    - Confidence score
    - Any available respiratory rate
    """
    try:
        result = service.push_frame(
            session_id=request.session_id,
            frame_base64=request.frame,
            timestamp=request.timestamp
        )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        vitals = result.get("vitals", {})
        frame_number = result.get("frame_number", 0)
        
        return ProcessFrameResponse(
            session_id=request.session_id,
            frame_number=frame_number,
            heart_rate=vitals.get("heart_rate"),
            heart_rate_confidence=vitals.get("heart_rate_confidence"),
            respiratory_rate=vitals.get("respiratory_rate"),
            respiratory_rate_confidence=vitals.get("respiratory_rate_confidence"),
            status="processing"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process frame: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{session_id}", response_model=StreamStatusResponse)
async def get_stream_status(
    session_id: str,
    service: StreamingService = Depends(get_service)
):
    """
    Get current status of a streaming session.
    
    Returns:
    - Current frame count
    - Duration since session started
    - Latest vital signs with confidence
    - Last update timestamp
    """
    status = service.get_status(session_id)
    
    if status is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    vitals = status.get("vitals", {})
    
    return StreamStatusResponse(
        session_id=session_id,
        status="active",
        frames_processed=status.get("frames_processed", 0),
        heart_rate=vitals.get("heart_rate"),
        heart_rate_confidence=vitals.get("heart_rate_confidence"),
        respiratory_rate=vitals.get("respiratory_rate"),
        respiratory_rate_confidence=vitals.get("respiratory_rate_confidence"),
        last_update=status.get("last_update"),
        duration_seconds=status.get("duration_seconds", 0)
    )


@router.post("/stop", response_model=StreamStopResponse)
async def stop_stream(
    request: StreamStopRequest,
    service: StreamingService = Depends(get_service)
):
    """
    Stop a streaming session and get final results.
    
    Returns:
    - Total frames processed
    - Final vital signs estimates
    - Total duration
    """
    try:
        result = service.stop_session(request.session_id)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        vitals = result.get("vitals", {})
        
        return StreamStopResponse(
            session_id=request.session_id,
            status="stopped",
            frames_processed=result.get("frames_processed", 0),
            heart_rate=vitals.get("heart_rate"),
            heart_rate_confidence=vitals.get("heart_rate_confidence"),
            respiratory_rate=vitals.get("respiratory_rate"),
            respiratory_rate_confidence=vitals.get("respiratory_rate_confidence"),
            duration_seconds=result.get("duration_seconds", 0),
            message="Streaming session stopped successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def streaming_health(service: StreamingService = Depends(get_service)):
    """Get streaming service health status"""
    return {
        "status": "healthy",
        "active_sessions": service.get_session_count()
    }


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
        vitals = VideoProcessor.process_frames_through_vitallens(frames, vitallens)
        
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
