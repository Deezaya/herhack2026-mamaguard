# MamaGuard Backend - Database Setup & Architecture

## ✅ What's Been Created

### Database Layer
- **SQLAlchemy ORM Models** for:
  - `User` - Mother profiles with medical history
  - `ScanSession` - rPPG + checklist sessions
  - `ChecklistResponse` - WHO-aligned danger signs
  - `RiskAuditLog` - Transparent risk scoring audit trail

### API Endpoints

#### Authentication (Layer 0)
```
POST   /auth/register           - Register new mother
POST   /auth/login              - Login with email/password
GET    /auth/me                 - Get current user profile
```

#### Scanning & Vitals (Layer 1: rPPG)
```
POST   /api/vitallens/stream/start        - Begin face scan session
POST   /api/vitallens/stream/process-frame - Stream individual frames
GET    /api/vitallens/stream/status/{id}  - Poll live vitals
POST   /api/vitallens/stream/stop         - End session, save vitals
```

#### Checklist & Risk (Layer 2 + 3)
```
POST   /api/scans/{session_id}/checklist      - Submit danger signs
GET    /api/scans/{session_id}/risk-score     - Get risk tier + explanation
GET    /api/scans/{session_id}/summary        - Complete scan summary
```

### Core Services

#### Risk Scoring Engine (`app/core/risk_scoring.py`)
- **Transparent, rules-based** risk calculation
- Combines Layer 1 (vitals) + Layer 2 (danger signs)
- Produces: `Low` / `Watch` / `Urgent`
- Full audit trail of scoring decisions
- NOT a diagnostic tool - supports clinical decision-making

#### Streaming Service (`app/services/streaming_service.py`)
- Manages concurrent rPPG sessions
- Receives frames, calculates heart rate/HRV in real-time
- Saves to database on session completion
- Thread-safe with session locking

#### Authentication (`app/core/security.py`)
- JWT-based token authentication
- Bcrypt password hashing
- 24-hour token expiration (configurable)

---

## 🗄️ Database Setup

### Option 1: Neon PostgreSQL (Recommended)

1. **Create Neon project:**
   - Go to https://console.neon.tech
   - Create a new project
   - Get connection string from "Connection string" tab

2. **Update `.env`:**
   ```env
   DATABASE_URL=postgresql://username:password@ep-xxxxx.us-east-1.neon.tech/mamaguard
   ```

3. **Tables will auto-create on first run** (via SQLAlchemy)

### Option 2: Local PostgreSQL

```bash
# Install PostgreSQL locally
# Create database
createdb mamaguard

# Update .env
DATABASE_URL=postgresql://localhost/mamaguard
```

---

## 🚀 Running the Backend

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up `.env`** (already partially configured):
   ```bash
   # Update these:
   DATABASE_URL=postgresql://...
   VITALLENS_API_KEY=your_api_key
   SECRET_KEY=your-secure-secret
   ```

3. **Start the server:**
   ```bash
   uvicorn app.main:app --reload
   ```

4. **Access API docs:**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

---

## 📊 Data Flow

```
Frontend (Camera)
    ↓
1. POST /auth/register              (Create account)
    ↓
2. POST /auth/login                 (Get JWT token)
    ↓
3. POST /api/vitallens/stream/start (Begin rPPG session)
    ↓
4. Loop: POST /api/vitallens/stream/process-frame
    (30-60 frames, calculates heart rate in real-time)
    ↓
5. POST /api/vitallens/stream/stop  (Save vitals to DB)
    ↓
6. POST /api/scans/{session_id}/checklist
    (Submit danger signs → database saves + calculates risk)
    ↓
7. GET /api/scans/{session_id}/risk-score
    (Returns risk tier + transparent rules explanation)
    ↓
Database saves:
├── users
├── scan_sessions (heart_rate, hrv, risk_tier, risk_score)
├── checklist_responses (danger sign flags)
└── risk_audit_log (transparent scoring rules)
```

---

## 🔒 Security Notes

- **JWT Tokens:** Change `SECRET_KEY` in production to a strong random string
- **Database:** Use connection pooling with Neon
- **CORS:** Update `allow_origins` in `app/main.py` to specify frontend domains
- **Password Hashing:** Using bcrypt with automatic salt generation

---

## 🧪 Testing

### 1. Register a user
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mama@example.com",
    "name": "Mama",
    "phone": "08012345678",
    "password": "SecurePassword123",
    "known_risk_factors": {"prior_hypertension": false}
  }'
```

Response:
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": { "id": 1, "email": "mama@example.com", ... }
}
```

### 2. Start streaming (with token)
```bash
TOKEN="eyJhbGc..."
curl -X POST http://localhost:8000/api/vitallens/stream/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"process_signals": true}'
```

---

## 📝 Next Steps

### Immediate (Before Demo)
- [ ] Set up Neon database
- [ ] Update `DATABASE_URL` in `.env`
- [ ] Test `/auth/register` and `/auth/login`
- [ ] Test streaming endpoints with test video

### Frontend Integration (Your team)
- [ ] Implement camera capture component
- [ ] Call streaming endpoints with frames
- [ ] Submit checklist after scan
- [ ] Display risk tier results

### Future Enhancements
- [ ] SMS/WhatsApp escalation alerts (Layer 3 Phase 2)
- [ ] GPS-based hospital finder endpoint
- [ ] NHIA/HMO data integration
- [ ] Analytics dashboard

---

## 📚 Key Files

| File | Purpose |
|------|---------|
| `app/models/models.py` | Database schema |
| `app/core/risk_scoring.py` | Risk tier calculation |
| `app/core/security.py` | JWT + password auth |
| `app/services/streaming_service.py` | rPPG session management |
| `app/routers/auth.py` | Auth endpoints |
| `app/routers/streaming.py` | Streaming endpoints |
| `app/routers/checklist.py` | Risk scoring endpoints |
| `app/main.py` | FastAPI app setup |

---

## 🆘 Troubleshooting

**"No module named 'vitallens'"**
```bash
pip install vitallens
```

**"Database connection failed"**
- Check `DATABASE_URL` in `.env`
- Verify Neon credentials
- Test with `psql` CLI first

**"JWT token invalid"**
- Token may have expired (24 hours)
- User not found in database
- `SECRET_KEY` mismatch

---

**Questions?** Check the FastAPI docs at http://localhost:8000/docs
