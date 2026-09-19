from flask import Flask
from config import Config
from app.extensions import db, login_manager, migrate

def create_app(config_class=Config):
    app_obj = Flask(__name__)
    if isinstance(config_class, dict):
        app_obj.config.from_object(Config)
        app_obj.config.update(config_class)
    elif config_class:
        app_obj.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app_obj)
    login_manager.init_app(app_obj)
    migrate.init_app(app_obj, db)

    # Optional Production Sentry Exception Monitoring
    import os
    sentry_dsn = os.environ.get('SENTRY_DSN')
    if sentry_dsn and not sentry_dsn.startswith('mock'):
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[FlaskIntegration()],
                traces_sample_rate=0.2,
            )
        except Exception as sentry_err:
            print(f"--> Sentry init notice: {sentry_err}")

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.health import health_bp
    from app.routes.auth import auth_bp
    from app.routes.products import products_bp
    from app.routes.inventory import inventory_bp
    from app.routes.customers import customers_bp
    from app.routes.payments import payments_bp
    from app.routes.billing import billing_bp
    from app.routes.receipts import receipts_bp
    from app.routes.sales import sales_bp
    from app.routes.voice import voice_bp
    from app.routes.ai import ai_bp
    from app.routes.assistant import assistant_bp
    from app.routes.alerts import alerts_bp
    from app.routes.inventory_csv import inventory_csv_bp
    from app.routes.stores import stores_bp

    app_obj.register_blueprint(main_bp)
    app_obj.register_blueprint(health_bp)
    app_obj.register_blueprint(auth_bp)
    app_obj.register_blueprint(products_bp)
    app_obj.register_blueprint(inventory_bp)
    app_obj.register_blueprint(customers_bp)
    app_obj.register_blueprint(payments_bp)
    app_obj.register_blueprint(billing_bp)
    app_obj.register_blueprint(receipts_bp)
    app_obj.register_blueprint(sales_bp)
    app_obj.register_blueprint(voice_bp)
    app_obj.register_blueprint(ai_bp)
    app_obj.register_blueprint(assistant_bp)
    app_obj.register_blueprint(alerts_bp)
    app_obj.register_blueprint(inventory_csv_bp)
    app_obj.register_blueprint(stores_bp)

    # Global 500 Error Handler (Sanitized output)
    @app_obj.errorhandler(500)
    def handle_internal_server_error(e):
        return {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred. Please try again."
            }
        }, 500

    # Automatically ensure DB tables & seed demo inventory on boot
    with app_obj.app_context():
        import app.models  # Ensure all SQLAlchemy models are registered
        try:
            db.create_all()
        except Exception as db_err:
            print(f"--> Database Connection Warning: {db_err}")
            print("--> Falling back to local SQLite database (vyapar_saarthi_dev.db)...")
            app_obj.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vyapar_saarthi_dev.db'
            try:
                db.engine.dispose()
            except Exception:
                pass
            if 'sqlalchemy' in app_obj.extensions:
                del app_obj.extensions['sqlalchemy']
            db.init_app(app_obj)
            db.create_all()

        if not app_obj.config.get('TESTING') and app_obj.config.get('SEED_DEMO', True):
            try:
                from app.models import Product
                if Product.query.count() == 0:
                    print("--> First boot detected: Auto-loading demo seed inventory...")
                    from seed.load_seed import run_seed_in_context
                    run_seed_in_context()
            except Exception as e:
                print(f"--> Database init notice: {e}")

    return app_obj
