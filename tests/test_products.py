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

    # 3. List products (owner)
    res_list = client.get('/api/v1/products')
    assert res_list.status_code == 200
    assert len(res_list.get_json()) == 1

    # 4. Update product price as owner
    res_update = client.patch(f'/api/v1/products/{product_id}', json={"price": 150.00})
    assert res_update.status_code == 200
    assert res_update.get_json()['product']['price'] == 150.00

    # 5. Unauthenticated access is rejected
    client.post('/api/v1/auth/logout')
    res_unauth = client.get('/api/v1/products')
    assert res_unauth.status_code == 401

    # 6. Logged back in owner can access products again
    client.post('/api/v1/auth/login', json={"phone": "9999999991", "password": "pass"})
    res_auth = client.get('/api/v1/products')
    assert res_auth.status_code == 200

    # 7. Soft-delete product
    res_del = client.delete(f'/api/v1/products/{product_id}')
    assert res_del.status_code == 200

    # 8. Deleted product no longer appears in list
    res_after_del = client.get('/api/v1/products')
    assert len(res_after_del.get_json()) == 0
