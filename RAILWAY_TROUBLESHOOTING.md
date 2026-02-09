# Railway Deployment Troubleshooting

## Healthcheck Failing: "Service Unavailable"

If you see this error:
```
Attempt #1 failed with service unavailable. Continuing to retry for 1m40s
```

### Common Causes & Solutions

#### 1. Missing Environment Variables

**Problem:** The app crashes during startup if required environment variables are missing.

**Solution:** Check Railway logs and verify ALL required variables are set:

**Required Variables:**
- ✅ `SUPABASE_URL`
- ✅ `SUPABASE_ANON_KEY`
- ✅ `SUPABASE_SERVICE_ROLE_KEY`
- ✅ `OPENAI_API_KEY`
- ✅ `ENVIRONMENT` (set to `production`)
- ✅ `CORS_ORIGINS` (your frontend URL)
- ✅ `AGENT_PROMPT_BASE`
- ✅ `AGENT_PROMPT_TYPEX`
- ✅ `AGENT_PROMPT_REFERENCES`
- ✅ `AGENT_PROMPT_ACADEMIC_REFERENCES`
- ✅ `AGENT_PROMPT_THERAPY_GPT`
- ✅ `AGENT_PROMPT_WHATS_TRENDY`
- ✅ `AGENT_PROMPT_COURSE`

**How to Check:**
1. Go to Railway Dashboard → Your Service → **Variables**
2. Verify all variables are present
3. Check Railway logs for errors like:
   - `❌ SUPABASE_URL: NOT SET`
   - `❌ OPENAI_API_KEY: NOT SET`
   - `ValueError: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set`

#### 2. App Crashing During Startup

**Problem:** The app imports services that require environment variables, causing crashes.

**How to Check:**
1. Go to Railway Dashboard → Your Service → **Deployments** → **View Logs**
2. Look for error messages like:
   - `ValueError: ... must be set`
   - `ImportError: ...`
   - `ModuleNotFoundError: ...`

**Solution:**
- Ensure all environment variables are set BEFORE deployment
- Check logs for specific missing variables
- Verify variable names are correct (case-sensitive)

#### 3. Port Binding Issues

**Problem:** App not binding to the correct port.

**Solution:** Verify your `Procfile` or `railway.json` uses `$PORT`:
```bash
# Procfile
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Railway automatically sets `$PORT`, so don't hardcode a port number.

#### 4. Python Version Mismatch

**Problem:** Wrong Python version causing import errors.

**Solution:** 
- Check `runtime.txt` specifies correct version: `python-3.11`
- Railway auto-detects, but explicit is better

#### 5. Missing Dependencies

**Problem:** `requirements.txt` missing packages.

**Solution:**
- Verify `requirements.txt` includes all dependencies
- Check logs for `ModuleNotFoundError`
- Add missing packages to `requirements.txt`

## How to Debug

### Step 1: Check Railway Logs

1. Go to Railway Dashboard
2. Click on your service
3. Go to **Deployments** tab
4. Click on the latest deployment
5. View **Build Logs** and **Deploy Logs**

Look for:
- ❌ Error messages
- ⚠️ Warning messages
- Environment variable status logs

### Step 2: Check Environment Variables

1. Railway Dashboard → Your Service → **Variables**
2. Verify all required variables are present
3. Check for typos in variable names
4. Verify values are correct (no extra spaces)

### Step 3: Test Locally with Same Environment

```bash
# Set all environment variables
export SUPABASE_URL="..."
export SUPABASE_ANON_KEY="..."
# ... etc

# Run the app
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Test health endpoint
curl http://localhost:8000/health
```

If it works locally but not on Railway, check:
- Environment variable differences
- Port configuration
- Network/firewall issues

### Step 4: Check Service Initialization

The app logs show service initialization:
```
🔧 Initializing SupabaseService...
📋 SUPABASE_URL: ...
✅ Supabase client created...
```

If you see errors here, that's the problem.

## Quick Fixes

### Fix 1: Add Missing Environment Variables

1. Railway Dashboard → Variables
2. Add missing variables
3. Redeploy (Railway auto-redeploys on variable changes)

### Fix 2: Verify Variable Format

For multi-line prompts, use `\n` for newlines:
```
AGENT_PROMPT_TYPEX="Line 1\nLine 2\nLine 3"
```

### Fix 3: Check CORS_ORIGINS Format

Should be comma-separated:
```
CORS_ORIGINS=https://app.vercel.app,https://yourdomain.com
```

Or with spaces (depending on your code):
```
CORS_ORIGINS=https://app.vercel.app, https://yourdomain.com
```

### Fix 4: Restart Service

1. Railway Dashboard → Your Service
2. Click **Settings**
3. Click **Restart**

## Expected Logs (Success)

When the app starts successfully, you should see:

```
🔄 Loading environment variables...
✅ Environment variables loaded
📋 Environment Variables Status:
  ✅ SUPABASE_URL: https://xxx.supabase.co (loaded)
  ✅ SUPABASE_ANON_KEY: eyJhbGc... (loaded)
  ✅ SUPABASE_SERVICE_ROLE_KEY: eyJhbGc... (loaded)
  ✅ OPENAI_API_KEY: sk-... (loaded)
  ✅ CORS_ORIGINS: https://app.vercel.app (loaded)
  ✅ ENVIRONMENT: production (loaded)
✅ Logging middleware added
🌐 CORS Origins configured: ['https://app.vercel.app']
✅ Auth router included
✅ Chat router included
✅ Subscription router included
✅ Admin router included
✅ Course router included
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:PORT (Press CTRL+C to quit)
```

## Still Not Working?

1. **Check Railway Status:** https://status.railway.app
2. **Review Full Logs:** Look for the FIRST error message
3. **Test Health Endpoint Manually:**
   ```bash
   curl https://your-app.up.railway.app/health
   ```
4. **Contact Support:** Railway Discord or support

## Prevention

Before deploying:
- ✅ Test locally with all environment variables
- ✅ Verify `requirements.txt` is complete
- ✅ Check all environment variables are set
- ✅ Test health endpoint locally
- ✅ Review logs before pushing
