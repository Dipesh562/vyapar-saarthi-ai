from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Customer, KhataEntry
from app.services.khata_engine import KhataEngine

customers_bp = Blueprint('customers', __name__, url_prefix='/api/v1/customers')

@customers_bp.route('', methods=['GET'])
@login_required
def list_customers():
    """
    GET /api/v1/customers
    List customers in store along with dynamically derived Khata balance.
    """
    customers = Customer.query.filter_by(store_id=current_user.store_id).all()
    result = []
    for c in customers:
        balance = KhataEngine.get_customer_balance(c.customer_id)
        result.append({
            "customer_id": c.customer_id,
            "name": c.name,
            "phone": c.phone,
            "balance": float(balance)
        })
    return jsonify(result), 200

@customers_bp.route('', methods=['POST'])
@login_required
def create_customer():
    """
    POST /api/v1/customers
    Create a new customer. Returns warning if duplicate is suspected (PRD §14).
    """
    data = request.get_json() or {}
    name = data.get('name')
    phone = data.get('phone')

    if not name:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Customer name is required."
            }
        }), 400

    # Duplicate detection (PRD §14)
    existing_by_phone = Customer.query.filter_by(store_id=current_user.store_id, phone=phone).first() if phone else None
    existing_by_name = Customer.query.filter_by(store_id=current_user.store_id, name=name).first()

    possible_duplicates = []
    if existing_by_phone:
        possible_duplicates.append({"customer_id": existing_by_phone.customer_id, "name": existing_by_phone.name, "phone": existing_by_phone.phone, "reason": "same_phone"})
    if existing_by_name and (not existing_by_phone or existing_by_name.customer_id != existing_by_phone.customer_id):
        possible_duplicates.append({"customer_id": existing_by_name.customer_id, "name": existing_by_name.name, "phone": existing_by_name.phone, "reason": "same_name"})

    customer = Customer(
        store_id=current_user.store_id,
        name=name,
        phone=phone
    )
    db.session.add(customer)
    db.session.commit()

    res = {
        "message": "Customer created successfully.",
        "customer": {
            "customer_id": customer.customer_id,
            "name": customer.name,
            "phone": customer.phone,
            "balance": 0.0
        }
    }
    if possible_duplicates:
        res["possible_duplicates"] = possible_duplicates

    return jsonify(res), 201

@customers_bp.route('/<int:customer_id>/khata', methods=['GET'])
@login_required
def get_customer_khata(customer_id):
    """
    GET /api/v1/customers/{id}/khata
    Returns customer's running Udhaar balance and transaction history.
    """
    customer = Customer.query.filter_by(customer_id=customer_id, store_id=current_user.store_id).first()
    if not customer:
        return jsonify({
            "error": {
                "code": "CUSTOMER_NOT_FOUND",
                "message": f"Customer with ID {customer_id} not found."
            }
        }), 404

    entries = KhataEntry.query.filter_by(customer_id=customer_id).order_by(KhataEntry.created_at.asc()).all()
    balance = KhataEngine.get_customer_balance(customer_id)

    return jsonify({
        "customer_id": customer.customer_id,
        "name": customer.name,
        "phone": customer.phone,
        "balance": float(balance),
        "entries": [{
            "entry_id": e.entry_id,
            "amount": float(e.amount),
            "type": e.type,
            "txn_id": e.txn_id,
            "created_at": e.created_at.isoformat()
        } for e in entries]
    }), 200
