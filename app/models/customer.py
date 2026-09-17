from datetime import datetime
from app.extensions import db

class Customer(db.Model):
    __tablename__ = 'customers'

    customer_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True, autoincrement=True)
    store_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('stores.store_id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    khata_entries = db.relationship('KhataEntry', backref='customer', lazy=True)
    transactions = db.relationship('Transaction', backref='customer', lazy=True)

    __table_args__ = (
        db.Index('idx_customers_store_name', 'store_id', 'name'),
        db.Index('idx_customers_store_phone', 'store_id', 'phone'),
    )
