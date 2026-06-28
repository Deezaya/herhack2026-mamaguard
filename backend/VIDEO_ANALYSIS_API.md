# MamaGuard Video Analysis API Documentation

**Version:** 1.0.0  
**Base URL:** `https://mamaguard.onrender.com`  
**Endpoint:** `POST /api/vitallens/analyze-video`

---

## Overview

The Video Analysis API allows users to record a video of their face (typically 15 seconds, but duration is controlled by the frontend) and send it to the backend for vital sign extraction. The backend processes all frames from the video to extract aggregated heart rate and respiratory rate measurements.

### Key Features

- ✅ **Asynchronous Processing**: Backend processes entire video at once
- ✅ **Frame Aggregation**: Uses median of all valid frames for stable results
- ✅ **Confidence Scores**: Returns confidence metrics for each vital sign
- ✅ **No Streaming**: Simple request/response (no real-time frame streaming)
- ✅ **Frontend-Controlled Duration**: Video length is controlled by frontend, not backend

---

## Authentication

This endpoint requires Bearer token authentication.

### Token Format

```
Authorization: Bearer <access_token>
```

**How to obtain token:**
1. Register: `POST /auth/register`
2. Login: `POST /auth/login`
3. Use returned `access_token` in Authorization header

---

## Request

### Endpoint

```
POST /api/vitallens/analyze-video
```

### Headers

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Request Body

```json
{
  "video": "base64_encoded_video_data_here",
  "format": "mp4"
}
```

### Request Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| video | string | Yes | Base64-encoded video file. Video format should be supported by OpenCV (mp4, webm, etc.) |
| format | string | No | Video format (default: "mp4"). Informational only - actual format is detected from video data. |

### Size Limitations

- **Maximum recommended video size**: < 100 MB (base64-encoded)
- **Typical 15-second video**: ~5-20 MB encoded
- Larger videos will take longer to process and consume more bandwidth

### Example Frontend Code

#### JavaScript/TypeScript

```javascript
// Record video and convert to base64
async function recordAndAnalyzeVideo() {
  const videoBlob = await recordVideo(15); // Record 15 seconds (frontend controls this)
  
  // Convert blob to base64
  const reader = new FileReader();
  reader.readAsDataURL(videoBlob);
  
  reader.onload = async () => {
    const base64Video = reader.result.split(',')[1]; // Remove data:video/mp4;base64, prefix
    
    // Send to backend
    const token = localStorage.getItem('access_token');
    const response = await fetch('https://mamaguard.onrender.com/api/vitallens/analyze-video', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        video: base64Video,
        format: 'mp4'
      })
    });
    
    const result = await response.json();
    console.log('Video analysis result:', result);
  };
}
```

#### React Component Example

```typescript
import { useState } from 'react';

export function VideoScanComponent() {
  const [recording, setRecording] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [vitals, setVitals] = useState(null);

  async function startVideoScan() {
    setRecording(true);
    
    // Use MediaRecorder API (user controls duration)
    const canvas = document.createElement('canvas');
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    const mediaRecorder = new MediaRecorder(stream);
    const chunks = [];

    mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
    mediaRecorder.onstop = async () => {
      const videoBlob = new Blob(chunks, { type: 'video/mp4' });
      await analyzeVideo(videoBlob);
    };

    mediaRecorder.start();
    
    // User controls when to stop (or set a timer in your UI)
    // mediaRecorder.stop();
  }

  async function analyzeVideo(videoBlob) {
    setAnalyzing(true);
    
    // Convert to base64
    const reader = new FileReader();
    reader.readAsDataURL(videoBlob);
    
    reader.onload = async () => {
      const base64Video = reader.result.split(',')[1];
      const token = localStorage.getItem('access_token');
      
      try {
        const response = await fetch(
          `${process.env.REACT_APP_API_URL}/api/vitallens/analyze-video`,
          {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              video: base64Video,
              format: 'mp4'
            })
          }
        );
        
        if (!response.ok) throw new Error('Video analysis failed');
        
        const data = await response.json();
        setVitals(data);
        console.log('Analysis complete:', data);
      } catch (error) {
        console.error('Error analyzing video:', error);
      } finally {
        setAnalyzing(false);
        setRecording(false);
      }
    };
  }

  return (
    <div>
      <button onClick={startVideoScan} disabled={recording || analyzing}>
        {recording ? 'Recording...' : analyzing ? 'Analyzing...' : 'Start Scan'}
      </button>
      
      {vitals && (
        <div>
          <h3>Vital Signs</h3>
          <p>Heart Rate: {vitals.heart_rate?.toFixed(1)} bpm (confidence: {(vitals.heart_rate_confidence * 100).toFixed(0)}%)</p>
          <p>Respiratory Rate: {vitals.respiratory_rate?.toFixed(1)} rpm (confidence: {(vitals.respiratory_rate_confidence * 100).toFixed(0)}%)</p>
          <p>Video Duration: {vitals.duration_seconds.toFixed(1)}s</p>
          <p>Frames Analyzed: {vitals.total_frames} ({vitals.valid_frames} with valid readings)</p>
        </div>
      )}
    </div>
  );
}
```

---

## Response

### Success Response (200)

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "heart_rate": 78.5,
  "heart_rate_confidence": 0.92,
  "respiratory_rate": 18.2,
  "respiratory_rate_confidence": 0.85,
  "total_frames": 450,
  "valid_frames": 420,
  "duration_seconds": 15.0,
  "status": "completed",
  "message": "Video analysis complete. Submit checklist to calculate risk score."
}
```

### Response Parameters

| Field | Type | Description |
|-------|------|-------------|
| session_id | string | Unique session ID for this scan. Use this ID for subsequent checklist and risk score endpoints. |
| heart_rate | float or null | Extracted heart rate in beats per minute (bpm). Null if insufficient data. |
| heart_rate_confidence | float | Confidence score for heart rate (0.0-1.0). Higher is better. |
| respiratory_rate | float or null | Extracted respiratory rate in breaths per minute (rpm). Null if insufficient data. |
| respiratory_rate_confidence | float | Confidence score for respiratory rate (0.0-1.0). Higher is better. |
| total_frames | integer | Total number of frames extracted from the video. |
| valid_frames | integer | Number of frames where valid vital sign readings were extracted. |
| duration_seconds | float | Duration of the video in seconds. |
| status | string | Processing status (typically "completed"). |
| message | string | Status message with next steps. |

---

## Error Responses

### 400 Bad Request

**Invalid base64 video:**
```json
{
  "detail": "Invalid base64 video data"
}
```

**No frames extracted:**
```json
{
  "detail": "Video analysis failed: No frames extracted from video"
}
```

**Corrupted video file:**
```json
{
  "detail": "Video analysis failed: Failed to open video file"
}
```

### 401 Unauthorized

**Missing or invalid token:**
```json
{
  "detail": "Could not validate credentials"
}
```

### 500 Internal Server Error

**VitalLens not initialized:**
```json
{
  "detail": "Video analysis failed: VitalLens not initialized"
}
```

**Processing error:**
```json
{
  "detail": "Video analysis failed: Failed to process frames through VitalLens"
}
```

---

## Processing Flow

1. **Frontend Records Video** → User records video (duration controlled by frontend)
2. **Frontend Encodes** → Convert video file to base64
3. **Frontend Sends Request** → POST with base64 video + access token
4. **Backend Decodes** → Decode base64 to video bytes
5. **Backend Saves Temp Video** → Save to temporary file
6. **Backend Extracts Frames** → Extract all frames at 40x40 resolution
7. **Backend Processes Frames** → Run through VitalLens
8. **Backend Aggregates Results** → Use median of valid frames
9. **Backend Creates Session** → Save ScanSession with vitals
10. **Backend Returns Response** → Return session_id + vitals
11. **Backend Cleans Up** → Delete temporary video file
12. **Frontend Stores session_id** → Use for checklist submission

---

## Next Steps After Video Analysis

### 1. Submit Danger Sign Checklist

Once video analysis is complete, submit the danger sign checklist:

```bash
POST /api/scans/{session_id}/checklist
Headers: Authorization: Bearer <token>

{
  "severe_headache": false,
  "blurred_vision": false,
  "abdominal_pain": true,
  "sudden_swelling": false,
  "shortness_of_breath": false
}
```

### 2. Get Risk Score

After submitting checklist, retrieve the calculated risk score:

```bash
GET /api/scans/{session_id}/risk-score
Headers: Authorization: Bearer <token>
```

### 3. Get Complete Summary

Retrieve full scan results:

```bash
GET /api/scans/{session_id}/summary
Headers: Authorization: Bearer <token>
```

---

## Complete Workflow Example

```javascript
async function completeScan(token) {
  // Step 1: Record and analyze video
  const videoAnalysis = await analyzeVideo(token);
  const sessionId = videoAnalysis.session_id;
  
  console.log(`Session created: ${sessionId}`);
  console.log(`Heart Rate: ${videoAnalysis.heart_rate} bpm`);
  console.log(`Respiratory Rate: ${videoAnalysis.respiratory_rate} rpm`);
  
  // Step 2: Submit checklist
  const checklistResponse = await fetch(`/api/scans/${sessionId}/checklist`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      severe_headache: false,
      blurred_vision: false,
      abdominal_pain: true,
      sudden_swelling: false,
      shortness_of_breath: false
    })
  });
  
  const checklistResult = await checklistResponse.json();
  console.log(`Risk Tier: ${checklistResult.risk_tier}`);
  console.log(`Risk Score: ${checklistResult.risk_score}`);
  
  // Step 3: Get detailed risk assessment
  const riskResponse = await fetch(`/api/scans/${sessionId}/risk-score`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  const riskDetails = await riskResponse.json();
  console.log(`Recommendation: ${riskDetails.recommendation}`);
  
  return {
    session: videoAnalysis,
    risk: riskDetails
  };
}
```

---

## Important Notes

### Video Format Requirements

- **Supported formats**: MP4, WebM, AVI, MOV (any format supported by OpenCV)
- **Recommended codec**: H.264 video, AAC audio
- **Resolution**: Any resolution (frames are resized to 40x40 internally)
- **Frame rate**: 24-30 fps recommended

### Duration Control

- **Frontend controls the duration** - Record however long you want (typically 15 seconds)
- Backend processes all frames from the duration you provide
- Longer videos = more frames = more stable results (but longer processing time)
- Shorter videos = faster processing but fewer data points

### Performance Considerations

- **Processing time**: ~2-5 seconds for 15-second video
- **Recommended duration**: 15 seconds (good balance of accuracy and speed)
- **Minimum duration**: 5-10 seconds (needs enough frames)
- **File size**: Base64 encoding increases size by ~33%, plan accordingly

### Confidence Scores

- **Confidence 0.9-1.0**: Excellent quality reading
- **Confidence 0.7-0.9**: Good quality reading (usable)
- **Confidence 0.5-0.7**: Moderate quality (use with caution)
- **Confidence < 0.5**: Poor quality (consider re-recording)

If confidence scores are low:
- Ensure face is centered in camera
- Maintain good lighting
- Keep head still during recording
- Avoid sudden movements

---

## Troubleshooting

### Issue: "Invalid base64 video data"

**Cause**: Video encoding went wrong

**Solution**:
```javascript
// Make sure you extract the base64 part correctly
const base64 = base64WithPrefix.split(',')[1]; // Remove "data:video/mp4;base64,"
```

### Issue: "No frames extracted from video"

**Cause**: Video file is corrupted or unsupported format

**Solution**:
- Use standard formats (MP4, WebM)
- Test video locally with VLC
- Try re-encoding the video

### Issue: Low confidence scores

**Cause**: Poor recording quality

**Solution**:
- Increase lighting
- Keep face centered
- Stay still while recording
- Ensure good contrast between face and background

### Issue: 401 Unauthorized

**Cause**: Token missing or expired

**Solution**:
```javascript
if (error.status === 401) {
  // Token expired, redirect to login
  window.location.href = '/login';
}
```

---

## API Reference Quick Links

- **Register**: `POST /auth/register`
- **Login**: `POST /auth/login`
- **Analyze Video**: `POST /api/vitallens/analyze-video` (this endpoint)
- **Submit Checklist**: `POST /api/scans/{session_id}/checklist`
- **Get Risk Score**: `GET /api/scans/{session_id}/risk-score`
- **Get Summary**: `GET /api/scans/{session_id}/summary`

---

*Last Updated: 2026-06-28*
