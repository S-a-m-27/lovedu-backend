import os
import logging
import re
from urllib.parse import quote, unquote
from typing import Optional, List
from datetime import datetime
from supabase import create_client
from app.models.admin import FileUploadResponse
from app.models.chat import AssistantType

logger = logging.getLogger(__name__)

class AdminService:
    _instance: Optional['AdminService'] = None
    _supabase_client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AdminService, cls).__new__(cls)
        return cls._instance
    
    def _get_supabase_client(self):
        """Get Supabase service role client"""
        if self._supabase_client is None:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            
            if not supabase_url or not supabase_service_key:
                raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
            
            self._supabase_client = create_client(supabase_url, supabase_service_key)
            logger.info("✅ Supabase service client created for AdminService")
        
        return self._supabase_client
    
    def _sanitize_filename_for_storage(self, filename: str) -> str:
        """
        Sanitize filename for Supabase Storage.
        Replaces invalid characters with underscores and URL-encodes the result.
        Keeps the file extension intact.
        """
        # Split filename and extension
        if '.' in filename:
            name_part, ext = filename.rsplit('.', 1)
            ext = '.' + ext
        else:
            name_part = filename
            ext = ''
        
        # Replace invalid characters with underscores
        # Invalid characters for storage keys: spaces, special unicode chars, etc.
        # Keep only alphanumeric, dots, hyphens, and underscores
        sanitized = re.sub(r'[^\w\-.]', '_', name_part)
        
        # Replace multiple consecutive underscores with single underscore
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        
        # If sanitized is empty, use a default name
        if not sanitized:
            sanitized = 'file'
        
        # URL encode the final filename to handle any remaining edge cases
        # But keep the extension readable
        final_name = quote(sanitized, safe='') + ext
        
        return final_name
    
    def _ensure_bucket_exists(self, bucket_name: str = "admin-uploads"):
        """Ensure the storage bucket exists, create it if it doesn't"""
        try:
            client = self._get_supabase_client()
            
            # Try to list buckets to check if it exists
            bucket_exists = False
            try:
                buckets = client.storage.list_buckets()
                if buckets:
                    # buckets might be a list of dicts or objects
                    if isinstance(buckets, list):
                        bucket_ids = []
                        for bucket in buckets:
                            if isinstance(bucket, dict):
                                bucket_ids.append(bucket.get("id", bucket.get("name", "")))
                            else:
                                bucket_ids.append(getattr(bucket, "id", getattr(bucket, "name", "")))
                        bucket_exists = bucket_name in bucket_ids
                    else:
                        # If it's a single object or different format
                        bucket_exists = False
                
                if bucket_exists:
                    logger.debug(f"   ✅ Bucket '{bucket_name}' already exists")
                    return True
            except Exception as list_err:
                logger.warning(f"   ⚠️  Could not list buckets (will try to create): {str(list_err)}")
            
            # Bucket doesn't exist, create it
            logger.info(f"📦 Creating storage bucket: {bucket_name}")
            try:
                # Create bucket with private access (not public)
                result = client.storage.create_bucket(
                    id=bucket_name,
                    name=bucket_name,
                    options={"public": False}  # Private bucket for admin uploads
                )
                logger.info(f"   ✅ Bucket '{bucket_name}' created successfully")
                return True
            except Exception as create_err:
                # Check if bucket was created by another process (race condition) or already exists
                error_str = str(create_err).lower()
                error_msg = str(create_err)
                
                # Check for various "already exists" error messages including RLS violations
                # RLS violations often occur when trying to create a bucket that already exists
                if any(phrase in error_str for phrase in [
                    "already exists", "duplicate", "bucket exists", "conflict",
                    "row-level security", "rls", "unauthorized", "violates"
                ]):
                    logger.debug(f"   ℹ️  Bucket '{bucket_name}' already exists or access denied (likely already exists)")
                    # Try to verify bucket exists by attempting to list it
                    try:
                        buckets = client.storage.list_buckets()
                        if buckets:
                            bucket_exists = False
                            if isinstance(buckets, list):
                                for b in buckets:
                                    if isinstance(b, dict):
                                        if b.get("id") == bucket_name or b.get("name") == bucket_name:
                                            bucket_exists = True
                                            break
                                    else:
                                        if (hasattr(b, "id") and b.id == bucket_name) or \
                                           (hasattr(b, "name") and getattr(b, "name", None) == bucket_name):
                                            bucket_exists = True
                                            break
                            else:
                                # Single bucket object
                                if isinstance(buckets, dict):
                                    bucket_exists = buckets.get("id") == bucket_name or buckets.get("name") == bucket_name
                                else:
                                    bucket_exists = (hasattr(buckets, "id") and buckets.id == bucket_name) or \
                                                  (hasattr(buckets, "name") and getattr(buckets, "name", None) == bucket_name)
                            
                            if bucket_exists:
                                logger.debug(f"   ✅ Verified bucket '{bucket_name}' exists")
                                return True
                            else:
                                logger.debug(f"   ⚠️  Bucket creation failed but bucket not found in list (assuming it exists)")
                    except Exception as verify_err:
                        logger.debug(f"   ⚠️  Could not verify bucket existence: {str(verify_err)}")
                    
                    # Assume bucket exists if we get RLS/unauthorized errors (common when bucket already exists)
                    # This is safe because if the bucket doesn't exist, the upload will fail anyway
                    logger.info(f"   ✅ Assuming bucket '{bucket_name}' exists (RLS error on create)")
                    return True
                
                # If it's a different error, log and re-raise
                logger.error(f"   ❌ Failed to create bucket: {error_msg}")
                raise Exception(f"Failed to create storage bucket '{bucket_name}': {error_msg}")
                
        except Exception as e:
            logger.error(f"❌ Error ensuring bucket exists: {str(e)}")
            logger.exception("Full error traceback:")
            raise
    
    def is_admin(self, user_id: str, user_metadata: dict = None) -> bool:
        """Check if user is an admin"""
        logger.debug(f"🔐 Checking admin status for user: {user_id}")
        
        # If user_metadata is provided, use it directly (preferred method - avoids Auth Admin API call)
        if user_metadata:
            is_admin = user_metadata.get("is_admin", False) or user_metadata.get("role") == "admin"
            logger.debug(f"   User admin status from metadata: {is_admin}")
            return is_admin
        
        # Fallback: Try to get from database using service role key
        # This is a backup method if user_metadata is not available
        try:
            client = self._get_supabase_client()
            response = client.auth.admin.get_user_by_id(user_id)
            
            if response.user:
                user_metadata = response.user.user_metadata or {}
                is_admin = user_metadata.get("is_admin", False) or user_metadata.get("role") == "admin"
                logger.debug(f"   User admin status from Auth Admin API: {is_admin}")
                return is_admin
            
            return False
        except Exception as e:
            logger.error(f"❌ Failed to check admin status: {str(e)}")
            logger.exception("Full error traceback:")
            return False
    
    async def upload_file(
        self,
        user_id: str,
        assistant_id: str,
        file_content: bytes,
        file_name: str,
        file_size: int
    ) -> FileUploadResponse:
        """
        Upload a content PDF file for an agent to Supabase Storage.
        
        Note: Agents only have content PDFs. Their behavior is defined in system prompts,
        not through behavior PDFs (unlike courses which have both behavior and content PDFs).
        """
        logger.info(f"📤 Uploading content PDF for agent - User: {user_id}, Assistant: {assistant_id}, File: {file_name}")
        
        try:
            client = self._get_supabase_client()
            
            # Ensure bucket exists before uploading
            self._ensure_bucket_exists("admin-uploads")
            
            # Sanitize filename for storage (keep original for database)
            sanitized_filename = self._sanitize_filename_for_storage(file_name)
            
            # Create file path in storage using sanitized filename
            file_path = f"assistants/{assistant_id}/{sanitized_filename}"
            
            # Upload to Supabase Storage
            try:
                storage_response = client.storage.from_("admin-uploads").upload(
                    path=file_path,
                    file=file_content,
                    file_options={"content-type": "application/pdf", "upsert": "true"}
                )
                logger.debug(f"   ✅ File uploaded to storage: {file_path}")
            except Exception as upload_err:
                logger.error(f"   ❌ Upload failed: {str(upload_err)}")
                raise Exception(f"Failed to upload to storage: {str(upload_err)}")
            
            # Generate signed URL (valid for 1 hour) since bucket is private
            try:
                signed_url_response = client.storage.from_("admin-uploads").create_signed_url(
                    path=file_path,
                    expires_in=3600  # 1 hour expiration
                )
                file_url = signed_url_response.get("signedURL") if isinstance(signed_url_response, dict) else str(signed_url_response)
                logger.debug(f"   ✅ Generated signed URL for file")
            except Exception as url_err:
                logger.warning(f"   ⚠️  Could not generate signed URL: {str(url_err)}")
                file_url = None
            
            # Store file metadata in database
            # Note: file_name is the original filename (for display), file_path uses sanitized filename (for storage)
            try:
                # Check if file already exists (by original filename)
                existing = client.table("assistant_files").select("id").eq("assistant_id", assistant_id).eq("file_name", file_name).execute()
                
                file_record_id = None
                if existing.data:
                    # Update existing record
                    update_result = client.table("assistant_files").update({
                        "file_path": file_path,  # Store sanitized path
                        "file_size": file_size,
                        "uploaded_at": datetime.utcnow().isoformat(),
                        "uploaded_by": user_id
                    }).eq("id", existing.data[0]["id"]).execute()
                    file_record_id = existing.data[0]["id"]
                    logger.debug(f"   ✅ Updated file metadata in database")
                else:
                    # Insert new record
                    insert_result = client.table("assistant_files").insert({
                        "assistant_id": assistant_id,
                        "file_name": file_name,  # Original filename for display
                        "file_path": file_path,  # Sanitized path for storage
                        "file_size": file_size,
                        "uploaded_by": user_id
                    }).execute()
                    if insert_result.data:
                        file_record_id = insert_result.data[0].get("id", file_path)
                    logger.debug(f"   ✅ Stored file metadata in database")
            except Exception as db_err:
                logger.warning(f"   ⚠️  Could not store file metadata: {str(db_err)}")
                file_record_id = file_path
            
            return FileUploadResponse(
                id=file_record_id or storage_response.get("id", file_path),
                assistant_id=assistant_id,
                file_name=file_name,
                file_url=file_url,
                file_size=file_size,
                uploaded_at=datetime.utcnow(),
                uploaded_by=user_id
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to upload file: {str(e)}")
            logger.exception("Full error traceback:")
            raise Exception(f"Failed to upload file: {str(e)}")
    
    def get_files_for_assistant(self, assistant_id: str) -> List[FileUploadResponse]:
        """Get all files for a specific assistant"""
        logger.debug(f"📋 Getting files for assistant: {assistant_id}")
        try:
            client = self._get_supabase_client()
            
            # First, get files from database
            try:
                db_files = client.table("assistant_files").select("*").eq("assistant_id", assistant_id).order("uploaded_at", desc=True).execute()
            except Exception as db_err:
                logger.warning(f"   ⚠️  Could not query database: {str(db_err)}")
                db_files = type('obj', (object,), {'data': []})()
            
            files = []
            if db_files.data:
                for file_record in db_files.data:
                    file_name = file_record.get("file_name", "")
                    file_path = file_record.get("file_path", f"assistants/{assistant_id}/{file_name}")
                    openai_file_id = file_record.get("openai_file_id")
                    
                    # Generate signed URL
                    try:
                        signed_url_response = client.storage.from_("admin-uploads").create_signed_url(
                            path=file_path,
                            expires_in=3600
                        )
                        file_url = signed_url_response.get("signedURL") if isinstance(signed_url_response, dict) else str(signed_url_response)
                    except Exception:
                        file_url = None
                    
                    uploaded_at_str = file_record.get("uploaded_at", "")
                    try:
                        if uploaded_at_str:
                            uploaded_at = datetime.fromisoformat(uploaded_at_str.replace("Z", "+00:00"))
                        else:
                            uploaded_at = datetime.utcnow()
                    except Exception:
                        uploaded_at = datetime.utcnow()
                    
                    files.append(FileUploadResponse(
                        id=file_record.get("id", file_path),
                        assistant_id=assistant_id,
                        file_name=file_name,
                        file_url=file_url,
                        file_size=file_record.get("file_size"),
                        uploaded_at=uploaded_at,
                        uploaded_by=file_record.get("uploaded_by", "system"),
                        openai_file_id=openai_file_id
                    ))
            
            logger.debug(f"   ✅ Found {len(files)} files for assistant: {assistant_id}")
            return files
            
        except Exception as e:
            logger.error(f"❌ Failed to get files: {str(e)}")
            logger.exception("Full error traceback:")
            return []
    
    def delete_file(self, assistant_id: str, file_name: str) -> bool:
        """Delete a file from storage"""
        logger.info(f"🗑️  Deleting file - Assistant: {assistant_id}, File: {file_name}")
        try:
            client = self._get_supabase_client()
            file_path = f"assistants/{assistant_id}/{file_name}"
            
            client.storage.from_("admin-uploads").remove([file_path])
            
            logger.info(f"   ✅ File deleted: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete file: {str(e)}")
            logger.exception("Full error traceback:")
            return False
    
    async def upload_course_file(
        self,
        user_id: str,
        course_id: str,
        file_content: bytes,
        file_name: str,
        file_size: int,
        file_type: str = "content"  # 'behavior' or 'content'
    ) -> FileUploadResponse:
        """Upload a PDF file for a specific course"""
        logger.info(f"📤 Uploading course file - User: {user_id}, Course: {course_id}, File: {file_name}, Type: {file_type}")
        
        try:
            client = self._get_supabase_client()
            
            # Ensure bucket exists before uploading
            self._ensure_bucket_exists("admin-uploads")
            
            # Sanitize filename for storage (keep original for database)
            sanitized_filename = self._sanitize_filename_for_storage(file_name)
            
            # Create file path in storage (separate folders for behavior and content)
            folder = "behavior" if file_type == "behavior" else "content"
            file_path = f"courses/{course_id}/{folder}/{sanitized_filename}"
            
            # Upload to Supabase Storage
            try:
                storage_response = client.storage.from_("admin-uploads").upload(
                    path=file_path,
                    file=file_content,
                    file_options={"content-type": "application/pdf", "upsert": "true"}
                )
                logger.debug(f"   ✅ File uploaded to storage: {file_path}")
            except Exception as upload_err:
                logger.error(f"   ❌ Upload failed: {str(upload_err)}")
                raise Exception(f"Failed to upload to storage: {str(upload_err)}")
            
            # Generate signed URL (valid for 1 hour) since bucket is private
            try:
                signed_url_response = client.storage.from_("admin-uploads").create_signed_url(
                    path=file_path,
                    expires_in=3600  # 1 hour expiration
                )
                file_url = signed_url_response.get("signedURL") if isinstance(signed_url_response, dict) else str(signed_url_response)
                logger.debug(f"   ✅ Generated signed URL for course file")
            except Exception as url_err:
                logger.warning(f"   ⚠️  Could not generate signed URL: {str(url_err)}")
                file_url = None
            
            # Store file metadata in course_files table
            try:
                file_record = client.table("course_files").insert({
                    "course_id": course_id,
                    "file_name": file_name,
                    "file_url": file_url,
                    "file_size": file_size,
                    "uploaded_by": user_id,
                    "file_type": file_type
                }).execute()
                
                if file_record.data:
                    logger.debug(f"   ✅ File metadata saved to database")
            except Exception as db_err:
                logger.warning(f"   ⚠️  Could not save file metadata to database: {str(db_err)}")
            
            return FileUploadResponse(
                id=storage_response.get("id", file_path) if isinstance(storage_response, dict) else file_path,
                assistant_id=course_id,  # Reusing assistant_id field for course_id
                file_name=file_name,
                file_url=file_url,
                file_size=file_size,
                uploaded_at=datetime.utcnow(),
                uploaded_by=user_id,
                file_type=file_type
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to upload course file: {str(e)}")
            logger.exception("Full error traceback:")
            raise Exception(f"Failed to upload course file: {str(e)}")
    
    def get_course_files(self, course_id: str, file_type: Optional[str] = None) -> List[FileUploadResponse]:
        """Get all files for a specific course, optionally filtered by file_type"""
        logger.debug(f"📋 Getting files for course: {course_id}, Type: {file_type or 'all'}")
        try:
            client = self._get_supabase_client()
            
            # Try to get from database first
            try:
                query = client.table("course_files").select("*").eq("course_id", course_id)
                if file_type:
                    query = query.eq("file_type", file_type)
                db_files = query.order("uploaded_at", desc=True).execute()
                
                if db_files.data:
                    files = []
                    for file_record in db_files.data:
                        # Generate fresh signed URL for each file (since stored URLs may be expired)
                        file_type_folder = file_record.get("file_type", "content")
                        # Try new path first (with file_type folder)
                        file_path = f"courses/{course_id}/{file_type_folder}/{file_record['file_name']}"
                        file_url = None
                        try:
                            signed_url_response = client.storage.from_("admin-uploads").create_signed_url(
                                path=file_path,
                                expires_in=3600  # 1 hour expiration
                            )
                            file_url = signed_url_response.get("signedURL") if isinstance(signed_url_response, dict) else str(signed_url_response)
                        except Exception as url_err:
                            # Try old path (backward compatibility for files uploaded before migration)
                            logger.debug(f"   ⚠️  New path failed, trying old path: {str(url_err)}")
                            try:
                                old_file_path = f"courses/{course_id}/{file_record['file_name']}"
                                signed_url_response = client.storage.from_("admin-uploads").create_signed_url(
                                    path=old_file_path,
                                    expires_in=3600
                                )
                                file_url = signed_url_response.get("signedURL") if isinstance(signed_url_response, dict) else str(signed_url_response)
                                logger.debug(f"   ✅ Found file at old path: {old_file_path}")
                            except Exception as old_path_err:
                                logger.warning(f"   ⚠️  Could not generate signed URL for {file_record['file_name']} (tried both paths): {str(old_path_err)}")
                        
                        files.append(FileUploadResponse(
                            id=file_record["id"],
                            assistant_id=course_id,
                            file_name=file_record["file_name"],
                            file_url=file_url,
                            file_size=file_record.get("file_size"),
                            uploaded_at=datetime.fromisoformat(file_record["uploaded_at"].replace("Z", "+00:00")) if file_record.get("uploaded_at") else datetime.utcnow(),
                            uploaded_by=file_record["uploaded_by"],
                            file_type=file_record.get("file_type", "content"),
                            openai_file_id=file_record.get("openai_file_id")  # Include OpenAI file ID
                        ))
                    logger.debug(f"   ✅ Found {len(files)} files in database for course: {course_id}")
                    return files
            except Exception as db_err:
                logger.warning(f"   ⚠️  Could not get files from database: {str(db_err)}")
            
            # Fallback to storage listing
            try:
                files_response = client.storage.from_("admin-uploads").list(path=f"courses/{course_id}/")
            except Exception as list_err:
                logger.warning(f"   ⚠️  Could not list files from storage: {str(list_err)}")
                files_response = []
            
            files = []
            if files_response:
                for file_info in files_response:
                    file_name = file_info.get("name", "")
                    if file_name and not file_name.endswith("/") and file_name.endswith(".pdf"):
                        file_path = f"courses/{course_id}/{file_name}"
                        try:
                            # Generate fresh signed URL (valid for 1 hour)
                            signed_url_response = client.storage.from_("admin-uploads").create_signed_url(
                                path=file_path,
                                expires_in=3600
                            )
                            file_url = signed_url_response.get("signedURL") if isinstance(signed_url_response, dict) else str(signed_url_response)
                        except Exception:
                            file_url = None
                        
                        created_at_str = file_info.get("created_at", "")
                        try:
                            uploaded_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")) if created_at_str else datetime.utcnow()
                        except Exception:
                            uploaded_at = datetime.utcnow()
                        
                        files.append(FileUploadResponse(
                            id=file_info.get("id", file_path),
                            assistant_id=course_id,
                            file_name=file_name,
                            file_url=file_url,
                            file_size=file_info.get("metadata", {}).get("size") if isinstance(file_info.get("metadata"), dict) else file_info.get("size"),
                            uploaded_at=uploaded_at,
                            uploaded_by="system"
                        ))
            
            logger.debug(f"   ✅ Found {len(files)} files for course: {course_id}")
            return files
            
        except Exception as e:
            logger.error(f"❌ Failed to get course files: {str(e)}")
            logger.exception("Full error traceback:")
            return []
    
    def delete_course_file(self, course_id: str, file_name: str, file_type: Optional[str] = None) -> bool:
        """Delete a course file from storage and database"""
        logger.info(f"🗑️  Deleting course file - Course: {course_id}, File: {file_name}, Type: {file_type or 'unknown'}")
        try:
            client = self._get_supabase_client()
            
            # If file_type is not provided, try to get it from database
            if not file_type:
                try:
                    file_record = client.table("course_files").select("file_type").eq("course_id", course_id).eq("file_name", file_name).execute()
                    if file_record.data and len(file_record.data) > 0:
                        file_type = file_record.data[0].get("file_type", "content")
                except Exception:
                    file_type = "content"  # Default fallback
            
            # Delete from database first (so it's removed even if storage deletion fails)
            db_deleted = False
            try:
                delete_result = client.table("course_files").delete().eq("course_id", course_id).eq("file_name", file_name).execute()
                if delete_result.data:
                    db_deleted = True
                    logger.debug(f"   ✅ File metadata deleted from database")
                else:
                    logger.warning(f"   ⚠️  No file found in database to delete")
            except Exception as db_err:
                logger.error(f"   ❌ Could not delete file metadata from database: {str(db_err)}")
                # Still try to delete from storage
            
            # Try to delete from storage - check both new and old paths
            deleted_from_storage = False
            folder = file_type if file_type in ["behavior", "content"] else "content"
            file_path = f"courses/{course_id}/{folder}/{file_name}"
            
            try:
                client.storage.from_("admin-uploads").remove([file_path])
                deleted_from_storage = True
                logger.debug(f"   ✅ File deleted from storage at new path: {file_path}")
            except Exception as new_path_err:
                # Try old path (backward compatibility)
                logger.debug(f"   ⚠️  New path deletion failed, trying old path: {str(new_path_err)}")
                try:
                    old_file_path = f"courses/{course_id}/{file_name}"
                    client.storage.from_("admin-uploads").remove([old_file_path])
                    deleted_from_storage = True
                    logger.debug(f"   ✅ File deleted from storage at old path: {old_file_path}")
                except Exception as old_path_err:
                    logger.warning(f"   ⚠️  Could not delete file from storage (tried both paths): {str(old_path_err)}")
                    # Continue - database deletion is more important
            
            # Return success if database was deleted (storage deletion is optional)
            if db_deleted:
                logger.info(f"   ✅ Course file deleted successfully (database: ✅, storage: {'✅' if deleted_from_storage else '⚠️'})")
                return True
            else:
                logger.error(f"   ❌ Failed to delete file from database")
                return False
            
        except Exception as e:
            logger.error(f"❌ Failed to delete course file: {str(e)}")
            logger.exception("Full error traceback:")
            return False
    
    def download_file(self, assistant_id: str, file_name: str) -> bytes:
        """Download a file from storage (legacy method - use download_assistant_file)"""
        return self.download_assistant_file(assistant_id, file_name)
    
    def download_assistant_file(self, assistant_id: str, file_name: str) -> bytes:
        """Download an assistant file from Supabase Storage"""
        logger.info(f"📥 Downloading assistant file - Assistant: {assistant_id}, File: {file_name}")
        try:
            client = self._get_supabase_client()
            
            # Get file path from database
            try:
                file_record = client.table("assistant_files").select("file_path").eq("assistant_id", assistant_id).eq("file_name", file_name).execute()
                if file_record.data:
                    file_path = file_record.data[0].get("file_path", f"assistants/{assistant_id}/{file_name}")
                else:
                    file_path = f"assistants/{assistant_id}/{file_name}"
            except Exception:
                file_path = f"assistants/{assistant_id}/{file_name}"
            
            # Download from storage
            file_content = client.storage.from_("admin-uploads").download(file_path)
            
            if isinstance(file_content, bytes):
                logger.info(f"   ✅ Assistant file downloaded: {file_name} ({len(file_content)} bytes)")
                return file_content
            else:
                raise Exception("Invalid file data received")
                
        except Exception as e:
            logger.error(f"❌ Failed to download assistant file: {str(e)}")
            logger.exception("Full error traceback:")
            raise Exception(f"Failed to download assistant file: {str(e)}")
    
    def download_course_file(self, course_id: str, file_name: str, file_type: Optional[str] = None) -> bytes:
        """Download a course file from storage"""
        logger.info(f"📥 Downloading course file - Course: {course_id}, File: {file_name}, Type: {file_type or 'unknown'}")
        try:
            client = self._get_supabase_client()
            
            # If file_type is not provided, try to get it from database
            if not file_type:
                try:
                    file_record = client.table("course_files").select("file_type").eq("course_id", course_id).eq("file_name", file_name).execute()
                    if file_record.data and len(file_record.data) > 0:
                        file_type = file_record.data[0].get("file_type", "content")
                except Exception:
                    file_type = "content"  # Default fallback
            
            # Try new path first (with file_type folder)
            folder = file_type if file_type in ["behavior", "content"] else "content"
            file_path = f"courses/{course_id}/{folder}/{file_name}"
            
            try:
                # Download file from storage
                file_content = client.storage.from_("admin-uploads").download(file_path)
                logger.info(f"   ✅ Course file downloaded from new path: {file_name} ({len(file_content)} bytes)")
                return file_content
            except Exception as new_path_err:
                # Try old path (backward compatibility)
                logger.debug(f"   ⚠️  New path download failed, trying old path: {str(new_path_err)}")
                try:
                    old_file_path = f"courses/{course_id}/{file_name}"
                    file_content = client.storage.from_("admin-uploads").download(old_file_path)
                    logger.info(f"   ✅ Course file downloaded from old path: {file_name} ({len(file_content)} bytes)")
                    return file_content
                except Exception as old_path_err:
                    logger.error(f"   ❌ Failed to download from both paths: {str(old_path_err)}")
                    raise Exception(f"Failed to download course file from both new and old paths: {str(old_path_err)}")
            
        except Exception as e:
            logger.error(f"❌ Failed to download course file: {str(e)}")
            logger.exception("Full error traceback:")
            raise Exception(f"Failed to download course file: {str(e)}")

