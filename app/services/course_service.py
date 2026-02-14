import logging
from typing import List, Optional
from supabase import create_client
from supabase.lib.client_options import ClientOptions
import os
from app.models.course import CourseResponse, StudentCourseResponse

logger = logging.getLogger(__name__)

class CourseService:
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not supabase_service_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        
        # Configure client to use api schema (all tables are in api schema)
        client_options = ClientOptions(schema="api")
        self.supabase = create_client(supabase_url, supabase_service_key, options=client_options)
        logger.info("✅ CourseService initialized (api schema)")
    
    def create_course(self, code: str, name: str, description: Optional[str], created_by: str) -> dict:
        """Create a new course (admin only)"""
        logger.info(f"📝 Creating course - Code: {code}, Name: {name}, Created by: {created_by}")
        try:
            response = self.supabase.table("courses").insert({
                "code": code,
                "name": name,
                "description": description,
                "created_by": created_by,
                "is_active": True
            }).execute()
            
            if response.data:
                logger.info(f"✅ Course created successfully - ID: {response.data[0]['id']}")
                return response.data[0]
            else:
                error_msg = "Failed to create course - no data returned"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Failed to create course: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def get_course_by_code(self, code: str) -> Optional[dict]:
        """Get course by code"""
        logger.info(f"🔍 Searching for course with code: {code}")
        try:
            response = self.supabase.table("courses").select("*").eq("code", code).eq("is_active", True).execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"✅ Course found - ID: {response.data[0]['id']}, Name: {response.data[0]['name']}")
                return response.data[0]
            else:
                logger.warning(f"⚠️  Course not found with code: {code}")
                return None
        except Exception as e:
            error_msg = f"Failed to get course by code: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def get_all_courses(self) -> List[dict]:
        """Get all active courses"""
        logger.info("📋 Fetching all active courses")
        try:
            response = self.supabase.table("courses").select("*").eq("is_active", True).order("created_at", desc=True).execute()
            
            if response.data:
                logger.info(f"✅ Found {len(response.data)} active courses")
                return response.data
            else:
                logger.info("ℹ️  No courses found")
                return []
        except Exception as e:
            error_msg = f"Failed to get all courses: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def enroll_student_in_course(self, user_id: str, course_id: str) -> dict:
        """Enroll a student in a course"""
        logger.info(f"📚 Enrolling student {user_id} in course {course_id}")
        try:
            # Check if already enrolled
            existing = self.supabase.table("student_courses").select("*").eq("user_id", user_id).eq("course_id", course_id).execute()
            
            if existing.data and len(existing.data) > 0:
                logger.info(f"ℹ️  Student already enrolled in course")
                return existing.data[0]
            
            # Enroll student
            response = self.supabase.table("student_courses").insert({
                "user_id": user_id,
                "course_id": course_id
            }).execute()
            
            if response.data:
                logger.info(f"✅ Student enrolled successfully")
                return response.data[0]
            else:
                error_msg = "Failed to enroll student - no data returned"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Failed to enroll student: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def get_student_courses(self, user_id: str) -> List[dict]:
        """Get all courses enrolled by a student"""
        logger.info(f"📋 Fetching courses for student: {user_id}")
        try:
            response = self.supabase.table("student_courses").select(
                "*, course:courses(*)"
            ).eq("user_id", user_id).order("enrolled_at", desc=True).execute()
            
            if response.data:
                logger.info(f"✅ Found {len(response.data)} enrolled courses")
                return response.data
            else:
                logger.info("ℹ️  No enrolled courses found")
                return []
        except Exception as e:
            error_msg = f"Failed to get student courses: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def create_course_chat_session(self, user_id: str, course_id: str) -> dict:
        """Create a chat session for a course"""
        logger.info(f"💬 Creating course chat session - User: {user_id}, Course: {course_id}")
        try:
            # Check if session already exists
            existing = self.supabase.table("chat_sessions").select("*").eq("user_id", user_id).eq("course_id", course_id).execute()
            
            if existing.data and len(existing.data) > 0:
                logger.info(f"ℹ️  Course chat session already exists")
                return existing.data[0]
            
            # Create new session with course_id
            response = self.supabase.table("chat_sessions").insert({
                "user_id": user_id,
                "assistant_id": "course",  # Special assistant_id for courses
                "course_id": course_id,
                "message_count": 0
            }).execute()
            
            if response.data:
                logger.info(f"✅ Course chat session created - ID: {response.data[0]['id']}")
                return response.data[0]
            else:
                error_msg = "Failed to create course chat session - no data returned"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Failed to create course chat session: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def update_course(self, course_id: str, name: Optional[str] = None, description: Optional[str] = None, code: Optional[str] = None) -> dict:
        """Update a course (admin only)"""
        logger.info(f"📝 Updating course - ID: {course_id}")
        try:
            update_data = {}
            if name is not None:
                update_data["name"] = name
            if description is not None:
                update_data["description"] = description
            if code is not None:
                update_data["code"] = code
            update_data["updated_at"] = "now()"
            
            response = self.supabase.table("courses").update(update_data).eq("id", course_id).execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"✅ Course updated successfully - ID: {course_id}")
                return response.data[0]
            else:
                error_msg = "Failed to update course - no data returned"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Failed to update course: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def delete_course(self, course_id: str) -> bool:
        """Delete (deactivate) a course (admin only)"""
        logger.info(f"🗑️  Deleting course - ID: {course_id}")
        try:
            # Soft delete by setting is_active to False
            response = self.supabase.table("courses").update({
                "is_active": False,
                "updated_at": "now()"
            }).eq("id", course_id).execute()
            
            if response.data:
                logger.info(f"✅ Course deactivated successfully - ID: {course_id}")
                return True
            else:
                error_msg = "Failed to delete course - no data returned"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Failed to delete course: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)
    
    def get_course_by_id(self, course_id: str) -> Optional[dict]:
        """Get course by ID"""
        logger.info(f"🔍 Fetching course by ID: {course_id}")
        try:
            response = self.supabase.table("courses").select("*").eq("id", course_id).execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"✅ Course found - ID: {course_id}, Name: {response.data[0]['name']}")
                return response.data[0]
            else:
                logger.warning(f"⚠️  Course not found with ID: {course_id}")
                return None
        except Exception as e:
            error_msg = f"Failed to get course by ID: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full error traceback:")
            raise Exception(error_msg)

