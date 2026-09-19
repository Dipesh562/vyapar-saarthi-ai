from datetime import datetime
from app.extensions import db

class Store(db.Model):
    __tablename__ = 'stores'

    store_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False)
    owner_user_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('users.user_id', use_alter=True, name='fk_stores_owner'), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(20), nullable=True)          # Store contact phone
    gstin = db.Column(db.String(20), nullable=True)          # GST Identification Number
    language_pref = db.Column(db.String(20), nullable=False, default='hi-en')
    is_active = db.Column(db.Boolean, nullable=False, default=True)  # Soft-delete flag
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = db.relationship('User', backref='store', foreign_keys='User.store_id', lazy=True)
    products = db.relationship('Product', backref='store', lazy=True)
    customers = db.relationship('Customer', backref='store', lazy=True)
    transactions = db.relationship('Transaction', backref='store', lazy=True)
    voice_sessions = db.relationship('VoiceSession', backref='store', lazy=True)
