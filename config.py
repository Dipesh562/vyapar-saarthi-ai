import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1' or os.environ.get('FLASK_ENV') == 'development'
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    raw_db_url = os.environ.get('DATABASE_URL', 'sqlite:///vyapar_saarthi_dev.db')
    if raw_db_url.startswith("postgres://"):
        raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = raw_db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session Cookie Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Demo Seed Gate (default True for demo mode)
    SEED_DEMO = os.environ.get('SEED_DEMO', 'true').lower() == 'true'

    # AI / STT / Twilio secrets
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')

    # Voice Pipeline Mode ('ai_first' or 'legacy')
    VOICE_PIPELINE_MODE = os.environ.get('VOICE_PIPELINE_MODE', 'ai_first')
