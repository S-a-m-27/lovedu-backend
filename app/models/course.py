from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class CourseCreateRequest(BaseModel):
    code: str
    name: str
    description: Optional[str] = None

class CourseResponse(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

class EnrollCourseRequest(BaseModel):
    course_code: str

class StudentCourseResponse(BaseModel):
    id: str
    course_id: str
    course: CourseResponse
    enrolled_at: datetime
    
    class Config:
        from_attributes = True

