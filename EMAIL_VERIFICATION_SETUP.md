# Email Verification Setup Guide

## Issue
After setting up custom SMTP, verification emails are not being sent to users during signup.

## Solution

The code has been updated to send verification emails by setting `email_confirm: False` when creating users. However, you need to ensure your Supabase project is configured correctly.

## Steps to Fix

### 1. Verify Custom SMTP is Enabled
1. Go to your Supabase Dashboard
2. Navigate to **Settings** > **Auth** > **SMTP Settings**
3. Ensure **"Enable custom SMTP"** toggle is **ON** (green)
4. Verify all SMTP settings are correct:
   - Host
   - Port
   - Username
   - Password
   - Sender email: `noreply@lovedu.ai`
   - Sender name: `LovEdu Team`

### 2. Check Email Templates
1. Go to **Authentication** > **Email Templates**
2. Ensure the **"Confirm signup"** template is enabled
3. The template should use your custom SMTP settings
4. Verify the template includes:
   - Confirmation link: `{{ .ConfirmationURL }}`
   - Proper formatting and branding

### 3. Verify Email Rate Limits
1. Go to **Settings** > **Auth** > **Rate Limits**
2. Check that email sending limits are not too restrictive
3. Adjust if necessary (though using Service Role Key should bypass most limits)

### 4. Test Email Sending
1. Try signing up a new user
2. Check the user's email inbox (including spam folder)
3. Check Supabase logs: **Logs** > **Auth Logs** for any email sending errors

### 5. Check Supabase Logs
1. Go to **Logs** > **Auth Logs**
2. Look for any errors related to email sending
3. Common issues:
   - SMTP connection errors
   - Authentication failures
   - Invalid sender email

## How It Works Now

When a user signs up:
1. User is created with `email_confirm: False`
2. Supabase automatically sends a verification email via your custom SMTP
3. User receives email with verification link
4. User clicks link to verify email
5. User can then log in

## Troubleshooting

### Emails Still Not Sending?

1. **Check SMTP Credentials**: Verify your SMTP provider credentials are correct
2. **Check Sender Email**: Ensure `noreply@lovedu.ai` is a valid email address in your SMTP provider
3. **Check SMTP Provider Logs**: Check your email service provider (e.g., SendGrid, Mailgun) for delivery issues
4. **Test SMTP Connection**: Use Supabase's "Test Email" feature in SMTP Settings
5. **Check Spam Folder**: Verification emails might be going to spam
6. **Verify Domain**: Ensure your domain (`lovedu.ai`) is properly configured with your SMTP provider

### Still Having Issues?

If emails are still not being sent:
1. Check Supabase Dashboard > Logs > Auth Logs for specific error messages
2. Verify your SMTP provider allows sending from `noreply@lovedu.ai`
3. Ensure your SMTP provider doesn't have rate limits that are too restrictive
4. Consider testing with a different email address to rule out recipient-side issues

## Code Changes

The signup code now uses:
```python
"email_confirm": False  # Send verification email (uses custom SMTP)
```

This ensures verification emails are sent via your custom SMTP configuration instead of auto-confirming users.
