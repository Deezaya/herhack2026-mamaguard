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
from app.services.streaming_service import get_streaming_service, StreamingService
from app.core.database import get_db
from app.routers.auth import get_current_user_dependency
from app.models.models import User
from sqlalchemy.orm import Session
import logging

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
