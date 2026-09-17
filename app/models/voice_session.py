from datetime import datetime
import uuid
from app.extensions import db

class VoiceSession(db.Model):
    __tablename__ = 'voice_sessions'

    session_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    store_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('stores.store_id'), nullable=False)
    user_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('users.user_id'), nullable=False)
    transcript = db.Column(db.Text, nullable=False)
    resolved_intent = db.Column(db.String(50), nullable=True)
    confidence_score = db.Column(db.Numeric(4, 3), nullable=True)
    needed_clarification = db.Column(db.Boolean, nullable=False, default=False)
    linked_txn_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('transactions.txn_id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])
    transaction = db.relationship('Transaction', foreign_keys=[linked_txn_id])

    __table_args__ = (
        db.Index('idx_vs_store_created', 'store_id', 'created_at'),
    )
