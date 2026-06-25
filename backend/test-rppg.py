import sys
import subprocess
import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

try:
	from vitallens import VitalLens
	import numpy as np
except ImportError:
	sys.exit("Missing dependencies: install 'vitallens' and 'numpy'")

# Load environment variables from .env file
load_dotenv()

# Suppress verbose warnings from underlying libraries
logging.getLogger('prpy').setLevel(logging.ERROR)

def get_video_fps(video_path: str) -> float:
	"""Extract FPS from video using ffprobe."""
	args = [
		"ffprobe", "-v", "error",
		"-select_streams", "v:0",
		"-show_entries", "stream=avg_frame_rate,r_frame_rate",
		"-of", "default=noprint_wrappers=1:nokey=1",
		video_path
	]
	try:
		result = subprocess.run(args, capture_output=True, text=True, check=True)
		lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
		
		for line in lines:
			if '/' in line:
				numerator, denominator = line.split('/')
				fps = float(numerator) / float(denominator)
				if fps > 0:
					return fps
		
		# Fallback to first line if it's a number
		fps = float(lines[0])
		if fps > 0:
			return fps
	except (subprocess.CalledProcessError, ValueError, IndexError):
		pass
	
	raise ValueError("Could not determine FPS from input video")

def preprocess_video_to_rgb24(video_path: str, output_fps: int = 30, duration: int = 30) -> np.ndarray:
	"""
	Preprocess video to RGB24 format at 40x40 resolution.
	Mirrors the Node.js toRgb24Base64 function.
	"""
	args = [
		"ffmpeg", "-i", video_path,
		"-t", str(duration),
		"-vf", f"fps={output_fps},scale=40:40:flags=bicubic",
		"-pix_fmt", "rgb24",
		"-f", "rawvideo",
		"pipe:1"
	]
	
	try:
		result = subprocess.run(args, capture_output=True, check=True)
		raw_video = result.stdout
		
		if not raw_video or len(raw_video) == 0:
			raise ValueError("ffmpeg returned empty raw video output")
		
		return raw_video
	except subprocess.CalledProcessError as e:
		raise RuntimeError(f"ffmpeg preprocessing failed: {e}")

def enforce_frame_constraints(raw_video_buffer: bytes, has_state: bool = False) -> int:
	"""
	Validate frame count and buffer size.
	Mirrors the Node.js enforceFrameConstraints function.
	"""
	bytes_per_frame = 40 * 40 * 3
	
	if len(raw_video_buffer) % bytes_per_frame != 0:
		raise ValueError(
			"Preprocessed video size is invalid. Expected raw RGB24 bytes with shape (frames, 40, 40, 3)"
		)
	
	frame_count = len(raw_video_buffer) // bytes_per_frame
	minimum_frames = 5 if has_state else 16
	
	if frame_count < minimum_frames:
		raise ValueError(
			f"Video chunk too short. Minimum {minimum_frames} frames required "
			f"({'when state is provided' if has_state else 'for stateless requests'})"
		)
	
	return frame_count

def analyze_video(video_path: str, method: str = "pos", api_key: str = None) -> dict:
	"""
	Analyze video following the same pipeline as the Node.js backend.
	"""
	if not Path(video_path).exists():
		raise FileNotFoundError(f"Video file not found: {video_path}")
	
	print(f"📹 Processing video: {video_path}")
	
	# Step 1: Extract FPS from video
	print("  → Extracting FPS...")
	fps = get_video_fps(video_path)
	print(f"  ✓ FPS: {fps}")
	
	# Step 2: Preprocess video to RGB24 40x40
	print("  → Preprocessing to RGB24 40x40...")
	raw_video_buffer = preprocess_video_to_rgb24(video_path, output_fps=30, duration=30)
	print(f"  ✓ Preprocessing complete ({len(raw_video_buffer):,} bytes)")
	
	# Step 3: Validate frame constraints
	print("  → Validating frame constraints...")
	frame_count = enforce_frame_constraints(raw_video_buffer, has_state=False)
	print(f"  ✓ Frame count: {frame_count}")
	
	# Step 4: Initialize VitalLens and analyze
	print(f"  → Analyzing with method: {method}...")
	vl = VitalLens(method=method, api_key=api_key)
	
	# Convert raw video buffer back to numpy array for VitalLens
	raw_array = np.frombuffer(raw_video_buffer, dtype=np.uint8)
	frames = raw_array.reshape(-1, 40, 40, 3)
	
	# ffmpeg preprocessing forces 30 fps output
	results = vl(frames, fps=30)
	vitals = results[0]["vitals"]
	print(f"  ✓ Analysis complete")
	
	# Step 5: Return structured response with preprocessing metadata
	return {
		"vitals": vitals,
		"preprocessing": {
			"input_frames": frame_count,
			"fps_used": 30,  # ffmpeg filter forces 30 fps
			"fps_original": fps,
			"resolution": "40x40",
			"pixel_format": "rgb24",
			"duration_seconds": 30
		}
	}

if __name__ == "__main__":
	try:
		# Get API key from environment variable
		api_key = os.getenv("VITALLENS_API_KEY")
		
		if not api_key:
			print("❌ Error: VITALLENS_API_KEY not found in environment variables")
			print("   Please set VITALLENS_API_KEY in your .env file or system environment")
			sys.exit(1)
		
		# Use vitallens method with API key for high-fidelity accuracy
		result = analyze_video("test_rppg.MP4", method="vitallens", api_key=api_key)
		
		vitals = result["vitals"]
		preprocessing = result["preprocessing"]
		
		print("\n" + "="*50)
		print("📊 VITALS ANALYSIS RESULTS")
		print("="*50)
		print(f"Heart Rate:     {vitals['heart_rate']['value']:.1f} bpm")
		print(f"Confidence:     {vitals['heart_rate']['confidence']:.1%}")
		
		# Display respiratory rate if available
		if 'respiratory_rate' in vitals:
			print(f"Respiratory Rate: {vitals['respiratory_rate']['value']:.1f} rpm")
		
		print(f"\n📋 Full Vitals:")
		print(json.dumps(vitals, indent=2))
		print(f"\n⚙️  Preprocessing Details:")
		print(json.dumps(preprocessing, indent=2))
		
	except Exception as e:
		print(f"\n❌ Error: {e}", file=sys.stderr)
		sys.exit(1)
