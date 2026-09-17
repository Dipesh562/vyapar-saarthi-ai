from datetime import datetime
import re
from app.extensions import db

class Product(db.Model):
    __tablename__ = 'products'

    product_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True, autoincrement=True)
    store_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('stores.store_id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    normalized_name = db.Column(db.String(150), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    category = db.Column(db.String(100), nullable=True)
    brand = db.Column(db.String(100), nullable=True)
    cost_price = db.Column(db.Numeric(10, 2), nullable=True)
    sku = db.Column(db.String(100), nullable=True)
    barcode = db.Column(db.String(100), nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    inventory = db.relationship('Inventory', backref='product', uselist=False, cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        if 'name' in kwargs and 'normalized_name' not in kwargs:
            kwargs['normalized_name'] = self.normalize_product_name(kwargs['name'])
        super().__init__(**kwargs)

    __table_args__ = (
        db.Index('idx_products_store_normalized', 'store_id', 'normalized_name'),
        db.Index('idx_products_store_category', 'store_id', 'category'),
        db.UniqueConstraint('store_id', 'sku', name='uq_products_store_sku'),
    )

    @staticmethod
    def normalize_product_name(raw_name: str) -> str:
        if not raw_name:
            return ""
        try:
            from unidecode import unidecode
            raw_name = unidecode(raw_name)
        except ImportError:
            pass
        # Replace hyphens with spaces first, then strip special characters
        cleaned = raw_name.lower().replace('-', ' ')
        cleaned = re.sub(r'[^\w\s]', '', cleaned)
        return re.sub(r'\s+', ' ', cleaned).strip()
