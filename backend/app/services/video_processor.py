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
        vitallens_instance
    ) -> Dict:
        """
        Process all frames through VitalLens to extract vital signs.
        
        Args:
            frames: List of numpy arrays (RGB images)
            vitallens_instance: Initialized VitalLens instance
            
        Returns:
            Dictionary with aggregated heart_rate, respiratory_rate, and confidence scores
        """
        if not vitallens_instance:
            raise ValueError("VitalLens instance not initialized")
        
        heart_rates = []
        respiratory_rates = []
        hr_confidences = []
        rr_confidences = []
        
        try:
            for idx, frame in enumerate(frames):
                try:
                    # Convert to bytes if needed
                    if isinstance(frame, np.ndarray):
                        frame_bytes = frame.tobytes()
                    else:
                        frame_bytes = frame
                    
                    # Process frame through VitalLens
                    result = vitallens_instance.process_frame(frame_bytes)
                    
                    if result:
                        if 'heart_rate' in result and result['heart_rate'] is not None:
                            heart_rates.append(result['heart_rate'])
                            if 'heart_rate_confidence' in result:
                                hr_confidences.append(result['heart_rate_confidence'])
                        
                        if 'respiratory_rate' in result and result['respiratory_rate'] is not None:
                            respiratory_rates.append(result['respiratory_rate'])
                            if 'respiratory_rate_confidence' in result:
                                rr_confidences.append(result['respiratory_rate_confidence'])
                
                except Exception as e:
                    logger.warning(f"Error processing frame {idx}: {e}")
                    continue
            
            # Aggregate results
            if heart_rates:
                # Use median for stability against outliers
                aggregated_hr = float(np.median(heart_rates))
                aggregated_hr_confidence = float(np.mean(hr_confidences)) if hr_confidences else 0.0
            else:
                aggregated_hr = None
                aggregated_hr_confidence = 0.0
            
            if respiratory_rates:
                aggregated_rr = float(np.median(respiratory_rates))
                aggregated_rr_confidence = float(np.mean(rr_confidences)) if rr_confidences else 0.0
            else:
                aggregated_rr = None
                aggregated_rr_confidence = 0.0
            
            logger.info(
                f"Processed {len(frames)} frames. "
                f"HR: {aggregated_hr} (confidence: {aggregated_hr_confidence}), "
                f"RR: {aggregated_rr} (confidence: {aggregated_rr_confidence})"
            )
            
            return {
                "heart_rate": aggregated_hr,
                "heart_rate_confidence": aggregated_hr_confidence,
                "respiratory_rate": aggregated_rr,
                "respiratory_rate_confidence": aggregated_rr_confidence,
                "frames_processed": len(frames),
                "valid_frames": len(heart_rates)  # Frames with valid HR readings
            }
            
        except Exception as e:
            logger.error(f"Failed to process frames through VitalLens: {e}")
            raise
