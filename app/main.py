from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api import webhook, tools
from app.core.logger import setup_logging, logger
from contextlib import asynccontextmanager
from datetime import datetime

setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting AI Receptionist Backend")
    yield
    # Shutdown
    logger.info("🛑 Shutting down backend")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"🔥 UNHANDLED ERROR: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": "An unexpected error occurred. Please contact support."}
    )

# Include routers
app.include_router(webhook.router, prefix="/api", tags=["Webhook"])
app.include_router(tools.router, tags=["Tools"])

@app.get("/")
async def health_check():
    return {'status': 'active', 'time': datetime.now().isoformat()}

@app.get("/health")
async def health_check_std():
    return {"status": "ok", "environment": settings.ENVIRONMENT, "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
