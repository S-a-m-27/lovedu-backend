# Environment Variables Setup

## Required Environment Variables

Add the following to your `backend/.env` file:

```env
# Supabase Configuration
SUPABASE_URL=https://avyvigkmcdqawzaydoan.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Application Configuration
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000

# Agent Prompts (Context Engineering)
# These replace the previously hardcoded prompts in code.
# See: backend/ENV_PROMPTS.example
AGENT_PROMPT_BASE="IMPORTANT CONTEXT RESTRICTION:\n..."
AGENT_PROMPT_TYPEX="..."
AGENT_PROMPT_REFERENCES="..."
AGENT_PROMPT_ACADEMIC_REFERENCES="..."
AGENT_PROMPT_THERAPY_GPT="..."
AGENT_PROMPT_WHATS_TRENDY="..."
AGENT_PROMPT_COURSE="..."
```

## How to Get Each Key

### 1. Supabase Keys

1. Go to your Supabase Dashboard: https://app.supabase.com
2. Select your project
3. Go to **Settings** → **API**
4. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **anon public** key → `SUPABASE_ANON_KEY`
   - **service_role** key → `SUPABASE_SERVICE_ROLE_KEY` (⚠️ Keep this secret!)

### 2. OpenAI API Key

1. Go to OpenAI Platform: https://platform.openai.com
2. Sign in or create an account
3. Go to **API Keys** section
4. Click **Create new secret key**
5. Copy the key → `OPENAI_API_KEY`
6. ⚠️ Save it immediately - you won't be able to see it again!

### 3. Application Settings

- `ENVIRONMENT`: Set to `development` for local development, `production` for production
- `CORS_ORIGINS`: Comma-separated list of allowed origins (e.g., `http://localhost:3000,https://yourdomain.com`)

## Security Notes

- ⚠️ **Never commit** your `.env` file to version control
- ⚠️ **Never share** your API keys publicly
- ⚠️ The `SUPABASE_SERVICE_ROLE_KEY` has admin privileges - keep it secure
- ⚠️ The `OPENAI_API_KEY` can incur costs - monitor usage

## Verification

When you start the server, you should see logs like:

```
✅ SUPABASE_URL: https://... (loaded)
✅ SUPABASE_ANON_KEY: eyJhbGciO... (loaded)
✅ SUPABASE_SERVICE_ROLE_KEY: eyJhbGciO... (loaded)
✅ OPENAI_API_KEY: sk-... (loaded)
✅ CORS_ORIGINS: http://localhost:3000 (loaded)
```

If any show "NOT SET", check your `.env` file.

