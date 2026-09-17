import pytest
from app import create_app
from app.extensions import db
from app.models import Store, User

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

def test_owner_registration_and_login(client):
    # 1. Register owner
    res = client.post('/api/v1/auth/register_owner', json={
        "store_name": "Karvenagar Kirana",
        "name": "Ramesh Owner",
        "phone": "9876543210",
        "password": "password123"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data['user']['role'] == 'owner'
    assert data['user']['store_name'] == 'Karvenagar Kirana'

    # 2. Check /auth/me
    res_me = client.get('/api/v1/auth/me')
    assert res_me.status_code == 200
    assert res_me.get_json()['user']['name'] == 'Ramesh Owner'

    # 3. Logout
    client.post('/api/v1/auth/logout')
    res_me2 = client.get('/api/v1/auth/me')
    assert res_me2.status_code == 401

    # 4. Login
    res_login = client.post('/api/v1/auth/login', json={
        "phone": "9876543210",
        "password": "password123"
    })
    assert res_login.status_code == 200

def test_helper_registration_and_role_matrix(client):
    # Register Owner
    client.post('/api/v1/auth/register_owner', json={
        "store_name": "Store A",
        "name": "Owner A",
        "phone": "9000000001",
        "password": "pass"
    })

    # Owner registers Helper
    res_helper_reg = client.post('/api/v1/auth/register_helper', json={
        "name": "Helper A",
        "phone": "9000000002",
        "password": "pass"
    })
    assert res_helper_reg.status_code == 201
    assert res_helper_reg.get_json()['user']['role'] == 'helper'

    # Logout Owner and Login as Helper
    client.post('/api/v1/auth/logout')
    client.post('/api/v1/auth/login', json={
        "phone": "9000000002",
        "password": "pass"
    })

    # Helper tries to register another helper (owner-only action) -> expect 403 FORBIDDEN_ROLE
    res_forbidden = client.post('/api/v1/auth/register_helper', json={
        "name": "Helper B",
        "phone": "9000000003",
        "password": "pass"
    })
    assert res_forbidden.status_code == 403
    assert res_forbidden.get_json()['error']['code'] == 'FORBIDDEN_ROLE'
