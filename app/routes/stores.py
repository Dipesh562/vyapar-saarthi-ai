from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Store, OwnerStore
from app.utils.decorators import require_role, get_active_store_id

stores_bp = Blueprint('stores', __name__, url_prefix='/api/v1/stores')


def _store_dict(store, is_primary=False, active_store_id=None):
    """Serialize a Store object to a dict for API responses."""
    return {
        "store_id": store.store_id,
        "name": store.name,
        "address": store.address,
        "phone": store.phone,
        "gstin": store.gstin,
        "language_pref": store.language_pref,
        "is_active": store.is_active,
        "is_primary": is_primary,
        "is_active_now": (store.store_id == active_store_id) if active_store_id else False,
        "created_at": store.created_at.isoformat() if store.created_at else None,
    }


def _assert_owns_store(store_id: int):
    """
    Returns the OwnerStore membership if current user owns the store.
    Returns None if not found (caller should return 403/404).
    """
    return OwnerStore.query.filter_by(
        owner_id=current_user.user_id,
        store_id=store_id
    ).first()


# ---------------------------------------------------------------------------
# GET /api/v1/stores
# List all stores owned by the current user.
# ---------------------------------------------------------------------------
@stores_bp.route('', methods=['GET'])
@require_role('owner')
def list_stores():
    """
    Returns all stores the logged-in owner owns, with active store marked.
    """
    active_id = get_active_store_id()
    memberships = OwnerStore.query.filter_by(owner_id=current_user.user_id).all()
    result = []
    for m in memberships:
        store = Store.query.get(m.store_id)
        if store:
            result.append(_store_dict(store, is_primary=m.is_primary, active_store_id=active_id))

    return jsonify({
        "stores": result,
        "active_store_id": active_id,
        "total": len(result)
    }), 200


# ---------------------------------------------------------------------------
# POST /api/v1/stores
# Create a new store under the logged-in owner's account.
# ---------------------------------------------------------------------------
@stores_bp.route('', methods=['POST'])
@require_role('owner')
def create_store():
    """
    Creates a new store and links it to the current owner.
    Automatically sets the new store as the active store for this session.
    """
    data = request.get_json() or {}
    store_name = data.get('store_name') or data.get('name')

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
            phone=data.get('phone'),
            gstin=data.get('gstin'),
            language_pref=data.get('language_pref', 'hi-en'),
            owner_user_id=current_user.user_id,
        )
        db.session.add(store)
        db.session.flush()

        membership = OwnerStore(
            owner_id=current_user.user_id,
            store_id=store.store_id,
            is_primary=False
        )
        db.session.add(membership)
        db.session.commit()

        # Switch session to the new store automatically
        session['active_store_id'] = store.store_id

        return jsonify({
            "message": f"Store '{store.name}' created successfully.",
            "store": _store_dict(store, is_primary=False, active_store_id=store.store_id),
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
# GET /api/v1/stores/<store_id>
# Get details of a specific store owned by the current user.
# ---------------------------------------------------------------------------
@stores_bp.route('/<int:store_id>', methods=['GET'])
@require_role('owner')
def get_store(store_id):
    """
    Returns details for a specific store. Must be owned by the current user.
    """
    membership = _assert_owns_store(store_id)
    if not membership:
        return jsonify({
            "error": {
                "code": "STORE_NOT_FOUND",
                "message": "Store not found or you do not have access."
            }
        }), 404

    store = Store.query.get(store_id)
    active_id = get_active_store_id()
    return jsonify({
        "store": _store_dict(store, is_primary=membership.is_primary, active_store_id=active_id)
    }), 200


# ---------------------------------------------------------------------------
# PATCH /api/v1/stores/<store_id>
# Update name, address, phone, gstin, or language_pref of an owned store.
# ---------------------------------------------------------------------------
@stores_bp.route('/<int:store_id>', methods=['PATCH'])
@require_role('owner')
def update_store(store_id):
    """
    Updates mutable fields of a store. Must be owned by current user.
    Allowed fields: name, address, phone, gstin, language_pref.
    """
    membership = _assert_owns_store(store_id)
    if not membership:
        return jsonify({
            "error": {
                "code": "STORE_NOT_FOUND",
                "message": "Store not found or you do not have access."
            }
        }), 404

    store = Store.query.get(store_id)
    if not store:
        return jsonify({"error": {"code": "STORE_NOT_FOUND", "message": "Store not found."}}), 404

    data = request.get_json() or {}
    updatable = ['name', 'address', 'phone', 'gstin', 'language_pref']
    for field in updatable:
        if field in data:
            setattr(store, field, data[field])

    db.session.commit()
    active_id = get_active_store_id()

    return jsonify({
        "message": "Store updated successfully.",
        "store": _store_dict(store, is_primary=membership.is_primary, active_store_id=active_id)
    }), 200


# ---------------------------------------------------------------------------
# POST /api/v1/stores/<store_id>/switch
# Switch active store for this session.
# ---------------------------------------------------------------------------
@stores_bp.route('/<int:store_id>/switch', methods=['POST'])
@stores_bp.route('/switch/<int:store_id>', methods=['POST'])
@require_role('owner')
def switch_to_store(store_id):
    """
    Sets the given store as the active store for this session.
    All API calls after this will operate in the context of this store.
    """
    membership = _assert_owns_store(store_id)
    if not membership:
        return jsonify({
            "error": {
                "code": "STORE_NOT_FOUND",
                "message": "Store not found or you do not have access."
            }
        }), 403

    store = Store.query.get(store_id)
    if not store or not store.is_active:
        return jsonify({
            "error": {
                "code": "STORE_INACTIVE",
                "message": "This store is inactive or does not exist."
            }
        }), 404

    session['active_store_id'] = store_id

    return jsonify({
        "message": f"Switched to '{store.name}'.",
        "active_store_id": store_id,
        "store": _store_dict(store, is_primary=membership.is_primary, active_store_id=store_id)
    }), 200


# ---------------------------------------------------------------------------
# DELETE /api/v1/stores/<store_id>
# Soft-delete an owned store (sets is_active=False).
# Cannot delete the primary/home store or the currently active store.
# ---------------------------------------------------------------------------
@stores_bp.route('/<int:store_id>', methods=['DELETE'])
@require_role('owner')
def delete_store(store_id):
    """
    Soft-deletes a store by setting is_active=False.
    Prevents deletion of the primary store or if only one store exists.
    """
    membership = _assert_owns_store(store_id)
    if not membership:
        return jsonify({
            "error": {
                "code": "STORE_NOT_FOUND",
                "message": "Store not found or you do not have access."
            }
        }), 404

    if membership.is_primary:
        return jsonify({
            "error": {
                "code": "CANNOT_DELETE_PRIMARY",
                "message": "Cannot delete your primary store. Please set another store as primary first."
            }
        }), 400

    total_stores = OwnerStore.query.filter_by(owner_id=current_user.user_id).count()
    if total_stores <= 1:
        return jsonify({
            "error": {
                "code": "LAST_STORE",
                "message": "You cannot delete your only store."
            }
        }), 400

    store = Store.query.get(store_id)
    store.is_active = False

    # If this was the active store, switch back to home store
    if session.get('active_store_id') == store_id:
        session['active_store_id'] = current_user.store_id

    db.session.commit()

    return jsonify({
        "message": f"Store '{store.name}' has been deactivated.",
        "store_id": store_id
    }), 200
