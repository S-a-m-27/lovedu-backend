#!/usr/bin/env python3
"""
Script to create an admin user in Supabase
Run this script once to create the admin user with random credentials
"""

import os
import sys
import random
import string
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def generate_random_email():
    """Generate a random admin email"""
    random_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"admin_{random_id}@grad.ku.edu.kw"

def generate_random_password():
    """Generate a secure random password"""
    # At least 12 characters with letters, digits, and special chars
    letters = string.ascii_letters
    digits = string.digits
    special = "!@#$%&*"
    password = (
        ''.join(random.choices(letters, k=6)) +
        ''.join(random.choices(digits, k=3)) +
        ''.join(random.choices(special, k=2))
    )
    # Shuffle the password
    password_list = list(password)
    random.shuffle(password_list)
    return ''.join(password_list)

def create_admin_user():
    """Create an admin user in Supabase"""
    
    # Get Supabase credentials from environment
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_service_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env file")
        print("\nPlease add these to your backend/.env file:")
        print("SUPABASE_URL=https://your-project.supabase.co")
        print("SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here")
        sys.exit(1)
    
    # Generate admin credentials
    admin_email = generate_random_email()
    admin_password = generate_random_password()
    admin_name = "System Administrator"
    
    print("🔐 Creating Admin User...")
    print(f"📧 Generated Email: {admin_email}")
    print(f"🔑 Generated Password: {admin_password}")
    print(f"👤 Name: {admin_name}\n")
    
    try:
        # Initialize Supabase client with service role key (has admin privileges)
        supabase: Client = create_client(supabase_url, supabase_service_key)
        
        # Create admin user
        print("📤 Sending request to Supabase...")
        response = supabase.auth.admin.create_user({
            "email": admin_email,
            "password": admin_password,
            "email_confirm": True,  # Auto-confirm email (no email verification needed)
            "user_metadata": {
                "is_admin": True,
                "role": "admin",
                "plan": "free",
                "full_name": admin_name,
                "is_ku_member": True,
                "email_verified": True
            }
        })
        
        # Ensure email is confirmed by updating the user if needed
        if response.user:
            try:
                # Update user to ensure email_confirmed_at is set
                from datetime import datetime
                update_response = supabase.auth.admin.update_user_by_id(
                    response.user.id,
                    {
                        "email_confirm": True,
                        "user_metadata": {
                            "is_admin": True,
                            "role": "admin",
                            "plan": "free",
                            "full_name": admin_name,
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
            print(f"📧 Email:    {admin_email}")
            print(f"🔑 Password: {admin_password}")
            print(f"👤 User ID:  {response.user.id}")
            print(f"✅ Metadata: {response.user.user_metadata}")
            print("="*60)
            print("\n💡 You can now login with these credentials on the login page.")
            print("   Admin users will be automatically redirected to /admin\n")
            
            # Also save to a file for reference (optional)
            try:
                with open("admin_credentials.txt", "w", encoding="utf-8") as f:
                    f.write("ADMIN USER CREDENTIALS\n")
                    f.write("="*60 + "\n")
                    f.write(f"Email: {admin_email}\n")
                    f.write(f"Password: {admin_password}\n")
                    f.write(f"User ID: {response.user.id}\n")
                    f.write("="*60 + "\n")
                    f.write("\n⚠️  Keep this file secure and delete it after saving the credentials!\n")
                print("📄 Credentials also saved to admin_credentials.txt")
                print("   ⚠️  Please delete this file after saving the credentials!\n")
            except Exception as file_error:
                print(f"⚠️  Could not save credentials to file: {file_error}\n")
                
        else:
            print("❌ Failed to create user - no user object returned")
            print(f"Response: {response}")
            sys.exit(1)
            
    except Exception as e:
        error_msg = str(e).lower()
        
        # Handle user already exists error
        if "already registered" in error_msg or "already exists" in error_msg or "user already" in error_msg:
            print(f"\n⚠️  User already exists: {admin_email}")
            print("Attempting to update existing user to admin...\n")
            
            try:
                # Get all users and find the one with this email
                users_response = supabase.auth.admin.list_users()
                user = next((u for u in users_response.users if u.email == admin_email), None)
                
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
                                "full_name": admin_name,
                                "is_ku_member": True,
                                "email_verified": True
                            }
                        }
                    )
                    
                    if update_response.user:
                        print("✅ User updated to admin successfully!")
                        print("\n" + "="*60)
                        print("📋 ADMIN USER INFO")
                        print("="*60)
                        print(f"📧 Email:    {admin_email}")
                        print(f"👤 User ID:  {user.id}")
                        print(f"✅ Metadata: {update_response.user.user_metadata}")
                        print("="*60)
                        print("\n⚠️  Note: You'll need to use the original password for this account.")
                        print("   If you don't remember it, reset the password in Supabase Dashboard.\n")
                    else:
                        print("❌ Failed to update user")
                else:
                    print(f"❌ User with email {admin_email} not found")
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
    create_admin_user()

