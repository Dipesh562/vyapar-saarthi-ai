from datetime import datetime
from app.extensions import db

class InventoryMovement(db.Model):
    __tablename__ = 'inventory_movements'

    movement_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True, autoincrement=True)
    store_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('stores.store_id'), nullable=False)
    product_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('products.product_id'), nullable=False)
    movement_type = db.Column(db.String(50), nullable=False) # STOCK_IN, STOCK_OUT, ADJUSTMENT, SALE, RETURN
    quantity = db.Column(db.Numeric(10, 3), nullable=False)
    previous_stock = db.Column(db.Numeric(10, 3), nullable=False)
    new_stock = db.Column(db.Numeric(10, 3), nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    product = db.relationship('Product', foreign_keys=[product_id])
    store = db.relationship('Store', foreign_keys=[store_id])
