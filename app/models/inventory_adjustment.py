from datetime import datetime
from app.extensions import db

class InventoryAdjustment(db.Model):
    __tablename__ = 'inventory_adjustments'

    adjustment_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True, autoincrement=True)
    product_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('products.product_id'), nullable=False)
    store_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('stores.store_id'), nullable=False)
    quantity_delta = db.Column(db.Numeric(10, 3), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    adjusted_by_user_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    product = db.relationship('Product', foreign_keys=[product_id])
    adjusted_by_user = db.relationship('User', foreign_keys=[adjusted_by_user_id])
