from fastapi import FastAPI
from app.core.config import settings
from app.api import webhook

from contextlib import asynccontextmanager
from sqlmodel import SQLModel
from app.core.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    SQLModel.metadata.create_all(engine)
    yield
    # Shutdown

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan
)

# Include routers
app.include_router(webhook.router, prefix="/api", tags=["Webhook"])

@app.get("/")
async def root():
    return {"message": "Hello World! AI Receptionist is running.", "docs_url": "/docs"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
