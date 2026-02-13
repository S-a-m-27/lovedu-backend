#!/usr/bin/env python3
"""
Script to create an admin user in Supabase with custom email and password
Usage: python create_admin_with_password.py <email> <password>
Example: python create_admin_with_password.py admin@grad.ku.edu.kw MySecurePassword123!
"""

import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_admin_user(email: str, password: str, full_name: str = "System Administrator"):
    """Create an admin user in Supabase with custom credentials"""
    
    # Get Supabase credentials from environment
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_service_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env file")
        print("\nPlease add these to your backend/.env file:")
        print("SUPABASE_URL=https://your-project.supabase.co")
        print("SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here")
        sys.exit(1)
    
    # Validate email format
    if not email or "@" not in email:
        print("❌ Error: Invalid email address")
        sys.exit(1)
    
    # Validate password length
    if not password or len(password) < 6:
        print("❌ Error: Password must be at least 6 characters long")
        sys.exit(1)
    
    print("🔐 Creating Admin User...")
    print(f"📧 Email: {email}")
    print(f"👤 Name: {full_name}\n")
    
    try:
        # Initialize Supabase client with service role key (has admin privileges)
        supabase: Client = create_client(supabase_url, supabase_service_key)
        
        # Create admin user
        print("📤 Sending request to Supabase...")
        response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,  # Auto-confirm email (no email verification needed)
            "user_metadata": {
                "is_admin": True,
                "role": "admin",
                "plan": "free",
                "full_name": full_name,
                "is_ku_member": True,
                "email_verified": True
            }
        })
        
        # Ensure email is confirmed by updating the user if needed
        if response.user:
            try:
                # Update user to ensure email_confirmed_at is set
                update_response = supabase.auth.admin.update_user_by_id(
                    response.user.id,
                    {
                        "email_confirm": True,
                        "user_metadata": {
                            "is_admin": True,
                            "role": "admin",
                            "plan": "free",
                            "full_name": full_name,
                            "is_ku_member": True,
                            "email_verified": True
                        }
                    }
                )
                print("✅ Email confirmation verified")
            except Exception as update_err:
                print(f"⚠️  Warning: Could not update email confirmation: {update_err}")
                print("   User was created but email confirmation may need manual verification in Supabase Dashboard")
        
        if response.user:
            print("\n✅ Admin user created successfully!")
            print("\n" + "="*60)
            print("📋 ADMIN CREDENTIALS (SAVE THESE SECURELY!)")
            print("="*60)
            print(f"📧 Email:    {email}")
            print(f"🔑 Password: {password}")
            print(f"👤 User ID:  {response.user.id}")
            print(f"✅ Metadata: {response.user.user_metadata}")
            print("="*60)
            print("\n💡 You can now login with these credentials on the login page.")
            print("   Admin users will be automatically redirected to /admin\n")
            
        else:
            print("❌ Failed to create user - no user object returned")
            print(f"Response: {response}")
            sys.exit(1)
            
    except Exception as e:
        error_msg = str(e).lower()
        
        # Handle user already exists error
        if "already registered" in error_msg or "already exists" in error_msg or "user already" in error_msg:
            print(f"\n⚠️  User already exists: {email}")
            print("Attempting to update existing user to admin...\n")
            
            try:
                # Get all users and find the one with this email
                users_response = supabase.auth.admin.list_users()
                user = next((u for u in users_response.users if u.email == email), None)
                
                if user:
                    # Update user metadata to admin and ensure email is confirmed
                    update_response = supabase.auth.admin.update_user_by_id(
                        user.id,
                        {
                            "email_confirm": True,  # Ensure email is confirmed
                            "user_metadata": {
                                **(user.user_metadata or {}),
                                "is_admin": True,
                                "role": "admin",
                                "plan": "free",
                                "full_name": full_name,
                                "is_ku_member": True,
                                "email_verified": True
                            }
                        }
                    )
                    
                    # Update password if user exists
                    try:
                        supabase.auth.admin.update_user_by_id(
                            user.id,
                            {"password": password}
                        )
                        print("✅ Password updated")
                    except Exception as pwd_err:
                        print(f"⚠️  Warning: Could not update password: {pwd_err}")
                    
                    if update_response.user:
                        print("✅ User updated to admin successfully!")
                        print("\n" + "="*60)
                        print("📋 ADMIN USER INFO")
                        print("="*60)
                        print(f"📧 Email:    {email}")
                        print(f"🔑 Password: {password}")
                        print(f"👤 User ID:  {user.id}")
                        print(f"✅ Metadata: {update_response.user.user_metadata}")
                        print("="*60)
                        print("\n💡 You can now login with these credentials.\n")
                    else:
                        print("❌ Failed to update user")
                else:
                    print(f"❌ User with email {email} not found")
                    print("   Please create the user manually or use a different email.\n")
                    sys.exit(1)
                    
            except Exception as update_error:
                print(f"❌ Error updating user: {str(update_error)}")
                sys.exit(1)
        else:
            print(f"❌ Error creating admin user: {str(e)}")
            print("\nTroubleshooting tips:")
            print("1. Check that SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are correct")
            print("2. Verify the service role key has admin privileges")
            print("3. Check Supabase dashboard for any error messages")
            sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_admin_with_password.py <email> <password> [full_name]")
        print("\nExample:")
        print("  python create_admin_with_password.py admin@grad.ku.edu.kw MyPassword123!")
        print("  python create_admin_with_password.py admin@grad.ku.edu.kw MyPassword123! 'John Doe'")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    full_name = sys.argv[3] if len(sys.argv) > 3 else "System Administrator"
    
    create_admin_user(email, password, full_name)
