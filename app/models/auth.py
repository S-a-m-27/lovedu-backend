from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserResponse(BaseModel):
    id: str
    email: str
    email_verified: Optional[bool] = False
    created_at: Optional[datetime] = None
    user_metadata: Optional[dict] = None
    
    class Config:
        from_attributes = True

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    user_metadata: Optional[dict] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class VerifyTokenRequest(BaseModel):
    token: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: Optional[int] = None
    token_type: str = "bearer"
    user: UserResponse

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None

class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password: str
