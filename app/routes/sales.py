from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, request, jsonify
from flask_login import current_user
from sqlalchemy import func
from app.extensions import db
from app.models import Transaction, KhataEntry, Customer
from app.utils.decorators import require_role, get_active_store_id

sales_bp = Blueprint('sales', __name__, url_prefix='/api/v1/sales')

@sales_bp.route('/summary', methods=['GET'])
@require_role('owner')
def sales_summary():
    """
    GET /api/v1/sales/summary?range=today|week|custom&start=&end=
    Aggregated sales metrics (Owner only). Helper is blocked per PRD Persona 2.
    """
    date_range = request.args.get('range', 'today')
    now = datetime.utcnow()

    if date_range == 'today':
        start_date = datetime(now.year, now.month, now.day, 0, 0, 0)
        end_date = datetime(now.year, now.month, now.day, 23, 59, 59)
    elif date_range == 'week':
        start_date = now - timedelta(days=7)
        end_date = now
    elif date_range == 'custom':
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        start_date = datetime.fromisoformat(start_str) if start_str else now - timedelta(days=30)
        end_date = datetime.fromisoformat(end_str) if end_str else now
    else:
        start_date = datetime(now.year, now.month, now.day, 0, 0, 0)
        end_date = datetime(now.year, now.month, now.day, 23, 59, 59)

    # 1. Total revenue & transaction count
    query = db.session.query(
        func.coalesce(func.sum(Transaction.total), 0),
        func.count(Transaction.txn_id)
    ).filter(
        Transaction.store_id == get_active_store_id(),
        Transaction.voided_at.is_(None),
        Transaction.created_at >= start_date,
        Transaction.created_at <= end_date
    ).first()

    total_revenue = Decimal(str(query[0] or 0))
    txn_count = query[1] or 0
    avg_order_value = Decimal(str(total_revenue / txn_count)) if txn_count > 0 else Decimal('0.00')

    # 2. Outstanding Udhaar total across all store customers (net: credits - payments)
    from sqlalchemy import case
    udhaar_query = db.session.query(
        func.coalesce(func.sum(case((KhataEntry.type == 'credit', KhataEntry.amount), else_=0)), 0) -
        func.coalesce(func.sum(case((KhataEntry.type == 'payment', KhataEntry.amount), else_=0)), 0)
    ).filter(KhataEntry.store_id == get_active_store_id()).scalar()

    outstanding_udhaar = Decimal(str(udhaar_query or 0))

    return jsonify({
        "range": date_range,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "total_revenue": float(total_revenue),
        "txn_count": txn_count,
        "avg_order_value": float(avg_order_value),
        "outstanding_udhaar_total": float(outstanding_udhaar)
    }), 200

@sales_bp.route('/history', methods=['GET'])
def sales_history():
    """
    GET /api/v1/sales/history?limit=50
    Returns store-scoped non-voided transaction history.
    """
    from flask_login import login_required
    limit = int(request.args.get('limit', 50))
    txns = Transaction.query.filter_by(
        store_id=get_active_store_id()
    ).filter(
        Transaction.voided_at.is_(None)
    ).order_by(
        Transaction.created_at.desc()
    ).limit(limit).all()

    results = []
    for t in txns:
        customer_name = t.customer.name if t.customer else "Walk-in Customer"
        items_count = len(t.items) if t.items else 0
        results.append({
            "txn_id": t.txn_id,
            "invoice_number": t.invoice_number,
            "created_at": t.created_at.isoformat(),
            "customer_name": customer_name,
            "items_count": items_count,
            "total": float(t.total),
            "payment_status": t.payment_status
        })

    return jsonify({
        "sales": results,
        "total_count": len(results)
    }), 200
