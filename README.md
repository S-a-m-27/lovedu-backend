# Backend API - Multi-Agent Project

FastAPI backend for the Multi-Agent project with Supabase authentication.

## Setup Instructions

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the `backend` folder with the following variables:

```env
# Supabase Configuration
SUPABASE_URL=https://avyvigkmcdqawzaydoan.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Application
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

**Important:** 
- Get `SUPABASE_SERVICE_ROLE_KEY` from your Supabase dashboard (Settings → API → service_role key)
- Get `OPENAI_API_KEY` from OpenAI platform (https://platform.openai.com/api-keys)
- These keys have admin/API privileges, keep them secure and never commit to version control
- Run the database schema SQL in Supabase SQL Editor (see `DATABASE_SETUP.md`)

### 3. Run the Server

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

## Deployment

### Railway Deployment

For production deployment on Railway, see the comprehensive guide:
- **[RAILWAY_DEPLOYMENT.md](./RAILWAY_DEPLOYMENT.md)** - Complete step-by-step Railway deployment instructions

**Quick Start:**
1. Push your code to GitHub
2. Connect your repository to Railway
3. Set all environment variables in Railway dashboard
4. Deploy!

**Required Files (already created):**
- ✅ `Procfile` - Start command for Railway
- ✅ `railway.json` - Railway configuration
- ✅ `requirements.txt` - Python dependencies
- ✅ `runtime.txt` - Python version specification

## API Endpoints

### Authentication Endpoints

- `POST /auth/login` - Login user with email and password
- `POST /auth/signup` - Sign up new user
- `POST /auth/verify-token` - Verify JWT token and return user information
- `GET /auth/me` - Get current authenticated user (requires Bearer token)
- `GET /auth/user/{user_id}` - Get user by ID (requires Bearer token)
- `POST /auth/refresh` - Refresh access token using refresh token

### Chat Endpoints

- `POST /chat/message` - Send a message and get AI response (requires Bearer token)
- `GET /chat/sessions` - Get all chat sessions for current user (requires Bearer token)
- `GET /chat/sessions/{session_id}` - Get specific chat session with messages (requires Bearer token)
- `POST /chat/sessions` - Create a new chat session (requires Bearer token)
- `DELETE /chat/sessions/{session_id}` - Delete a chat session (requires Bearer token)

### General Endpoints

- `GET /` - API status
- `GET /health` - Health check

## API Documentation

Once the server is running, you can access:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Authentication

All protected endpoints require a Bearer token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

The JWT token is obtained from Supabase Auth when users log in through the frontend.

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── auth/
│   │       ├── __init__.py
│   │       ├── routes.py          # Auth endpoints
│   │       └── dependencies.py    # Auth dependencies
│   ├── models/
│   │   └── auth.py                 # Pydantic models
│   ├── services/
│   │   └── supabase_service.py    # Supabase client
│   └── main.py                     # FastAPI app
├── requirements.txt
└── README.md
```

