import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Import routers
from app.routers import streaming, auth, checklist, hospital
from app.services.streaming_service import get_streaming_service
from app.core.database import engine
from app.models.models import Base

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MamaGuard Backend",
    description="Real-time vitals monitoring backend for postpartum mothers",
    version="1.0.0"
)

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
except Exception as e:
    logger.error(f"Failed to create database tables: {e}")

# Initialize VitalLens
def initialize_vitallens():
    """Initialize VitalLens with API key"""
    try:
        from vitallens import VitalLens
        
        api_key = os.getenv("VITALLENS_API_KEY")
        if not api_key:
            logger.warning("VITALLENS_API_KEY not set. Using local 'pos' method only.")
            vitallens = VitalLens(method="pos")
        else:
            logger.info("Initializing VitalLens with API key")
            vitallens = VitalLens(method="vitallens", api_key=api_key)
        
        # Initialize streaming service
        streaming_service = get_streaming_service()
        streaming_service.initialize(vitallens)
        logger.info("VitalLens streaming service initialized")
        return vitallens
    except Exception as e:
        logger.error(f"Failed to initialize VitalLens: {e}")
        raise

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        initialize_vitallens()
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

# Include routers
app.include_router(auth.router)
app.include_router(streaming.router)
app.include_router(checklist.router)
app.include_router(hospital.router)

@app.get("/")
def read_root():
    """Health check endpoint"""
    return {
        "message": "MamaGuard backend is alive",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "service": "mamaguard-backend",
        "streaming": "available"
    }
