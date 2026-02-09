"""
Script to set a user as admin in Supabase
Usage: python scripts/set_admin.py <user_email> [--role admin]
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def set_admin_user(email: str, is_admin: bool = True):
    """Set user as admin in Supabase"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_service_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env file")
        sys.exit(1)
    
    # Create Supabase client with service role key
    client = create_client(supabase_url, supabase_service_key)
    
    try:
        # Find user by email
        users = client.auth.admin.list_users()
        user = None
        
        for u in users.users:
            if u.email == email:
                user = u
                break
        
        if not user:
            print(f"❌ Error: User with email '{email}' not found")
            sys.exit(1)
        
        # Get current user metadata
        current_metadata = user.user_metadata or {}
        
        # Update metadata
        if is_admin:
            current_metadata["is_admin"] = True
            current_metadata["role"] = "admin"
        else:
            current_metadata.pop("is_admin", None)
            if current_metadata.get("role") == "admin":
                current_metadata.pop("role", None)
        
        # Update user
        client.auth.admin.update_user_by_id(
            user.id,
            {"user_metadata": current_metadata}
        )
        
        print(f"✅ Successfully set user '{email}' as {'admin' if is_admin else 'regular user'}")
        print(f"   User ID: {user.id}")
        print(f"   Metadata: {current_metadata}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/set_admin.py <user_email> [--remove]")
        sys.exit(1)
    
    email = sys.argv[1]
    is_admin = "--remove" not in sys.argv
    
    set_admin_user(email, is_admin)

