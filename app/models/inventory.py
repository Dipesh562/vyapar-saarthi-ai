from datetime import datetime
from app.extensions import db

class Inventory(db.Model):
    __tablename__ = 'inventory'

    product_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('products.product_id'), primary_key=True)
    quantity_on_hand = db.Column(db.Numeric(10, 3), nullable=False, default=0)
    low_stock_threshold = db.Column(db.Numeric(10, 3), nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_low_stock(self) -> bool:
        return float(self.quantity_on_hand) <= float(self.low_stock_threshold)

    @property
    def stock_status(self) -> str:
        qty = float(self.quantity_on_hand)
        if qty <= 0:
            return "out_of_stock"
        elif qty <= float(self.low_stock_threshold):
            return "low_stock"
        else:
            return "in_stock"
