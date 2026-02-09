"""
Migration script to move old course files to new folder structure
Run this script to migrate files from courses/{course_id}/{file_name} 
to courses/{course_id}/content/{file_name}

Usage:
    python migrate_old_course_files.py
"""

import os
import sys
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def migrate_course_files():
    """Migrate old course files to new folder structure"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_service_key:
        print("❌ SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)
    
    client = create_client(supabase_url, supabase_service_key)
    
    print("🔄 Starting migration of course files...")
    
    # Get all course files from database
    try:
        files_response = client.table("course_files").select("*").execute()
        files = files_response.data if files_response.data else []
        
        print(f"📋 Found {len(files)} files in database")
        
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        for file_record in files:
            course_id = file_record["course_id"]
            file_name = file_record["file_name"]
            file_type = file_record.get("file_type", "content")  # Default to content
            
            old_path = f"courses/{course_id}/{file_name}"
            new_path = f"courses/{course_id}/{file_type}/{file_name}"
            
            try:
                # Check if file exists at old path
                try:
                    # Try to download from old path
                    old_file = client.storage.from_("admin-uploads").download(old_path)
                    
                    # Upload to new path
                    client.storage.from_("admin-uploads").upload(
                        path=new_path,
                        file=old_file,
                        file_options={"content-type": "application/pdf", "upsert": "true"}
                    )
                    
                    # Delete from old path
                    client.storage.from_("admin-uploads").remove([old_path])
                    
                    print(f"   ✅ Migrated: {file_name} ({old_path} → {new_path})")
                    migrated_count += 1
                    
                except Exception as old_path_err:
                    # File might already be at new path or doesn't exist
                    try:
                        # Check if file exists at new path
                        client.storage.from_("admin-uploads").download(new_path)
                        print(f"   ⏭️  Skipped (already at new path): {file_name}")
                        skipped_count += 1
                    except Exception:
                        print(f"   ⚠️  File not found at either path: {file_name}")
                        error_count += 1
                        
            except Exception as e:
                print(f"   ❌ Error migrating {file_name}: {str(e)}")
                error_count += 1
        
        print(f"\n✅ Migration complete!")
        print(f"   - Migrated: {migrated_count}")
        print(f"   - Skipped: {skipped_count}")
        print(f"   - Errors: {error_count}")
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    migrate_course_files()

