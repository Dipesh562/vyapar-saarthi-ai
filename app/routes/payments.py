from decimal import Decimal
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Customer
from app.services.khata_engine import KhataEngine
from app.utils.decorators import require_role

payments_bp = Blueprint('payments', __name__, url_prefix='/api/v1/payments')

# In-memory idempotency cache for payment endpoints (store_id + idempotency_key -> response)
IDEMPOTENCY_CACHE = {}

@payments_bp.route('', methods=['POST'])
@login_required
def record_payment():
    """
    POST /api/v1/payments
    Record payment against customer's Udhaar. Supports idempotency key (API_SPEC.md §5).
    """
    data = request.get_json() or {}
    customer_id = data.get('customer_id')
    amount = data.get('amount')
    idempotency_key = data.get('idempotency_key')

    if not all([customer_id, amount is not None, idempotency_key]):
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "customer_id, amount, and idempotency_key are required."
            }
        }), 400

    # Idempotency check
    cache_key = f"{current_user.store_id}:{idempotency_key}"
    if cache_key in IDEMPOTENCY_CACHE:
        cached_data, cached_code = IDEMPOTENCY_CACHE[cache_key]
        return jsonify(cached_data), cached_code

    customer = Customer.query.filter_by(customer_id=customer_id, store_id=current_user.store_id).first()
    if not customer:
        return jsonify({
            "error": {
                "code": "CUSTOMER_NOT_FOUND",
                "message": f"Customer with ID {customer_id} not found."
            }
        }), 404

    amt_dec = Decimal(str(amount))
    if amt_dec <= 0:
        return jsonify({
            "error": {
                "code": "INVALID_AMOUNT",
                "message": "Payment amount must be greater than zero."
            }
        }), 400

    entry = KhataEngine.add_payment_entry(
        customer_id=customer_id,
        store_id=current_user.store_id,
        user_id=current_user.user_id,
        amount=amt_dec
    )
    db.session.commit()

    new_balance = KhataEngine.get_customer_balance(customer_id)

    response_payload = {
        "message": "Payment recorded successfully.",
        "entry_id": entry.entry_id,
        "customer_id": customer_id,
        "amount_paid": float(amt_dec),
        "new_balance": float(new_balance)
    }

    # Store in idempotency cache
    IDEMPOTENCY_CACHE[cache_key] = (response_payload, 200)

    return jsonify(response_payload), 200
