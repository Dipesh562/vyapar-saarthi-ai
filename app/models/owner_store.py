from datetime import datetime
from app.extensions import db


class OwnerStore(db.Model):
    """
    Junction table mapping one owner (User) to many Stores.
    An owner can own multiple stores; each row represents ownership of one store.
    Only users with role='owner' appear in this table.
    """
    __tablename__ = 'owner_stores'

    id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        primary_key=True,
        autoincrement=True
    )
    owner_id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        db.ForeignKey('users.user_id', ondelete='CASCADE'),
        nullable=False
    )
    store_id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        db.ForeignKey('stores.store_id', ondelete='CASCADE'),
        nullable=False
    )
    # True for the store the owner first registered with (their home/primary store)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('owner_id', 'store_id', name='uq_owner_stores'),
        db.Index('idx_owner_stores_owner', 'owner_id'),
    )
