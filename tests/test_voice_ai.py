import pytest
from app import create_app
from app.extensions import db
from app.models import Product

@pytest.fixture
def app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_voice_ai_and_product_matching_pipeline(client):
    # 1. Onboard Owner & setup Product Catalogue
    client.post('/api/v1/auth/register_owner', json={
        "store_name": "Karvenagar Kirana",
        "name": "Ramesh Owner",
        "phone": "9888888888",
        "password": "pass"
    })

    # Add Product 1: Aata (Flour)
    client.post('/api/v1/products', json={
        "name": "Ashirvaad Whole Wheat Aata 5kg",
        "unit": "packet",
        "price": 260.00,
        "category": "Flour",
        "quantity_on_hand": 20.0
    })

    # Add Product 2: Fortune Oil
    client.post('/api/v1/products', json={
        "name": "Fortune Refined Sunflower Oil 1L",
        "unit": "packet",
        "price": 145.00,
        "category": "Oil",
        "brand": "Fortune",
        "quantity_on_hand": 15.0
    })

    # Add Product 3: Saffola Oil (for ambiguity test)
    client.post('/api/v1/products', json={
        "name": "Saffola Gold Edible Oil 1L",
        "unit": "packet",
        "price": 170.00,
        "category": "Oil",
        "brand": "Saffola",
        "quantity_on_hand": 10.0
    })

    # 2. Test /api/v1/ai/understand
    res_ai = client.post('/api/v1/ai/understand', json={
        "transcript": "2 packet fortune oil aur 1 packet aata do"
    })
    assert res_ai.status_code == 200
    ai_data = res_ai.get_json()
    assert ai_data['intent'] == 'create_bill'
    assert len(ai_data['items']) >= 2

    # 3. Test End-to-End Voice Billing Pipeline (/api/v1/voice/process_bill)
    res_voice = client.post('/api/v1/voice/process_bill', json={
        "transcript": "2 packet fortune oil aur 1 packet aata do"
    })
    assert res_voice.status_code == 201
    voice_data = res_voice.get_json()
    assert voice_data['status'] == 'draft_created'
    assert 'draft_bill' in voice_data
    assert len(voice_data['draft_bill']['line_items']) == 2

    # 4. Test Ambiguity Clarification Trigger (Journey G: "1 packet oil")
    res_ambiguous = client.post('/api/v1/voice/process_bill', json={
        "transcript": "1 packet oil do"
    })
    assert res_ambiguous.status_code == 200
    amb_data = res_ambiguous.get_json()
    assert amb_data['status'] == 'needs_clarification'
    assert len(amb_data['clarifications']) > 0
