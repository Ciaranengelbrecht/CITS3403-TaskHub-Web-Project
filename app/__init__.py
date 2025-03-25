# app/__init__.py
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf
from .config import Config
import time
from sqlalchemy.exc import OperationalError

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)  # Initialize CSRF protection

    login_manager.login_view = 'app.authentication'

    from .models import User, Note, Board, Access, Reply #need to import all models here

    @app.before_request
    def before_request():
        # Ensure CSRF token is set in the session for all requests
        if 'csrf_token' not in session:
            session['csrf_token'] = generate_csrf()

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception as e:
            # Log the error but don't crash
            current_app.logger.error(f"Error loading user: {e}")
            return None

    from .routes import app as app_blueprint
    app.register_blueprint(app_blueprint)
    
    with app.app_context():
        db.create_all() # Generate all tables if they do not exist

    #create any database tables (and file) if they don't exist:
    with app.app_context():
        initialize_database(app)

    return app

def initialize_database(app, retries=5, delay=2):
    """Initialize database with retry logic for production environments"""
    for attempt in range(retries):
        try:
            with app.app_context():
                db.create_all()
                print(f"Database initialized successfully on attempt {attempt + 1}")
                return True
        except OperationalError as e:
            if attempt < retries - 1:
                print(f"Database connection failed (attempt {attempt + 1}/{retries}): {e}")
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print(f"Failed to connect to database after {retries} attempts")
                # In production, fall back to SQLite
                if os.environ.get('RENDER'):
                    print("Falling back to SQLite database")
                    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
                    db.create_all()
                    return True
                return False
