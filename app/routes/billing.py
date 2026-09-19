from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.billing_engine import BillingEngine
from app.services.cart_session import MerchantCartSession
from app.utils.decorators import get_active_store_id

billing_bp = Blueprint('billing', __name__, url_prefix='/api/v1/billing')

@billing_bp.route('/create', methods=['POST'])
@login_required
def create_draft_bill():
    """
    POST /api/v1/billing/create
    Creates a draft bill from a set of validated product IDs and quantities.
    """
    data = request.get_json() or {}
    items = data.get('items', [])
    customer_id = data.get('customer_id')

    if not items or not isinstance(items, list):
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "items array is required."
            }
        }), 400

    draft_bill_id = data.get('draft_bill_id')
    final_items = items

    if draft_bill_id:
        existing_draft = BillingEngine.get_draft_bill(draft_bill_id, get_active_store_id())
        if existing_draft:
            # Extract existing items
            existing_items_input = [{'product_id': item['product_id'], 'quantity': item['quantity']} for item in existing_draft.get('line_items', [])]
            
            # Merge with new items by aggregating quantities
            merged_items_dict = {}
            for item in existing_items_input + items:
                pid = item['product_id']
                merged_items_dict[pid] = merged_items_dict.get(pid, 0.0) + item['quantity']
            
            final_items = [{'product_id': pid, 'quantity': qty} for pid, qty in merged_items_dict.items()]
            
            if not customer_id:
                customer_id = existing_draft.get('customer_id')
                
            BillingEngine.void_draft_bill(draft_bill_id, get_active_store_id())

    try:
        draft = BillingEngine.create_draft_bill(
            store_id=get_active_store_id(),
            items=final_items,
            customer_id=customer_id
        )
        from app.services.voice_feedback import VoiceFeedbackService
        draft['readback_text'] = VoiceFeedbackService.build_readback_text(draft)
        # Keep MerchantCartSession in sync so "add more" follow-ups resolve correctly
        MerchantCartSession.update_cart(get_active_store_id(), final_items)
        return jsonify(draft), 201

    except ValueError as ve:
        err_msg = str(ve)
        if err_msg.startswith("PRODUCT_NOT_FOUND"):
            product_id = err_msg.split(":")[1] if ":" in err_msg else ""
            return jsonify({
                "error": {
                    "code": "PRODUCT_NOT_FOUND",
                    "message": f"Product with ID {product_id} not found."
                }
            }), 404
        return jsonify({
            "error": {
                "code": "DRAFT_CREATION_FAILED",
                "message": err_msg
            }
        }), 400

@billing_bp.route('/confirm', methods=['POST'])
@login_required
def confirm_bill():
    """
    POST /api/v1/billing/confirm
    Finalises a draft bill, deducts inventory, and records transaction/Udhaar ledger entry.
    Requires idempotency_key.
    """
    data = request.get_json() or {}
    draft_bill_id = data.get('draft_bill_id')
    payment_status = data.get('payment_status')
    customer_id = data.get('customer_id')
    idempotency_key = data.get('idempotency_key')

    if not all([draft_bill_id, payment_status, idempotency_key]):
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "draft_bill_id, payment_status ('paid'|'udhaar'), and idempotency_key are required."
            }
        }), 400

    if payment_status not in ['paid', 'udhaar']:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "payment_status must be 'paid' or 'udhaar'."
            }
        }), 400

    try:
        result = BillingEngine.confirm_bill(
            store_id=get_active_store_id(),
            user_id=current_user.user_id,
            draft_bill_id=draft_bill_id,
            payment_status=payment_status,
            customer_id=customer_id,
            idempotency_key=idempotency_key
        )
        return jsonify(result), 200

    except ValueError as ve:
        err_msg = str(ve)
        if err_msg == "DRAFT_BILL_NOT_FOUND":
            return jsonify({
                "error": {
                    "code": "DRAFT_BILL_NOT_FOUND",
                    "message": "Draft bill not found or expired."
                }
            }), 404
        elif err_msg == "CUSTOMER_REQUIRED_FOR_UDHAAR":
            return jsonify({
                "error": {
                    "code": "CUSTOMER_REQUIRED",
                    "message": "Customer is required when payment status is Udhaar."
                }
            }), 400
        elif err_msg.startswith("INSUFFICIENT_STOCK"):
            parts = err_msg.split(":")
            prod_id = parts[1] if len(parts) > 1 else ""
            prod_name = parts[2] if len(parts) > 2 else ""
            req_qty = float(parts[3]) if len(parts) > 3 else 0.0
            avail_qty = float(parts[4]) if len(parts) > 4 else 0.0
            return jsonify({
                "error": {
                    "code": "INSUFFICIENT_STOCK",
                    "message": f"Insufficient stock for {prod_name}. Requested: {req_qty}, Available: {avail_qty}",
                    "details": {
                        "product_id": int(prod_id) if prod_id.isdigit() else prod_id,
                        "requested": req_qty,
                        "available": avail_qty
                    }
                }
            }), 422
        return jsonify({
            "error": {
                "code": "CONFIRMATION_FAILED",
                "message": err_msg
            }
        }), 400

@billing_bp.route('/<draft_bill_id>', methods=['DELETE'])
@login_required
def void_draft_bill(draft_bill_id):
    """
    DELETE /api/v1/billing/{draft_bill_id}
    Voids a draft bill prior to payment confirmation (PRD §12).
    """
    success = BillingEngine.void_draft_bill(draft_bill_id, get_active_store_id())
    if not success:
        return jsonify({
            "error": {
                "code": "DRAFT_BILL_NOT_FOUND",
                "message": "Draft bill not found."
            }
        }), 404
    return jsonify({"message": "Draft bill voided successfully."}), 200
