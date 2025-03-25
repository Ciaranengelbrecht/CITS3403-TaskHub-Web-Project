# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Get database URL from environment or use SQLite for local development
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    
    # If the URL starts with postgres://, convert to postgresql://
    # (SQLAlchemy requires postgresql://, but Supabase provides postgres://)
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'development-key')
    
    # Fix for CSRF issues in production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes
    
    # Make session permanent to avoid early expiration
    PERMANENT_SESSION = True

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
