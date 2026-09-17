import pytest
from app import create_app
from app.extensions import db
from app.models import Product, Inventory, ProductSynonym, User
from seed.load_seed import load_seed

@pytest.fixture
def app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.app_context():
        db.create_all()
        # Seed the database
        load_seed()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_seed_acceptance_criteria(client):
    with client.application.app_context():
        # 1. 22 products loaded under store_id = 1
        products = Product.query.filter_by(store_id=1).all()
        assert len(products) == 22, f"Expected 22 products, found {len(products)}"

        # 2. Every product has a corresponding Inventory row
        for p in products:
            inv = Inventory.query.filter_by(product_id=p.product_id).first()
            assert inv is not None, f"Product {p.name} (id {p.product_id}) missing inventory row!"

        # 3. Every product has at least 2 ProductAlias / ProductSynonym rows
        for p in products:
            syns = ProductSynonym.query.filter_by(maps_to_product_id=p.product_id).all()
            assert len(syns) >= 2, f"Product {p.name} has fewer than 2 aliases!"

        # Total synonyms count >= 60
        total_syns = ProductSynonym.query.filter_by(store_id=1).count()
        assert total_syns >= 60, f"Expected >= 60 total synonyms, found {total_syns}"

        # 4. Green Chilli (product_id 21) seeded below low_stock_threshold
        chilli_inv = Inventory.query.filter_by(product_id=21).first()
        assert chilli_inv is not None
        assert float(chilli_inv.quantity_on_hand) == 2.0
        assert float(chilli_inv.low_stock_threshold) == 5.0
        assert float(chilli_inv.quantity_on_hand) <= float(chilli_inv.low_stock_threshold)

        # 5. Three Oil-category products exist with distinct brand names (Fortune, Saffola, Dhara)
        oils = Product.query.filter_by(store_id=1, category='Oil').all()
        assert len(oils) >= 3
        brands = {o.brand for o in oils}
        assert 'Fortune' in brands
        assert 'Saffola' in brands
        assert 'Dhara' in brands

def test_live_voice_billing_seed_resolution(client):
    # Create or update owner user for pilot store (store_id = 1) and login
    with client.application.app_context():
        owner = User.query.filter_by(store_id=1, phone='9876543210').first()
        if not owner:
            owner = User(store_id=1, role='owner', name='Pilot Owner', phone='9876543210')
            db.session.add(owner)
        owner.set_password('pass')
        db.session.commit()

    client.post('/api/v1/auth/login', json={"phone": "9876543210", "password": "pass"})

    # 6. Live voice-billing test: "do kilo sugar, ek Fortune Sunlite Oil aur teen Parle-G"
    res_voice = client.post('/api/v1/voice/process_bill', json={
        "transcript": "do kilo sugar, ek Fortune Sunlite Oil aur teen Parle-G"
    })
    assert res_voice.status_code == 201
    data = res_voice.get_json()
    assert data['status'] == 'draft_created'
    
    draft_items = data['draft_bill']['line_items']
    assert len(draft_items) == 3

    item_names = [i['name'] for i in draft_items]
    assert any("Sugar" in name for name in item_names)
    assert any("Fortune" in name for name in item_names)
    assert any("Parle-G" in name for name in item_names)
