import pytest
from datetime import datetime, timedelta, timezone
from app import create_app
from app.extensions import db
from app.models import Product, Transaction, TransactionItem, Inventory

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

def test_sales_queries_comprehensive(client):
    # 1. Register Owner
    reg_res = client.post('/api/v1/auth/register_owner', json={
        "store_name": "Ganesh Kirana Stores",
        "name": "Owner Ramesh",
        "phone": "9888888888",
        "password": "password123"
    })
    assert reg_res.status_code == 201

    # 2. Create Products
    res_p1 = client.post('/api/v1/products', json={
        "name": "Maggi 2-Minute Noodles",
        "unit": "packet",
        "price": 14.00,
        "quantity_on_hand": 50.0
    })
    maggi_id = res_p1.get_json()['product']['product_id']

    res_p2 = client.post('/api/v1/products', json={
        "name": "Fortune Sunlite Sunflower Oil 1L",
        "unit": "litre",
        "price": 140.00,
        "quantity_on_hand": 25.0
    })
    oil_id = res_p2.get_json()['product']['product_id']

    res_p3 = client.post('/api/v1/products', json={
        "name": "Tata Salt 1kg",
        "unit": "packet",
        "price": 28.00,
        "quantity_on_hand": 30.0
    })
    salt_id = res_p3.get_json()['product']['product_id']

    # 3. Insert Historical and Today Transactions
    now_utc = datetime.now(timezone.utc)
    yesterday_utc = now_utc - timedelta(days=1)
    three_days_ago_utc = now_utc - timedelta(days=3)

    with client.application.app_context():
        # Transaction 1 (Today): 5 Maggi + 1 Oil = (5*14) + 140 = 70 + 140 = 210
        t1 = Transaction(
            store_id=1,
            total=210.00,
            payment_status='paid',
            invoice_number='INV-TODAY-001',
            created_by_user_id=1,
            created_at=now_utc
        )
        db.session.add(t1)
        db.session.flush()

        ti1_1 = TransactionItem(txn_id=t1.txn_id, product_id=maggi_id, quantity=5.0, unit_price=14.0, line_total=70.0)
        ti1_2 = TransactionItem(txn_id=t1.txn_id, product_id=oil_id, quantity=1.0, unit_price=140.0, line_total=140.0)
        db.session.add_all([ti1_1, ti1_2])

        # Transaction 2 (Today): 3 Maggi + 2 Salt = (3*14) + (2*28) = 42 + 56 = 98
        t2 = Transaction(
            store_id=1,
            total=98.00,
            payment_status='paid',
            invoice_number='INV-TODAY-002',
            created_by_user_id=1,
            created_at=now_utc
        )
        db.session.add(t2)
        db.session.flush()

        ti2_1 = TransactionItem(txn_id=t2.txn_id, product_id=maggi_id, quantity=3.0, unit_price=14.0, line_total=42.0)
        ti2_2 = TransactionItem(txn_id=t2.txn_id, product_id=salt_id, quantity=2.0, unit_price=28.0, line_total=56.0)
        db.session.add_all([ti2_1, ti2_2])

        # Transaction 3 (Yesterday): 1 Oil = 140
        t3 = Transaction(
            store_id=1,
            total=140.00,
            payment_status='paid',
            invoice_number='INV-YEST-001',
            created_by_user_id=1,
            created_at=yesterday_utc
        )
        db.session.add(t3)
        db.session.flush()

        ti3_1 = TransactionItem(txn_id=t3.txn_id, product_id=oil_id, quantity=1.0, unit_price=140.0, line_total=140.0)
        db.session.add(ti3_1)

        # Transaction 4 (3 days ago): 2 Maggi = 28
        t4 = Transaction(
            store_id=1,
            total=28.00,
            payment_status='paid',
            invoice_number='INV-WEEK-001',
            created_by_user_id=1,
            created_at=three_days_ago_utc
        )
        db.session.add(t4)
        db.session.flush()

        ti4_1 = TransactionItem(txn_id=t4.txn_id, product_id=maggi_id, quantity=2.0, unit_price=14.0, line_total=28.0)
        db.session.add(ti4_1)

        db.session.commit()

    # Total today = 210 + 98 = 308 (2 bills)
    # Total yesterday = 140 (1 bill)
    # Total week = 308 + 140 + 28 = 476 (4 bills)

    # ── Test 1: Today's Total Sales in Marathi ──
    res = client.post('/api/v1/assistant/query', json={"question": "Aaj kiti sale zali?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "₹308.00" in ans
    assert "2 बिल्स" in ans
    assert "विक्री झाली" in ans

    # ── Test 2: Today's Total Sales in Hindi ──
    res = client.post('/api/v1/assistant/query', json={"question": "Aaj ka total sale kitna hua?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "₹308.00" in ans
    assert "2 बिल्स" in ans
    assert "बिक्री हुई" in ans

    # ── Test 3: Today's Total Sales in English (via language parameter) ──
    res = client.post('/api/v1/assistant/query', json={"question": "How much did I sell today?", "language": "en-IN"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "₹308.00" in ans
    assert "2 transactions" in ans

    # ── Test 4: Yesterday's Sales in Marathi ──
    res = client.post('/api/v1/assistant/query', json={"question": "Kal kiti sales zali?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "₹140.00" in ans
    assert "1 बिल्स" in ans
    assert "काल" in ans

    # ── Test 5: Last 7 Days' Sales in Marathi ──
    res = client.post('/api/v1/assistant/query', json={"question": "Ya week madhe kiti sale zali?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "₹476.00" in ans
    assert "4 बिल्स" in ans

    # ── Test 6: Number of Bills Today in Marathi ──
    res = client.post('/api/v1/assistant/query', json={"question": "Aaj kiti bills banle?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "2 बिल्स बनले" in ans

    # ── Test 7: Average Bill Value in Marathi ──
    res = client.post('/api/v1/assistant/query', json={"question": "Aajcha average bill kiti aahe?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    # 308 / 2 = 154.00
    assert "₹154.00" in ans
    assert "सरासरी बिल" in ans

    # ── Test 8: Best-Selling Product ──
    # Overall Maggi has 5 + 3 + 2 = 10 units sold
    res = client.post('/api/v1/assistant/query', json={"question": "Sagleat jast konta product vikla?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "Maggi 2-Minute Noodles" in ans
    assert "10 packet" in ans

    # ── Test 9: Specific Product Sales (Maggi in Marathi) ──
    # Overall Maggi = 10 packets, ₹140 total
    res = client.post('/api/v1/assistant/query', json={"question": "Maggi kiti vikli?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "Maggi 2-Minute Noodles" in ans
    assert "10 packet" in ans
    assert "₹140.00" in ans

    # ── Test 10: Product in Time Range (Last 7 days Maggi) ──
    res = client.post('/api/v1/assistant/query', json={"question": "Last 7 days madhye Maggi kiti vikli?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "Maggi 2-Minute Noodles" in ans
    assert "10 packet" in ans

    # ── Test 11: Product Not Found in Store ──
    res = client.post('/api/v1/assistant/query', json={"question": "iPhone kiti vikla?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "सापडले नाही" in ans or "nahi mila" in ans

    # ── Test 12: "Aajchi total sale kiti aahe?" ──
    res = client.post('/api/v1/assistant/query', json={"question": "Aajchi total sale kiti aahe?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "₹308.00" in ans
    assert "2 बिल्स" in ans

    # ── Test 13: "Aaj konta product saglyat jast vikla?" ──
    res = client.post('/api/v1/assistant/query', json={"question": "Aaj konta product saglyat jast vikla?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "Maggi 2-Minute Noodles" in ans
    assert "8 packet" in ans  # 5 + 3 = 8 packets today

    # ── Test 14: "Aaj Maggi kiti vikli?" ──
    res = client.post('/api/v1/assistant/query', json={"question": "Aaj Maggi kiti vikli?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "Maggi 2-Minute Noodles" in ans
    assert "8 packet" in ans
    assert "₹112.00" in ans

    # ── Test 15: "Aaj kiti paise ale?" ──
    res = client.post('/api/v1/assistant/query', json={"question": "Aaj kiti paise ale?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "₹308.00" in ans

    # ── Test 16: "Aajchi sale sang" ──
    res = client.post('/api/v1/assistant/query', json={"question": "Aajchi sale sang"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "₹308.00" in ans

    # ── Test 17: "Ya mahinyat kiti sale zali?" ──
    res = client.post('/api/v1/assistant/query', json={"question": "Ya mahinyat kiti sale zali?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "₹476.00" in ans

    # ── Test 18: Hindi queries ──
    # Bill count in Hindi
    res = client.post('/api/v1/assistant/query', json={"question": "Aaj kitne bill bane?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "2 बिल्स" in ans

    # Avg bill in Hindi
    res = client.post('/api/v1/assistant/query', json={"question": "Average bill kitna hai?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "₹154.00" in ans

    # Top product in Hindi
    res = client.post('/api/v1/assistant/query', json={"question": "Sabse jyada kya bika?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "Maggi 2-Minute Noodles" in ans

    # Specific product in Hindi
    res = client.post('/api/v1/assistant/query', json={"question": "Fortune oil kitna bika?"})
    assert res.status_code == 200
    ans = res.get_json()['answer_text']
    assert "Fortune Sunlite Sunflower Oil 1L" in ans
    assert "2 litre" in ans

