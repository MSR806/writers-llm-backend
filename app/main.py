from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from app.routes import router
from app.database import engine, Base, SessionLocal
from app.auth import get_current_user
from app.repository.base_repository import BaseRepository

# Create database tables
Base.metadata.create_all(bind=engine)

# Security scheme for Swagger UI
security = HTTPBearer()

app = FastAPI(
    title="Writers LLM API",
    description="An API for managing books, chapters, scenes, and characters with AI assistance",
    version="1.0.0",
    # Configure OpenAPI to include authorization
    openapi_tags=[
        {
            "name": "auth",
            "description": "Authentication endpoints",
        },
    ],
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set global session for repositories at startup
@app.on_event("startup")
async def set_global_db_session():
    db = SessionLocal()
    BaseRepository.set_session(db)

# Include routers
app.include_router(router, prefix="/vaani/api/v1", dependencies=[Depends(get_current_user)])

@app.get("/", tags=["public"])
async def root():
    return {
        "message": "Welcome to Writers LLM API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }

@app.get("/vaani/health", tags=["public"])
async def health_check():
    return {
        "status": "healthy",
        "api": "Writers LLM API",
        "version": "1.0.0"
    }