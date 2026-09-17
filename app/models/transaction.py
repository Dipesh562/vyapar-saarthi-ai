from datetime import datetime
from app.extensions import db

class Transaction(db.Model):
    __tablename__ = 'transactions'

    txn_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True, autoincrement=True)
    store_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('stores.store_id'), nullable=False)
    customer_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('customers.customer_id'), nullable=True)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    payment_status = db.Column(db.Enum('paid', 'udhaar', name='txn_payment_status'), nullable=False)
    invoice_number = db.Column(db.String(50), nullable=False)
    created_by_user_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('users.user_id'), nullable=False)
    voided_at = db.Column(db.DateTime, nullable=True)
    void_reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    items = db.relationship('TransactionItem', backref='transaction', lazy=True, cascade="all, delete-orphan")
    adjustments = db.relationship('TransactionAdjustment', backref='transaction', lazy=True)
    creator = db.relationship('User', foreign_keys=[created_by_user_id])

    __table_args__ = (
        db.UniqueConstraint('store_id', 'invoice_number', name='uq_txn_store_invoice'),
        db.Index('idx_txn_store_created', 'store_id', 'created_at'),
    )

class TransactionItem(db.Model):
    __tablename__ = 'transaction_items'

    txn_item_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True, autoincrement=True)
    txn_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('transactions.txn_id'), nullable=False)
    product_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('products.product_id'), nullable=False)
    quantity = db.Column(db.Numeric(10, 3), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)

    product = db.relationship('Product', foreign_keys=[product_id])

    __table_args__ = (
        db.Index('idx_ti_txn', 'txn_id'),
    )

class TransactionAdjustment(db.Model):
    __tablename__ = 'transaction_adjustments'

    adjustment_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True, autoincrement=True)
    original_txn_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('transactions.txn_id'), nullable=False)
    adjustment_type = db.Column(db.Enum('void', 'item_correction', 'refund', name='txn_adj_type'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount_delta = db.Column(db.Numeric(10, 2), nullable=False)
    adjusted_by_user_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    adjusted_by_user = db.relationship('User', foreign_keys=[adjusted_by_user_id])
