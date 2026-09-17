import pytest
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

def test_business_assistant_and_alerts(client):
    # 1. Onboard Owner
    client.post('/api/v1/auth/register_owner', json={
        "store_name": "Karvenagar Store",
        "name": "Owner K",
        "phone": "9777777777",
        "password": "pass"
    })

    # Add Low Stock Product (1 packet available, threshold 5)
    client.post('/api/v1/products', json={
        "name": "Tata Salt 1kg",
        "unit": "packet",
        "price": 28.00,
        "quantity_on_hand": 1.0,
        "low_stock_threshold": 5.0
    })

    # Create Customer with Udhaar
    res_c = client.post('/api/v1/customers', json={"name": "Suresh Customer", "phone": "9666666666"})
    cust_id = res_c.get_json()['customer']['customer_id']

    # Record credit entry
    from app.services.khata_engine import KhataEngine
    with client.application.app_context():
        KhataEngine.add_credit_entry(cust_id, 1, 1, 150.00)
        db.session.commit()

    # 2. Test Assistant Query: Today Sales
    res_q1 = client.post('/api/v1/assistant/query', json={"question": "aaj ka total sale kitna hua?"})
    assert res_q1.status_code == 200
    assert "₹0.00" in res_q1.get_json()['answer_text']

    # 3. Test Assistant Query: Low Stock
    res_q2 = client.post('/api/v1/assistant/query', json={"question": "konsa item kam stock par hai?"})
    assert res_q2.status_code == 200
    assert "Tata Salt 1kg" in res_q2.get_json()['answer_text']

    # 4. Test Dashboard Alerts (/api/v1/alerts)
    res_alerts = client.get('/api/v1/alerts')
    assert res_alerts.status_code == 200
    alerts_data = res_alerts.get_json()
    assert len(alerts_data['low_stock_alerts']) == 1
    assert alerts_data['low_stock_alerts'][0]['name'] == "Tata Salt 1kg"
    assert len(alerts_data['udhaar_alerts']) == 1
    assert alerts_data['udhaar_alerts'][0]['name'] == "Suresh Customer"
