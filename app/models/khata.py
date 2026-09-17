from datetime import datetime
from app.extensions import db

class KhataEntry(db.Model):
    __tablename__ = 'khata_entries'

    entry_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True, autoincrement=True)
    customer_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('customers.customer_id'), nullable=False)
    store_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('stores.store_id'), nullable=False)
    txn_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('transactions.txn_id'), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    type = db.Column(db.Enum('credit', 'payment', name='khata_entry_type'), nullable=False)
    recorded_by_user_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    recorder = db.relationship('User', foreign_keys=[recorded_by_user_id])
    transaction = db.relationship('Transaction', foreign_keys=[txn_id])

    __table_args__ = (
        db.Index('idx_khata_customer', 'customer_id', 'created_at'),
    )
