from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import Product, Inventory
from app.services.inventory_engine import InventoryEngine
from app.utils.decorators import require_role

inventory_bp = Blueprint('inventory', __name__, url_prefix='/api/v1/inventory')

@inventory_bp.route('', methods=['GET'])
@login_required
def get_inventory():
    """
    GET /api/v1/inventory
    Returns current stock levels for all products in the store.
    """
    products = Product.query.filter_by(store_id=current_user.store_id, is_active=True).all()
    result = []
    for p in products:
        inv = p.inventory
        result.append({
            "product_id": p.product_id,
            "name": p.name,
            "quantity_on_hand": float(inv.quantity_on_hand) if inv else 0.0,
            "low_stock_threshold": float(inv.low_stock_threshold) if inv else 0.0,
            "is_low": inv.is_low_stock if inv else False
        })
    return jsonify(result), 200

@inventory_bp.route('/<int:product_id>', methods=['PATCH'])
@require_role('owner')
def adjust_inventory(product_id):
    """
    PATCH /api/v1/inventory/{product_id}
    Manual stock correction (Owner only). Writes an audit entry to inventory_adjustments.
    """
    data = request.get_json() or {}
    quantity_delta = data.get('quantity_delta')
    reason = data.get('reason')

    if quantity_delta is None or not reason:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "quantity_delta and reason are required."
            }
        }), 400

    try:
        updated_inv = InventoryEngine.adjust_stock(
            store_id=current_user.store_id,
            product_id=product_id,
            user_id=current_user.user_id,
            quantity_delta=quantity_delta,
            reason=reason
        )
        return jsonify({
            "message": "Stock adjusted successfully.",
            "product_id": product_id,
            "quantity_on_hand": float(updated_inv.quantity_on_hand)
        }), 200
    except ValueError as ve:
        if str(ve) == "PRODUCT_NOT_FOUND":
            return jsonify({
                "error": {
                    "code": "PRODUCT_NOT_FOUND",
                    "message": f"Product with ID {product_id} not found."
                }
            }), 404
        return jsonify({
            "error": {
                "code": "ADJUSTMENT_FAILED",
                "message": str(ve)
            }
        }), 400
from app.models.inventory_movement import InventoryMovement

@inventory_bp.route('/<int:product_id>/history', methods=['GET'])
@login_required
def get_inventory_history(product_id):
    """
    GET /api/v1/inventory/{product_id}/history
    Returns inventory movement history for a product.
    """
    # Ensure product belongs to store
    product = Product.query.filter_by(product_id=product_id, store_id=current_user.store_id).first()
    if not product:
        return jsonify({
            "error": {
                "code": "PRODUCT_NOT_FOUND",
                "message": f"Product with ID {product_id} not found."
            }
        }), 404
        
    movements = InventoryMovement.query.filter_by(
        product_id=product_id, 
        store_id=current_user.store_id
    ).order_by(InventoryMovement.created_at.desc()).all()
    
    result = []
    for m in movements:
        result.append({
            "movement_id": m.movement_id,
            "movement_type": m.movement_type,
            "quantity": float(m.quantity),
            "previous_stock": float(m.previous_stock),
            "new_stock": float(m.new_stock),
            "reason": m.reason,
            "created_at": m.created_at.isoformat()
        })
        
    return jsonify(result), 200
