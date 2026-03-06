"""Flask application factory."""

import os
from flask import Flask
from config import config
from app.extensions import db, login_manager, migrate, csrf


def create_app(config_name='development'):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Ensure instance and receipts folders exist
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config.get('RECEIPTS_FOLDER', 'receipts'), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    # Register blueprints
    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.schools.routes import schools_bp
    app.register_blueprint(schools_bp, url_prefix='/schools')

    from app.students.routes import students_bp
    app.register_blueprint(students_bp, url_prefix='/students')

    from app.payments.routes import payments_bp
    app.register_blueprint(payments_bp, url_prefix='/payments')

    from app.reports.routes import reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')

    # Register main routes
    from app.main import main_bp
    app.register_blueprint(main_bp)

    # User loader
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    return app
