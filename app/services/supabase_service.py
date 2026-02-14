from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from httpx import Timeout
import os
import logging
from typing import Optional
import time

logger = logging.getLogger(__name__)

class SupabaseService:
    _instance: Optional['SupabaseService'] = None
    _client: Optional[Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            logger.info("🔧 Initializing SupabaseService...")
            
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            
            logger.info(f"📋 SUPABASE_URL: {supabase_url if supabase_url else 'NOT SET'}")
            if supabase_key:
                masked_key = supabase_key[:10] + "..." + supabase_key[-4:] if len(supabase_key) > 14 else "***"
                logger.info(f"📋 SUPABASE_SERVICE_ROLE_KEY: {masked_key} (loaded)")
            else:
                logger.error("❌ SUPABASE_SERVICE_ROLE_KEY: NOT SET")
            
            if not supabase_url or not supabase_key:
                error_msg = "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            try:
                # Create client with service role key and api schema
                # The service role key bypasses RLS and never expires
                # All tables are in the 'api' schema
                client_options = ClientOptions(schema="api")
                self._client = create_client(supabase_url, supabase_key, options=client_options)
                
                # Verify we're using service role key (not anon key)
                # Service role keys are longer and start with 'eyJ' (JWT format)
                if supabase_key and len(supabase_key) > 100:
                    logger.info("✅ Supabase client created with service role key (bypasses RLS)")
                else:
                    logger.warning("⚠️  Supabase key appears to be anon key, not service role key!")
                
                # Ensure no user session is set - service role key should be used directly
                # Clear any potential cached session
                try:
                    # The service role key client should not have user sessions
                    # But we clear it just in case
                    if hasattr(self._client, 'auth') and hasattr(self._client.auth, 'get_session'):
                        session = self._client.auth.get_session()
                        if session:
                            logger.warning("⚠️  Found existing session on service role client, clearing it")
                            self._client.auth.sign_out()
                except Exception as e:
                    # Ignore errors - service role key might not support auth methods
                    logger.debug(f"   Could not check/clear session (expected for service role): {str(e)}")
                
                logger.info("✅ Supabase service role client ready for database operations")
            except Exception as e:
                logger.error(f"❌ Failed to create Supabase client: {str(e)}")
                raise
    
    @property
    def client(self) -> Client:
        """
        Get the Supabase client with service role key.
        This client bypasses RLS and should never use user JWT tokens.
        """
        if self._client is None:
            raise ValueError("Supabase client not initialized")
        return self._client
    
    def get_db_client(self) -> Client:
        """
        Get a fresh database client that uses service role key.
        This ensures we never use expired user JWT tokens.
        """
        # Return the service role client (which bypasses RLS)
        return self.client
    
    def get_user_by_id(self, user_id: str):
        """Get user by ID from Supabase"""
        logger.info(f"🔍 Fetching user by ID: {user_id}")
        try:
            response = self._client.auth.admin.get_user_by_id(user_id)
            logger.info(f"✅ User fetched successfully: {user_id}")
            return response
        except Exception as e:
            error_msg = f"Error fetching user: {str(e)}"
            logger.error(f"❌ {error_msg} - User ID: {user_id}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def update_user_metadata(self, user_id: str, user_metadata: dict):
        """Update user metadata in Supabase"""
        logger.info(f"📝 Updating user metadata for: {user_id}")
        try:
            response = self._client.auth.admin.update_user_by_id(
                user_id,
                {"user_metadata": user_metadata}
            )
            logger.info(f"✅ User metadata updated successfully for: {user_id}")
            return response
        except Exception as e:
            error_msg = f"Error updating user metadata: {str(e)}"
            logger.error(f"❌ {error_msg} - User ID: {user_id}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def update_user_password(self, email: str, current_password: str, new_password: str):
        """Update user password by first verifying current password, then updating"""
        logger.info(f"🔐 Updating password for: {email}")
        try:
            from supabase import create_client
            import os
            
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
            
            if not supabase_url or not supabase_anon_key:
                raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
            
            # Create anon client for password update
            anon_client = create_client(supabase_url, supabase_anon_key)
            
            # First, verify current password by attempting to sign in
            logger.debug("   Verifying current password...")
            try:
                verify_response = anon_client.auth.sign_in_with_password({
                    "email": email,
                    "password": current_password
                })
                if not verify_response.session:
                    raise Exception("Current password is incorrect")
            except Exception as verify_err:
                error_str = str(verify_err).lower()
                if "invalid" in error_str or "incorrect" in error_str or "wrong" in error_str:
                    raise Exception("Current password is incorrect")
                raise Exception(f"Failed to verify current password: {str(verify_err)}")
            
            # If verification successful, update password using admin API
            logger.debug("   Current password verified, updating to new password...")
            user_id = verify_response.user.id
            
            # Update password using admin API
            update_response = self._client.auth.admin.update_user_by_id(
                user_id,
                {"password": new_password}
            )
            
            logger.info(f"✅ Password updated successfully for: {email}")
            return update_response
        except Exception as e:
            error_msg = f"Error updating password: {str(e)}"
            logger.error(f"❌ {error_msg} - Email: {email}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def verify_token(self, token: str, max_retries: int = 3, retry_delay: float = 1.0):
        """Verify JWT token with Supabase using a separate client to avoid affecting service role client
        
        Args:
            token: JWT token to verify
            max_retries: Maximum number of retry attempts for transient network errors
            retry_delay: Delay in seconds between retries
        """
        logger.info("🔐 Verifying token...")
        token_preview = token[:20] + "..." if len(token) > 20 else token
        logger.debug(f"Token preview: {token_preview}")
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
        
        if not supabase_url or not supabase_anon_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set for token verification")
        
        # Configure client options with increased timeout
        # Use httpx.Timeout for connection and read timeouts
        timeout_config = Timeout(
            connect=10.0,  # 10 seconds to establish connection
            read=30.0,     # 30 seconds to read response
            write=10.0,    # 10 seconds to write request
            pool=5.0       # 5 seconds to get connection from pool
        )
        
        client_options = ClientOptions(
            postgrest_client_timeout=timeout_config,
            storage_client_timeout=timeout_config,
            headers={}
        )
        
        last_exception = None
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(f"   Attempt {attempt}/{max_retries} to verify token...")
                
                # Create a temporary client for token verification with timeout configuration
                verify_client = create_client(supabase_url, supabase_anon_key, options=client_options)
                response = verify_client.auth.get_user(token)
                
                if response.user:
                    logger.info(f"✅ Token verified successfully for user: {response.user.email}")
                else:
                    logger.warning("⚠️  Token verification returned no user")
                return response
                
            except (TimeoutError, ConnectionError, Exception) as e:
                error_type = type(e).__name__
                error_str = str(e)
                error_repr = repr(e)
                
                # Log detailed error information
                logger.debug(f"   Exception caught: {error_type}")
                logger.debug(f"   Error string: {error_str}")
                logger.debug(f"   Error repr: {error_repr}")
                
                # Check if it's a network-related error
                error_str_lower = error_str.lower()
                is_network_error = any(keyword in error_str_lower for keyword in [
                    'timeout', 'timed out', 'connection', 'connect', 'network', 
                    'unreachable', 'refused', 'reset', 'dns', 'socket'
                ])
                
                # Check for Supabase-specific errors
                is_auth_error = any(keyword in error_str_lower for keyword in [
                    'invalid', 'expired', 'unauthorized', 'forbidden', 'jwt',
                    'token', 'authentication', 'auth', '401', '403'
                ])
                
                logger.debug(f"   Is network error: {is_network_error}")
                logger.debug(f"   Is auth error: {is_auth_error}")
                
                if is_network_error and attempt < max_retries:
                    # Network-related errors - retry
                    last_exception = e
                    logger.warning(f"   ⚠️  Network error on attempt {attempt}/{max_retries}: {error_type} - {error_str}")
                    
                    wait_time = retry_delay * attempt  # Exponential backoff
                    logger.info(f"   ⏳ Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                elif is_network_error:
                    # Exhausted retries for network errors
                    last_exception = e
                    logger.error(f"   ❌ All {max_retries} attempts failed due to network errors")
                    logger.error(f"   Last error: {error_type} - {error_str}")
                else:
                    # Non-retryable errors (authentication errors, invalid token, etc.)
                    # Provide more specific error message
                    if is_auth_error:
                        if 'expired' in error_str_lower:
                            error_msg = "Token has expired. Please sign in again."
                        elif 'invalid' in error_str_lower:
                            error_msg = f"Invalid token: {error_str}"
                        else:
                            error_msg = f"Authentication error: {error_str}"
                    else:
                        error_msg = f"Token verification failed: {error_type} - {error_str}"
                    
                    logger.error(f"❌ {error_msg}")
                    logger.error(f"   Error type: {error_type}")
                    logger.error(f"   Error details: {error_str}")
                    logger.exception("Full error traceback:")
                    raise Exception(error_msg)
        
        # If we exhausted all retries, raise the last network exception
        if last_exception:
            error_msg = f"Token verification failed after {max_retries} attempts: {str(last_exception)}"
            logger.error(f"❌ {error_msg}")
            raise Exception(f"Network timeout: Unable to connect to Supabase. Please check your internet connection and try again.")
    
    def sign_in(self, email: str, password: str):
        """Sign in user with email and password"""
        logger.info(f"🔑 Attempting sign in for email: {email}")
        try:
            # Use anon key client for user operations
            from supabase import create_client
            import os
            
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
            
            logger.debug(f"📋 SUPABASE_URL: {supabase_url if supabase_url else 'NOT SET'}")
            if supabase_anon_key:
                masked_key = supabase_anon_key[:10] + "..." + supabase_anon_key[-4:] if len(supabase_anon_key) > 14 else "***"
                logger.debug(f"📋 SUPABASE_ANON_KEY: {masked_key} (loaded)")
            else:
                logger.error("❌ SUPABASE_ANON_KEY: NOT SET")
            
            if not supabase_url or not supabase_anon_key:
                error_msg = "SUPABASE_URL and SUPABASE_ANON_KEY must be set"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            logger.info("🔧 Creating Supabase anon client for sign in...")
            anon_client = create_client(supabase_url, supabase_anon_key)
            
            logger.info(f"📤 Calling Supabase sign_in_with_password for: {email}")
            try:
                response = anon_client.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                logger.debug(f"   Supabase API call completed - Response type: {type(response)}")
            except Exception as supabase_error:
                logger.error(f"   ❌ Supabase API call failed: {str(supabase_error)}")
                logger.error(f"   Error type: {type(supabase_error).__name__}")
                logger.exception("   Supabase error traceback:")
                raise
            
            logger.debug(f"   Response has session: {hasattr(response, 'session')}")
            logger.debug(f"   Response has user: {hasattr(response, 'user')}")
            
            if response.session:
                logger.info(f"✅ Sign in successful for: {email}")
                logger.debug(f"   Session created - User ID: {response.session.user.id}")
                logger.debug(f"   Access token present: {hasattr(response.session, 'access_token')}")
                logger.debug(f"   Refresh token present: {hasattr(response.session, 'refresh_token')}")
            else:
                logger.warning(f"⚠️  Sign in returned no session for: {email}")
                if hasattr(response, 'user'):
                    logger.debug(f"   User object exists: {response.user}")
                    logger.debug(f"   User ID: {response.user.id if hasattr(response.user, 'id') else 'N/A'}")
                    logger.debug(f"   Email confirmed: {response.user.email_confirmed_at if hasattr(response.user, 'email_confirmed_at') else 'N/A'}")
            
            return response
        except ValueError as ve:
            error_msg = f"ValueError in sign_in: {str(ve)}"
            logger.error(f"❌ {error_msg} - Email: {email}")
            logger.exception("Full ValueError traceback:")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Sign in failed: {str(e)}"
            error_type = type(e).__name__
            logger.error(f"❌ {error_msg} - Email: {email}")
            logger.error(f"   Exception Type: {error_type}")
            logger.error(f"   Exception Args: {e.args if hasattr(e, 'args') else 'N/A'}")
            if hasattr(e, 'message'):
                logger.error(f"   Exception Message: {e.message}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def sign_up(self, email: str, password: str, user_metadata: Optional[dict] = None):
        """Sign up new user using Service Role Key (bypasses rate limits)"""
        logger.info(f"📝 Attempting sign up for email: {email}")
        try:
            # Use SERVICE ROLE KEY to bypass rate limits
            from supabase import create_client
            import os
            
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            
            logger.debug(f"📋 SUPABASE_URL: {supabase_url if supabase_url else 'NOT SET'}")
            if supabase_service_key:
                masked_key = supabase_service_key[:10] + "..." + supabase_service_key[-4:] if len(supabase_service_key) > 14 else "***"
                logger.debug(f"📋 SUPABASE_SERVICE_ROLE_KEY: {masked_key} (loaded)")
            else:
                logger.error("❌ SUPABASE_SERVICE_ROLE_KEY: NOT SET")
            
            if not supabase_url or not supabase_service_key:
                error_msg = "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            logger.info("🔧 Creating Supabase admin client with SERVICE ROLE KEY (bypasses rate limits)...")
            admin_client = create_client(supabase_url, supabase_service_key)
            
            # Determine if email is from Kuwait University
            is_ku_email = email.endswith("@grad.ku.edu.kw") if email else False
            
            # Build user metadata
            metadata = {
                "plan": "free",  # Set default plan to free
                "is_ku_member": is_ku_email,  # Track if user is KU member
                "original_email": email  # Preserve original email casing for display
            }
            
            # Merge with provided metadata (which may include full_name, date_of_birth)
            if user_metadata:
                metadata.update(user_metadata)
            
            logger.debug(f"User metadata included - Plan: free, Is KU Member: {is_ku_email}, Additional: {user_metadata}")
            
            logger.info(f"📤 Creating user via Admin API (bypasses rate limits) for: {email}")
            try:
                # Use admin.create_user instead of auth.sign_up to bypass rate limits
                response = admin_client.auth.admin.create_user({
                    "email": email,
                    "password": password,
                    "email_confirm": True,  # Auto-confirm email (no verification needed)
                    "user_metadata": metadata
                })
                logger.debug(f"   Supabase API call completed - Response type: {type(response)}")
            except Exception as supabase_error:
                logger.error(f"   ❌ Supabase API call failed: {str(supabase_error)}")
                logger.error(f"   Error type: {type(supabase_error).__name__}")
                logger.exception("   Supabase error traceback:")
                raise
            
            logger.debug(f"   Response has user: {hasattr(response, 'user')}")
            
            if response.user:
                logger.info(f"✅ User created successfully via Admin API for: {email}")
                logger.debug(f"   User ID: {response.user.id if hasattr(response.user, 'id') else 'N/A'}")
                logger.debug(f"   Email confirmed: {response.user.email_confirmed_at if hasattr(response.user, 'email_confirmed_at') else 'N/A'}")
                
                # Admin API doesn't return a session, so we need to sign in to get one
                # Use anon key client to sign in and get a session
                logger.info("🔑 Signing in user to create session...")
                try:
                    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
                    if supabase_anon_key:
                        anon_client = create_client(supabase_url, supabase_anon_key)
                        sign_in_response = anon_client.auth.sign_in_with_password({
                            "email": email,
                            "password": password
                        })
                        
                        if sign_in_response.session:
                            logger.info("✅ Session created successfully")
                            # Create a response object with both user and session
                            class SignUpResponse:
                                def __init__(self, user, session):
                                    self.user = user
                                    self.session = session
                            
                            return SignUpResponse(response.user, sign_in_response.session)
                        else:
                            logger.warning("⚠️  Sign in returned no session, but user was created")
                    else:
                        logger.warning("⚠️  SUPABASE_ANON_KEY not set, cannot create session")
                except Exception as sign_in_error:
                    logger.warning(f"⚠️  Could not sign in user after creation: {str(sign_in_error)}")
                    logger.info("   User was created but session creation failed - user can sign in manually")
                
                # Return response with user but no session (user can sign in manually)
                class SignUpResponse:
                    def __init__(self, user):
                        self.user = user
                        self.session = None
                
                return SignUpResponse(response.user)
            else:
                logger.error(f"❌ User creation failed - no user object returned for: {email}")
                raise Exception("User creation failed - no user object returned")
        except ValueError as ve:
            error_msg = f"ValueError in sign_up: {str(ve)}"
            logger.error(f"❌ {error_msg} - Email: {email}")
            logger.exception("Full ValueError traceback:")
            raise Exception(error_msg)
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for rate limit errors
            if "rate limit" in error_str or "too many" in error_str:
                error_msg = "Too many signup attempts. Please wait a few minutes before trying again."
                logger.warning(f"⚠️  Rate limit exceeded for: {email}")
            else:
                error_msg = f"Sign up failed: {str(e)}"
            
            error_type = type(e).__name__
            logger.error(f"❌ {error_msg} - Email: {email}")
            logger.error(f"   Exception Type: {error_type}")
            logger.error(f"   Exception Args: {e.args if hasattr(e, 'args') else 'N/A'}")
            if hasattr(e, 'message'):
                logger.error(f"   Exception Message: {e.message}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)

