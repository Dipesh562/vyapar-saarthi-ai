import pytest
import uuid
from app import create_app
from app.extensions import db

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

def test_billing_pipeline_and_idempotency(client):
    # 1. Onboard Owner & setup Product & Customer
    client.post('/api/v1/auth/register_owner', json={
        "store_name": "Test Kirana",
        "name": "Owner Test",
        "phone": "9111111111",
        "password": "pass"
    })

    # Create Product (Stock: 5 packets)
    res_p = client.post('/api/v1/products', json={
        "name": "Maggi Noodles 70g",
        "unit": "packet",
        "price": 14.00,
        "quantity_on_hand": 5.0
    })
    prod_id = res_p.get_json()['product']['product_id']

    # Create Customer
    res_c = client.post('/api/v1/customers', json={"name": "Rahul Customer", "phone": "9222222222"})
    cust_id = res_c.get_json()['customer']['customer_id']

    # 2. Create Draft Bill (2 packets Maggi)
    res_draft = client.post('/api/v1/billing/create', json={
        "customer_id": cust_id,
        "items": [{"product_id": prod_id, "quantity": 2.0}]
    })
    assert res_draft.status_code == 201
    draft_data = res_draft.get_json()
    assert draft_data['subtotal'] == 28.00
    draft_id = draft_data['draft_bill_id']

    # 3. Confirm Bill on Udhaar with Idempotency Key
    idempotency_key = str(uuid.uuid4())
    res_confirm = client.post('/api/v1/billing/confirm', json={
        "draft_bill_id": draft_id,
        "payment_status": "udhaar",
        "customer_id": cust_id,
        "idempotency_key": idempotency_key
    })
    assert res_confirm.status_code == 200
    conf_data = res_confirm.get_json()
    assert conf_data['total'] == 28.00
    assert conf_data['new_khata_balance'] == 28.00

    # 4. Verify Stock Deducted (5 -> 3)
    res_inv = client.get('/api/v1/inventory')
    assert res_inv.get_json()[0]['quantity_on_hand'] == 3.0

    # 5. Retry Confirm with SAME idempotency key -> Returns original result, no duplicate transaction
    res_retry = client.post('/api/v1/billing/confirm', json={
        "draft_bill_id": draft_id,
        "payment_status": "udhaar",
        "customer_id": cust_id,
        "idempotency_key": idempotency_key
    })
    assert res_retry.status_code == 200
    assert res_retry.get_json()['txn_id'] == conf_data['txn_id']

    # 6. Record Payment of 20 against Customer Udhaar
    res_pay = client.post('/api/v1/payments', json={
        "customer_id": cust_id,
        "amount": 20.00,
        "idempotency_key": str(uuid.uuid4())
    })
    assert res_pay.status_code == 200
    assert res_pay.get_json()['new_balance'] == 8.00  # (28 - 20)

    # 7. Check Khata history
    res_khata = client.get(f'/api/v1/customers/{cust_id}/khata')
    assert res_khata.get_json()['balance'] == 8.00
    assert len(res_khata.get_json()['entries']) == 2

def test_empty_bill_rejection(client):
    client.post('/api/v1/auth/register_owner', json={
        "store_name": "Test Kirana 2",
        "name": "Owner 2",
        "phone": "9222222333",
        "password": "pass"
    })
    res = client.post('/api/v1/billing/create', json={"items": []})
    assert res.status_code == 400

def test_receipt_auth_idor(client):
    # Register store 1 and create a bill
    client.post('/api/v1/auth/register_owner', json={
        "store_name": "Store 1",
        "name": "Owner 1",
        "phone": "9333333333",
        "password": "pass"
    })
    res_p = client.post('/api/v1/products', json={"name": "Item 1", "unit": "packet", "price": 10.0, "quantity_on_hand": 10.0})
    pid = res_p.get_json()['product']['product_id']
    res_d = client.post('/api/v1/billing/create', json={"items": [{"product_id": pid, "quantity": 1}]})
    did = res_d.get_json()['draft_bill_id']
    res_c = client.post('/api/v1/billing/confirm', json={"draft_bill_id": did, "payment_status": "paid", "idempotency_key": str(uuid.uuid4())})
    txn_id = res_c.get_json()['txn_id']

    # Logout
    client.post('/api/v1/auth/logout')

    # Unauthenticated access to receipt view should be rejected (401)
    res_unauth = client.get(f'/api/v1/receipts/{txn_id}/view')
    assert res_unauth.status_code == 401
