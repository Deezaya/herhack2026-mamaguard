from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    name: str
    phone: str


class UserRegister(UserBase):
    password: str = Field(min_length=8, description="Password must be at least 8 characters")
    gestational_history: Optional[dict] = Field(default=None, description="Clinical history")
    known_risk_factors: Optional[dict] = Field(default=None, description="Known risk factors")
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
