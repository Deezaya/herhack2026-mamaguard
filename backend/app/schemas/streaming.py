from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class StreamStartRequest(BaseModel):
    """Request to start a streaming session"""
    process_signals: bool = Field(default=True, description="Enable signal processing")
    model: Optional[str] = Field(default=None, description="VitalLens model to use")


class StreamStartResponse(BaseModel):
    """Response when streaming session starts"""
    session_id: str = Field(description="Unique streaming session ID")
    status: str = Field(default="started", description="Session status")
    message: str = Field(description="Status message")


class ProcessFrameRequest(BaseModel):
    """Request to process a single frame"""
    session_id: str = Field(description="Streaming session ID")
    frame: str = Field(description="Frame as base64-encoded RGB24")
    timestamp: float = Field(description="Frame timestamp in seconds")


class ProcessFrameResponse(BaseModel):
    """Response after processing a frame"""
    session_id: str
    frame_number: int = Field(description="Frame count in this session")
    heart_rate: Optional[float] = Field(default=None, description="Estimated heart rate in bpm")
    heart_rate_confidence: Optional[float] = Field(default=None, description="Confidence (0-1)")
    respiratory_rate: Optional[float] = Field(default=None, description="Estimated respiratory rate in rpm")
    respiratory_rate_confidence: Optional[float] = Field(default=None, description="Confidence (0-1)")
    status: str = Field(default="processing", description="Processing status")


class StreamStatusRequest(BaseModel):
    """Request to get session status"""
    session_id: str


class StreamStatusResponse(BaseModel):
    """Response with current session status"""
    session_id: str
    status: str
    frames_processed: int
    heart_rate: Optional[float] = None
    heart_rate_confidence: Optional[float] = None
    respiratory_rate: Optional[float] = None
    respiratory_rate_confidence: Optional[float] = None
    last_update: Optional[datetime] = None
    duration_seconds: float


class StreamStopRequest(BaseModel):
    """Request to stop streaming session"""
    session_id: str


class StreamStopResponse(BaseModel):
    """Response when streaming session stops"""
    session_id: str
    status: str = Field(default="stopped")
    frames_processed: int
    heart_rate: Optional[float]
    heart_rate_confidence: Optional[float]
    respiratory_rate: Optional[float]
    respiratory_rate_confidence: Optional[float]
    duration_seconds: float
    message: str
