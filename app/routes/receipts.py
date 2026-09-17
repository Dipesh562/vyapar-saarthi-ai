from flask import Blueprint, request, jsonify, render_template_string
from flask_login import login_required, current_user
from app.models import Transaction, TransactionItem, Store, Customer

receipts_bp = Blueprint('receipts', __name__, url_prefix='/api/v1/receipts')

RECEIPT_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Receipt - {{ txn.invoice_number }}</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 400px; margin: 20px auto; padding: 15px; border: 1px solid #ccc; }
        .header { text-align: center; border-bottom: 1px dashed #000; padding-bottom: 10px; }
        .header h2 { margin: 5px 0; }
        .details { margin: 10px 0; font-size: 14px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 5px 0; font-size: 14px; }
        .right { text-align: right; }
        .total { border-top: 1px solid #000; font-weight: bold; margin-top: 10px; padding-top: 5px; font-size: 16px; }
        .footer { text-align: center; margin-top: 15px; font-size: 12px; color: #555; }
    </style>
</head>
<body>
    <div class="header">
        <h2>{{ store.name }}</h2>
        <p>{{ store.address or 'Karvenagar, Pune' }}</p>
    </div>
    <div class="details">
        <p><strong>Invoice:</strong> {{ txn.invoice_number }}</p>
        <p><strong>Date:</strong> {{ txn.created_at.strftime('%Y-%m-%d %H:%M') }}</p>
        {% if customer %}
        <p><strong>Customer:</strong> {{ customer.name }} ({{ customer.phone or 'N/A' }})</p>
        {% endif %}
        <p><strong>Payment Status:</strong> {{ txn.payment_status.upper() }}</p>
    </div>
    <table>
        <thead>
            <tr>
                <th>Item</th>
                <th>Qty</th>
                <th class="right">Price</th>
                <th class="right">Total</th>
            </tr>
        </thead>
        <tbody>
            {% for item in items %}
            <tr>
                <td>{{ item.product.name }}</td>
                <td>{{ item.quantity }} {{ item.product.unit }}</td>
                <td class="right">₹{{ "%.2f"|format(item.unit_price) }}</td>
                <td class="right">₹{{ "%.2f"|format(item.line_total) }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <div class="total">
        <span style="float: left;">Total:</span>
        <span style="float: right;">₹{{ "%.2f"|format(txn.total) }}</span>
        <div style="clear: both;"></div>
    </div>
    <div class="footer">
        <p>Thank you for shopping with us!</p>
        <p>Powered by Vyapar Saarthi AI</p>
    </div>
</body>
</html>
"""

@receipts_bp.route('/generate', methods=['POST'])
@login_required
def generate_receipt():
    """
    POST /api/v1/receipts/generate
    Generates a shareable receipt link.
    """
    data = request.get_json() or {}
    txn_id = data.get('txn_id')
    send_via = data.get('send_via', 'none')

    if not txn_id:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "txn_id is required."
            }
        }), 400

    txn = Transaction.query.filter_by(txn_id=txn_id, store_id=current_user.store_id).first()
    if not txn:
        return jsonify({
            "error": {
                "code": "TRANSACTION_NOT_FOUND",
                "message": f"Transaction with ID {txn_id} not found."
            }
        }), 404

    receipt_url = f"/api/v1/receipts/{txn_id}/view"
    sent = False
    delivery_note = "Digital receipt created."

    from config import Config
    if send_via in ['whatsapp', 'sms'] and Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN:
        try:
            from twilio.rest import Client
            twilio_client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
            
            customer = Customer.query.get(txn.customer_id) if txn.customer_id else None
            cust_phone = customer.phone if customer else None

            if cust_phone:
                full_receipt_link = f"{request.host_url.rstrip('/')}{receipt_url}"
                msg_body = f"Receipt for Invoice #{txn.invoice_number} Total: ₹{txn.total:.2f}. View bill: {full_receipt_link}"
                
                if send_via == 'whatsapp':
                    from_num = getattr(Config, 'TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')
                    to_num = f"whatsapp:{cust_phone}" if not cust_phone.startswith('whatsapp:') else cust_phone
                    twilio_client.messages.create(body=msg_body, from_=from_num, to=to_num)
                    sent = True
                    delivery_note = f"WhatsApp receipt sent to {cust_phone}"
                else:
                    from_num = getattr(Config, 'TWILIO_PHONE_NUMBER', '')
                    if from_num:
                        twilio_client.messages.create(body=msg_body, from_=from_num, to=cust_phone)
                        sent = True
                        delivery_note = f"SMS receipt sent to {cust_phone}"
        except Exception as twilio_err:
            print(f"[Receipts] Twilio delivery error: {twilio_err}")
            delivery_note = f"Receipt created. Twilio notice: {twilio_err}"

    return jsonify({
        "message": "Receipt generated.",
        "receipt_url": receipt_url,
        "sent": sent,
        "delivery_note": delivery_note
    }), 200

@receipts_bp.route('/<int:txn_id>/view', methods=['GET'])
@login_required
def view_receipt(txn_id):
    """
    GET /api/v1/receipts/{txn_id}/view
    Renders HTML view for receipt link (Store authenticated).
    """
    txn = Transaction.query.filter_by(txn_id=txn_id, store_id=current_user.store_id).first()
    if not txn:
        return "Receipt Not Found", 404

    store = Store.query.get(txn.store_id)
    customer = Customer.query.get(txn.customer_id) if txn.customer_id else None
    items = TransactionItem.query.filter_by(txn_id=txn.txn_id).all()

    return render_template_string(
        RECEIPT_HTML_TEMPLATE,
        txn=txn,
        store=store,
        customer=customer,
        items=items
    )
