from functools import wraps
from flask import jsonify, session, abort
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


def get_active_store_id() -> int:
    """
    Returns the store_id that is currently active for this session.

    Resolution order:
      1. If session['active_store_id'] is set AND the current user owns that store → use it.
      2. Otherwise fall back to current_user.store_id (home store).

    Raises 403 JSON error if the user tries to access a store they do not own.
    This is the single point of truth for all store-scoped API calls.
    """
    if not current_user.is_authenticated:
        return abort(401)

    requested_id = session.get('active_store_id')
    if requested_id is None:
        return current_user.store_id

    # Validate ownership — check the OwnerStore junction table
    accessible = current_user.accessible_store_ids
    if requested_id not in accessible:
        # Session is stale or tampered — reset and fall back to home store
        session.pop('active_store_id', None)
        return current_user.store_id

    return requested_id
