import uuid
import base64
import time
import numpy as np
from datetime import datetime
from typing import Dict, Optional, List
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class StreamingSession:
    """Manages a single streaming session"""
    
    def __init__(self, session_id: str, user_id: int, vitallens, db_session=None, process_signals: bool = True, model: Optional[str] = None):
        self.session_id = session_id
        self.user_id = user_id
        self.vitallens = vitallens
        self.db_session = db_session
        self.process_signals = process_signals
        self.model = model
        self.created_at = datetime.utcnow()
        self.last_update = None
        self.frames: List[np.ndarray] = []
        self.frame_timestamps: List[float] = []
        self.vitals = {
            "heart_rate": None,
            "heart_rate_confidence": None,
            "respiratory_rate": None,
            "respiratory_rate_confidence": None,
        }
        self.lock = Lock()
        self._session = None  # VitalLens streaming session
    
    def start_vitallens_stream(self):
        """Initialize VitalLens streaming session"""
        try:
            self._session = self.vitallens.stream()
            self._session.__enter__()
            logger.info(f"VitalLens streaming session started: {self.session_id} for user {self.user_id}")
        except Exception as e:
            logger.error(f"Failed to start VitalLens stream: {e}")
            raise
    
    def push_frame(self, frame_base64: str, timestamp: float) -> Dict:
        """
        Push a base64-encoded frame to the session.
        
        Frame format: RGB24 40x40 (or will be reshaped)
        """
        with self.lock:
            try:
                # Decode base64 frame
                frame_bytes = base64.b64decode(frame_base64)
                frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
                
                # Reshape to (height, width, channels) - assuming 40x40 RGB24
                frame_array = frame_array.reshape(40, 40, 3)
                
                # Store frame
                self.frames.append(frame_array)
                self.frame_timestamps.append(timestamp)
                
                # Push to VitalLens stream
                if self._session:
                    self._session.push(frame_array, timestamp=timestamp)
                    
                    # Try to get result (non-blocking)
                    try:
                        results = self._session.get_result(block=False)
                        if results:
                            self._update_vitals(results)
                    except Exception as e:
                        logger.debug(f"No result ready yet: {e}")
                
                self.last_update = datetime.utcnow()
                
                return {
                    "status": "success",
                    "frame_number": len(self.frames),
                    "vitals": self.vitals
                }
                
            except Exception as e:
                logger.error(f"Error pushing frame: {e}")
                return {
                    "status": "error",
                    "message": str(e)
                }
    
    def _update_vitals(self, results):
        """Update vitals from VitalLens results"""
        try:
            if results and isinstance(results, list) and len(results) > 0:
                result = results[0]
                vitals_data = result.get("vitals", {})
                
                if "heart_rate" in vitals_data:
                    hr_info = vitals_data["heart_rate"]
                    self.vitals["heart_rate"] = hr_info.get("value")
                    self.vitals["heart_rate_confidence"] = hr_info.get("confidence")
                
                if "respiratory_rate" in vitals_data:
                    rr_info = vitals_data["respiratory_rate"]
                    self.vitals["respiratory_rate"] = rr_info.get("value")
                    self.vitals["respiratory_rate_confidence"] = rr_info.get("confidence")
                    
        except Exception as e:
            logger.warning(f"Could not parse vitals: {e}")
    
    def get_status(self) -> Dict:
        """Get current session status"""
        with self.lock:
            duration = (datetime.utcnow() - self.created_at).total_seconds()
            return {
                "session_id": self.session_id,
                "frames_processed": len(self.frames),
                "duration_seconds": duration,
                "last_update": self.last_update,
                "vitals": self.vitals
            }
    
    def stop(self) -> Dict:
        """Stop the streaming session and save to database"""
        with self.lock:
            try:
                if self._session:
                    # Get final results
                    try:
                        results = self._session.get_result(block=True, timeout=2)
                        if results:
                            self._update_vitals(results)
                    except Exception as e:
                        logger.debug(f"Could not get final results: {e}")
                    
                    self._session.__exit__(None, None, None)
                
                duration = (datetime.utcnow() - self.created_at).total_seconds()
                
                # Save to database
                if self.db_session:
                    try:
                        from app.models.models import ScanSession
                        
                        db_scan = ScanSession(
                            id=self.session_id,
                            user_id=self.user_id,
                            heart_rate=self.vitals.get("heart_rate"),
                            hrv=self.vitals.get("respiratory_rate"),  # Note: VitalLens may not always provide HRV
                            total_frames=len(self.frames),
                            status="processing",  # Will be updated when checklist is submitted
                            started_at=self.created_at,
                            ended_at=datetime.utcnow()
                        )
                        
                        self.db_session.add(db_scan)
                        self.db_session.commit()
                        logger.info(f"Scan session saved to database: {self.session_id}")
                    except Exception as e:
                        logger.error(f"Failed to save session to database: {e}")
                        self.db_session.rollback()
                
                return {
                    "session_id": self.session_id,
                    "frames_processed": len(self.frames),
                    "duration_seconds": duration,
                    "vitals": self.vitals
                }
            except Exception as e:
                logger.error(f"Error stopping session: {e}")
                raise


class StreamingService:
    """Manages multiple concurrent streaming sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, StreamingSession] = {}
        self.lock = Lock()
        self.vitallens = None
    
    def initialize(self, vitallens_instance):
        """Initialize with VitalLens instance"""
        self.vitallens = vitallens_instance
    
    def create_session(self, user_id: int, db_session=None, process_signals: bool = True, model: Optional[str] = None) -> str:
        """Create a new streaming session"""
        session_id = str(uuid.uuid4())
        
        with self.lock:
            session = StreamingSession(
                session_id=session_id,
                user_id=user_id,
                vitallens=self.vitallens,
                db_session=db_session,
                process_signals=process_signals,
                model=model
            )
            session.start_vitallens_stream()
            self.sessions[session_id] = session
            logger.info(f"Created streaming session: {session_id} for user {user_id}")
        
        return session_id
    
    def push_frame(self, session_id: str, frame_base64: str, timestamp: float) -> Dict:
        """Push a frame to a session"""
        if session_id not in self.sessions:
            return {
                "status": "error",
                "message": f"Session {session_id} not found"
            }
        
        session = self.sessions[session_id]
        result = session.push_frame(frame_base64, timestamp)
        return result
    
    def get_status(self, session_id: str) -> Optional[Dict]:
        """Get status of a session"""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        return session.get_status()
    
    def stop_session(self, session_id: str) -> Dict:
        """Stop a streaming session"""
        if session_id not in self.sessions:
            return {
                "status": "error",
                "message": f"Session {session_id} not found"
            }
        
        session = self.sessions[session_id]
        result = session.stop()
        
        with self.lock:
            del self.sessions[session_id]
        
        logger.info(f"Stopped streaming session: {session_id}")
        return result
    
    def get_session_count(self) -> int:
        """Get number of active sessions"""
        with self.lock:
            return len(self.sessions)


# Global instance
_streaming_service = StreamingService()


def get_streaming_service() -> StreamingService:
    """Get the streaming service instance"""
    return _streaming_service
