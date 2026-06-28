from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.models.models import User
from app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserResponse, UserProfileUpdate
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

oauth2_scheme = HTTPBearer()

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new mother profile.
    
    Returns JWT token for immediate access.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    try:
        # Create new user
        db_user = User(
            email=user_data.email,
            name=user_data.name,
            phone=user_data.phone,
            password_hash=hash_password(user_data.password),
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"User registered: {db_user.email}")
        
        # Create access token
        access_token = create_access_token(data={"sub": str(db_user.id), "email": db_user.email})
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse.from_orm(db_user)
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Login with email and password.
    
    Returns JWT token for accessing protected endpoints.
    """
    # Find user by email
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    
    logger.info(f"User logged in: {user.email}")
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse.from_orm(user)
    )


async def get_current_user_dependency(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Dependency to get current authenticated user from JWT token"""
    from app.core.security import decode_token

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    return user


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: User = Depends(get_current_user_dependency),
):
    """Get current authenticated user's profile"""
    return UserResponse.from_orm(current_user)


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """
    Update user profile with clinical history and emergency contact (onboarding).
    
    This endpoint is called after registration to collect health and emergency information.
    """
    try:
        # Update user fields
        if profile_data.gestational_history is not None:
            current_user.gestational_history = profile_data.gestational_history
        if profile_data.known_risk_factors is not None:
            current_user.known_risk_factors = profile_data.known_risk_factors
        if profile_data.emergency_contact_name is not None:
            current_user.emergency_contact_name = profile_data.emergency_contact_name
        if profile_data.emergency_contact_phone is not None:
            current_user.emergency_contact_phone = profile_data.emergency_contact_phone
        
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"User profile updated: {current_user.email}")
        
        return UserResponse.from_orm(current_user)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Profile update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed"
        )
