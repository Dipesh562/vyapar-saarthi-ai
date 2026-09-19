from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True, autoincrement=True)
    store_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('stores.store_id'), nullable=False)
    role = db.Column(db.Enum('owner', 'helper', name='user_roles'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('store_id', 'phone', name='uq_users_store_phone'),
    )

    def get_id(self):
        return str(self.user_id)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_owner(self):
        return self.role == 'owner'

    @property
    def is_helper(self):
        return self.role == 'helper'

    @property
    def accessible_store_ids(self):
        """
        Returns list of store_ids this user can access.
        For owners: all stores in owner_stores junction table.
        For helpers (future): only their assigned store.
        """
        if self.role != 'owner':
            return [self.store_id]
        # Import here to avoid circular import at module level
        from app.models.owner_store import OwnerStore
        links = OwnerStore.query.filter_by(owner_id=self.user_id).all()
        return [link.store_id for link in links]


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
