from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from app.models.auth import LoginRequest, SignupRequest, UserResponse, TokenResponse, VerifyTokenRequest, RefreshTokenRequest, AuthResponse, UpdateProfileRequest, UpdatePasswordRequest
from app.services.supabase_service import SupabaseService
from app.api.auth.dependencies import get_current_user
from supabase import Client
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    supabase_service: SupabaseService = Depends(lambda: SupabaseService())
):
    """
    Login user with email and password
    """
    logger.info(f"📥 Login request received for email: {request.email}")
    logger.debug(f"   Request details - Email: {request.email}, Password length: {len(request.password) if request.password else 0}")
    
    try:
        logger.info(f"🔑 Step 1: Calling sign_in service for: {request.email}")
        response = supabase_service.sign_in(request.email, request.password)
        logger.debug(f"   Step 1 completed - Response received: {type(response)}")
        
        if not response.session:
            error_msg = "Invalid credentials - no session returned"
            logger.warning(f"⚠️  {error_msg} for: {request.email}")
            logger.debug(f"   Response object: {response}")
            logger.debug(f"   Response has session: {hasattr(response, 'session')}")
            if hasattr(response, 'user'):
                logger.debug(f"   Response has user: {response.user}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        logger.info(f"🔑 Step 2: Extracting session data")
        session = response.session
        user = session.user
        logger.debug(f"   Session extracted - User ID: {user.id}, Email: {user.email}")
        logger.debug(f"   Session has access_token: {hasattr(session, 'access_token')}")
        logger.debug(f"   Session has refresh_token: {hasattr(session, 'refresh_token')}")
        
        logger.info(f"✅ Login successful for: {request.email} (User ID: {user.id})")
        logger.debug(f"   Returning AuthResponse with token")
        
        return AuthResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            expires_in=session.expires_in,
            token_type="bearer",
            user=UserResponse(
                id=user.id,
                email=user.email,
                email_verified=user.email_confirmed_at is not None,
                created_at=user.created_at,
                user_metadata=user.user_metadata or {}
            )
        )
    except HTTPException as http_ex:
        logger.error(f"❌ HTTP Exception in login - Status: {http_ex.status_code}, Detail: {http_ex.detail}")
        logger.debug(f"   HTTP Exception headers: {http_ex.headers}")
        raise
    except ValueError as ve:
        error_msg = f"ValueError in login: {str(ve)}"
        logger.error(f"❌ {error_msg} - Email: {request.email}")
        logger.exception("Full ValueError traceback:")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Login failed: {str(ve)}"
        )
    except Exception as e:
        error_msg = f"Login failed: {str(e)}"
        error_type = type(e).__name__
        logger.error(f"❌ {error_msg} - Email: {request.email}")
        logger.error(f"   Exception Type: {error_type}")
        logger.error(f"   Exception Args: {e.args if hasattr(e, 'args') else 'N/A'}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Login failed: {str(e)}"
        )

@router.post("/signup", response_model=AuthResponse)
async def signup(
    request: SignupRequest,
    background_tasks: BackgroundTasks,
    supabase_service: SupabaseService = Depends(lambda: SupabaseService())
):
    """
    Sign up new user - non-blocking (returns immediately, sends email asynchronously)
    """
    logger.info(f"📥 Signup request received for email: {request.email}")
    logger.debug(f"   Request details - Email: {request.email}, Password length: {len(request.password) if request.password else 0}")
    if request.user_metadata:
        logger.debug(f"   User metadata: {request.user_metadata}")
    
    try:
        logger.info(f"📝 Step 1: Calling sign_up service for: {request.email}")
        
        # Build user metadata from request
        user_metadata = request.user_metadata or {}
        if request.full_name:
            user_metadata["full_name"] = request.full_name
        if request.date_of_birth:
            user_metadata["date_of_birth"] = request.date_of_birth
        
        # Create user quickly using admin API (non-blocking)
        response = supabase_service.sign_up(
            request.email, 
            request.password, 
            user_metadata
        )
        logger.debug(f"   Step 1 completed - Response received: {type(response)}")
        logger.debug(f"   Response has user: {hasattr(response, 'user')}")
        
        # Check if user was created
        if not hasattr(response, 'user') or not response.user:
            error_msg = "Signup failed - no user object returned"
            logger.warning(f"⚠️  {error_msg} for: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Signup failed - user creation failed"
            )
        
        user = response.user
        logger.info(f"✅ User created successfully for: {request.email} (User ID: {user.id})")
        
        # Add background task to send verification email asynchronously
        # This doesn't block the response and prevents timeout issues
        background_tasks.add_task(
            supabase_service.send_verification_email,
            request.email
        )
        logger.info(f"📧 Verification email queued for background sending to: {request.email}")
        
        # Return success immediately (non-blocking)
        # User needs to verify email before they can log in
        raise HTTPException(
            status_code=status.HTTP_200_OK,
            detail="Account created successfully. Please check your email to confirm your account before logging in."
        )
    except HTTPException as http_ex:
        logger.error(f"❌ HTTP Exception in signup - Status: {http_ex.status_code}, Detail: {http_ex.detail}")
        raise
    except ValueError as ve:
        error_msg = f"ValueError in signup: {str(ve)}"
        logger.error(f"❌ {error_msg} - Email: {request.email}")
        logger.exception("Full ValueError traceback:")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Signup failed: {str(ve)}"
        )
    except Exception as e:
        error_str = str(e).lower()
        
        # Check for rate limit errors and provide better status code
        if "rate limit" in error_str or "too many" in error_str:
            error_msg = "Too many signup attempts. Please wait a few minutes before trying again."
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
            logger.warning(f"⚠️  Rate limit exceeded for: {request.email}")
        else:
            error_msg = f"Signup failed: {str(e)}"
            status_code = status.HTTP_400_BAD_REQUEST
        
        error_type = type(e).__name__
        logger.error(f"❌ {error_msg} - Email: {request.email}")
        logger.error(f"   Exception Type: {error_type}")
        logger.error(f"   Exception Args: {e.args if hasattr(e, 'args') else 'N/A'}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status_code,
            detail=error_msg
        )

@router.post("/verify-token", response_model=UserResponse)
async def verify_token(
    request: VerifyTokenRequest,
    supabase_service: SupabaseService = Depends(lambda: SupabaseService())
):
    """
    Verify JWT token and return user information
    """
    logger.info("📥 Verify token request received")
    try:
        token = request.token
        if not token:
            logger.warning("⚠️  Verify token request missing token")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token is required"
            )
        
        # Log token details (safely)
        token_length = len(token) if token else 0
        token_preview = token[:20] + "..." if token and len(token) > 20 else token or "None"
        logger.debug(f"   Token length: {token_length}, preview: {token_preview}")
        
        logger.info("🔐 Verifying token...")
        try:
            response = supabase_service.verify_token(token)
        except ValueError as ve:
            # Configuration errors (missing env vars, etc.)
            error_msg = f"Configuration error: {str(ve)}"
            logger.error(f"❌ {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )
        except Exception as verify_error:
            # Supabase verification errors
            error_type = type(verify_error).__name__
            error_str = str(verify_error)
            
            logger.error(f"❌ Token verification failed: {error_type} - {error_str}")
            logger.exception("Full verification error traceback:")
            
            # Provide more specific error messages based on error type
            if "timeout" in error_str.lower() or "connection" in error_str.lower():
                detail = "Unable to connect to authentication service. Please try again."
            elif "invalid" in error_str.lower() or "expired" in error_str.lower():
                detail = "Token is invalid or expired. Please sign in again."
            elif "unauthorized" in error_str.lower() or "forbidden" in error_str.lower():
                detail = "Token is not authorized. Please sign in again."
            else:
                detail = f"Token verification failed: {error_str}"
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=detail
            )
        
        user = response.user if response else None
        
        if not user:
            logger.warning("⚠️  Token verification returned no user")
            logger.debug(f"   Response object: {response}")
            logger.debug(f"   Response type: {type(response)}")
            if response:
                logger.debug(f"   Response attributes: {dir(response)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification succeeded but no user data was returned"
            )
        
        logger.info(f"✅ Token verified successfully for user: {user.email} (ID: {user.id})")
        logger.debug(f"   Email confirmed: {user.email_confirmed_at is not None}")
        logger.debug(f"   User metadata keys: {list(user.user_metadata.keys()) if user.user_metadata else 'None'}")
        
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
        error_type = type(e).__name__
        error_str = str(e)
        error_msg = f"Unexpected error during token verification: {error_type} - {error_str}"
        logger.error(f"❌ {error_msg}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {error_str}"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_user),
    supabase_service: SupabaseService = Depends(lambda: SupabaseService())
):
    """
    Get current authenticated user information with fresh metadata from Supabase
    """
    logger.info(f"📥 Get current user request for: {current_user.email}")
    try:
        # Fetch fresh user data from Supabase to get latest metadata
        logger.debug(f"   Fetching fresh user data from Supabase for: {current_user.id}")
        response = supabase_service.get_user_by_id(current_user.id)
        user = response.user
        
        if user:
            logger.info(f"✅ Returning fresh user info for: {user.email} (ID: {user.id})")
            logger.debug(f"   User metadata: {user.user_metadata}")
            return UserResponse(
                id=user.id,
                email=user.email,
                email_verified=user.email_confirmed_at is not None,
                created_at=user.created_at,
                user_metadata=user.user_metadata or {}
            )
        else:
            logger.warning(f"⚠️  No user found, returning cached data")
            return current_user
    except Exception as e:
        logger.error(f"❌ Failed to fetch fresh user data: {str(e)}")
        logger.exception("Full error traceback:")
        # Fallback to cached user data if fetch fails
        logger.warning(f"⚠️  Returning cached user data due to error")
        return current_user

@router.get("/user/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    current_user: UserResponse = Depends(get_current_user),
    supabase_service: SupabaseService = Depends(lambda: SupabaseService())
):
    """
    Get user by ID (requires authentication)
    """
    logger.info(f"📥 Get user by ID request - User ID: {user_id} (Requested by: {current_user.email})")
    try:
        response = supabase_service.get_user_by_id(user_id)
        user = response.user
        
        logger.info(f"✅ User found: {user.email} (ID: {user_id})")
        
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
        error_msg = f"User not found: {str(e)}"
        logger.error(f"❌ {error_msg} - User ID: {user_id}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {str(e)}"
        )

@router.post("/refresh")
async def refresh_token(
    request: RefreshTokenRequest,
    supabase_service: SupabaseService = Depends(lambda: SupabaseService())
):
    """
    Refresh access token using refresh token
    """
    logger.info("📥 Refresh token request received")
    try:
        refresh_token_value = request.refresh_token
        if not refresh_token_value:
            logger.warning("⚠️  Refresh token request missing refresh_token")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refresh token is required"
            )
        
        logger.info("🔄 Attempting to refresh token...")
        # Note: Supabase Python client handles refresh differently
        # You may need to use the REST API directly for refresh
        response = supabase_service.client.auth.refresh_session(refresh_token_value)
        
        logger.info("✅ Token refreshed successfully")
        
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "expires_in": response.session.expires_in
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to refresh token: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to refresh token: {str(e)}"
        )

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: UserResponse = Depends(get_current_user),
    supabase_service: SupabaseService = Depends(lambda: SupabaseService())
):
    """
    Update user profile (full_name and date_of_birth)
    """
    logger.info(f"📥 Update profile request for: {current_user.email}")
    try:
        # Get current user metadata
        response = supabase_service.get_user_by_id(current_user.id)
        current_metadata = response.user.user_metadata or {}
        
        # Update metadata with new values (only update provided fields)
        updated_metadata = current_metadata.copy()
        if request.full_name is not None:
            updated_metadata["full_name"] = request.full_name
        if request.date_of_birth is not None:
            updated_metadata["date_of_birth"] = request.date_of_birth
        
        logger.debug(f"   Updating metadata: {updated_metadata}")
        
        # Update user metadata in Supabase
        update_response = supabase_service.update_user_metadata(current_user.id, updated_metadata)
        updated_user = update_response.user
        
        logger.info(f"✅ Profile updated successfully for: {current_user.email}")
        
        return UserResponse(
            id=updated_user.id,
            email=updated_user.email,
            email_verified=updated_user.email_confirmed_at is not None,
            created_at=updated_user.created_at,
            user_metadata=updated_user.user_metadata or {}
        )
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to update profile: {str(e)}"
        logger.error(f"❌ {error_msg} - User: {current_user.email}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )

@router.put("/password", response_model=dict)
async def update_password(
    request: UpdatePasswordRequest,
    current_user: UserResponse = Depends(get_current_user),
    supabase_service: SupabaseService = Depends(lambda: SupabaseService())
):
    """
    Update user password
    """
    logger.info(f"📥 Update password request for: {current_user.email}")
    try:
        # Validate new password length
        if len(request.new_password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be at least 6 characters long"
            )
        
        # Update password
        supabase_service.update_user_password(
            current_user.email,
            request.current_password,
            request.new_password
        )
        
        logger.info(f"✅ Password updated successfully for: {current_user.email}")
        
        return {"message": "Password updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to update password: {str(e)}"
        logger.error(f"❌ {error_msg} - User: {current_user.email}")
        logger.exception("Full error traceback:")
        
        # Provide more specific error messages
        error_str = str(e).lower()
        if "incorrect" in error_str or "invalid" in error_str:
            status_code = status.HTTP_401_UNAUTHORIZED
            detail = "Current password is incorrect"
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            detail = error_msg
        
        raise HTTPException(
            status_code=status_code,
            detail=detail
        )
