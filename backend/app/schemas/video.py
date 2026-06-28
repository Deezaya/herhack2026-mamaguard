from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class VideoAnalysisRequest(BaseModel):
    """Request to analyze a video for vital signs"""
    video: str = Field(description="Base64-encoded video file data")
    format: str = Field(default="mp4", description="Video format (mp4, webm, etc.)")


class VideoAnalysisResponse(BaseModel):
    """Response with vital signs extracted from video"""
    session_id: str = Field(description="Unique scan session ID")
    heart_rate: Optional[float] = Field(default=None, description="Average heart rate in bpm")
    heart_rate_confidence: float = Field(description="Confidence score for heart rate (0-1)")
    respiratory_rate: Optional[float] = Field(default=None, description="Average respiratory rate in rpm")
    respiratory_rate_confidence: float = Field(description="Confidence score for respiratory rate (0-1)")
    total_frames: int = Field(description="Total frames extracted from video")
    valid_frames: int = Field(description="Frames with valid vital sign readings")
    duration_seconds: float = Field(description="Duration of video in seconds")
    status: str = Field(default="completed", description="Processing status")
    message: str = Field(description="Status message")
