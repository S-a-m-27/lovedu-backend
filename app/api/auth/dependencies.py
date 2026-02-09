from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.supabase_service import SupabaseService
from app.models.auth import UserResponse
from typing import Optional
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserResponse:
    """
    Verify JWT token and return current user
    """
    logger.info("🔐 get_current_user dependency called")
    token = credentials.credentials
    token_preview = token[:20] + "..." if len(token) > 20 else token
    logger.debug(f"Token preview: {token_preview}")
    
    supabase_service = SupabaseService()
    
    try:
        logger.info("🔍 Verifying token in get_current_user...")
        # Verify token with Supabase
        response = supabase_service.verify_token(token)
        user = response.user
        
        if not user:
            logger.warning("⚠️  Token verification returned no user in get_current_user")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.info(f"✅ Token verified in get_current_user for: {user.email}")
        
        return UserResponse(
            id=user.id,
            email=user.email,
            email_verified=user.email_confirmed_at is not None,
            created_at=user.created_at,
            user_metadata=user.user_metadata or {}
        )
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Could not validate credentials: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[UserResponse]:
    """
    Optional authentication - returns None if no token provided
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

