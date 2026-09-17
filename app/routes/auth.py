from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import Store, User
from app.utils.decorators import require_role

auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')

@auth_bp.route('/register_owner', methods=['POST'])
def register_owner():
    """
    Onboarding endpoint: Creates store, creates owner user, and links store's owner_user_id.
    """
    data = request.get_json() or {}
    store_name = data.get('store_name')
    name = data.get('name')
    phone = data.get('phone')
    password = data.get('password')

    if not all([store_name, name, phone, password]):
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "store_name, name, phone, and password are required."
            }
        }), 400

    existing_user = User.query.filter_by(phone=phone).first()
    if existing_user:
        return jsonify({
            "error": {
                "code": "DUPLICATE_USER",
                "message": "A user with this phone number already exists."
            }
        }), 400

    try:
        # Step 1: Create store without owner_user_id
        store = Store(name=store_name, address=data.get('address'), language_pref=data.get('language_pref', 'hi-en'))
        db.session.add(store)
        db.session.flush()

        # Step 2: Create owner user
        user = User(
            store_id=store.store_id,
            role='owner',
            name=name,
            phone=phone
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Step 3: Backfill store's owner_user_id
        store.owner_user_id = user.user_id
        db.session.commit()

        login_user(user)

        return jsonify({
            "message": "Owner registered successfully.",
            "user": {
                "user_id": user.user_id,
                "name": user.name,
                "role": user.role,
                "store_id": user.store_id,
                "store_name": store.name
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": {
                "code": "REGISTRATION_FAILED",
                "message": "Failed to complete owner registration. Please try again."
            }
        }), 500

@auth_bp.route('/register_helper', methods=['POST'])
@require_role('owner')
def register_helper():
    """
    Owner registers a new helper user for their store.
    """
    data = request.get_json() or {}
    name = data.get('name')
    phone = data.get('phone')
    password = data.get('password')

    if not all([name, phone, password]):
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "name, phone, and password are required."
            }
        }), 400

    existing_user = User.query.filter_by(store_id=current_user.store_id, phone=phone).first()
    if existing_user:
        return jsonify({
            "error": {
                "code": "DUPLICATE_USER",
                "message": "A user with this phone number already exists in your store."
            }
        }), 400

    user = User(
        store_id=current_user.store_id,
        role='helper',
        name=name,
        phone=phone
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "Helper user registered successfully.",
        "user": {
            "user_id": user.user_id,
            "name": user.name,
            "role": user.role,
            "store_id": user.store_id
        }
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    phone = data.get('phone')
    password = data.get('password')

    if not phone or not password:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "phone and password are required."
            }
        }), 400

    user = User.query.filter_by(phone=phone).first()
    if not user or not user.check_password(password):
        return jsonify({
            "error": {
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid phone number or password."
            }
        }), 401

    login_user(user)

    return jsonify({
        "message": "Logged in successfully.",
        "user": {
            "user_id": user.user_id,
            "name": user.name,
            "role": user.role,
            "store_id": user.store_id
        }
    }), 200

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out successfully."}), 200

@auth_bp.route('/me', methods=['GET'])
@login_required
def get_me():
    return jsonify({
        "user": {
            "user_id": current_user.user_id,
            "name": current_user.name,
            "role": current_user.role,
            "store_id": current_user.store_id,
            "store_name": current_user.store.name if current_user.store else None
        }
    }), 200
