from functools import wraps
from flask import jsonify
from flask_login import current_user

def require_role(*allowed_roles):
    """
    Decorator to restrict route access to specific roles ('owner', 'helper').
    Returns 401 UNAUTHORIZED if not authenticated, or 403 FORBIDDEN_ROLE if role is not allowed.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Authentication required."
                    }
                }), 401
            
            if current_user.role not in allowed_roles:
                return jsonify({
                    "error": {
                        "code": "FORBIDDEN_ROLE",
                        "message": f"User role '{current_user.role}' does not have permission to access this resource."
                    }
                }), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator
