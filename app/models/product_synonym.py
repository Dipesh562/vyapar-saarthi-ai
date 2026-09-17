from datetime import datetime
from app.extensions import db

class ProductSynonym(db.Model):
    __tablename__ = 'product_synonyms'

    synonym_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True, autoincrement=True)
    store_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('stores.store_id'), nullable=True)
    term = db.Column(db.String(100), nullable=False)
    maps_to_category = db.Column(db.String(100), nullable=True)
    maps_to_product_id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), db.ForeignKey('products.product_id'), nullable=True)
    language = db.Column(db.String(10), nullable=True)
    evidence_count = db.Column(db.Integer, default=1, nullable=False)
    last_confirmed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    is_auto_learned = db.Column(db.Boolean, default=False, nullable=False)

    product = db.relationship('Product', foreign_keys=[maps_to_product_id])

    __table_args__ = (
        db.Index('idx_syn_store_term', 'store_id', 'term'),
    )
