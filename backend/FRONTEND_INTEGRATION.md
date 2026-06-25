# Frontend Integration Guide - Real-time rPPG Streaming

This guide shows how to implement real-time heart rate monitoring on the frontend using the MamaGuard backend streaming APIs.

## Architecture

```
Frontend (React/Vue)
    ↓
1. /api/vitallens/stream/start (POST)
    ↓
2. Camera Capture Loop:
    - Get frame from webcam
    - Convert to base64 RGB24 40x40
    - /api/vitallens/stream/process-frame (POST)
    - Display live heart rate
    ↓
3. /api/vitallens/stream/stop (POST)
    ↓
Final Results
```

## API Reference

### 1. Start Streaming Session

**Request:**
```http
POST /api/vitallens/stream/start
Content-Type: application/json

{
  "process_signals": true,
  "model": null
}
```

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "started",
  "message": "Streaming session ... started"
}
```

### 2. Process Frame

**Request:**
```http
POST /api/vitallens/stream/process-frame
Content-Type: application/json

{
  "session_id": "uuid-string",
  "frame": "base64-encoded-rgb24-buffer",
  "timestamp": 1234567890.123
}
```

**Frame Format:**
- Must be RGB24 (3 channels, 8-bit per channel)
- Resolution: 40x40 pixels
- Total size: 40 × 40 × 3 = 4,800 bytes
- Encoded as base64 string

**Response:**
```json
{
  "session_id": "uuid-string",
  "frame_number": 42,
  "heart_rate": 72.5,
  "heart_rate_confidence": 0.95,
  "respiratory_rate": null,
  "respiratory_rate_confidence": null,
  "status": "processing"
}
```

### 3. Get Status (Optional)

**Request:**
```http
GET /api/vitallens/stream/status/{session_id}
```

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "active",
  "frames_processed": 42,
  "heart_rate": 72.5,
  "heart_rate_confidence": 0.95,
  "respiratory_rate": null,
  "respiratory_rate_confidence": null,
  "last_update": "2026-06-25T12:34:56",
  "duration_seconds": 5.2
}
```

### 4. Stop Streaming

**Request:**
```http
POST /api/vitallens/stream/stop
Content-Type: application/json

{
  "session_id": "uuid-string"
}
```

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "stopped",
  "frames_processed": 150,
  "heart_rate": 73.2,
  "heart_rate_confidence": 0.97,
  "respiratory_rate": null,
  "respiratory_rate_confidence": null,
  "duration_seconds": 5.0,
  "message": "Streaming session stopped successfully"
}
```

## Frontend Implementation

### JavaScript/React Example

```typescript
// services/vitallensService.ts
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

export class VitallensStreamingClient {
  private sessionId: string | null = null;

  async startStreaming() {
    const response = await axios.post(`${API_BASE}/api/vitallens/stream/start`, {
      process_signals: true,
      model: null,
    });
    this.sessionId = response.data.session_id;
    return this.sessionId;
  }

  async processFrame(frameBase64: string, timestamp: number) {
    if (!this.sessionId) {
      throw new Error('No active session. Call startStreaming first.');
    }

    const response = await axios.post(
      `${API_BASE}/api/vitallens/stream/process-frame`,
      {
        session_id: this.sessionId,
        frame: frameBase64,
        timestamp,
      }
    );

    return {
      frameNumber: response.data.frame_number,
      heartRate: response.data.heart_rate,
      confidence: response.data.heart_rate_confidence,
    };
  }

  async getStatus() {
    if (!this.sessionId) return null;
    
    try {
      const response = await axios.get(
        `${API_BASE}/api/vitallens/stream/status/${this.sessionId}`
      );
      return response.data;
    } catch {
      return null;
    }
  }

  async stopStreaming() {
    if (!this.sessionId) return null;

    const response = await axios.post(
      `${API_BASE}/api/vitallens/stream/stop`,
      { session_id: this.sessionId }
    );
    
    this.sessionId = null;
    return response.data;
  }
}

// hooks/useVitallensStream.ts
import { useEffect, useRef, useState } from 'react';
import { VitallensStreamingClient } from '@/services/vitallensService';

interface StreamingState {
  isStreaming: boolean;
  frameCount: number;
  heartRate: number | null;
  confidence: number | null;
  error: string | null;
}

export function useVitallensStream() {
  const [state, setState] = useState<StreamingState>({
    isStreaming: false,
    frameCount: 0,
    heartRate: null,
    confidence: null,
    error: null,
  });

  const clientRef = useRef(new VitallensStreamingClient());
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();

  const startStreaming = async () => {
    try {
      // Start backend session
      await clientRef.current.startStreaming();
      setState((prev) => ({ ...prev, isStreaming: true, error: null }));

      // Start camera
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }

      // Start processing frames
      processFrames();
    } catch (error) {
      setState((prev) => ({
        ...prev,
        error: `Failed to start streaming: ${error}`,
      }));
    }
  };

  const processFrames = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;

    if (!video || !canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const processNextFrame = async () => {
      // Draw video frame to canvas (scaled to 40x40)
      ctx.drawImage(video, 0, 0, 40, 40);

      // Get RGB24 buffer
      const imageData = ctx.getImageData(0, 0, 40, 40);
      const frameBuffer = imageData.data.slice(0, -1); // Remove alpha channel
      const frameBase64 = btoa(
        Array.from(frameBuffer).map((b) => String.fromCharCode(b)).join('')
      );

      try {
        const result = await clientRef.current.processFrame(
          frameBase64,
          performance.now() / 1000
        );

        setState((prev) => ({
          ...prev,
          frameCount: result.frameNumber,
          heartRate: result.heartRate,
          confidence: result.confidence,
        }));
      } catch (error) {
        console.error('Frame processing error:', error);
      }

      if (state.isStreaming) {
        animationFrameRef.current = requestAnimationFrame(processNextFrame);
      }
    };

    processNextFrame();
  };

  const stopStreaming = async () => {
    try {
      // Stop animation loop
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }

      // Stop camera
      if (videoRef.current?.srcObject) {
        const tracks = (videoRef.current.srcObject as MediaStream).getTracks();
        tracks.forEach((track) => track.stop());
      }

      // Stop backend session
      const finalResults = await clientRef.current.stopStreaming();
      setState((prev) => ({ ...prev, isStreaming: false }));
      return finalResults;
    } catch (error) {
      setState((prev) => ({
        ...prev,
        error: `Failed to stop streaming: ${error}`,
      }));
    }
  };

  return {
    ...state,
    startStreaming,
    stopStreaming,
    videoRef,
    canvasRef,
  };
}

// components/VitalsMonitor.tsx
export function VitalsMonitor() {
  const { isStreaming, frameCount, heartRate, confidence, error, startStreaming, stopStreaming, videoRef, canvasRef } =
    useVitallensStream();

  return (
    <div className="vitals-monitor">
      <video
        ref={videoRef}
        style={{ display: 'none' }}
        width={40}
        height={40}
      />
      <canvas ref={canvasRef} width={40} height={40} style={{ display: 'none' }} />

      {error && <div className="error">{error}</div>}

      <div className="controls">
        {!isStreaming ? (
          <button onClick={startStreaming} className="btn-primary">
            Start Scanning
          </button>
        ) : (
          <button onClick={stopStreaming} className="btn-danger">
            Stop Scanning
          </button>
        )}
      </div>

      {isStreaming && (
        <div className="live-stats">
          <div className="stat">
            <span className="label">Heart Rate:</span>
            <span className="value">
              {heartRate !== null ? `${heartRate.toFixed(1)} bpm` : 'Measuring...'}
            </span>
            {confidence !== null && (
              <span className="confidence">{(confidence * 100).toFixed(0)}%</span>
            )}
          </div>
          <div className="stat">
            <span className="label">Frames:</span>
            <span className="value">{frameCount}</span>
          </div>
        </div>
      )}
    </div>
  );
}
```

## Key Points

1. **Frame Format**: Convert camera frames to RGB24 40x40 format
2. **Base64 Encoding**: Frames must be base64-encoded for JSON transport
3. **Timestamps**: Use high-precision timestamps (performance.now() / 1000)
4. **Session ID**: Keep track of session_id for all subsequent requests
5. **Error Handling**: Implement retry logic and graceful fallbacks
6. **CORS**: Backend allows cross-origin requests for frontend integration

## Performance Considerations

- Optimal frame rate: 30 fps (33ms per frame)
- Frame processing should be non-blocking
- Use `requestAnimationFrame` for smooth camera capture
- Consider WebWorker for frame preprocessing if needed

## Testing

Use the included test-rppg.py for backend validation:
```bash
python test-rppg.py
```

Use curl for API testing:
```bash
# Start session
curl -X POST http://localhost:8000/api/vitallens/stream/start

# Process frame
curl -X POST http://localhost:8000/api/vitallens/stream/process-frame \
  -H "Content-Type: application/json" \
  -d @frame.json

# Stop session
curl -X POST http://localhost:8000/api/vitallens/stream/stop
```
