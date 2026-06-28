# MamaGuard Backend API Documentation

**Version:** 1.0.0  
**Base URL:** `https://mamaguard.onrender.com`  
**API Title:** MamaGuard Backend - Real-time vitals monitoring for postpartum mothers

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Error Handling](#error-handling)
4. [API Endpoints](#api-endpoints)
   - [Health Check](#health-check)
   - [Authentication](#authentication-endpoints)
   - [Video Analysis](#video-analysis-endpoints) ⭐ **NEW - RECOMMENDED**
   - [Streaming & Vitals](#streaming--vitals-endpoints) (deprecated)
   - [Checklist & Risk Assessment](#checklist--risk-assessment-endpoints)
   - [Hospitals](#hospitals-endpoints)
5. [Data Models](#data-models)
6. [Status Codes](#status-codes)

---

## Overview

MamaGuard is a vital signs monitoring system designed for postpartum mothers. The backend provides APIs for:

- **User Authentication**: Register and login for mothers
- **Video-Based Scanning** ⭐ **NEW**: Record a video and extract vitals (heart rate, respiratory rate)
- **Risk Assessment**: Two-layer risk scoring combining vitals and danger sign checklists
- **Location Services**: Find nearby hospitals in case of emergencies

### Key Features

- **Simple Video Upload**: Record a 15-second (or custom duration) video and upload for analysis
- **Frame Aggregation**: Processes all frames from the video and aggregates results using median values
- **Confidence Scores**: Returns confidence metrics for each vital sign measurement
- **Layer 1 Risk Assessment**: Based on rPPG (remote photoplethysmography) vitals
- **Layer 2 Risk Assessment**: Based on danger sign checklist responses
- **Transparent Risk Scoring**: Audit logs showing why a risk tier was assigned

### Recommended Workflow

1. **Register/Login** → Authenticate user
2. **Complete Onboarding** → Submit health information (gestational history, risk factors, emergency contact)
3. **Record Video** → User records 15-second video (frontend controls duration)
4. **Analyze Video** → Upload video to `/api/vitallens/analyze-video` endpoint ⭐ **NEW**
5. **Submit Checklist** → Report any danger signs observed
6. **Get Risk Score** → Receive comprehensive risk assessment with recommendations

### API Changes

- ✅ **NEW**: [Video Analysis Endpoint](#video-analysis-endpoints) - Simplified video upload model
- 🔄 **Deprecated**: Real-time streaming endpoints (still available for backward compatibility, but not recommended)

---

## Authentication

All protected endpoints require Bearer token authentication via HTTP Bearer scheme.

### Token Format

```
Authorization: Bearer <access_token>
```

### Obtaining a Token

Tokens are obtained by:
1. **POST** `/auth/register` - Creates account and returns token
2. **POST** `/auth/login` - Authenticates existing account and returns token

The returned token is a JWT (JSON Web Token) that must be included in the `Authorization` header for all subsequent requests to protected endpoints.

### Token Expiration

Default token expiration: Configured via `ACCESS_TOKEN_EXPIRE_MINUTES` (typically 24 hours)

---

## Frontend Authorization Guide

### Step-by-Step Implementation

#### 1. After Registration/Login - Store Token

```javascript
// After POST /auth/register or POST /auth/login
const response = await fetch('/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'mother@example.com',
    name: 'Jane Doe',
    phone: '+1234567890',
    password: 'SecurePassword123'
  })
});

const data = await response.json();
const accessToken = data.access_token;

// Store token in localStorage or sessionStorage
localStorage.setItem('access_token', accessToken);
localStorage.setItem('user_id', data.user.id);
localStorage.setItem('user_email', data.user.email);
```

#### 2. Include Token in API Requests

**Always add this header to protected endpoints:**

```javascript
const token = localStorage.getItem('access_token');

const headers = {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${token}`  // ← CRITICAL: Must be "Bearer <token>"
};

// Example: Updating user profile
const response = await fetch('/auth/profile', {
  method: 'PUT',
  headers: headers,
  body: JSON.stringify({
    gestational_history: { pregnancies: 2 },
    known_risk_factors: { hypertension: false },
    emergency_contact_name: 'John Doe',
    emergency_contact_phone: '+1987654321'
  })
});
```

#### 3. Handle 401 Unauthorized Errors

```javascript
async function apiRequest(url, options = {}) {
  const token = localStorage.getItem('access_token');
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  
  // Only add Authorization header if token exists
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  let response = await fetch(url, {
    ...options,
    headers
  });
  
  // If 401, token expired - force re-login
  if (response.status === 401) {
    // Clear stored token
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_id');
    
    // Redirect to login page
    window.location.href = '/login';
    throw new Error('Session expired. Please login again.');
  }
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'API request failed');
  }
  
  return response.json();
}
```

#### 4. Protected Endpoints That Need Token

All these endpoints require `Authorization: Bearer <token>` header:

- ✅ `PUT /auth/profile` - Update onboarding info
- ✅ `GET /auth/me` - Get current user profile
- ✅ `POST /api/vitallens/stream/start` - Start scanning
- ✅ `POST /api/scans/{session_id}/checklist` - Submit checklist
- ✅ `GET /api/scans/{session_id}/risk-score` - Get risk assessment
- ✅ `GET /api/scans/{session_id}/summary` - Get scan summary

#### 5. Unprotected Endpoints (No Token Needed)

These endpoints do NOT require authorization:

- ❌ `POST /auth/register` - Create account
- ❌ `POST /auth/login` - Login
- ❌ `GET /` - Health check
- ❌ `GET /health` - Detailed health check
- ❌ `POST /api/vitallens/stream/process-frame` - Process frame (uses session_id)
- ❌ `GET /api/vitallens/stream/status/{session_id}` - Get stream status
- ❌ `POST /api/vitallens/stream/stop` - Stop stream
- ❌ `GET /api/vitallens/stream/health` - Streaming health
- ❌ `GET /hospitals/nearby` - Find hospitals

### Common Authorization Errors

#### Error: "Could not validate credentials" (401)

**Cause:** Token is missing, invalid, or expired

**Solutions:**
1. Check token is being stored: `console.log(localStorage.getItem('access_token'))`
2. Verify Authorization header format: `Authorization: Bearer <token>` (with space!)
3. Check token hasn't expired (default 24 hours)
4. User should re-login to get fresh token

**Debug code:**
```javascript
// Check what's in localStorage
console.log('Token:', localStorage.getItem('access_token'));
console.log('User ID:', localStorage.getItem('user_id'));

// Make test request and log response
const token = localStorage.getItem('access_token');
console.log('Authorization header:', `Bearer ${token}`);
```

#### Error: "Email already registered" (400)

**Cause:** Account already exists with that email

**Solution:** Use login instead of register, or use different email

#### Error: "User account is inactive" (403)

**Cause:** Account was deactivated

**Solution:** Contact support or create new account

### TypeScript Example (Next.js/React)

```typescript
// utils/apiService.ts
export class ApiService {
  private static BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  static async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = localStorage.getItem('access_token');
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user_id');
      window.location.href = '/login';
      throw new Error('Unauthorized: Please login again');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API error: ${response.statusText}`);
    }

    return response.json();
  }

  static async register(email: string, name: string, phone: string, password: string) {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, name, phone, password }),
    });
  }

  static async login(email: string, password: string) {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  static async updateProfile(gestationalHistory: any, knownRiskFactors: any, emergencyContactName: string, emergencyContactPhone: string) {
    return this.request('/auth/profile', {
      method: 'PUT',
      body: JSON.stringify({
        gestational_history: gestationalHistory,
        known_risk_factors: knownRiskFactors,
        emergency_contact_name: emergencyContactName,
        emergency_contact_phone: emergencyContactPhone,
      }),
    });
  }

  static async startScan(processSignals: boolean = true, model?: string) {
    return this.request('/api/vitallens/stream/start', {
      method: 'POST',
      body: JSON.stringify({ process_signals: processSignals, model }),
    });
  }
}

// Usage in React component:
async function handleStartScan() {
  try {
    const session = await ApiService.startScan();
    console.log('Scan started:', session.session_id);
  } catch (error) {
    console.error('Scan error:', error.message);
    if (error.message.includes('Unauthorized')) {
      // Token expired, redirect to login
      window.location.href = '/login';
    }
  }
}
```

---

## Error Handling

All errors follow a consistent format:

### Error Response Format

```json
{
  "detail": "Error message describing the issue"
}
```

### Common Error Codes

- **400 Bad Request**: Invalid input parameters or business logic violations
- **401 Unauthorized**: Missing or invalid authentication token
- **403 Forbidden**: User account is inactive or insufficient permissions
- **404 Not Found**: Resource not found (session, user, etc.)
- **500 Internal Server Error**: Unexpected server error

---

## API Endpoints

### Health Check

#### GET / - Health Check

Get basic health status of the API.

**URL:** `/`

**Method:** `GET`

**Authentication:** Not required

**Response (200):**
```json
{
  "message": "MamaGuard backend is alive",
  "version": "1.0.0",
  "status": "running"
}
```

---

#### GET /health - Detailed Health Check

Get detailed health information of the API and services.

**URL:** `/health`

**Method:** `GET`

**Authentication:** Not required

**Response (200):**
```json
{
  "status": "healthy",
  "service": "mamaguard-backend",
  "streaming": "available"
}
```

---

## Authentication Endpoints

### POST /auth/register - Register New Mother

Create a new user account for a postpartum mother. Returns JWT token for immediate access. Health information is collected later via the onboarding endpoint.

**URL:** `/auth/register`

**Method:** `POST`

**Authentication:** Not required

**Request Body:**
```json
{
  "email": "mother@example.com",
  "name": "Jane Doe",
  "phone": "+1234567890",
  "password": "SecurePassword123"
}
```

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| email | string (email) | Yes | User's email address (unique) |
| name | string | Yes | Full name of the mother |
| phone | string | Yes | Contact phone number |
| password | string | Yes | Password (8-72 characters, bcrypt limit is 72 bytes) |

**Response (200) - Success:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "mother@example.com",
    "name": "Jane Doe",
    "phone": "+1234567890",
    "is_active": true,
    "created_at": "2026-06-27T10:30:00Z"
  }
}
```

**Responses:**

| Status | Description |
|--------|-------------|
| 200 | Account created successfully, token returned |
| 400 | Email already registered or validation error |
| 500 | Server error during registration |

**Error Examples:**

Email already exists (400):
```json
{
  "detail": "Email already registered"
}
```

---

### POST /auth/login - Login Mother

Authenticate with email and password to obtain an access token.

**URL:** `/auth/login`

**Method:** `POST`

**Authentication:** Not required

**Request Body:**
```json
{
  "email": "mother@example.com",
  "password": "SecurePassword123"
}
```

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| email | string (email) | Yes | User's email address |
| password | string | Yes | User's password |

**Response (200) - Success:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "mother@example.com",
    "name": "Jane Doe",
    "phone": "+1234567890",
    "is_active": true,
    "created_at": "2026-06-27T10:30:00Z"
  }
}
```

**Responses:**

| Status | Description |
|--------|-------------|
| 200 | Authentication successful, token returned |
| 401 | Invalid email or password |
| 403 | User account is inactive |
| 500 | Server error |

**Error Examples:**

Invalid credentials (401):
```json
{
  "detail": "Invalid email or password"
}
```

Inactive account (403):
```json
{
  "detail": "User account is inactive"
}
```

---

### GET /auth/me - Get Current User Profile

Retrieve the authenticated user's profile information.

**URL:** `/auth/me`

**Method:** `GET`

**Authentication:** Required (Bearer Token)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200) - Success:**
```json
{
  "id": 1,
  "email": "mother@example.com",
  "name": "Jane Doe",
  "phone": "+1234567890",
  "is_active": true,
  "created_at": "2026-06-27T10:30:00Z"
}
```

**Responses:**

| Status | Description |
|--------|-------------|
| 200 | User profile retrieved successfully |
| 401 | Invalid or missing authentication token |
| 500 | Server error |

**Error Examples:**

Invalid token (401):
```json
{
  "detail": "Could not validate credentials"
}
```

---

### PUT /auth/profile - Update User Profile (Onboarding)

Update user profile with clinical history and emergency contact information. Called during the onboarding process after registration.

**URL:** `/auth/profile`

**Method:** `PUT`

**Authentication:** Required (Bearer Token)

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "gestational_history": {
    "pregnancies": 2,
    "previous_complications": false
  },
  "known_risk_factors": {
    "hypertension": false,
    "diabetes": false,
    "preeclampsia_history": false
  },
  "emergency_contact_name": "John Doe",
  "emergency_contact_phone": "+1987654321"
}
```

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| gestational_history | object | No | Clinical history information (e.g., pregnancies, previous complications) |
| known_risk_factors | object | No | Pre-existing risk factors (hypertension, diabetes, preeclampsia, etc.) |
| emergency_contact_name | string | No | Emergency contact person's name |
| emergency_contact_phone | string | No | Emergency contact person's phone number |

**Response (200) - Success:**
```json
{
  "id": 1,
  "email": "mother@example.com",
  "name": "Jane Doe",
  "phone": "+1234567890",
  "is_active": true,
  "created_at": "2026-06-27T10:30:00Z"
}
```

**Responses:**

| Status | Description |
|--------|-------------|
| 200 | Profile updated successfully |
| 400 | Invalid input data |
| 401 | Invalid or missing authentication token |
| 500 | Server error during update |

**Error Examples:**

Invalid token (401):
```json
{
  "detail": "Could not validate credentials"
}
```

Update error (500):
```json
{
  "detail": "Profile update failed"
}
```

---

## Video Analysis Endpoints

### ⭐ NEW: Video Analysis for Vital Signs

> **📌 Recommended Approach**: Use the video analysis API instead of real-time streaming for better stability and simpler implementation.

**For comprehensive video analysis documentation, see [VIDEO_ANALYSIS_API.md](./VIDEO_ANALYSIS_API.md)**

#### POST /api/vitallens/analyze-video - Analyze Video for Vitals

Upload a recorded video to extract vital signs (heart rate and respiratory rate).

**URL:** `/api/vitallens/analyze-video`

**Method:** `POST`

**Authentication:** Required (Bearer Token)

**Request Body:**
```json
{
  "video": "base64_encoded_video_data_here",
  "format": "mp4"
}
```

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| video | string | Yes | Base64-encoded video file data |
| format | string | No | Video format (default: "mp4"). Informational only. |

**Response (200) - Success:**
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

**Responses:**

| Status | Description |
|--------|-------------|
| 200 | Video analyzed successfully, vitals extracted |
| 400 | Invalid video data or corrupted file |
| 401 | Invalid or missing authentication token |
| 500 | Video processing error |

**Error Examples:**

Invalid video (400):
```json
{
  "detail": "Video analysis failed: No frames extracted from video"
}
```

**Key Advantages:**

- ✅ Simple: One request with base64 video
- ✅ Stable: Aggregates results from all frames (median values)
- ✅ No streaming complexity: No real-time frame buffering needed
- ✅ Frontend-controlled duration: User decides when to stop recording
- ✅ Better vitals quality: More frames = more stable measurements

**Typical Workflow:**

1. Frontend records 15-second video (or custom duration)
2. Frontend converts video to base64
3. Frontend sends to `POST /api/vitallens/analyze-video`
4. Backend processes all frames and returns vitals
5. Frontend displays vitals and prompts for checklist
6. User submits checklist via `POST /api/scans/{session_id}/checklist`
7. Backend calculates risk score and returns assessment

**Next Steps After Video Analysis:**

After receiving vitals, the workflow continues with:

```
GET /api/scans/{session_id}/checklist          # Get checklist questions
POST /api/scans/{session_id}/checklist          # Submit danger sign responses
GET /api/scans/{session_id}/risk-score          # Get calculated risk tier
GET /api/scans/{session_id}/summary             # Get full assessment
```

---

## Streaming & Vitals Endpoints

⚠️ **DEPRECATED**: These endpoints are still functional but not recommended. Use [Video Analysis](#video-analysis-endpoints) instead.


### POST /api/vitallens/stream/start - Start Streaming Session

Initiate a new real-time streaming session for vital sign processing.

**URL:** `/api/vitallens/stream/start`

**Method:** `POST`

**Authentication:** Required (Bearer Token)

**Request Body:**
```json
{
  "process_signals": true,
  "model": "pos"
}
```

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| process_signals | boolean | No | Enable signal processing (default: true) |
| model | string | No | VitalLens model to use (e.g., "pos", "vitallens") |

**Response (200) - Success:**
```json
{
  "session_id": "session_123456789",
  "status": "started",
  "message": "Streaming session session_123456789 started"
}
```

**Responses:**

| Status | Description |
|--------|-------------|
| 200 | Streaming session created successfully |
| 401 | Invalid or missing authentication token |
| 500 | Failed to initialize streaming service |

**Error Examples:**

Server error (500):
```json
{
  "detail": "Failed to initialize streaming service"
}
```

---

### POST /api/vitallens/stream/process-frame - Process Camera Frame

Process a single frame from the camera stream to extract vital signs.

**URL:** `/api/vitallens/stream/process-frame`

**Method:** `POST`

**Authentication:** Not required (session-based)

**Request Body:**
```json
{
  "session_id": "session_123456789",
  "frame": "iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAALEgAACxIB0t1+/AAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAFWSURBVEiJ7ZSxDYNADIZ/8QMsDuCA8AoMyAA4IBMyARuQsAAJEyBhBhawAQwwoQwZQVmBhMSBiOuSU4lOp/vd9/vnzgfSNIEkSZIkSZIkSZIkSZIkSZL0t8vlQpIkAMiyDN/3ieMYURQRhiFhGJJlGVEUkWUZrutyv9+RpimDwQDf96nVahiGQbvdRlEUqtUqiqJgWRa2bQOwLIvi8XgQ58F+v9/zfZ98Ps/3/fP5HA6H",
  "timestamp": 1656316200.123
}
```

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| session_id | string | Yes | Streaming session ID from /start endpoint |
| frame | string | Yes | Base64-encoded RGB24 frame (40x40x3 pixels) |
| timestamp | float | Yes | Frame timestamp in seconds (Unix time) |

**Response (200) - Success:**
```json
{
  "session_id": "session_123456789",
  "frame_number": 120,
  "heart_rate": 78.5,
  "heart_rate_confidence": 0.92,
  "respiratory_rate": 18.2,
  "respiratory_rate_confidence": 0.85,
  "status": "processing"
}
```

**Response Parameters:**

| Field | Type | Description |
|-------|------|-------------|
| session_id | string | Current streaming session ID |
| frame_number | int | Cumulative frame count in session |
| heart_rate | float | Estimated heart rate in beats per minute (bpm) |
| heart_rate_confidence | float | Confidence score (0-1) for HR estimate |
| respiratory_rate | float | Estimated respiratory rate in breaths per minute (rpm) |
| respiratory_rate_confidence | float | Confidence score (0-1) for RR estimate |
| status | string | Current processing status |

**Responses:**

| Status | Description |
|--------|-------------|
| 200 | Frame processed successfully |
| 400 | Invalid session or frame format |
| 404 | Session not found |
| 500 | Processing error |

**Error Examples:**

Session not found (404):
```json
{
  "detail": "Session session_123456789 not found"
}
```

Processing error (500):
```json
{
  "detail": "Failed to process frame: Frame dimensions incorrect"
}
```

---

### GET /api/vitallens/stream/status/{session_id} - Get Stream Status

Retrieve current status and vital signs for an active streaming session.

**URL:** `/api/vitallens/stream/status/{session_id}`

**Method:** `GET`

**Authentication:** Not required

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| session_id | string | Streaming session ID |

**Response (200) - Success:**
```json
{
  "session_id": "session_123456789",
  "status": "active",
  "frames_processed": 250,
  "heart_rate": 78.5,
  "heart_rate_confidence": 0.92,
  "respiratory_rate": 18.2,
  "respiratory_rate_confidence": 0.85,
  "last_update": "2026-06-27T10:35:45Z",
  "duration_seconds": 125.5
}
```

**Response Parameters:**

| Field | Type | Description |
|-------|------|-------------|
| session_id | string | Current streaming session ID |
| status | string | Session status ("active", "stopped", etc.) |
| frames_processed | int | Total frames processed in session |
| heart_rate | float | Latest heart rate estimate (bpm) |
| heart_rate_confidence | float | Confidence score (0-1) |
| respiratory_rate | float | Latest respiratory rate estimate (rpm) |
| respiratory_rate_confidence | float | Confidence score (0-1) |
| last_update | datetime | Timestamp of last processed frame |
| duration_seconds | float | Session duration in seconds |

**Responses:**

| Status | Description |
|--------|-------------|
| 200 | Session status retrieved successfully |
| 404 | Session not found |
| 500 | Server error |

**Error Examples:**

Session not found (404):
```json
{
  "detail": "Session session_123456789 not found"
}
```

---

### POST /api/vitallens/stream/stop - Stop Streaming Session

Stop an active streaming session and retrieve final vital sign estimates.

**URL:** `/api/vitallens/stream/stop`

**Method:** `POST`

**Authentication:** Not required (session-based)

**Request Body:**
```json
{
  "session_id": "session_123456789"
}
```

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| session_id | string | Yes | Streaming session ID to stop |

**Response (200) - Success:**
```json
{
  "session_id": "session_123456789",
  "status": "stopped",
  "frames_processed": 350,
  "heart_rate": 78.5,
  "heart_rate_confidence": 0.92,
  "respiratory_rate": 18.2,
  "respiratory_rate_confidence": 0.85,
  "duration_seconds": 175.3,
  "message": "Streaming session stopped successfully"
}
```

**Response Parameters:**

| Field | Type | Description |
|-------|------|-------------|
| session_id | string | Streaming session ID |
| status | string | Session status (now "stopped") |
| frames_processed | int | Total frames processed |
| heart_rate | float | Final heart rate estimate (bpm) |
| heart_rate_confidence | float | Confidence score (0-1) |
| respiratory_rate | float | Final respiratory rate estimate (rpm) |
| respiratory_rate_confidence | float | Confidence score (0-1) |
| duration_seconds | float | Total session duration |
| message | string | Success message |

**Responses:**

| Status | Description |
|--------|-------------|
| 200 | Session stopped successfully |
| 400 | Invalid session ID |
| 500 | Error stopping session |

---

### GET /api/vitallens/stream/health - Streaming Service Health

Check the health status of the streaming service.

**URL:** `/api/vitallens/stream/health`

**Method:** `GET`

**Authentication:** Not required

**Response (200) - Success:**
```json
{
  "status": "healthy",
  "active_sessions": 3
}
```

**Response Parameters:**

| Field | Type | Description |
|-------|------|-------------|
| status | string | Health status ("healthy", "degraded", etc.) |
| active_sessions | int | Number of active streaming sessions |

---

## Checklist & Risk Assessment Endpoints

### POST /api/scans/{session_id}/checklist - Submit Danger Sign Checklist

Submit danger sign responses for a scan session to calculate comprehensive risk tier.

**URL:** `/api/scans/{session_id}/checklist`

**Method:** `POST`

**Authentication:** Required (Bearer Token)

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| session_id | string | Streaming session ID |

**Request Body:**
```json
{
  "severe_headache": false,
  "blurred_vision": false,
  "abdominal_pain": true,
  "sudden_swelling": false,
  "shortness_of_breath": false
}
```

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| severe_headache | boolean | Yes | Presence of severe headache |
| blurred_vision | boolean | Yes | Presence of blurred or flashing vision |
| abdominal_pain | boolean | Yes | Presence of upper abdominal pain |
| sudden_swelling | boolean | Yes | Presence of sudden swelling |
| shortness_of_breath | boolean | Yes | Presence of shortness of breath |

**Response (200) - Success:**
```json
{
  "session_id": "session_123456789",
  "danger_sign_count": 1,
  "risk_tier": "MODERATE",
  "risk_score": 65.5,
  "message": "Checklist submitted. Risk score calculated."
}
```

**Response Parameters:**

| Field | Type | Description |
|-------|------|-------------|
| session_id | string | Session ID |
| danger_sign_count | int | Total number of danger signs present (0-5) |
| risk_tier | string | Risk tier: "LOW", "MODERATE", "HIGH", "CRITICAL" |
| risk_score | float | Numerical risk score (0-100) |
| message | string | Status message |

**Responses:**

| Status | Description |
|--------|-------------|
| 200 | Checklist submitted, risk score calculated |
| 400 | Session not found or invalid state |
| 401 | Invalid or missing authentication token |
| 404 | Scan session not found |
| 500 | Server error |

**Error Examples:**

Session not found (404):
```json
{
  "detail": "Scan session not found"
}
```

Session not active (400):
```json
{
  "detail": "Can only submit checklist for active sessions"
}
```

---

### GET /api/scans/{session_id}/risk-score - Get Risk Assessment

Retrieve detailed risk assessment for a completed scan session with transparent scoring rules.

**URL:** `/api/scans/{session_id}/risk-score`

**Method:** `GET`

**Authentication:** Required (Bearer Token)

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| session_id | string | Scan session ID |

**Response (200) - Success:**
```json
{
  "session_id": "session_123456789",
  "risk_tier": "MODERATE",
  "risk_score": 65.5,
  "heart_rate": 78.5,
  "hrv": 45.2,
  "danger_signs_count": 1,
  "rules_applied": {
    "elevated_heart_rate": true,
    "low_hrv": false,
    "danger_signs_present": true,
    "known_risk_factors": false
  },
  "recommendation": "Monitor closely. Seek medical attention if symptoms worsen.",
  "created_at": "2026-06-27T10:35:45Z"
}
```

**Response Parameters:**

| Field | Type | Description |
|-------|------|-------------|
| session_id | string | Session ID |
| risk_tier | string | Final risk tier classification |
| risk_score | float | Numerical risk score (0-100) |
| heart_rate | float | Heart rate from vital signs (bpm) |
| hrv | float | Heart rate variability measurement |
| danger_signs_count | int | Number of danger signs reported |
| rules_applied | object | Dictionary showing which scoring rules triggered |
| recommendation | string | Clinical recommendation based on risk tier |
| created_at | datetime | Session completion timestamp |

**Responses:**

| Status | Description |
|--------|-------------|
| 200 | Risk assessment retrieved successfully |
| 400 | Session not completed yet |
| 401 | Invalid or missing authentication token |
| 404 | Scan session not found |
| 500 | Server error |

**Error Examples:**

Session not completed (400):
```json
{
  "detail": "Risk score only available for completed sessions"
}
```

---

### GET /api/scans/{session_id}/summary - Get Scan Summary

Retrieve complete scan session summary with all results and metadata.

**URL:** `/api/scans/{session_id}/summary`

**Method:** `GET`

**Authentication:** Required (Bearer Token)

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| session_id | string | Scan session ID |

**Response (200) - Success:**
```json
{
  "session_id": "session_123456789",
  "total_frames": 350,
  "heart_rate": 78.5,
  "hrv": 45.2,
  "risk_tier": "MODERATE",
  "risk_score": 65.5,
  "checklist": {
    "id": 42,
    "scan_session_id": "session_123456789",
    "severe_headache": false,
    "blurred_vision": false,
    "abdominal_pain": true,
    "sudden_swelling": false,
    "shortness_of_breath": false,
    "danger_sign_count": 1,
    "created_at": "2026-06-27T10:35:45Z"
  },
  "recommendation": "Monitor closely. Seek medical attention if symptoms worsen.",
  "duration_seconds": 175.3,
  "created_at": "2026-06-27T10:35:45Z"
}
```

**Response Parameters:**

| Field | Type | Description |
|-------|------|-------------|
| session_id | string | Scan session ID |
| total_frames | int | Total frames processed during scan |
| heart_rate | float | Average or final heart rate (bpm) |
| hrv | float | Heart rate variability |
| risk_tier | string | Risk tier classification |
| risk_score | float | Numerical risk score |
| checklist | object | Submitted danger sign checklist |
| recommendation | string | Clinical recommendation |
| duration_seconds | float | Total scan duration |
| created_at | datetime | Scan completion time |

**Responses:**

| Status | Description |
|--------|-------------|
| 200 | Scan summary retrieved successfully |
| 401 | Invalid or missing authentication token |
| 404 | Scan session not found |
| 500 | Server error |

---

## Hospitals Endpoints

### GET /hospitals/nearby - Find Nearby Hospitals

Find hospitals near a given location within a specified radius.

**URL:** `/hospitals/nearby`

**Method:** `GET`

**Authentication:** Not required

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| lat | float | Yes | Latitude of search center |
| lon | float | Yes | Longitude of search center |
| radius | integer | No | Search radius in meters (default: 5000, min: 100, max: 50000) |

**Example Request:**
```
GET /hospitals/nearby?lat=40.7128&lon=-74.0060&radius=10000
```

**Response (200) - Success:**
```json
{
  "count": 3,
  "hospitals": [
    {
      "name": "Metropolitan Hospital",
      "latitude": 40.7150,
      "longitude": -74.0080,
      "address": "1901 First Avenue, New York, NY 10128",
      "distance": 542.3
    },
    {
      "name": "Central Medical Center",
      "latitude": 40.7100,
      "longitude": -74.0040,
      "address": "900 Amsterdam Avenue, New York, NY 10025",
      "distance": 821.5
    },
    {
      "name": "East Side Hospital",
      "latitude": 40.7170,
      "longitude": -74.0050,
      "address": "430 East 68th Street, New York, NY 10065",
      "distance": 1243.7
    }
  ]
}
```

**Response Parameters:**

| Field | Type | Description |
|-------|------|-------------|
| count | integer | Number of hospitals found |
| hospitals | array | List of hospital objects |
| hospitals[].name | string | Hospital name |
| hospitals[].latitude | float | Hospital latitude |
| hospitals[].longitude | float | Hospital longitude |
| hospitals[].address | string | Hospital address (nullable) |
| hospitals[].distance | float | Distance from search center in meters |

**Responses:**

| Status | Description |
|--------|-------------|
| 200 | Hospitals found successfully |
| 400 | Invalid latitude/longitude or radius |
| 500 | Server error |

**Error Examples:**

Invalid radius (400):
```json
{
  "detail": "Query validation error: radius must be between 100 and 50000 meters"
}
```

---

## Data Models

### User Model

```json
{
  "id": 1,
  "email": "mother@example.com",
  "name": "Jane Doe",
  "phone": "+1234567890",
  "is_active": true,
  "password_hash": "hashed_password",
  "gestational_history": {},
  "known_risk_factors": {},
  "emergency_contact_name": "John Doe",
  "emergency_contact_phone": "+1987654321",
  "created_at": "2026-06-27T10:30:00Z"
}
```

### Scan Session Model

```json
{
  "id": "session_123456789",
  "user_id": 1,
  "started_at": "2026-06-27T10:30:00Z",
  "ended_at": "2026-06-27T10:35:45Z",
  "status": "completed",
  "heart_rate": 78.5,
  "hrv": 45.2,
  "respiratory_rate": 18.2,
  "total_frames": 350,
  "risk_tier": "MODERATE",
  "risk_score": 65.5
}
```

### Risk Tiers

| Tier | Score Range | Description |
|------|-------------|-------------|
| LOW | 0-30 | Normal vital signs, no danger signs |
| MODERATE | 31-60 | Slightly elevated vitals or 1-2 danger signs |
| HIGH | 61-85 | Significantly elevated vitals or 3+ danger signs |
| CRITICAL | 86-100 | Severe vitals or multiple critical danger signs |

---

## Status Codes

### Success Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request successful |

### Client Error Codes

| Code | Meaning |
|------|---------|
| 400 | Bad Request - Invalid parameters or business logic error |
| 401 | Unauthorized - Missing or invalid authentication token |
| 403 | Forbidden - User account inactive or insufficient permissions |
| 404 | Not Found - Resource does not exist |

### Server Error Codes

| Code | Meaning |
|------|---------|
| 500 | Internal Server Error - Unexpected server error |

---

## Example Workflows

### Complete User Registration & Vital Signs Scanning Workflow

```
1. Register (Create Account)
   POST /auth/register
   {
     "email": "mother@example.com",
     "name": "Jane Doe",
     "phone": "+1234567890",
     "password": "SecurePassword123"
   }
   → Receive access_token

2. Onboarding (Update Health Information)
   PUT /auth/profile
   Headers: Authorization: Bearer <token>
   {
     "gestational_history": {"pregnancies": 2},
     "known_risk_factors": {"hypertension": false},
     "emergency_contact_name": "John Doe",
     "emergency_contact_phone": "+1987654321"
   }
   → Profile updated with clinical history

3. Start Streaming Session
   POST /api/vitallens/stream/start
   → Receive session_id

4. Process Frames (repeat for each camera frame)
   POST /api/vitallens/stream/process-frame
   → Get real-time heart rate & respiratory rate

5. Submit Danger Sign Checklist
   POST /api/scans/{session_id}/checklist
   → Get risk_tier and risk_score

6. Get Complete Risk Assessment
   GET /api/scans/{session_id}/risk-score
   → Get detailed risk analysis with recommendations

7. Get Full Scan Summary
   GET /api/scans/{session_id}/summary
   → Get all results combined
```

### Login & Vital Signs Scanning Workflow (Returning User)

```
1. Login
   POST /auth/login
   {
     "email": "mother@example.com",
     "password": "SecurePassword123"
   }
   → Receive access_token

2. Start Streaming Session
   POST /api/vitallens/stream/start
   → Receive session_id

3. Process Frames (repeat for each camera frame)
   POST /api/vitallens/stream/process-frame
   → Get real-time heart rate & respiratory rate

4. Submit Danger Sign Checklist
   POST /api/scans/{session_id}/checklist
   → Get risk_tier and risk_score

5. Get Complete Risk Assessment
   GET /api/scans/{session_id}/risk-score
   → Get detailed risk analysis with recommendations
```

### Emergency Hospital Lookup Workflow

```
1. User is in critical condition
   
2. Get current location coordinates (from mobile device)

3. Find nearby hospitals
   GET /hospitals/nearby?lat=40.7128&lon=-74.0060&radius=10000
   → Get list of nearest hospitals

4. Navigate user to nearest hospital using coordinates
```

---

## Rate Limiting

Currently, no rate limiting is enforced. For production deployment:
- Implement rate limiting per user
- Suggest: 100 requests/minute per authenticated user
- Suggest: 10 requests/minute per IP for non-authenticated endpoints

---

## CORS

The API enables CORS for all origins. In production:
- Configure `allow_origins` to specific frontend domain
- Restrict allowed methods and headers as needed
- Current setting: `allow_origins=["*"]` (development only)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-27 | Initial API release |

---

## Support

For issues or questions about the API:
1. Check error messages in responses
2. Review audit logs via risk-score endpoint
3. Contact development team with session IDs for debugging

---

*Last Updated: 2026-06-27*
