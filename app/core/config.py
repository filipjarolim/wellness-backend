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
    
    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    
    # Notifications
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
