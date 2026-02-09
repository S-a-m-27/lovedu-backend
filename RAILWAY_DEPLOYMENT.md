# Railway Deployment Guide

Step-by-step instructions to deploy the FastAPI backend on Railway.

## Prerequisites

- GitHub account (or GitLab/Bitbucket)
- Railway account (free tier available at [railway.app](https://railway.app))
- Your project pushed to a Git repository
- All environment variables ready (see below)

## Step 1: Prepare Your Repository

1. **Push your code to GitHub:**
   ```bash
   cd backend
   git add .
   git commit -m "Prepare for Railway deployment"
   git push origin main
   ```

2. **Verify your files are present:**
   - ✅ `requirements.txt` (already present)
   - ✅ `Procfile` or `railway.json` (created)
   - ✅ `app/main.py` (your FastAPI app)

## Step 2: Deploy to Railway

### Option A: Deploy via Railway Dashboard (Recommended)

1. **Go to Railway:**
   - Visit [https://railway.app](https://railway.app)
   - Sign up/Login with GitHub

2. **Create New Project:**
   - Click **"New Project"**
   - Select **"Deploy from GitHub repo"**
   - Select your repository
   - Railway will auto-detect it's a Python project

3. **Configure Service:**
   - Railway will automatically:
     - Detect Python
     - Install dependencies from `requirements.txt`
     - Use the `Procfile` or `railway.json` for start command
   - If auto-detection fails, manually set:
     - **Build Command:** (leave empty, Railway handles it)
     - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

4. **Set Environment Variables:**
   Click **"Variables"** tab and add all required variables:

   **Supabase Configuration:**
   ```
   SUPABASE_URL=your_supabase_url_here
   SUPABASE_ANON_KEY=your_supabase_anon_key_here
   SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here
   ```

   **OpenAI Configuration:**
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

   **Application Configuration:**
   ```
   ENVIRONMENT=production
   CORS_ORIGINS=https://your-frontend.vercel.app,https://yourdomain.com
   ```

   **Agent Prompts (Required):**
   ```
   AGENT_PROMPT_BASE="IMPORTANT CONTEXT RESTRICTION:\n..."
   AGENT_PROMPT_TYPEX="KU Advisor – All Majors (Bilingual System Instruction | FINAL)\n\n..."
   AGENT_PROMPT_REFERENCES="..."
   AGENT_PROMPT_ACADEMIC_REFERENCES="References Advisor – APA (Kuwait University)\n..."
   AGENT_PROMPT_THERAPY_GPT="Success Stories – Bilingual System Instruction | FINAL\n..."
   AGENT_PROMPT_WHATS_TRENDY="What's Trendy – Bilingual System Instruction | FINAL (Revised)\n..."
   AGENT_PROMPT_COURSE="..."
   ```

   **Important Notes:**
   - Replace all placeholder values with your actual credentials
   - For multi-line prompts, use `\n` for newlines
   - Railway supports multi-line environment variables
   - Update `CORS_ORIGINS` with your Vercel frontend URL after frontend is deployed

5. **Deploy:**
   - Railway will automatically start building and deploying
   - Watch the build logs in the Railway dashboard
   - Wait for deployment to complete (2-5 minutes)

6. **Get Your Backend URL:**
   - Once deployed, Railway will provide a URL like: `https://your-project.up.railway.app`
   - Click **"Settings"** → **"Generate Domain"** to get a permanent URL
   - Copy this URL - you'll need it for frontend configuration

### Option B: Deploy via Railway CLI

1. **Install Railway CLI:**
   ```bash
   npm i -g @railway/cli
   ```

2. **Login:**
   ```bash
   railway login
   ```

3. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

4. **Initialize Railway:**
   ```bash
   railway init
   ```
   - Follow prompts to create/link project

5. **Set Environment Variables:**
   ```bash
   railway variables set SUPABASE_URL=your_supabase_url_here
   railway variables set SUPABASE_ANON_KEY=your_supabase_anon_key_here
   railway variables set SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here
   railway variables set OPENAI_API_KEY=your_openai_api_key_here
   railway variables set ENVIRONMENT=production
   railway variables set CORS_ORIGINS=https://your-frontend.vercel.app
   # Add all agent prompts...
   ```

6. **Deploy:**
   ```bash
   railway up
   ```

## Step 3: Configure Custom Domain (Optional)

If you want to use a custom domain:

1. **In Railway Dashboard:**
   - Go to your service → **Settings** → **Networking**
   - Click **"Custom Domain"**
   - Enter your domain (e.g., `api.yourdomain.com`)

2. **Configure DNS in GoDaddy:**
   - Add a **CNAME** record:
     - **Type:** CNAME
     - **Name:** `api` (or `backend`)
     - **Value:** Railway will provide the CNAME target (e.g., `your-project.up.railway.app`)

3. **Wait for SSL:**
   - Railway automatically provisions SSL certificates
   - Can take a few minutes

## Step 4: Update Frontend Configuration

After backend is deployed:

1. **Update Vercel Environment Variables:**
   - Go to Vercel Dashboard → Your Project → Settings → Environment Variables
   - Update `NEXT_PUBLIC_API_URL` to your Railway URL:
     ```
     NEXT_PUBLIC_API_URL=https://your-project.up.railway.app
     ```
   - Redeploy frontend

2. **Verify Backend CORS:**
   - Make sure `CORS_ORIGINS` in Railway includes your Vercel domain
   - Format: `https://your-frontend.vercel.app,https://yourdomain.com`

## Step 5: Test Your Deployment

1. **Health Check:**
   ```bash
   curl https://your-project.up.railway.app/health
   ```
   Should return: `{"status": "healthy"}`

2. **API Docs:**
   - Visit: `https://your-project.up.railway.app/docs`
   - Should show Swagger UI

3. **Test from Frontend:**
   - Try logging in from your Vercel-deployed frontend
   - Check browser console for API calls
   - Verify authentication works

## Troubleshooting

### Build Fails

1. **Check build logs in Railway dashboard**
2. **Common issues:**
   - Missing `requirements.txt` → Ensure it exists
   - Python version mismatch → Railway auto-detects, but you can specify in `runtime.txt`
   - Missing dependencies → Check `requirements.txt` is complete

### Application Crashes

1. **Check logs in Railway dashboard**
2. **Common issues:**
   - Missing environment variables → Add all required vars
   - Port binding error → Ensure using `$PORT` variable
   - Database connection issues → Verify Supabase credentials

### Environment Variables Not Working

- **Restart service** after adding env vars
- **Check variable names** (case-sensitive)
- **Verify no typos** in variable values
- **Check for hidden characters** in multi-line prompts

### CORS Errors

- **Verify `CORS_ORIGINS`** includes your frontend URL
- **Check format:** Comma-separated, no spaces (or with spaces, depending on your code)
- **Include both** Vercel URL and custom domain if applicable

### API Not Responding

- **Check service is running** in Railway dashboard
- **Verify health endpoint:** `/health`
- **Check logs** for errors
- **Test locally** with same environment variables

## Post-Deployment Checklist

- [ ] Backend deployed successfully
- [ ] All environment variables set correctly
- [ ] Health endpoint responding (`/health`)
- [ ] API docs accessible (`/docs`)
- [ ] Frontend `NEXT_PUBLIC_API_URL` updated
- [ ] CORS configured correctly
- [ ] Custom domain configured (if applicable)
- [ ] SSL certificate active (automatic with Railway)
- [ ] Test authentication flow
- [ ] Test chat functionality
- [ ] Test all major API endpoints

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SUPABASE_URL` | Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase anon key | `eyJhbGc...` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | `eyJhbGc...` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `ENVIRONMENT` | Environment name | `production` |
| `CORS_ORIGINS` | Allowed CORS origins | `https://app.vercel.app,https://domain.com` |
| `AGENT_PROMPT_BASE` | Base prompt for all agents | `"..."` |
| `AGENT_PROMPT_TYPEX` | TypeX agent prompt | `"..."` |
| `AGENT_PROMPT_REFERENCES` | References agent prompt | `"..."` |
| `AGENT_PROMPT_ACADEMIC_REFERENCES` | Academic References prompt | `"..."` |
| `AGENT_PROMPT_THERAPY_GPT` | Therapy GPT prompt | `"..."` |
| `AGENT_PROMPT_WHATS_TRENDY` | What's Trendy prompt | `"..."` |
| `AGENT_PROMPT_COURSE` | Course agent prompt | `"..."` |

### Optional Variables

- `PORT` - Automatically set by Railway (don't override)
- `PYTHON_VERSION` - Python version (auto-detected, but can specify)

## Next Steps

After backend is deployed:
1. Update frontend `NEXT_PUBLIC_API_URL` in Vercel
2. Update backend `CORS_ORIGINS` with frontend URL
3. Test full integration
4. Configure custom domains if needed
5. Set up monitoring and alerts

## Support

- Railway Docs: https://docs.railway.app
- Railway Status: https://status.railway.app
- FastAPI Deployment: https://fastapi.tiangolo.com/deployment/

## Notes

- Railway automatically handles:
  - Python version detection
  - Dependency installation
  - Port binding
  - SSL certificates
  - Health checks
  - Auto-restart on failure

- Railway free tier includes:
  - $5 credit per month
  - 500 hours of usage
  - Unlimited deployments
  - Custom domains
