from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.subscription import router as subscription_router
from app.api.admin import router as admin_router
from app.api.course import router as course_router
from app.middleware.logging_middleware import LoggingMiddleware
import os
import logging
from dotenv import load_dotenv
import sys

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Set specific loggers to DEBUG for more detail
logging.getLogger("app").setLevel(logging.DEBUG)
logging.getLogger("app.api").setLevel(logging.DEBUG)
logging.getLogger("app.services").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

# Load environment variables
logger.info("🔄 Loading environment variables...")
load_dotenv()
logger.info("✅ Environment variables loaded")

# Log all environment variables (masking sensitive ones)
env_vars = {
    "SUPABASE_URL": os.getenv("SUPABASE_URL"),
    "SUPABASE_ANON_KEY": os.getenv("SUPABASE_ANON_KEY"),
    "SUPABASE_SERVICE_ROLE_KEY": os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "CORS_ORIGINS": os.getenv("CORS_ORIGINS"),
    "ENVIRONMENT": os.getenv("ENVIRONMENT", "development"),
}

logger.info("📋 Environment Variables Status:")
for key, value in env_vars.items():
    if value:
        if "KEY" in key or "SECRET" in key or "TOKEN" in key:
            masked_value = value[:10] + "..." + value[-4:] if len(value) > 14 else "***"
            logger.info(f"  ✅ {key}: {masked_value} (loaded)")
        else:
            logger.info(f"  ✅ {key}: {value} (loaded)")
    else:
        logger.warning(f"  ⚠️  {key}: NOT SET")

app = FastAPI(
    title="Multi-Agent Backend API",
    description="Backend API for Multi-Agent Project",
    version="1.0.0"
)

# Add logging middleware first (before CORS)
app.add_middleware(LoggingMiddleware)
logger.info("✅ Logging middleware added")

# CORS Configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
logger.info(f"🌐 CORS Origins configured: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
logger.info("✅ Auth router included")
app.include_router(chat_router)
logger.info("✅ Chat router included")
app.include_router(subscription_router)
logger.info("✅ Subscription router included")
app.include_router(admin_router)
logger.info("✅ Admin router included")
app.include_router(course_router)
logger.info("✅ Course router included")

@app.get("/")
async def root():
    logger.info("📡 Root endpoint accessed")
    return {"message": "Multi-Agent Backend API", "status": "running"}

@app.get("/health")
async def health_check():
    logger.info("🏥 Health check endpoint accessed")
    return {"status": "healthy"}

