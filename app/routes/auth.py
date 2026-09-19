from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import Store, User, OwnerStore
from app.utils.decorators import require_role

auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')


# ---------------------------------------------------------------------------
# Helper: build a store dict for API responses
# ---------------------------------------------------------------------------
def _store_dict(store):
    return {
        "store_id": store.store_id,
        "name": store.name,
        "address": store.address,
        "phone": store.phone,
        "gstin": store.gstin,
        "language_pref": store.language_pref,
        "is_active": store.is_active,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register_owner
# Onboarding: creates a brand-new store + owner user (no prior account needed).
# ---------------------------------------------------------------------------
@auth_bp.route('/register_owner', methods=['POST'])
def register_owner():
    """
    Onboarding endpoint for brand-new owners.
    Creates a store, creates the owner user, links them, and auto-creates an OwnerStore row.
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
        # Step 1: Create store (without owner_user_id first)
        store = Store(
            name=store_name,
            address=data.get('address'),
            phone=data.get('store_phone'),
            gstin=data.get('gstin'),
            language_pref=data.get('language_pref', 'hi-en'),
        )
        db.session.add(store)
        db.session.flush()

        # Step 2: Create owner user linked to this store
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

        # Step 4: Create OwnerStore junction row (primary/home store)
        owner_store = OwnerStore(
            owner_id=user.user_id,
            store_id=store.store_id,
            is_primary=True
        )
        db.session.add(owner_store)
        db.session.commit()

        login_user(user)

        return jsonify({
            "message": "Owner registered successfully.",
            "user": {
                "user_id": user.user_id,
                "name": user.name,
                "role": user.role,
                "store_id": user.store_id,
                "active_store_id": store.store_id,
            },
            "store": _store_dict(store)
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": {
                "code": "REGISTRATION_FAILED",
                "message": "Failed to complete owner registration. Please try again."
            }
        }), 500


# ---------------------------------------------------------------------------
# POST /api/v1/auth/add_store
# Logged-in owner adds another store under the same account.
# ---------------------------------------------------------------------------
@auth_bp.route('/add_store', methods=['POST'])
@require_role('owner')
def add_store():
    """
    A logged-in owner creates an additional store linked to their account.
    After creation the new store becomes the active store in the session.
    """
    data = request.get_json() or {}
    store_name = data.get('store_name')

    if not store_name:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "store_name is required."
            }
        }), 400

    try:
        store = Store(
            name=store_name,
            address=data.get('address'),
            phone=data.get('store_phone'),
            gstin=data.get('gstin'),
            language_pref=data.get('language_pref', 'hi-en'),
            owner_user_id=current_user.user_id,
        )
        db.session.add(store)
        db.session.flush()

        owner_store = OwnerStore(
            owner_id=current_user.user_id,
            store_id=store.store_id,
            is_primary=False
        )
        db.session.add(owner_store)
        db.session.commit()

        # Automatically switch session to the new store
        session['active_store_id'] = store.store_id

        return jsonify({
            "message": "New store created and set as active.",
            "store": _store_dict(store),
            "active_store_id": store.store_id
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": {
                "code": "STORE_CREATION_FAILED",
                "message": "Failed to create store. Please try again."
            }
        }), 500


# ---------------------------------------------------------------------------
# POST /api/v1/auth/switch_store
# Owner switches which store is active in their session.
# ---------------------------------------------------------------------------
@auth_bp.route('/switch_store', methods=['POST'])
@require_role('owner')
def switch_store():
    """
    Owner sets the active store for this session.
    Body: { "store_id": <int> }
    All subsequent API calls will operate on this store until switched again.
    """
    data = request.get_json() or {}
    target_store_id = data.get('store_id')

    if not target_store_id:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "store_id is required."
            }
        }), 400

    # Validate the owner actually owns this store
    membership = OwnerStore.query.filter_by(
        owner_id=current_user.user_id,
        store_id=target_store_id
    ).first()

    if not membership:
        return jsonify({
            "error": {
                "code": "STORE_NOT_FOUND",
                "message": "You do not have access to this store."
            }
        }), 403

    store = Store.query.get(target_store_id)
    if not store or not store.is_active:
        return jsonify({
            "error": {
                "code": "STORE_INACTIVE",
                "message": "This store is inactive or does not exist."
            }
        }), 404

    session['active_store_id'] = target_store_id

    return jsonify({
        "message": f"Switched to store: {store.name}",
        "active_store_id": target_store_id,
        "store": _store_dict(store)
    }), 200


# ---------------------------------------------------------------------------
# GET /api/v1/auth/my_stores
# Returns all stores the current owner owns.
# ---------------------------------------------------------------------------
@auth_bp.route('/my_stores', methods=['GET'])
@require_role('owner')
def my_stores():
    """
    Returns all stores owned by the current user, including which is currently active.
    """
    active_store_id = session.get('active_store_id', current_user.store_id)

    memberships = OwnerStore.query.filter_by(owner_id=current_user.user_id).all()
    stores = []
    for m in memberships:
        store = Store.query.get(m.store_id)
        if store:
            d = _store_dict(store)
            d['is_primary'] = m.is_primary
            d['is_active_now'] = (store.store_id == active_store_id)
            stores.append(d)

    return jsonify({
        "owned_stores": stores,
        "active_store_id": active_store_id,
        "total": len(stores)
    }), 200


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------
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

    # For owners: ensure primary store_id has an OwnerStore junction record
    if user.role == 'owner' and user.store_id:
        existing_link = OwnerStore.query.filter_by(owner_id=user.user_id, store_id=user.store_id).first()
        if not existing_link:
            link = OwnerStore(owner_id=user.user_id, store_id=user.store_id, is_primary=True)
            db.session.add(link)
            db.session.commit()

    owned_count = 0
    requires_store_selection = False
    if user.role == 'owner':
        owned_count = OwnerStore.query.filter_by(owner_id=user.user_id).count()
        requires_store_selection = owned_count > 1

    return jsonify({
        "message": "Logged in successfully.",
        "user": {
            "user_id": user.user_id,
            "name": user.name,
            "role": user.role,
            "store_id": user.store_id,
            "active_store_id": session.get('active_store_id', user.store_id),
        },
        "requires_store_selection": requires_store_selection,
        "owned_stores_count": owned_count
    }), 200


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout
# ---------------------------------------------------------------------------
@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.pop('active_store_id', None)
    logout_user()
    return jsonify({"message": "Logged out successfully."}), 200


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------
@auth_bp.route('/me', methods=['GET'])
@login_required
def get_me():
    from app.utils.decorators import get_active_store_id
    active_store_id = get_active_store_id()
    active_store = Store.query.get(active_store_id)

    # Build owned stores list for owners
    owned_stores = []
    if current_user.role == 'owner':
        memberships = OwnerStore.query.filter_by(owner_id=current_user.user_id).all()
        for m in memberships:
            s = Store.query.get(m.store_id)
            if s:
                owned_stores.append({
                    "store_id": s.store_id,
                    "name": s.name,
                    "is_primary": m.is_primary,
                    "is_active": s.is_active,
                    "is_active_now": (s.store_id == active_store_id),
                })

    return jsonify({
        "user": {
            "user_id": current_user.user_id,
            "name": current_user.name,
            "role": current_user.role,
            "store_id": current_user.store_id,
            "active_store_id": active_store_id,
            "active_store_name": active_store.name if active_store else None,
        },
        "owned_stores": owned_stores
    }), 200


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register_helper  (placeholder — scope for later)
# ---------------------------------------------------------------------------
@auth_bp.route('/register_helper', methods=['POST'])
@require_role('owner')
def register_helper():
    """
    Placeholder — helper registration is out of scope for this release.
    """
    return jsonify({
        "error": {
            "code": "NOT_IMPLEMENTED",
            "message": "Helper registration is not available in this release."
        }
    }), 501
