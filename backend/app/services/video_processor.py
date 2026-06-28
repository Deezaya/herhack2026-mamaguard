"""
Video Processing Service for MamaGuard

Handles extraction and analysis of 15-second video recordings.
Returns aggregated heart rate and respiratory rate from all frames.
"""

import cv2
import numpy as np
import base64
import tempfile
import os
from typing import Dict, Tuple, List
import logging

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Process video files to extract vital signs"""
    
    @staticmethod
    def decode_base64_video(video_base64: str) -> bytes:
        """Decode base64-encoded video data"""
        try:
            video_bytes = base64.b64decode(video_base64)
            return video_bytes
        except Exception as e:
            logger.error(f"Failed to decode video: {e}")
            raise ValueError("Invalid base64 video data")
    
    @staticmethod
    def save_temp_video(video_bytes: bytes) -> str:
        """Save video bytes to temporary file and return path"""
        try:
            # Create temp file with proper extension
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                tmp_file.write(video_bytes)
                temp_path = tmp_file.name
            return temp_path
        except Exception as e:
            logger.error(f"Failed to save temp video: {e}")
            raise
    
    @staticmethod
    def extract_frames(video_path: str, target_size: Tuple[int, int] = (40, 40)) -> List[np.ndarray]:
        """
        Extract frames from video file.
        
        Args:
            video_path: Path to video file
            target_size: Size to resize frames to (default 40x40 for VitalLens)
            
        Returns:
            List of numpy arrays representing frames
        """
        frames = []
        
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                raise ValueError("Failed to open video file")
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"Video: {total_frames} frames at {fps} fps")
            
            frame_count = 0
            while True:
                ret, frame = cap.read()
                
                if not ret:
                    break
                
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Resize to target size
                frame_resized = cv2.resize(frame_rgb, target_size)
                
                frames.append(frame_resized)
                frame_count += 1
            
            cap.release()
            
            logger.info(f"Extracted {len(frames)} frames from video")
            
            if len(frames) == 0:
                raise ValueError("No frames extracted from video")
            
            return frames
            
        except Exception as e:
            logger.error(f"Failed to extract frames: {e}")
            raise
    
    @staticmethod
    def cleanup_temp_file(temp_path: str):
        """Remove temporary video file"""
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logger.info(f"Cleaned up temp file: {temp_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {temp_path}: {e}")
    
    @staticmethod
    def process_frames_through_vitallens(
        frames: List[np.ndarray],
        vitallens_instance,
        fps: float = 10.0
    ) -> Dict:
        """
        Process all frames through VitalLens to extract vital signs.
        
        Args:
            frames: List of numpy arrays (RGB images, 40x40)
            vitallens_instance: Initialized VitalLens instance
            fps: Frames per second of the video (used for temporal analysis)
            
        Returns:
            Dictionary with aggregated heart_rate, respiratory_rate, and confidence scores
        """
        if not vitallens_instance:
            raise ValueError("VitalLens instance not initialized")
        
        if len(frames) == 0:
            raise ValueError("No frames to process")
        
        try:
            # Convert list of frames to numpy array: (num_frames, 40, 40, 3)
            frames_array = np.array(frames, dtype=np.uint8)
            
            logger.info(f"Processing {len(frames)} frames through VitalLens (fps={fps})")
            
            # Call VitalLens directly on batch of frames
            results = vitallens_instance(frames_array, fps=fps)
            
            # Extract vitals from first (and only) result
            if not results or len(results) == 0:
                logger.warning("VitalLens returned no results")
                return {
                    "heart_rate": None,
                    "heart_rate_confidence": 0.0,
                    "respiratory_rate": None,
                    "respiratory_rate_confidence": 0.0,
                    "frames_processed": len(frames),
                    "valid_frames": 0
                }
            
            vitals_data = results[0].get("vitals", {})
            
            # Extract heart rate and confidence
            hr_info = vitals_data.get("heart_rate", {})
            heart_rate = hr_info.get("value") if isinstance(hr_info, dict) else hr_info
            hr_confidence = hr_info.get("confidence", 0.0) if isinstance(hr_info, dict) else 0.0
            
            # Extract respiratory rate and confidence
            rr_info = vitals_data.get("respiratory_rate", {})
            respiratory_rate = rr_info.get("value") if isinstance(rr_info, dict) else rr_info
            rr_confidence = rr_info.get("confidence", 0.0) if isinstance(rr_info, dict) else 0.0
            
            logger.info(
                f"VitalLens results - HR: {heart_rate} (confidence: {hr_confidence}), "
                f"RR: {respiratory_rate} (confidence: {rr_confidence})"
            )
            
            return {
                "heart_rate": heart_rate,
                "heart_rate_confidence": float(hr_confidence) if hr_confidence else 0.0,
                "respiratory_rate": respiratory_rate,
                "respiratory_rate_confidence": float(rr_confidence) if rr_confidence else 0.0,
                "frames_processed": len(frames),
                "valid_frames": len(frames)
            }
            
        except Exception as e:
            logger.error(f"Failed to process frames through VitalLens: {e}")
            raise
