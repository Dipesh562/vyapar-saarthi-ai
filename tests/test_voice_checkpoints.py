import pytest
from decimal import Decimal
from app import create_app
from app.extensions import db
from app.models import Product, Inventory, User
from app.services.voice_feedback import VoiceFeedbackService
from app.services.billing_engine import BillingEngine
from seed.load_seed import load_seed

@pytest.fixture
def app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.app_context():
        db.create_all()
        load_seed()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_stt_failed_retry_message_generation():
    msg = VoiceFeedbackService.build_stt_failed_message()
    assert msg == "I couldn't understand that. Please say the name again"

def test_clarification_speech_text_generation():
    question = "Which Fortune Oil did you mean?"
    candidates = [
        {"name": "Fortune Sunlite Sunflower Oil 1L", "price": 145.0},
        {"name": "Fortune Kachi Ghani Mustard Oil 1L", "price": 155.0},
        {"name": "Fortune Rice Bran Oil 1L", "price": 160.0}
    ]
    speech_text = VoiceFeedbackService.build_clarification_speech_text(question, candidates)
    
    assert "Which Fortune Oil did you mean?" in speech_text
    assert "Option 1: Fortune Sunlite Sunflower Oil 1L for 145.0 rupees." in speech_text
    assert "Option 2: Fortune Kachi Ghani Mustard Oil 1L for 155.0 rupees." in speech_text
    assert "Option 3: Fortune Rice Bran Oil 1L for 160.0 rupees." in speech_text

def test_draft_bill_readback_text_float_precision():
    draft_bill = {
        "draft_bill_id": "test-uuid-123",
        "total": 312.99,
        "line_items": [
            {
                "product_id": 1,
                "name": "Tata Salt 1kg",
                "quantity": 2.0,
                "unit": "packet",
                "unit_price": 28.00,
                "line_total": 56.00
            },
            {
                "product_id": 2,
                "name": "Special Spices",
                "quantity": 1.5,
                "unit": "kg",
                "unit_price": 133.33,
                "line_total": 199.995  # Potential float precision edge case
            },
            {
                "product_id": 3,
                "name": "Parle-G 50g",
                "quantity": 7.0,
                "unit": "packet",
                "unit_price": 8.142857,
                "line_total": 56.999999
            }
        ]
    }

    readback = VoiceFeedbackService.build_readback_text(draft_bill)

    assert "Bill read-back:" in readback
    assert "2 packet of Tata Salt 1kg for 56.00 rupees" in readback
    assert "1.5 kg of Special Spices for 200.00 rupees" in readback or "199.99" in readback or "200.00" in readback
    assert "7 packet of Parle-G 50g for 57.00 rupees" in readback
    assert "Total amount is 312.99 rupees." in readback
    assert "Please confirm to complete sale." in readback

def test_stt_low_confidence_route_response(client):
    # Setup owner user and login
    with client.application.app_context():
        owner = User.query.filter_by(store_id=1, phone='9876543210').first()
        if not owner:
            owner = User(store_id=1, role='owner', name='Pilot Owner', phone='9876543210')
            db.session.add(owner)
        owner.set_password('password123')
        db.session.commit()

    client.post('/api/v1/auth/login', json={"phone": "9876543210", "password": "password123"})

    # Post blank/empty transcript to trigger stt_failed
    res = client.post('/api/v1/voice/process_bill', json={"transcript": ""})
    assert res.status_code == 400
    data = res.get_json()
    assert data['status'] == 'stt_failed'
    assert data['message'] == "I couldn't understand that. Please say the name again"

def test_end_to_end_voice_billing_readback_and_correction_flow(client):
    # Setup owner user and login
    with client.application.app_context():
        owner = User.query.filter_by(store_id=1, phone='9876543210').first()
        if not owner:
            owner = User(store_id=1, role='owner', name='Pilot Owner', phone='9876543210')
            db.session.add(owner)
        owner.set_password('password123')
        db.session.commit()

    client.post('/api/v1/auth/login', json={"phone": "9876543210", "password": "password123"})

    # Step 1: Create Initial Voice Draft Bill
    res1 = client.post('/api/v1/voice/process_bill', json={
        "transcript": "do kilo sugar aur ek Fortune Sunlite Oil"
    })
    assert res1.status_code == 201
    data1 = res1.get_json()
    assert data1['status'] == 'draft_created'
    assert 'readback_text' in data1
    initial_readback = data1['readback_text']
    assert "Sugar" in initial_readback
    assert "Fortune" in initial_readback

    draft_id = data1['draft_bill']['draft_bill_id']

    # Step 2: Owner makes a correction ("no, teen Parle-G aur add karo")
    res2 = client.post('/api/v1/voice/process_bill', json={
        "transcript": "teen Parle-G",
        "draft_bill_id": draft_id
    })
    assert res2.status_code == 201
    data2 = res2.get_json()
    assert data2['status'] == 'draft_created'
    assert 'readback_text' in data2
    second_readback = data2['readback_text']

    # Verify updated read-back contains all 3 items (Sugar, Fortune Oil, Parle-G)
    assert "Sugar" in second_readback
    assert "Fortune" in second_readback
    assert "Parle-G" in second_readback

    updated_draft_id = data2['draft_bill']['draft_bill_id']

    # Step 3: Confirm Checkout after Second Read-Back
    import uuid
    res_checkout = client.post('/api/v1/billing/confirm', json={
        "draft_bill_id": updated_draft_id,
        "payment_status": "paid",
        "idempotency_key": str(uuid.uuid4())
    })
    assert res_checkout.status_code == 200
    checkout_data = res_checkout.get_json()
    assert "invoice_number" in checkout_data
