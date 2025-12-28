from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Voice Receptionist"
    API_V1_STR: str = "/api"
    
    # Server
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    
    # Vapi
    VAPI_PRIVATE_KEY: str = ""
    VAPI_ORG_ID: str = ""
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    
    # Security
    SECRET_KEY: str = "dev_secret_key"
    
    # Google
    GOOGLE_CALENDAR_ID: str = "primary"
    GOOGLE_CREDENTIALS_JSON: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
