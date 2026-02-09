import time
import logging
import json
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Start timer
        start_time = time.time()
        
        # Get request details
        method = request.method
        path = request.url.path
        query_params = str(request.query_params) if request.query_params else None
        client_ip = request.client.host if request.client else "unknown"
        
        # Log request
        logger.info(f"📥 {method} {path}")
        logger.debug(f"   Client IP: {client_ip}")
        if query_params:
            logger.debug(f"   Query Params: {query_params}")
        
        # Try to log request body (for non-streaming requests)
        try:
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
                if body:
                    try:
                        body_json = json.loads(body.decode())
                        # Mask sensitive fields
                        masked_body = self._mask_sensitive_data(body_json)
                        logger.debug(f"   Request Body: {json.dumps(masked_body, indent=2)}")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        logger.debug(f"   Request Body: [Binary or non-JSON data]")
                # Recreate request with body (since we consumed it)
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
        except Exception as e:
            logger.warning(f"   ⚠️  Could not log request body: {str(e)}")
        
        # Log headers (masking sensitive ones)
        try:
            headers = dict(request.headers)
            masked_headers = self._mask_sensitive_headers(headers)
            logger.debug(f"   Headers: {json.dumps(masked_headers, indent=2)}")
        except Exception as e:
            logger.debug(f"   Could not log headers: {str(e)}")
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Get response status
            status_code = response.status_code if hasattr(response, 'status_code') else 200
            
            # Log response
            if status_code >= 400:
                logger.error(f"❌ {method} {path} - Status: {status_code} - Time: {process_time:.3f}s")
            elif status_code >= 300:
                logger.warning(f"⚠️  {method} {path} - Status: {status_code} - Time: {process_time:.3f}s")
            else:
                logger.info(f"✅ {method} {path} - Status: {status_code} - Time: {process_time:.3f}s")
            
            # Try to log response body for errors (without consuming it)
            if status_code >= 400:
                logger.debug(f"   Error response - Status: {status_code}")
                # Note: We don't read the body here to avoid consuming it
                # The actual error details will be logged by the route handler
            
            # Add timing header
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            # Log exception
            process_time = time.time() - start_time
            logger.error(f"💥 {method} {path} - Exception after {process_time:.3f}s")
            logger.error(f"   Exception Type: {type(e).__name__}")
            logger.error(f"   Exception Message: {str(e)}")
            logger.exception("   Full Stack Trace:")
            
            # Re-raise to let FastAPI handle it
            raise
    
    def _mask_sensitive_data(self, data: dict) -> dict:
        """Mask sensitive fields in request/response data"""
        sensitive_keys = ['password', 'token', 'access_token', 'refresh_token', 'api_key', 'secret']
        masked = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                if isinstance(value, str) and len(value) > 10:
                    masked[key] = value[:4] + "..." + value[-4:]
                else:
                    masked[key] = "***"
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive_data(value)
            elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                masked[key] = [self._mask_sensitive_data(item) for item in value]
            else:
                masked[key] = value
        return masked
    
    def _mask_sensitive_headers(self, headers: dict) -> dict:
        """Mask sensitive headers"""
        sensitive_headers = ['authorization', 'cookie', 'x-api-key']
        masked = {}
        for key, value in headers.items():
            if any(sensitive in key.lower() for sensitive in sensitive_headers):
                if isinstance(value, str) and len(value) > 20:
                    masked[key] = value[:10] + "..." + value[-4:]
                else:
                    masked[key] = "***"
            else:
                masked[key] = value
        return masked

