from fastapi import APIRouter, Depends, HTTPException, status
import logging
from typing import Optional
from app.models.course import CourseCreateRequest, CourseResponse, EnrollCourseRequest, StudentCourseResponse
from app.services.course_service import CourseService
from app.api.auth.dependencies import get_current_user
from app.models.auth import UserResponse

router = APIRouter(prefix="/course", tags=["courses"])
logger = logging.getLogger(__name__)

@router.post("/create", response_model=CourseResponse)
async def create_course(
    request: CourseCreateRequest,
    current_user = Depends(get_current_user),
    course_service: CourseService = Depends(lambda: CourseService())
):
    """
    Create a new course (admin only)
    """
    logger.info(f"📥 Create course request - Code: {request.code}, Name: {request.name}")
    
    # Check if user is admin
    user_metadata = current_user.user_metadata or {}
    is_admin = user_metadata.get("is_admin", False) or user_metadata.get("role") == "admin"
    
    if not is_admin:
        logger.warning(f"⚠️  Non-admin user attempted to create course: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create courses"
        )
    
    try:
        course = course_service.create_course(
            code=request.code,
            name=request.name,
            description=request.description,
            created_by=current_user.id
        )
        
        logger.info(f"✅ Course created successfully - ID: {course['id']}")
        return CourseResponse(**course)
    except Exception as e:
        logger.error(f"❌ Failed to create course: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create course: {str(e)}"
        )

@router.get("/list", response_model=list[CourseResponse])
async def list_courses(
    course_service: CourseService = Depends(lambda: CourseService())
):
    """
    Get all active courses
    """
    logger.info("📥 List courses request")
    try:
        courses = course_service.get_all_courses()
        logger.info(f"✅ Returning {len(courses)} courses")
        return [CourseResponse(**course) for course in courses]
    except Exception as e:
        logger.error(f"❌ Failed to list courses: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to list courses: {str(e)}"
        )

@router.post("/enroll", response_model=StudentCourseResponse)
async def enroll_course(
    request: EnrollCourseRequest,
    current_user = Depends(get_current_user),
    course_service: CourseService = Depends(lambda: CourseService())
):
    """
    Enroll in a course by code
    """
    logger.info(f"📥 Enroll course request - Code: {request.course_code}, User: {current_user.email}")
    
    try:
        # Get course by code
        course = course_service.get_course_by_code(request.course_code)
        
        if not course:
            logger.warning(f"⚠️  Course not found with code: {request.course_code}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )
        
        # Enroll student
        enrollment = course_service.enroll_student_in_course(
            user_id=current_user.id,
            course_id=course["id"]
        )
        
        # Create course chat session
        chat_session = course_service.create_course_chat_session(
            user_id=current_user.id,
            course_id=course["id"]
        )
        
        logger.info(f"✅ Student enrolled successfully - Course: {course['name']}")
        
        # Build response with course details
        enrollment["course"] = course
        return StudentCourseResponse(**enrollment)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to enroll in course: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to enroll in course: {str(e)}"
        )

@router.get("/my-courses", response_model=list[StudentCourseResponse])
async def get_my_courses(
    current_user: UserResponse = Depends(get_current_user),
    course_service: CourseService = Depends(lambda: CourseService())
):
    """
    Get all courses enrolled by the current user
    """
    logger.info(f"📥 Get my courses request - User: {current_user.email}")
    try:
        enrollments = course_service.get_student_courses(current_user.id)
        
        # Transform nested course data
        result = []
        for enrollment in enrollments:
            if isinstance(enrollment.get("course"), list) and len(enrollment["course"]) > 0:
                enrollment["course"] = enrollment["course"][0]
            result.append(StudentCourseResponse(**enrollment))
        
        logger.info(f"✅ Returning {len(result)} enrolled courses")
        return result
    except Exception as e:
        logger.error(f"❌ Failed to get my courses: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get my courses: {str(e)}"
        )

@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    code: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    course_service: CourseService = Depends(lambda: CourseService())
):
    """
    Update a course (admin only)
    """
    logger.info(f"📥 Update course request - ID: {course_id}, User: {current_user.email}")
    
    # Check if user is admin
    user_metadata = current_user.user_metadata or {}
    is_admin = user_metadata.get("is_admin", False) or user_metadata.get("role") == "admin"
    
    if not is_admin:
        logger.warning(f"⚠️  Non-admin user attempted to update course: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update courses"
        )
    
    try:
        course = course_service.update_course(course_id, name=name, description=description, code=code)
        logger.info(f"✅ Course updated successfully - ID: {course_id}")
        return CourseResponse(**course)
    except Exception as e:
        logger.error(f"❌ Failed to update course: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update course: {str(e)}"
        )

@router.delete("/{course_id}")
async def delete_course(
    course_id: str,
    current_user: UserResponse = Depends(get_current_user),
    course_service: CourseService = Depends(lambda: CourseService())
):
    """
    Delete (deactivate) a course (admin only)
    """
    logger.info(f"📥 Delete course request - ID: {course_id}, User: {current_user.email}")
    
    # Check if user is admin
    user_metadata = current_user.user_metadata or {}
    is_admin = user_metadata.get("is_admin", False) or user_metadata.get("role") == "admin"
    
    if not is_admin:
        logger.warning(f"⚠️  Non-admin user attempted to delete course: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete courses"
        )
    
    try:
        success = course_service.delete_course(course_id)
        if success:
            logger.info(f"✅ Course deleted successfully - ID: {course_id}")
            return {"message": "Course deleted successfully", "course_id": course_id}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete course"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete course: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete course: {str(e)}"
        )

