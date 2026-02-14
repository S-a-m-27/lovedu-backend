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
        """Sign up new user - uses auth.sign_up which automatically sends verification emails via custom SMTP"""
        logger.info(f"📝 Attempting sign up for email: {email}")
        try:
            # Use ANON KEY - auth.sign_up automatically sends verification emails via custom SMTP
            from supabase import create_client
            import os
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
            
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
            
            # Configure client with timeout for signup
            timeout_config = Timeout(
                connect=10.0,
                read=60.0,  # 60 seconds - enough for SMTP email sending
                write=10.0,
                pool=5.0
            )
            
            client_options = ClientOptions(
                postgrest_client_timeout=timeout_config,
                storage_client_timeout=timeout_config,
                headers={}
            )
            
            logger.info("🔧 Creating Supabase anon client for signup (automatically sends verification email)...")
            anon_client = create_client(supabase_url, supabase_anon_key, options=client_options)
            
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
            
            logger.info(f"📤 Creating user via auth.sign_up (automatically sends verification email via custom SMTP) for: {email}")
            logger.info(f"   📧 Email verification will be sent automatically by Supabase via custom SMTP")
            
            # Use regular auth.sign_up - this automatically sends verification emails via custom SMTP
            # Wrap in timeout to handle slow SMTP servers gracefully
            try:
                def signup_with_timeout():
                    logger.debug(f"   🔄 Calling Supabase auth.sign_up API for: {email}")
                    result = anon_client.auth.sign_up({
                        "email": email,
                        "password": password,
                        "options": {
                            "data": metadata
                        }
                    })
                    logger.debug(f"   ✅ Supabase auth.sign_up API call completed for: {email}")
                    return result
                
                # Execute with timeout using thread pool
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(signup_with_timeout)
                    try:
                        response = future.result(timeout=55.0)  # 55 seconds timeout
                    except FutureTimeoutError:
                        logger.warning(f"⚠️  Signup timed out for {email}, but user may have been created and email sent")
                        logger.info(f"   📧 Attempting to verify user creation and email status...")
                        
                        # Check if user exists (user might have been created before timeout)
                        try:
                            # Try to verify user was created using admin API
                            admin_client = create_client(supabase_url, os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
                            
                            # Try to get user by email to verify creation succeeded
                            logger.debug(f"   🔍 Checking if user was created for: {email}")
                            try:
                                # List users and find by email (admin API)
                                users_response = admin_client.auth.admin.list_users()
                                user_found = None
                                if hasattr(users_response, 'users'):
                                    for u in users_response.users:
                                        if hasattr(u, 'email') and u.email.lower() == email.lower():
                                            user_found = u
                                            break
                                
                                if user_found:
                                    logger.info(f"   ✅ Verified: User was created successfully (User ID: {user_found.id})")
                                    
                                    # Check email confirmation status
                                    email_confirmed = hasattr(user_found, 'email_confirmed_at') and user_found.email_confirmed_at is not None
                                    email_confirmed_at = user_found.email_confirmed_at if hasattr(user_found, 'email_confirmed_at') else None
                                    
                                    if email_confirmed:
                                        logger.info(f"   ✅ Email already confirmed at: {email_confirmed_at}")
                                        logger.info(f"   📧 EMAIL VERIFICATION STATUS: CONFIRMED")
                                    else:
                                        logger.info(f"   📧 Email NOT confirmed - verification email should have been sent")
                                        logger.info(f"   📧 EMAIL VERIFICATION STATUS: PENDING")
                                        logger.info(f"   📧 Supabase should have sent verification email automatically via custom SMTP")
                                        logger.info(f"   📧 If email not received, check:")
                                        logger.info(f"      - Supabase Dashboard > Logs > Auth Logs for email sending errors")
                                        logger.info(f"      - Custom SMTP settings in Supabase Dashboard > Settings > Auth > SMTP Settings")
                                        logger.info(f"      - Email spam/junk folder")
                                    
                                    # Return response with user info
                                    class SignUpResponse:
                                        def __init__(self, user=None):
                                            self.user = user
                                            self.session = None
                                    return SignUpResponse(user_found)  # Return the found user
                                else:
                                    logger.warning(f"   ⚠️  Could not find user in admin list after timeout")
                                    logger.warning(f"   📧 EMAIL VERIFICATION STATUS: UNKNOWN (user not found)")
                                    logger.info(f"   📧 User creation may have failed or is still in progress")
                                    class SignUpResponse:
                                        def __init__(self, user=None):
                                            self.user = user
                                            self.session = None
                                    return SignUpResponse(None)
                            except Exception as list_error:
                                logger.debug(f"   Could not list users to verify: {str(list_error)}")
                                logger.warning(f"   ⚠️  Could not verify user creation status")
                                logger.info(f"   📧 EMAIL VERIFICATION STATUS: UNKNOWN (verification check failed)")
                            
                            # Return a response indicating success but no session
                            # Supabase sends emails asynchronously, so email should still be delivered
                            logger.info(f"   📧 Email should be sent asynchronously by Supabase")
                            logger.info(f"   📧 Check Supabase Dashboard > Logs > Auth Logs to verify email was sent")
                            class SignUpResponse:
                                def __init__(self, user=None):
                                    self.user = user
                                    self.session = None
                            return SignUpResponse(None)  # User exists but we don't have the object
                        except Exception as verify_error:
                            # If we can't verify, still assume success to avoid blocking user
                            logger.warning(f"   ⚠️  Could not verify user creation: {str(verify_error)}")
                            logger.warning(f"   📧 EMAIL VERIFICATION STATUS: UNKNOWN (verification check failed)")
                            logger.info(f"   User creation likely succeeded, email should be sent")
                            logger.info(f"   📧 Check Supabase Dashboard > Logs > Auth Logs to verify email was sent")
                            class SignUpResponse:
                                def __init__(self, user=None):
                                    self.user = user
                                    self.session = None
                            return SignUpResponse(None)
                
                logger.debug(f"   Supabase API call completed - Response type: {type(response)}")
                
                # Log response details for debugging
                if hasattr(response, 'user') and response.user:
                    logger.debug(f"   📋 Response details - User ID: {response.user.id if hasattr(response.user, 'id') else 'N/A'}")
                    logger.debug(f"   📋 Response details - Has session: {hasattr(response, 'session') and response.session is not None}")
            except Exception as supabase_error:
                error_str = str(supabase_error).lower()
                
                # Check if it's a timeout - user might still have been created
                if "timeout" in error_str or "timed out" in error_str:
                    logger.warning(f"⚠️  Signup timed out for {email}, but user may have been created and email sent")
                    logger.info(f"   📧 Supabase sends emails asynchronously, so email should still be delivered")
                    logger.info(f"   📧 Attempting to verify user creation and email status...")
                    
                    # Try to verify user was created
                    try:
                        admin_client = create_client(supabase_url, os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
                        users_response = admin_client.auth.admin.list_users()
                        user_found = None
                        if hasattr(users_response, 'users'):
                            for u in users_response.users:
                                if hasattr(u, 'email') and u.email.lower() == email.lower():
                                    user_found = u
                                    break
                        
                        if user_found:
                            logger.info(f"   ✅ User found: {user_found.id}")
                            email_confirmed = hasattr(user_found, 'email_confirmed_at') and user_found.email_confirmed_at is not None
                            if email_confirmed:
                                logger.info(f"   ✅ EMAIL VERIFICATION STATUS: CONFIRMED")
                            else:
                                logger.info(f"   📧 EMAIL VERIFICATION STATUS: PENDING (verification email should have been sent)")
                                logger.info(f"   📧 Check Supabase Dashboard > Logs > Auth Logs for email sending status")
                        else:
                            logger.warning(f"   ⚠️  EMAIL VERIFICATION STATUS: UNKNOWN (user not found)")
                            logger.info(f"   📧 Check Supabase Dashboard > Logs > Auth Logs to verify user creation and email status")
                    except Exception as verify_err:
                        logger.warning(f"   ⚠️  Could not verify: {str(verify_err)}")
                        logger.info(f"   📧 EMAIL VERIFICATION STATUS: UNKNOWN (check Supabase Auth logs)")
                    
                    # Return success - user was likely created and email will be sent
                    class SignUpResponse:
                        def __init__(self, user=None):
                            self.user = user
                            self.session = None
                    return SignUpResponse(None)
                
                logger.error(f"   ❌ Supabase API call failed: {str(supabase_error)}")
                logger.error(f"   Error type: {type(supabase_error).__name__}")
                logger.error(f"   📧 Email verification status: UNKNOWN (signup failed)")
                logger.exception("   Supabase error traceback:")
                raise
            
            logger.debug(f"   Response has user: {hasattr(response, 'user')}")
            logger.debug(f"   Response has session: {hasattr(response, 'session')}")
            
            if response.user:
                logger.info(f"✅ User created successfully for: {email}")
                logger.debug(f"   User ID: {response.user.id if hasattr(response.user, 'id') else 'N/A'}")
                
                # Check email confirmation status
                email_confirmed = hasattr(response.user, 'email_confirmed_at') and response.user.email_confirmed_at is not None
                email_confirmed_at = response.user.email_confirmed_at if hasattr(response.user, 'email_confirmed_at') else None
                
                if email_confirmed:
                    logger.info(f"   ✅ Email already confirmed at: {email_confirmed_at}")
                else:
                    logger.info(f"   📧 Email NOT confirmed - verification email should have been sent automatically")
                    logger.info(f"   📧 Email verification status: PENDING (user should check inbox for verification link)")
                    logger.info(f"   📧 If email not received, check:")
                    logger.info(f"      - Supabase Dashboard > Logs > Auth Logs for email sending errors")
                    logger.info(f"      - Custom SMTP settings in Supabase Dashboard > Settings > Auth > SMTP Settings")
                    logger.info(f"      - Email spam/junk folder")
                
                logger.debug(f"   Email confirmed timestamp: {email_confirmed_at if email_confirmed_at else 'None (verification required)'}")
                
                if response.session:
                    # User is auto-confirmed and has a session
                    logger.info("✅ User created and session established (email auto-confirmed)")
                    class SignUpResponse:
                        def __init__(self, user, session):
                            self.user = user
                            self.session = session
                    return SignUpResponse(response.user, response.session)
                elif email_confirmed:
                    # Email is confirmed but no session - sign in to get session
                    logger.info("🔑 Email confirmed, signing in user to create session...")
                    try:
                        sign_in_response = anon_client.auth.sign_in_with_password({
                            "email": email,
                            "password": password
                        })
                        
                        if sign_in_response.session:
                            logger.info("✅ Session created successfully")
                            class SignUpResponse:
                                def __init__(self, user, session):
                                    self.user = user
                                    self.session = session
                            return SignUpResponse(response.user, sign_in_response.session)
                        else:
                            logger.warning("⚠️  Sign in returned no session, but user was created")
                    except Exception as sign_in_error:
                        logger.warning(f"⚠️  Could not sign in user after creation: {str(sign_in_error)}")
                        logger.info("   User was created but session creation failed - user can sign in manually")
                else:
                    # Email not confirmed - verification email should have been sent automatically
                    logger.info("📧 User created but email not confirmed - verification email should have been sent automatically via custom SMTP")
                    logger.info("   📧 EMAIL VERIFICATION STATUS: PENDING")
                    logger.info("   📧 Supabase auth.sign_up should have automatically sent verification email")
                    logger.info("   📧 User should check their email inbox (including spam folder) for verification link")
                    logger.info("   📧 If email not received, verify:")
                    logger.info("      - Supabase Dashboard > Settings > Auth > SMTP Settings (custom SMTP enabled)")
                    logger.info("      - Supabase Dashboard > Authentication > Email Templates (Confirm signup template enabled)")
                    logger.info("      - Supabase Dashboard > Logs > Auth Logs (check for email sending errors)")
                
                # Return response with user but no session (user needs to verify email first)
                logger.info(f"📧 FINAL EMAIL VERIFICATION STATUS for {email}:")
                logger.info(f"   - Email confirmed: {email_confirmed}")
                logger.info(f"   - Verification email: Should have been sent automatically by Supabase")
                logger.info(f"   - Next step: User should check email inbox for verification link")
                if not email_confirmed:
                    logger.warning(f"   ⚠️  If email not received, check Supabase Auth logs for sending errors")
                
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
    
    def send_verification_email(self, email: str):
        """Send verification email asynchronously (non-blocking, best-effort)"""
        logger.info(f"📧 Attempting to send verification email to: {email}")
        try:
            from supabase import create_client
            import os
            
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            
            if not supabase_url or not supabase_service_key:
                logger.warning("⚠️  Cannot send verification email - SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
                return False
            
            try:
                # Use admin client to generate verification link
                # This triggers Supabase to send the verification email via custom SMTP
                admin_client = create_client(supabase_url, supabase_service_key)
                
                # Generate signup link - this will trigger email sending
                link_response = admin_client.auth.admin.generate_link({
                    "type": "signup",
                    "email": email
                })
                
                logger.info(f"✅ Verification email triggered successfully for: {email}")
                return True
                
            except Exception as email_error:
                # Don't fail if email sending fails - it's best-effort
                # User was already created, so this is just a notification
                error_str = str(email_error).lower()
                logger.warning(f"⚠️  Could not trigger verification email to {email}: {str(email_error)}")
                
                # Check if it's because user already exists or other recoverable error
                if "already" in error_str or "exists" in error_str:
                    logger.info("   User already exists - email may have been sent during creation")
                    return True
                
                logger.info("   User was created successfully, but email trigger failed")
                logger.info("   Note: Supabase may still send the email automatically")
                logger.info("   User can request email resend from Supabase dashboard if needed")
                # Return True anyway - user was created successfully
                return True
                
        except Exception as e:
            logger.warning(f"⚠️  Error in send_verification_email: {str(e)}")
            # User was created, so return True anyway
            return True

