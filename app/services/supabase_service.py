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
        """Sign up new user - uses admin.create_user for fast creation, then sends verification email separately"""
        import time
        signup_start_time = time.time()
        
        logger.info(f"📝 Attempting sign up for email: {email}")
        logger.info(f"   ⏱️  Signup process started at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(signup_start_time))}")
        logger.info(f"   📋 Signup parameters:")
        logger.info(f"      - Email: {email}")
        logger.info(f"      - Password length: {len(password) if password else 0} characters")
        logger.info(f"      - User metadata provided: {bool(user_metadata)}")
        
        try:
            # Use SERVICE ROLE KEY for fast user creation (doesn't wait for email)
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
            
            logger.info("🔧 Creating Supabase admin client for fast user creation...")
            # Configure timeout for admin client (for email sending operations)
            timeout_config = Timeout(
                connect=10.0,
                read=30.0,  # 30 seconds for email sending
                write=10.0,
                pool=5.0
            )
            
            client_options = ClientOptions(
                postgrest_client_timeout=timeout_config,
                storage_client_timeout=timeout_config,
                headers={}
            )
            
            logger.info(f"   📋 Timeout Configuration (for email operations):")
            logger.info(f"      - Connect Timeout: {timeout_config.connect}s")
            logger.info(f"      - Read Timeout: {timeout_config.read}s")
            logger.info(f"      - Write Timeout: {timeout_config.write}s")
            logger.info(f"      - Pool Timeout: {timeout_config.pool}s")
            logger.info(f"   ⚠️  NOTE: If email sending takes longer than {timeout_config.read}s, it will timeout")
            
            admin_client = create_client(supabase_url, supabase_service_key, options=client_options)
            logger.info(f"   ✅ Admin client created with timeout configuration")
            
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
            
            logger.info(f"📤 Creating user via admin.create_user (fast, non-blocking) for: {email}")
            logger.info(f"   📧 Verification email will be sent separately after user creation")
            
            # Use admin.create_user - fast, doesn't wait for email sending
            try:
                logger.debug(f"   🔄 Calling Supabase admin.create_user API for: {email}")
                response = admin_client.auth.admin.create_user({
                    "email": email,
                    "password": password,
                    "email_confirm": False,  # Don't auto-confirm, email will be sent separately
                    "user_metadata": metadata
                })
                logger.debug(f"   ✅ Supabase admin.create_user API call completed for: {email}")
                
                if not response.user:
                    logger.error(f"❌ User creation failed - no user object returned for: {email}")
                    raise Exception("User creation failed - no user object returned")
                
                logger.info(f"✅ User created successfully for: {email} (User ID: {response.user.id})")
                
                # Now send verification email using admin.generate_link
                logger.info(f"📧 Sending verification email via admin.generate_link for: {email}")
                logger.info(f"   📋 Email sending configuration:")
                logger.info(f"      - Method: admin.generate_link")
                logger.info(f"      - Type: signup")
                logger.info(f"      - Email: {email}")
                logger.info(f"      - Supabase URL: {supabase_url}")
                logger.info(f"      - Expected timeout: {timeout_config.read}s")
                
                try:
                    start_time = time.time()
                    logger.info(f"   ⏱️  Starting email send request at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
                    logger.info(f"   ⏱️  Timestamp: {start_time}")
                    
                    # Log before making the API call
                    logger.debug(f"   🔄 About to call admin.generate_link API...")
                    logger.debug(f"   📡 Network request details:")
                    logger.debug(f"      - Target: {supabase_url}/auth/v1/admin/generate_link")
                    logger.debug(f"      - Method: POST")
                    logger.debug(f"      - Timeout limit: {timeout_config.read}s")
                    
                    # Make the API call with detailed logging
                    api_call_start = time.time()
                    logger.debug(f"   📤 API call initiated at: {api_call_start}")
                    logger.info(f"   🔄 Calling Supabase admin.generate_link API...")
                    
                    link_response = admin_client.auth.admin.generate_link({
                        "type": "signup",
                        "email": email
                    })
                    
                    api_call_end = time.time()
                    api_call_duration = api_call_end - api_call_start
                    elapsed_time = time.time() - start_time
                    
                    logger.info(f"✅ Verification email triggered successfully for: {email}")
                    logger.info(f"   ⏱️  Timing Details:")
                    logger.info(f"      - API call duration: {api_call_duration:.2f} seconds")
                    logger.info(f"      - Total elapsed time: {elapsed_time:.2f} seconds")
                    logger.info(f"      - Timeout limit was: {timeout_config.read}s")
                    logger.info(f"      - Time remaining before timeout: {max(0, timeout_config.read - api_call_duration):.2f}s")
                    logger.info(f"   📧 EMAIL VERIFICATION STATUS: EMAIL SENT")
                    logger.info(f"   📧 User should check their email inbox for verification link")
                    
                    # Log response details if available
                    if hasattr(link_response, 'properties') or hasattr(link_response, 'action_link'):
                        logger.debug(f"   📋 Response received from Supabase")
                        if hasattr(link_response, 'properties'):
                            logger.debug(f"      - Response has properties: {type(link_response.properties)}")
                        if hasattr(link_response, 'action_link'):
                            action_link = str(link_response.action_link)
                            logger.debug(f"      - Action link generated: {action_link[:50]}..." if len(action_link) > 50 else f"      - Action link: {action_link}")
                except Exception as email_error:
                    api_call_end = time.time() if 'api_call_start' in locals() else None
                    elapsed_time = time.time() - start_time if 'start_time' in locals() else None
                    error_type = type(email_error).__name__
                    error_str = str(email_error).lower()
                    
                    logger.error(f"❌ EMAIL SENDING FAILED for {email}")
                    logger.error(f"   📧 EMAIL VERIFICATION STATUS: EMAIL SENDING FAILED")
                    logger.error(f"   ⏱️  Timing Information:")
                    if elapsed_time:
                        logger.error(f"      - Total time elapsed: {elapsed_time:.2f} seconds")
                        logger.error(f"      - Timeout limit was: {timeout_config.read}s")
                        timeout_percentage = (elapsed_time / timeout_config.read * 100) if timeout_config.read > 0 else 0
                        logger.error(f"      - Timeout occurred at: {elapsed_time:.2f}s / {timeout_config.read}s ({timeout_percentage:.1f}% of timeout limit)")
                    if api_call_end and 'api_call_start' in locals():
                        api_call_duration = api_call_end - api_call_start
                        logger.error(f"      - API call duration before failure: {api_call_duration:.2f} seconds")
                    logger.error(f"   🔍 Error Details:")
                    logger.error(f"      - Error Type: {error_type}")
                    logger.error(f"      - Error Message: {str(email_error)}")
                    logger.error(f"      - Error Module: {email_error.__class__.__module__ if hasattr(email_error, '__class__') else 'N/A'}")
                    
                    # Detailed timeout analysis
                    is_timeout = False
                    timeout_details = []
                    
                    if "timeout" in error_str or "timed out" in error_str:
                        is_timeout = True
                        timeout_details.append("⚠️  TIMEOUT DETECTED")
                        logger.error(f"   ⚠️  TIMEOUT ERROR DETECTED")
                        logger.error(f"      - This indicates the SMTP server or Supabase email service is taking too long to respond")
                        if elapsed_time:
                            logger.error(f"      - Timeout occurred after: {elapsed_time:.2f}s (limit: {timeout_config.read}s)")
                            
                            # Analyze which phase timed out
                            if elapsed_time < timeout_config.connect:
                                logger.error(f"      - ⚠️  TIMEOUT PHASE: Connection establishment")
                                logger.error(f"      - Connection timeout limit: {timeout_config.connect}s")
                                logger.error(f"      - Failed during: Initial TCP connection to Supabase")
                            elif elapsed_time < timeout_config.connect + 2:
                                logger.error(f"      - ⚠️  TIMEOUT PHASE: Initial handshake")
                                logger.error(f"      - Failed during: SSL/TLS handshake or initial API handshake")
                            else:
                                logger.error(f"      - ⚠️  TIMEOUT PHASE: Data transfer / SMTP communication")
                                logger.error(f"      - Read timeout limit: {timeout_config.read}s")
                                logger.error(f"      - Failed during: Waiting for Supabase to communicate with SMTP server")
                                logger.error(f"      - This suggests Supabase is waiting for your SMTP server to respond")
                    
                    if "read operation timed out" in error_str or "read timeout" in error_str:
                        is_timeout = True
                        timeout_details.append("Read timeout - SMTP server response too slow")
                        logger.error(f"      - Read Timeout: The SMTP server did not respond in time")
                        logger.error(f"      - Read timeout limit: {timeout_config.read}s")
                        if elapsed_time:
                            logger.error(f"      - Time elapsed: {elapsed_time:.2f}s")
                        logger.error(f"      - Possible causes:")
                        logger.error(f"         * SMTP server is slow or overloaded")
                        logger.error(f"         * Network latency issues")
                        logger.error(f"         * Custom SMTP configuration issues")
                        logger.error(f"         * Supabase is waiting for SMTP server response")
                        logger.error(f"      - 🔍 DIAGNOSIS: Supabase received the request but SMTP server took too long")
                    
                    if "connect timeout" in error_str or "connection timeout" in error_str:
                        is_timeout = True
                        timeout_details.append("Connection timeout - Cannot connect to SMTP server")
                        logger.error(f"      - Connection Timeout: Cannot establish connection to SMTP server")
                        logger.error(f"      - Connection timeout limit: {timeout_config.connect}s")
                        if elapsed_time:
                            logger.error(f"      - Time elapsed: {elapsed_time:.2f}s")
                        logger.error(f"      - Possible causes:")
                        logger.error(f"         * SMTP server host/port incorrect")
                        logger.error(f"         * Firewall blocking connection")
                        logger.error(f"         * SMTP server is down")
                        logger.error(f"         * Network routing issues")
                        logger.error(f"      - 🔍 DIAGNOSIS: Cannot establish connection to SMTP server")
                    
                    if "write timeout" in error_str:
                        is_timeout = True
                        timeout_details.append("Write timeout - SMTP server not accepting data")
                        logger.error(f"      - Write Timeout: SMTP server not accepting data fast enough")
                        logger.error(f"      - Write timeout limit: {timeout_config.write}s")
                        logger.error(f"      - 🔍 DIAGNOSIS: SMTP server not accepting data")
                    
                    # Network-level error detection
                    if "connection" in error_str and ("refused" in error_str or "reset" in error_str):
                        logger.error(f"   🌐 NETWORK ERROR DETECTED:")
                        logger.error(f"      - Connection was refused or reset")
                        logger.error(f"      - This suggests network/firewall issues")
                        logger.error(f"      - Check if Supabase can reach your SMTP server")
                    
                    # Log full exception details
                    logger.error(f"   📋 Full Exception Details:")
                    logger.error(f"      - Exception Type: {error_type}")
                    logger.error(f"      - Exception Module: {email_error.__class__.__module__}")
                    logger.error(f"      - Exception Args: {email_error.args if hasattr(email_error, 'args') else 'N/A'}")
                    if hasattr(email_error, '__cause__') and email_error.__cause__:
                        logger.error(f"      - Caused by: {type(email_error.__cause__).__name__}: {str(email_error.__cause__)}")
                        logger.error(f"      - Cause Module: {email_error.__cause__.__class__.__module__}")
                    if hasattr(email_error, '__context__') and email_error.__context__:
                        logger.error(f"      - Context: {type(email_error.__context__).__name__}: {str(email_error.__context__)}")
                    
                    # Log full traceback with line numbers
                    import traceback
                    logger.error(f"   📋 Full Traceback (with line numbers):")
                    tb_lines = traceback.format_exception(type(email_error), email_error, email_error.__traceback__)
                    for tb_line in tb_lines:
                        for line in tb_line.strip().split('\n'):
                            if line.strip():
                                logger.error(f"      {line}")
                    
                    # Log the exact point of failure
                    if email_error.__traceback__:
                        tb = email_error.__traceback__
                        logger.error(f"   🔍 Failure Point Analysis:")
                        frame_count = 0
                        while tb:
                            frame = tb.tb_frame
                            logger.error(f"      Frame {frame_count}: {frame.f_code.co_filename}:{tb.tb_lineno} in {frame.f_code.co_name}")
                            tb = tb.tb_next
                            frame_count += 1
                            if frame_count > 10:  # Limit to prevent too much output
                                logger.error(f"      ... (more frames)")
                                break
                    
                    # Provide troubleshooting guidance
                    logger.error(f"   🔧 Troubleshooting Steps:")
                    logger.error(f"      1. Check Supabase Dashboard > Logs > Auth Logs for detailed email sending errors")
                    logger.error(f"      2. Verify Custom SMTP settings in Supabase Dashboard > Settings > Auth > SMTP Settings")
                    logger.error(f"         - SMTP Host: Should be correct and accessible")
                    logger.error(f"         - SMTP Port: Should match your SMTP provider's requirements")
                    logger.error(f"         - SMTP Username/Password: Should be valid")
                    logger.error(f"         - Sender Email: Should be verified with your SMTP provider")
                    logger.error(f"      3. Test SMTP connection from Supabase Dashboard")
                    logger.error(f"      4. Check if SMTP provider has rate limits or blocking")
                    logger.error(f"      5. Verify email template is enabled in Supabase Dashboard > Authentication > Email Templates")
                    
                    if is_timeout:
                        logger.error(f"   ⏱️  TIMEOUT-SPECIFIC TROUBLESHOOTING:")
                        logger.error(f"      - Current timeout: {timeout_config.read}s")
                        if elapsed_time:
                            logger.error(f"      - Time elapsed before timeout: {elapsed_time:.2f}s")
                        logger.error(f"      - Recommendation: Check Supabase SMTP timeout settings (may need to increase)")
                        logger.error(f"      - Check SMTP server response times")
                        logger.error(f"      - Consider using a different SMTP provider if current one is consistently slow")
                        logger.error(f"      - Verify network connectivity to SMTP server")
                        logger.error(f"      - Check if SMTP server is experiencing high load")
                        logger.error(f"      - Verify SMTP server logs for connection attempts")
                    
                    logger.warning(f"   ⚠️  User was created successfully, but verification email sending failed")
                    logger.info(f"   📧 User can request email resend from Supabase dashboard if needed")
                    # Don't fail signup if email sending fails - user can request resend
                
                # Check email confirmation status
                email_confirmed = hasattr(response.user, 'email_confirmed_at') and response.user.email_confirmed_at is not None
                email_confirmed_at = response.user.email_confirmed_at if hasattr(response.user, 'email_confirmed_at') else None
                
                if email_confirmed:
                    logger.info(f"   ✅ Email already confirmed at: {email_confirmed_at}")
                    logger.info(f"   📧 EMAIL VERIFICATION STATUS: CONFIRMED")
                else:
                    logger.info(f"   📧 Email NOT confirmed - verification required")
                    logger.info(f"   📧 EMAIL VERIFICATION STATUS: PENDING")
                
                # Return response with user but no session (user needs to verify email first)
                total_signup_time = time.time() - signup_start_time
                logger.info(f"✅ Signup process completed successfully for: {email}")
                logger.info(f"   ⏱️  Total signup time: {total_signup_time:.2f} seconds")
                logger.info(f"   📋 Summary:")
                logger.info(f"      - User creation: ✅ Success")
                logger.info(f"      - Email sending: {'✅ Success' if 'link_response' in locals() else '⚠️  Failed (check logs above)'}")
                
                class SignUpResponse:
                    def __init__(self, user):
                        self.user = user
                        self.session = None
                
                return SignUpResponse(response.user)
            except Exception as supabase_error:
                error_str = str(supabase_error).lower()
                
                logger.error(f"   ❌ Supabase API call failed: {str(supabase_error)}")
                logger.error(f"   Error type: {type(supabase_error).__name__}")
                logger.error(f"   📧 Email verification status: UNKNOWN (signup failed)")
                logger.exception("   Supabase error traceback:")
                raise
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
                error_type = type(email_error).__name__
                error_str = str(email_error).lower()
                
                logger.error(f"❌ EMAIL SENDING FAILED in send_verification_email for {email}")
                logger.error(f"   🔍 Error Details:")
                logger.error(f"      - Error Type: {error_type}")
                logger.error(f"      - Error Message: {str(email_error)}")
                
                # Check for timeout-related errors
                is_timeout = False
                if "timeout" in error_str or "timed out" in error_str:
                    is_timeout = True
                    logger.error(f"   ⚠️  TIMEOUT ERROR DETECTED")
                    logger.error(f"      - This indicates the SMTP server or Supabase email service is taking too long")
                
                if "read operation timed out" in error_str or "read timeout" in error_str:
                    is_timeout = True
                    logger.error(f"      - Read Timeout: SMTP server response too slow")
                
                if "connect timeout" in error_str or "connection timeout" in error_str:
                    is_timeout = True
                    logger.error(f"      - Connection Timeout: Cannot connect to SMTP server")
                
                # Log full exception details
                import traceback
                logger.error(f"   📋 Full Exception Traceback:")
                for line in traceback.format_exception(type(email_error), email_error, email_error.__traceback__):
                    for traceback_line in line.strip().split('\n'):
                        if traceback_line.strip():
                            logger.error(f"      {traceback_line}")
                
                # Check if it's because user already exists or other recoverable error
                if "already" in error_str or "exists" in error_str:
                    logger.info("   ✅ User already exists - email may have been sent during creation")
                    return True
                
                if is_timeout:
                    logger.error(f"   ⏱️  TIMEOUT-SPECIFIC TROUBLESHOOTING:")
                    logger.error(f"      - Check SMTP server response times")
                    logger.error(f"      - Verify SMTP configuration in Supabase Dashboard")
                    logger.error(f"      - Check network connectivity to SMTP server")
                
                logger.warning("   ⚠️  User was created successfully, but email trigger failed")
                logger.info("   📧 Note: Supabase may still send the email automatically")
                logger.info("   📧 User can request email resend from Supabase dashboard if needed")
                # Return True anyway - user was created successfully
                return True
                
        except Exception as e:
            logger.warning(f"⚠️  Error in send_verification_email: {str(e)}")
            # User was created, so return True anyway
            return True

