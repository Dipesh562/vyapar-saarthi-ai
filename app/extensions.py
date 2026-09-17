from flask import jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Authentication required."
        }
    }), 401
