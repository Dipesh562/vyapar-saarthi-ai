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

def test_product_crud_and_role_permissions(client):
    # 1. Onboard Owner
    client.post('/api/v1/auth/register_owner', json={
        "store_name": "Kirana A",
        "name": "Owner A",
        "phone": "9999999991",
        "password": "pass"
    })

    # 2. Create product as owner
    res_prod = client.post('/api/v1/products', json={
        "name": "Fortune Sunflower Oil 1L",
        "unit": "packet",
        "price": 145.00,
        "category": "Oil",
        "brand": "Fortune",
        "quantity_on_hand": 10.0,
        "low_stock_threshold": 2.0
    })
    assert res_prod.status_code == 201
    prod_data = res_prod.get_json()['product']
    assert prod_data['name'] == "Fortune Sunflower Oil 1L"
    assert prod_data['normalized_name'] == "fortune sunflower oil 1l"
    assert prod_data['quantity_on_hand'] == 10.0

    product_id = prod_data['product_id']

    # 3. List products
    res_list = client.get('/api/v1/products')
    assert res_list.status_code == 200
    assert len(res_list.get_json()) == 1

    # 4. Owner registers helper and logs in as helper
    client.post('/api/v1/auth/register_helper', json={
        "name": "Helper A",
        "phone": "9999999992",
        "password": "pass"
    })
    client.post('/api/v1/auth/logout')
    client.post('/api/v1/auth/login', json={"phone": "9999999992", "password": "pass"})

    # 5. Helper CAN list products
    res_helper_list = client.get('/api/v1/products')
    assert res_helper_list.status_code == 200

    # 6. Helper CANNOT edit product price -> 403 FORBIDDEN_ROLE
    res_edit_forbidden = client.patch(f'/api/v1/products/{product_id}', json={"price": 130.00})
    assert res_edit_forbidden.status_code == 403
