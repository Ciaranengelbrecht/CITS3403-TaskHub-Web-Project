# app/__init__.py
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf
from .config import Config

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
        return User.query.get(int(user_id))

    from .routes import app as app_blueprint
    app.register_blueprint(app_blueprint)
    
    with app.app_context():
        db.create_all() # Generate all tables if they do not exist

    #create any database tables (and file) if they don't exist:
    with app.app_context():
        db.create_all()

    return app
