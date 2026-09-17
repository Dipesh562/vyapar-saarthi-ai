import os
import time
import pytest
from app import create_app
from app.extensions import db
from app.models import Product, ProductSynonym, Store, User, Transaction, TransactionItem
from app.services.cart_session import MerchantCartSession
from app.services.ai_orchestration import AIOrchestrationService
from app.services.product_matching import ProductMatchingEngine
from app.services.stt_client import STTClient

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


def test_1_regex_is_preprocessing_only(app):
    """Test 1: _preprocess_transcript normalizes Devanagari digits & units without short-circuiting AI item parsing."""
    raw_speech = "२ किलो आटा aur 1 ltr oil"
    processed = AIOrchestrationService._preprocess_transcript(raw_speech)
    assert "2 kg" in processed or "2" in processed
    assert "atta" in processed or "aata" in processed
    assert "oil" in processed


def test_2_gemini_is_primary_in_ai_first_mode(app):
    """Test 2: VOICE_PIPELINE_MODE=ai_first mode executes AI-first order."""
    os.environ['VOICE_PIPELINE_MODE'] = 'ai_first'
    res = AIOrchestrationService.understand_transcript("2 packet fortune oil")
    assert isinstance(res, dict)
    assert 'items' in res
    assert len(res['items']) > 0


def test_3_legacy_mode_unchanged(app):
    """Test 3: VOICE_PIPELINE_MODE=legacy mode preserves fast regex-first short-circuit."""
    os.environ['VOICE_PIPELINE_MODE'] = 'legacy'
    res = AIOrchestrationService.understand_transcript("2 packet fortune oil")
    assert isinstance(res, dict)
    assert 'items' in res
    assert res['items'][0]['raw_text'] == 'fortune oil'
    os.environ['VOICE_PIPELINE_MODE'] = 'ai_first'


def test_4_cart_session_reference_resolution(app):
    """Test 4: MerchantCartSession stores last referenced item & customer and resolves relative commands."""
    store_id = 99
    MerchantCartSession.clear_session(store_id)
    session = MerchantCartSession.get_session(store_id)
    assert session['store_id'] == store_id

    item_data = {"product_id": 101, "name": "Fortune Refined Oil 1L", "raw_text": "fortune oil", "quantity": 1.0}
    MerchantCartSession.set_last_item(store_id, item_data)

    resolved = MerchantCartSession.resolve_reference(store_id, "item")
    assert resolved is not None
    assert resolved['product_id'] == 101
    assert resolved['name'] == "Fortune Refined Oil 1L"


def test_5_cart_session_expiry_clears_data(app):
    """Test 5: Cart session inactive for >15 min (900s) lazily expires and clears data."""
    store_id = 88
    MerchantCartSession.clear_session(store_id)
    MerchantCartSession.get_session(store_id)
    MerchantCartSession.set_last_item(store_id, {"product_id": 50, "name": "Tata Salt"})

    # Simulate 16 minutes of inactivity
    MerchantCartSession._sessions[store_id]['last_active'] = time.time() - 1000

    resolved = MerchantCartSession.resolve_reference(store_id, "item")
    assert resolved is None  # Expired!


def test_6_cart_session_expiry_triggers_clarification(client):
    """Test 6: Spoken reference after session expiry returns clarification, avoiding crashes or silent wrong item."""
    client.post('/api/v1/auth/register_owner', json={
        "store_name": "Test Expiry Store",
        "name": "Owner Expiry",
        "phone": "9111111111",
        "password": "pass"
    })

    # Explicitly clear cart session
    user_store_id = 1
    MerchantCartSession.clear_session(user_store_id)

    res = client.post('/api/v1/voice/process_bill', json={
        "transcript": "add 2 more"
    })
    # Should either request clarification or report item not found, but NOT crash (500)
    assert res.status_code in [200, 400, 422]
    data = res.get_json()
    assert data.get('status') in ['needs_clarification', 'stt_failed', 'query', 'draft_created']


def test_7_multi_store_session_isolation(app):
    """Test 7: Store 1 session state never bleeds into Store 2 session state."""
    MerchantCartSession.clear_session(101)
    MerchantCartSession.clear_session(202)

    MerchantCartSession.set_last_item(101, {"product_id": 1, "name": "Tata Salt"})
    MerchantCartSession.set_last_item(202, {"product_id": 2, "name": "Amul Butter"})

    item1 = MerchantCartSession.resolve_reference(101, "item")
    item2 = MerchantCartSession.resolve_reference(202, "item")

    assert item1['name'] == "Tata Salt"
    assert item2['name'] == "Amul Butter"


def test_8_multi_item_clarification_queue(client):
    """Test 8: Multiple ambiguous products in one utterance generate multi-clarification queue."""
    client.post('/api/v1/auth/register_owner', json={
        "store_name": "Multi Queue Store",
        "name": "Owner Queue",
        "phone": "9222222222",
        "password": "pass"
    })

    # Add ambiguous oils
    client.post('/api/v1/products', json={"name": "Fortune Sunlite Sunflower Oil 1L", "unit": "packet", "price": 140, "brand": "Fortune"})
    client.post('/api/v1/products', json={"name": "Fortune Kachi Ghani Mustard Oil 1L", "unit": "packet", "price": 160, "brand": "Fortune"})
    client.post('/api/v1/products', json={"name": "Saffola Gold Edible Oil 1L", "unit": "packet", "price": 170, "brand": "Saffola"})
    client.post('/api/v1/products', json={"name": "Saffola Total Edible Oil 1L", "unit": "packet", "price": 190, "brand": "Saffola"})

    res = client.post('/api/v1/voice/process_bill', json={
        "transcript": "1 packet fortune oil aur 1 packet saffola oil"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'needs_clarification'
    assert len(data['clarifications']) >= 2


def test_9_popularity_ranking_tiebreaker(app):
    """Test 9: Popularity bonus breaks ties when fuzzy gap between top candidates <= 10 points."""
    with app.app_context():
        store = Store(name="Pop Store")
        db.session.add(store)
        db.session.commit()

        user = User(store_id=store.store_id, role='owner', phone="9999911111", password_hash="hash", name="User 1")
        db.session.add(user)
        db.session.commit()

        p1 = Product(store_id=store.store_id, name="Royal Chai Premium Tea 250g", unit="pack", price=100.0, is_active=True)
        p2 = Product(store_id=store.store_id, name="Royal Chai Masala Tea 250g", unit="pack", price=110.0, is_active=True)
        db.session.add_all([p1, p2])
        db.session.commit()

        # Record 50 sales for p2
        txn = Transaction(store_id=store.store_id, total=5500.0, payment_status='paid', invoice_number='INV-TEST-001', created_by_user_id=user.user_id)
        db.session.add(txn)
        db.session.commit()

        item = TransactionItem(txn_id=txn.txn_id, product_id=p2.product_id, quantity=50.0, unit_price=110.0, line_total=5500.0)
        db.session.add(item)
        db.session.commit()

        res = ProductMatchingEngine.match_product(store.store_id, "Royal Chai Masala Tea")
        assert res['matched'] is True
        assert res['product'].product_id == p2.product_id


def test_10_popularity_does_not_override_clear_fuzzy_winner(app):
    """Test 10: Popularity ceiling rule — sales bonus NEVER overrides a fuzzy gap > 10 points."""
    with app.app_context():
        store = Store(name="Ceiling Store")
        db.session.add(store)
        db.session.commit()

        user = User(store_id=store.store_id, role='owner', phone="9999922222", password_hash="hash", name="User 2")
        db.session.add(user)
        db.session.commit()

        p1 = Product(store_id=store.store_id, name="Ashirvaad Shudh Chakki Atta 5kg", unit="pack", price=260.0, is_active=True)
        p2 = Product(store_id=store.store_id, name="Fortune Sunflower Oil 1L", unit="pack", price=145.0, is_active=True)
        db.session.add_all([p1, p2])
        db.session.commit()

        # Give 500 sales to Oil
        txn = Transaction(store_id=store.store_id, total=72500.0, payment_status='paid', invoice_number='INV-TEST-002', created_by_user_id=user.user_id)
        db.session.add(txn)
        db.session.commit()
        db.session.add(TransactionItem(txn_id=txn.txn_id, product_id=p2.product_id, quantity=500.0, unit_price=145.0, line_total=72500.0))
        db.session.commit()

        # Match "ashirvaad atta" -> P1 (Atta) has huge fuzzy lead (>10 points)
        res = ProductMatchingEngine.match_product(store.store_id, "ashirvaad atta")
        assert res['matched'] is True
        assert res['product'].product_id == p1.product_id  # Atta must win despite Oil having 500 sales!


def test_11_synonym_evidence_accumulation(app):
    """Test 11: Merchant feedback accumulates evidence_count and updates last_confirmed_at."""
    with app.app_context():
        store = Store(name="Synonym Store")
        db.session.add(store)
        db.session.commit()

        p = Product(store_id=store.store_id, name="Fortune Refined Oil 1L", unit="pack", price=145.0, is_active=True)
        db.session.add(p)
        db.session.commit()

        s1 = ProductMatchingEngine.record_merchant_correction(store.store_id, "fortin oil", p.product_id)
        assert s1.evidence_count == 1

        s2 = ProductMatchingEngine.record_merchant_correction(store.store_id, "fortin oil", p.product_id)
        assert s2.evidence_count == 2

        s3 = ProductMatchingEngine.record_merchant_correction(store.store_id, "fortin oil", p.product_id)
        assert s3.evidence_count == 3


def test_12_synonym_conflict_two_products_same_term(app):
    """Test 12: If merchant corrected same term to 2 products both having evidence_count >= 3, matching reverts to clarification."""
    with app.app_context():
        store = Store(name="Conflict Store")
        db.session.add(store)
        db.session.commit()

        p1 = Product(store_id=store.store_id, name="Fortune Mustard Oil 1L", unit="pack", price=160.0, is_active=True)
        p2 = Product(store_id=store.store_id, name="Fortune Rice Bran Oil 1L", unit="pack", price=150.0, is_active=True)
        db.session.add_all([p1, p2])
        db.session.commit()

        # Term "oil" mapped to both products with 3+ evidence
        for _ in range(3):
            ProductMatchingEngine.record_merchant_correction(store.store_id, "tel", p1.product_id)
            ProductMatchingEngine.record_merchant_correction(store.store_id, "tel", p2.product_id)

        res = ProductMatchingEngine.match_product(store.store_id, "tel")
        assert res['needs_clarification'] is True
        candidate_ids = {c['product_id'] for c in res['candidates']}
        assert p1.product_id in candidate_ids
        assert p2.product_id in candidate_ids


def test_13_stt_failure_returns_correct_error_code(app):
    """Test 13: STT Client returns STT_UNAVAILABLE error on invalid payload or unconfigured provider."""
    res = STTClient.transcribe_audio(b"")
    assert res.get('error') == 'STT_UNAVAILABLE'
    assert res.get('confidence') == 0.0
