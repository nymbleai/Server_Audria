from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from dotenv import load_dotenv

from app.routers import auth
from app.core.config import settings

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

app = FastAPI(
    title="Audria API",
    description="FastAPI backend for Audria with Supabase authentication",
    version="1.0.0",
    redirect_slashes=False
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [settings.frontend_url],
    allow_credentials=False if settings.environment == "development" else True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return JSONResponse(content={
        "status": "healthy",
        "service": "Audria API",
        "version": "1.0.0"
    })

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])

# Include persons router
from app.routers import persons
app.include_router(persons.router, prefix="/api/persons", tags=["Persons"])

# Include voices router
from app.routers import voices
app.include_router(voices.router, prefix="/api/voices", tags=["Voices"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
