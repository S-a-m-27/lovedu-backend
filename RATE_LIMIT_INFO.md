# Email Rate Limit Error - Explanation & Solutions

## What is the Rate Limit Error?

The **"email rate limit exceeded"** error occurs when Supabase Auth detects too many signup attempts in a short period. This is a security feature to prevent abuse and spam.

## Why Does This Happen?

Supabase has built-in rate limits to protect against:
- **Spam signups** - Automated account creation
- **Brute force attacks** - Multiple failed attempts
- **Email abuse** - Sending too many verification emails

## Rate Limit Details

Supabase typically limits:
- **Per email address**: ~3-5 signup attempts per hour
- **Per IP address**: ~10-20 signup attempts per hour
- **Global**: Additional limits on total signups

## Solutions

### 1. Wait and Retry (Recommended)
- **Wait 5-10 minutes** before trying again
- The rate limit resets automatically after the time window expires
- This is the simplest solution

### 2. Use a Different Email
- If you need to test immediately, use a different email address
- Each email has its own rate limit counter

### 3. Check Supabase Dashboard
- Go to your Supabase Dashboard
- Check **Authentication → Users** to see if the account was actually created
- Sometimes the account is created but the response fails due to rate limiting

### 4. For Development/Testing
If you're doing heavy testing:

**Option A: Use Supabase Admin API**
- Use the service role key to create users directly
- Admin API has higher rate limits
- See `backend/create_admin_with_password.py` for example

**Option B: Increase Rate Limits (Paid Plans)**
- Supabase Pro and higher plans have higher rate limits
- Check your plan in Supabase Dashboard → Settings → Billing

**Option C: Disable Rate Limiting (Not Recommended)**
- Only for development/testing
- Go to Supabase Dashboard → Authentication → Settings
- Look for rate limiting options (may require custom configuration)

## Error Message Improvements

The error messages have been updated to be more user-friendly:

**Before:**
```
Signup failed: Sign up failed: email rate limit exceeded
```

**After:**
```
Too many signup attempts. Please wait 5-10 minutes before trying again.
```

## Prevention Tips

1. **Don't spam signups** - Wait between attempts
2. **Use different emails for testing** - Each email has separate limits
3. **Check if account exists** - Try logging in first before signing up
4. **Use admin scripts for bulk creation** - Use `create_admin_with_password.py` for admin accounts

## Checking Rate Limit Status

You can check if you're rate limited by:
1. Waiting 5-10 minutes
2. Trying signup again
3. If it still fails, wait longer (up to 1 hour)

## For Production

In production, you should:
- Implement proper error handling (already done ✅)
- Show user-friendly messages (already done ✅)
- Consider implementing a "cooldown" timer in the UI
- Monitor rate limit errors in your logs

## Related Files

- `backend/app/services/supabase_service.py` - Handles rate limit errors
- `backend/app/api/auth/routes.py` - Returns proper HTTP 429 status
- `frontend/lib/errorMessages.ts` - User-friendly error messages
