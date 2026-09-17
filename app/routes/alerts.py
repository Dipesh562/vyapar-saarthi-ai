from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app.models import Product, Customer
from app.services.khata_engine import KhataEngine

alerts_bp = Blueprint('alerts', __name__, url_prefix='/api/v1/alerts')

@alerts_bp.route('', methods=['GET'])
@login_required
def get_dashboard_alerts():
    """
    GET /api/v1/alerts (M14: In-App Low-Stock & Payment-Due Alerts)
    Surfaces low-stock items and aging Udhaar balances on the dashboard.
    """
    # 1. Low stock alerts
    products = Product.query.filter_by(store_id=current_user.store_id, is_active=True).all()
    low_stock_alerts = []
    for p in products:
        if p.inventory and p.inventory.is_low_stock:
            low_stock_alerts.append({
                "product_id": p.product_id,
                "name": p.name,
                "quantity_on_hand": float(p.inventory.quantity_on_hand),
                "low_stock_threshold": float(p.inventory.low_stock_threshold),
                "unit": p.unit
            })

    # 2. Payment due / Udhaar alerts
    customers = Customer.query.filter_by(store_id=current_user.store_id).all()
    udhaar_alerts = []
    for c in customers:
        balance = float(KhataEngine.get_customer_balance(c.customer_id))
        if balance > 0:
            udhaar_alerts.append({
                "customer_id": c.customer_id,
                "name": c.name,
                "phone": c.phone,
                "outstanding_balance": balance
            })

    return jsonify({
        "low_stock_alerts": low_stock_alerts,
        "udhaar_alerts": udhaar_alerts,
        "total_alerts": len(low_stock_alerts) + len(udhaar_alerts)
    }), 200
