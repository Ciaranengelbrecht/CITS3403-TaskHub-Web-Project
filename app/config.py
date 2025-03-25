# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database configuration
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    
    # If the URL starts with postgres://, convert to postgresql://
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Add these connection pool settings for better stability
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,  # Recycle connections every 5 minutes
        'pool_timeout': 30,   # Connection timeout after 30 seconds
        'pool_size': 10       # Maximum pool size
    }
    
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
