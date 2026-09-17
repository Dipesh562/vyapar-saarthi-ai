import os
import sys
from decimal import Decimal

# Ensure project root directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text, inspect
from app import create_app
from app.extensions import db
from app.models import Store, User, Product, Inventory, ProductSynonym

def run_seed_in_context():
    """
    Idempotent inventory seed data loader running inside active app context.
    """
    print("--> Checking Database Connection & Schema Alignment...")
    
    # 1. Schema Validation Gate (Fail loudly if required tables/columns missing)
    inspector = inspect(db.engine)
    existing_tables = inspector.get_table_names()

    required_tables = ['stores', 'users', 'products', 'inventory', 'product_synonyms']
    for table in required_tables:
        if table not in existing_tables:
            db.create_all()
            break

    # Re-check columns for Product and Inventory tables
    product_cols = [c['name'] for c in inspector.get_columns('products')] if 'products' in inspector.get_table_names() else []
    inventory_cols = [c['name'] for c in inspector.get_columns('inventory')] if 'inventory' in inspector.get_table_names() else []

    required_product_cols = ['product_id', 'store_id', 'name', 'normalized_name', 'unit', 'price']
    for col in required_product_cols:
        if product_cols and col not in product_cols:
            raise RuntimeError(f"SCHEMA MISMATCH EXCEPTION: Column '{col}' missing from 'products' table!")

    required_inventory_cols = ['product_id', 'quantity_on_hand', 'low_stock_threshold']
    for col in required_inventory_cols:
        if inventory_cols and col not in inventory_cols:
            raise RuntimeError(f"SCHEMA MISMATCH EXCEPTION: Column '{col}' missing from 'inventory' table!")

    print("--> Schema Validation Passed.")
    print("--> Seeding Pilot Store (store_id = 1)...")

    # 2. Ensure Store (store_id = 1)
    store = Store.query.get(1)
    if not store:
        store = Store(store_id=1, name='Karvenagar Kirana Store', address='Karvenagar, Pune', language_pref='hi-en')
        db.session.add(store)
        db.session.commit()

    # 2b. Ensure Demo Owner User for Store 1
    owner = User.query.filter_by(store_id=1, role='owner').first()
    if not owner:
        owner = User(
            store_id=1,
            role='owner',
            name='Ramesh Owner',
            phone='9876543210'
        )
        owner.set_password('password123')
        db.session.add(owner)
        db.session.flush()
        store.owner_user_id = owner.user_id
        db.session.commit()

    print("--> Cleaning existing demo rows (product_id 1..22) for Idempotency...")
    # Disable FK checks temporarily based on engine dialect
    if db.engine.name == 'sqlite':
        db.session.execute(text("PRAGMA foreign_keys = OFF;"))
    elif db.engine.name == 'mysql':
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))

    # Clean existing range 1-22
    ProductSynonym.query.filter(ProductSynonym.maps_to_product_id.between(1, 22)).delete(synchronize_session=False)
    Inventory.query.filter(Inventory.product_id.between(1, 22)).delete(synchronize_session=False)
    Product.query.filter(Product.product_id.between(1, 22)).delete(synchronize_session=False)
    db.session.commit()

    # 3. Read seed_inventory.csv data and seed via ORM to guarantee cross-dialect compatibility
    csv_path = os.path.join(os.path.dirname(__file__), 'seed_inventory.csv')
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Seed CSV not found at {csv_path}")

    import csv
    alias_count = 0
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            p_id = int(row['product_id'])
            name = row['name']
            category = row['category']
            brand = row['brand']
            unit = row['unit']
            price = Decimal(row['price'])
            qty = Decimal(row['quantity_on_hand'])
            threshold = Decimal(row['low_stock_threshold'])
            aliases_raw = row['aliases'].strip('"').split('|')

            # Create Product
            prod = Product(
                product_id=p_id,
                store_id=1,
                name=name,
                normalized_name=Product.normalize_product_name(name),
                unit=unit,
                price=price,
                category=category,
                brand=brand,
                is_active=True
            )
            db.session.add(prod)
            db.session.flush()

            # Create Inventory
            inv = Inventory(
                product_id=p_id,
                quantity_on_hand=qty,
                low_stock_threshold=threshold
            )
            db.session.add(inv)

            # Create ProductSynonyms / Aliases
            for alias in aliases_raw:
                alias_clean = alias.strip()
                if alias_clean:
                    syn = ProductSynonym(
                        store_id=1,
                        term=alias_clean,
                        maps_to_category=category,
                        maps_to_product_id=p_id,
                        language='hinglish'
                    )
                    db.session.add(syn)
                    alias_count += 1

    # Re-enable FK checks
    if db.engine.name == 'sqlite':
        db.session.execute(text("PRAGMA foreign_keys = ON;"))
    elif db.engine.name == 'mysql':
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

    db.session.commit()

    # 4. Verification assertions
    prod_count = Product.query.filter_by(store_id=1).count()
    inv_count = Inventory.query.count()
    syn_count = ProductSynonym.query.filter_by(store_id=1).count()
    chilli_inv = Inventory.query.get(21)

    print(f"--> SEED LOAD COMPLETED SUCCESSFULLY!")
    print(f"    - Products Loaded: {prod_count} (Expect 22)")
    print(f"    - Inventory Rows Loaded: {inv_count} (Expect 22)")
    print(f"    - Product Synonyms/Aliases Loaded: {syn_count} (Expect 60+)")
    print(f"    - Product 21 (Green Chilli) Stock: {chilli_inv.quantity_on_hand} (Threshold: {chilli_inv.low_stock_threshold})")

    assert prod_count == 22, f"Expected 22 products, got {prod_count}"
    assert syn_count >= 60, f"Expected >= 60 aliases, got {syn_count}"
    assert float(chilli_inv.quantity_on_hand) <= float(chilli_inv.low_stock_threshold), "Green Chilli low stock condition failed!"

def load_seed(app=None):
    """
    Idempotent inventory seed data loader.
    Reuses existing project DB configuration (Config / DATABASE_URL).
    """
    from flask import has_app_context
    if has_app_context():
        run_seed_in_context()
    elif app:
        with app.app_context():
            run_seed_in_context()
    else:
        app = create_app()
        with app.app_context():
            run_seed_in_context()

if __name__ == '__main__':
    load_seed()
