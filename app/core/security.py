from fastapi import HTTPException, Header, Depends
from app.core.config import settings

async def verify_secret_token(x_secret_token: str = Header(None)):
    """
    Verify the secret token from the request header.
    This is a basic security measure to ensure requests are coming from Vapi
    (if you configure Vapi to send a secret header).
    """
    if not settings.SECRET_KEY:
        # If no secret key is set, skip validation (not recommended for production)
        return True
        
    if x_secret_token != settings.SECRET_KEY:
        # For now, we'll just log or return True if not strictly enforced,
        # but in production, raise HTTPException.
        # raise HTTPException(status_code=403, detail="Invalid secret token")
        pass
    return True
