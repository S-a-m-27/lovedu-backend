# Admin Panel Setup Guide

## Prerequisites

1. Admin user account - A user with `is_admin: true` in their `user_metadata` in Supabase
2. Supabase Storage bucket named `admin-uploads`

## Setting Up Admin User

To make a user an admin, update their user metadata in Supabase:

1. Go to Supabase Dashboard → Authentication → Users
2. Find the user you want to make admin
3. Click on the user to edit
4. In the "User Metadata" section, add:
   ```json
   {
     "is_admin": true
   }
   ```
   OR set:
   ```json
   {
     "role": "admin"
   }
   ```

## Setting Up Supabase Storage

1. Go to Supabase Dashboard → Storage
2. Create a new bucket named `admin-uploads`
3. Set bucket to **Public** (if you want public URLs) or **Private** (for authenticated access only)
4. Enable the bucket

## API Endpoints

### Upload File
```
POST /admin/upload
Content-Type: multipart/form-data

Form fields:
- assistant_id: string (one of: typeX, references, academicReferences, therapyGPT, whatsTrendy)
- file: File (PDF file)

Headers:
Authorization: Bearer <admin_jwt_token>
```

### Get Files for Assistant
```
GET /admin/files/{assistant_id}

Headers:
Authorization: Bearer <admin_jwt_token>
```

### Delete File
```
DELETE /admin/files/{assistant_id}/{file_name}

Headers:
Authorization: Bearer <admin_jwt_token>
```

## Frontend Access

The admin panel is accessible at `/admin` route. Users must have admin privileges to access it.

## File Storage Structure

Files are stored in Supabase Storage with the following structure:
```
admin-uploads/
  assistants/
    typeX/
      file1.pdf
      file2.pdf
    references/
      file1.pdf
    ...
```

## Notes

- Only PDF files are accepted
- Files are organized by assistant ID
- The admin service automatically handles file paths and URLs
- File metadata (uploaded_by, uploaded_at) is tracked

