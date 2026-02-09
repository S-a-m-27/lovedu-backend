# Behavior PDF Implementation Guide

## Overview

The system now supports two types of PDFs for courses:
1. **Behavior PDFs** - Define agent behavior, rules, and guidelines
2. **Course Content PDFs** - Contain course materials (syllabi, lecture notes, etc.)

Both types are uploaded to OpenAI and used by the Assistants API for semantic search.

## Database Changes

### Migration Required

Run the migration SQL file:
```sql
-- Run: backend/migration_add_file_type.sql
```

This adds:
- `file_type` column to `course_files` table
- Values: `'behavior'` or `'content'`
- Default: `'content'` (for backward compatibility)
- Index for efficient filtering

## How It Works

### 1. File Storage Structure

Files are stored in Supabase Storage with separate folders:
```
admin-uploads/
  courses/
    {course_id}/
      behavior/
        behavior-file-1.pdf
        behavior-file-2.pdf
      content/
        syllabus.pdf
        lecture-notes.pdf
```

### 2. Upload Flow

**Backend Endpoint:**
- `POST /admin/courses/{course_id}/upload`
- Form parameter: `file_type` ('behavior' or 'content')
- Default: 'content' (if not specified)

**Frontend:**
- Two separate upload buttons in admin panel
- "Upload Behavior PDF" - uploads with `file_type='behavior'`
- "Upload Course Content PDF" - uploads with `file_type='content'`

### 3. Chat Flow

When a student chats about a course:

1. **Fetch Files:**
   - Get behavior PDFs: `get_course_files(course_id, file_type='behavior')`
   - Get content PDFs: `get_course_files(course_id, file_type='content')`

2. **Upload to OpenAI:**
   - Both types are uploaded to OpenAI
   - Files are processed and indexed

3. **Create Assistant:**
   - All files (behavior + content) are added to the same vector store
   - GPT can search through both types semantically

4. **Answer Questions:**
   - GPT searches both behavior and content PDFs
   - Behavior PDFs guide how to answer
   - Content PDFs provide course-specific information

## API Changes

### Backend

**Updated Methods:**
- `AdminService.upload_course_file()` - Now accepts `file_type` parameter
- `AdminService.get_course_files()` - Now accepts optional `file_type` filter
- `AdminService.download_course_file()` - Now handles file_type folder structure
- `AdminService.delete_course_file()` - Now handles file_type folder structure

**Updated Endpoints:**
- `POST /admin/courses/{course_id}/upload` - Accepts `file_type` form parameter

### Frontend

**Updated Methods:**
- `apiClient.uploadCourseFile()` - Now accepts `fileType` parameter
- `apiClient.getCourseFiles()` - Returns files with `file_type` field

**Updated UI:**
- Separate upload sections for behavior and content PDFs
- Separate state management for each type
- Visual distinction (blue for behavior, red for content)

## Usage Example

### Upload Behavior PDF (Admin)

```typescript
// Frontend
await apiClient.uploadCourseFile(courseId, file, 'behavior')
```

### Upload Content PDF (Admin)

```typescript
// Frontend
await apiClient.uploadCourseFile(courseId, file, 'content')
```

### Chat with Both PDFs (Student)

When a student chats about a course:
1. System automatically fetches both behavior and content PDFs
2. Both are uploaded to OpenAI
3. GPT uses both when answering questions

## Benefits

1. **Separation of Concerns:**
   - Behavior rules are separate from course content
   - Easier to manage and update

2. **Flexible Configuration:**
   - Each course can have its own behavior PDFs
   - Different courses can have different rules

3. **Semantic Search:**
   - GPT searches both types intelligently
   - Behavior PDFs guide responses
   - Content PDFs provide information

4. **Better Organization:**
   - Clear distinction in UI
   - Separate storage folders
   - Easy to filter and manage

## Testing

1. **Upload Behavior PDF:**
   - Go to admin panel
   - Select a course
   - Click "Upload Behavior PDF"
   - Select a PDF file
   - Verify upload success

2. **Upload Content PDF:**
   - Same course
   - Click "Upload Course Content PDF"
   - Select a PDF file
   - Verify upload success

3. **Test Chat:**
   - Enroll as student
   - Start course chat
   - Ask questions
   - Verify GPT uses both PDF types

## Migration Steps

1. **Run Database Migration:**
   ```sql
   -- Execute: backend/migration_add_file_type.sql
   ```

2. **Restart Backend:**
   - Backend code is already updated
   - No additional configuration needed

3. **Update Frontend:**
   - Frontend code is already updated
   - Refresh browser to see new UI

4. **Test:**
   - Upload behavior PDF
   - Upload content PDF
   - Test chat functionality

## Notes

- Existing files default to `'content'` type
- Behavior PDFs are uploaded to OpenAI same as content PDFs
- Both types are included in the same vector store
- GPT automatically searches both when answering questions
- No text extraction needed - OpenAI handles it via file_search tool

