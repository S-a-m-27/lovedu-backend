# How to Add an Admin User to the Platform

There are two ways to add an admin user: using a Python script (recommended) or using SQL queries.

## Method 1: Using Python Script (Recommended) ✅

### Option A: Create Admin with Custom Email and Password

```bash
cd backend
python create_admin_with_password.py <email> <password> [full_name]
```

**Example:**
```bash
python create_admin_with_password.py admin@grad.ku.edu.kw MySecurePassword123!
python create_admin_with_password.py admin@grad.ku.edu.kw MyPassword123! "John Doe"
```

### Option B: Create Admin with Random Credentials

```bash
cd backend
python create_admin_user.py
```

This will generate random email and password and display them.

**Requirements:**
- Make sure your `backend/.env` file has:
  ```
  SUPABASE_URL=https://your-project.supabase.co
  SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
  ```

## Method 2: Using SQL Queries (Advanced) ⚠️

**Note:** You **cannot** set passwords directly via SQL in Supabase Auth. Passwords are hashed and managed by Supabase's authentication system. However, you can:

1. **Create the user via Supabase Dashboard or API first** (to set password)
2. **Then update metadata via SQL** to make them admin

### Step 1: Create User (Use Supabase Dashboard or API)

Go to Supabase Dashboard → Authentication → Users → Add User
- Enter email and password
- Mark email as confirmed

### Step 2: Update User Metadata to Admin (SQL)

After creating the user, run this SQL in Supabase SQL Editor:

```sql
-- Update user metadata to make them admin
-- Replace 'user@grad.ku.edu.kw' with the actual email

UPDATE auth.users
SET 
  raw_user_meta_data = jsonb_build_object(
    'is_admin', true,
    'role', 'admin',
    'plan', 'free',
    'is_ku_member', true,
    'email_verified', true,
    'full_name', 'System Administrator'
  ) || COALESCE(raw_user_meta_data, '{}'::jsonb),
  email_confirmed_at = COALESCE(email_confirmed_at, NOW())
WHERE email = 'user@grad.ku.edu.kw';
```

### Step 3: Verify Admin Status

```sql
-- Check if user is admin
SELECT 
  id,
  email,
  raw_user_meta_data->>'is_admin' as is_admin,
  raw_user_meta_data->>'role' as role,
  email_confirmed_at
FROM auth.users
WHERE email = 'user@grad.ku.edu.kw';
```

## Method 3: Using Supabase Admin API (Alternative)

If you prefer to use the API directly, you can use curl:

```bash
curl -X POST 'https://your-project.supabase.co/auth/v1/admin/users' \
  -H "apikey: YOUR_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@grad.ku.edu.kw",
    "password": "YourPassword123!",
    "email_confirm": true,
    "user_metadata": {
      "is_admin": true,
      "role": "admin",
      "plan": "free",
      "is_ku_member": true,
      "email_verified": true,
      "full_name": "System Administrator"
    }
  }'
```

## Important Notes

1. **Password Requirements:**
   - Minimum 6 characters (enforced by Supabase)
   - Recommended: Use strong passwords with letters, numbers, and special characters

2. **Email Format:**
   - Must be in format: `@grad.ku.edu.kw` (as per your platform restrictions)

3. **Admin Metadata:**
   - `is_admin: true` - Required for admin access
   - `role: "admin"` - Alternative check for admin role
   - `is_ku_member: true` - Required for platform access

4. **Email Confirmation:**
   - Always set `email_confirm: true` or `email_confirmed_at` to allow immediate login

5. **Security:**
   - Never commit credentials to version control
   - Store service role key securely
   - Delete credential files after use

## Troubleshooting

- **"User already exists"**: The script will attempt to update the existing user to admin
- **"Invalid credentials"**: Check your SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
- **"Permission denied"**: Ensure you're using the SERVICE_ROLE_KEY, not the anon key
