from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import List
import logging
from app.models.admin import FileUploadResponse, FileListResponse
from app.services.admin_service import AdminService
from app.api.auth.dependencies import get_current_user
from app.models.auth import UserResponse
from app.models.chat import AssistantType
import io

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

async def check_admin(
    current_user: UserResponse = Depends(get_current_user),
    admin_service: AdminService = Depends(lambda: AdminService())
) -> UserResponse:
    """Dependency to check if user is admin"""
    logger.debug(f"🔐 Checking admin access for user: {current_user.email}")
    
    # Pass user_metadata directly to avoid Auth Admin API call (which requires special permissions)
    # This uses the metadata already available from token verification
    is_admin = admin_service.is_admin(
        current_user.id, 
        user_metadata=current_user.user_metadata or {}
    )
    
    if not is_admin:
        logger.warning(f"   ⚠️  Access denied - User {current_user.email} is not an admin")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    logger.debug(f"   ✅ Admin access granted for: {current_user.email}")
    return current_user

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    assistant_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(check_admin),
    admin_service: AdminService = Depends(lambda: AdminService())
):
    """Upload a PDF file for a specific assistant"""
    logger.info(f"📤 Upload request - User: {current_user.email}, Assistant: {assistant_id}, File: {file.filename}")
    
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        logger.warning(f"   ⚠️  Invalid file type: {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )
    
    # Validate assistant ID
    try:
        assistant_type = AssistantType(assistant_id)
    except ValueError:
        logger.warning(f"   ⚠️  Invalid assistant ID: {assistant_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid assistant_id: {assistant_id}"
        )
    
    try:
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        logger.debug(f"   File size: {file_size} bytes")
        
        # Upload file
        uploaded_file = await admin_service.upload_file(
            user_id=current_user.id,
            assistant_id=assistant_id,
            file_content=file_content,
            file_name=file.filename,
            file_size=file_size
        )
        
        logger.info(f"✅ File uploaded successfully - ID: {uploaded_file.id}")
        return uploaded_file
        
    except Exception as e:
        logger.error(f"❌ Failed to upload file: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )

@router.get("/files/{assistant_id}", response_model=FileListResponse)
async def get_files(
    assistant_id: str,
    current_user: UserResponse = Depends(check_admin),
    admin_service: AdminService = Depends(lambda: AdminService())
):
    """Get all files for a specific assistant"""
    logger.info(f"📋 Getting files - User: {current_user.email}, Assistant: {assistant_id}")
    
    # Validate assistant ID
    try:
        assistant_type = AssistantType(assistant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid assistant_id: {assistant_id}"
        )
    
    try:
        files = admin_service.get_files_for_assistant(assistant_id)
        logger.info(f"✅ Retrieved {len(files)} files for assistant: {assistant_id}")
        
        return FileListResponse(
            files=files,
            total=len(files)
        )
    except Exception as e:
        logger.error(f"❌ Failed to get files: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve files"
        )

@router.delete("/files/{assistant_id}/{file_name}")
async def delete_file(
    assistant_id: str,
    file_name: str,
    current_user: UserResponse = Depends(check_admin),
    admin_service: AdminService = Depends(lambda: AdminService())
):
    """Delete a file for a specific assistant"""
    logger.info(f"🗑️  Delete request - User: {current_user.email}, Assistant: {assistant_id}, File: {file_name}")
    
    # Validate assistant ID
    try:
        assistant_type = AssistantType(assistant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid assistant_id: {assistant_id}"
        )
    
    try:
        success = admin_service.delete_file(assistant_id, file_name)
        
        if success:
            logger.info(f"✅ File deleted successfully: {file_name}")
            return {"message": "File deleted successfully", "file_name": file_name}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete file"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete file: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )

@router.post("/courses/{course_id}/upload", response_model=FileUploadResponse)
async def upload_course_file(
    course_id: str,
    file: UploadFile = File(...),
    file_type: str = Form("content"),  # 'behavior' or 'content'
    current_user: UserResponse = Depends(check_admin),
    admin_service: AdminService = Depends(lambda: AdminService())
):
    """Upload a PDF file for a specific course (content or behavior)"""
    logger.info(f"📤 Course file upload request - User: {current_user.email}, Course: {course_id}, File: {file.filename}, Type: {file_type}")
    
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        logger.warning(f"   ⚠️  Invalid file type: {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )
    
    # Validate file_type parameter
    if file_type not in ['behavior', 'content']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_type must be 'behavior' or 'content'"
        )
    
    try:
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        logger.debug(f"   File size: {file_size} bytes")
        
        # Upload file
        uploaded_file = await admin_service.upload_course_file(
            user_id=current_user.id,
            course_id=course_id,
            file_content=file_content,
            file_name=file.filename,
            file_size=file_size,
            file_type=file_type
        )
        
        logger.info(f"✅ Course file uploaded successfully - ID: {uploaded_file.id}, Type: {file_type}")
        return uploaded_file
        
    except Exception as e:
        logger.error(f"❌ Failed to upload course file: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload course file: {str(e)}"
        )

@router.get("/courses/{course_id}/files", response_model=FileListResponse)
async def get_course_files(
    course_id: str,
    current_user: UserResponse = Depends(check_admin),
    admin_service: AdminService = Depends(lambda: AdminService())
):
    """Get all files for a specific course"""
    logger.info(f"📋 Getting course files - User: {current_user.email}, Course: {course_id}")
    
    try:
        files = admin_service.get_course_files(course_id)
        logger.info(f"✅ Retrieved {len(files)} files for course: {course_id}")
        
        return FileListResponse(
            files=files,
            total=len(files)
        )
    except Exception as e:
        logger.error(f"❌ Failed to get course files: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve course files"
        )

@router.delete("/courses/{course_id}/files/{file_name}")
async def delete_course_file(
    course_id: str,
    file_name: str,
    current_user: UserResponse = Depends(check_admin),
    admin_service: AdminService = Depends(lambda: AdminService())
):
    """Delete a file for a specific course"""
    logger.info(f"🗑️  Delete course file request - User: {current_user.email}, Course: {course_id}, File: {file_name}")
    
    try:
        success = admin_service.delete_course_file(course_id, file_name)
        
        if success:
            logger.info(f"✅ Course file deleted successfully: {file_name}")
            return {"message": "Course file deleted successfully", "file_name": file_name}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete course file"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete course file: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete course file: {str(e)}"
        )

@router.get("/files/{assistant_id}/{file_name}/download")
async def download_file(
    assistant_id: str,
    file_name: str,
    current_user: UserResponse = Depends(check_admin),
    admin_service: AdminService = Depends(lambda: AdminService())
):
    """Download a file from storage"""
    logger.info(f"📥 Download request - User: {current_user.email}, Assistant: {assistant_id}, File: {file_name}")
    
    try:
        # Download file from storage
        file_content = admin_service.download_file(assistant_id, file_name)
        
        # Return file as streaming response
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{file_name}"',
                "Content-Type": "application/pdf"
            }
        )
    except Exception as e:
        logger.error(f"❌ Failed to download file: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {str(e)}"
        )

@router.get("/courses/{course_id}/files/{file_name}/download")
async def download_course_file(
    course_id: str,
    file_name: str,
    current_user: UserResponse = Depends(check_admin),
    admin_service: AdminService = Depends(lambda: AdminService())
):
    """Download a course file from storage"""
    logger.info(f"📥 Course file download request - User: {current_user.email}, Course: {course_id}, File: {file_name}")
    
    try:
        # Download file from storage
        file_content = admin_service.download_course_file(course_id, file_name)
        
        # Return file as streaming response
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{file_name}"',
                "Content-Type": "application/pdf"
            }
        )
    except Exception as e:
        logger.error(f"❌ Failed to download course file: {str(e)}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download course file: {str(e)}"
        )

