from datetime import datetime
from app.extensions import db

class DraftBill(db.Model):
    __tablename__ = 'draft_bills'

    draft_bill_id = db.Column(db.String(64), primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.store_id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.customer_id'), nullable=True)
    line_items_json = db.Column(db.Text, nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    warnings_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        import json
        return {
            "draft_bill_id": self.draft_bill_id,
            "store_id": self.store_id,
            "customer_id": self.customer_id,
            "line_items": json.loads(self.line_items_json) if self.line_items_json else [],
            "subtotal": float(self.subtotal),
            "total": float(self.total),
            "warnings": json.loads(self.warnings_json) if self.warnings_json else [],
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class BillingIdempotency(db.Model):
    __tablename__ = 'billing_idempotency'

    id = db.Column(db.Integer, primary_key=True)
    cache_key = db.Column(db.String(128), unique=True, index=True, nullable=False)
    response_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
