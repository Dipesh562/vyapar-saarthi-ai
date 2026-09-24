import pytest
from app import create_app
from app.extensions import db
from app.models import Store, User, OwnerStore

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
    assert data['store']['name'] == 'Karvenagar Kirana'

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

def test_multi_store_owner_workflow(client):
    """
    Tests the full multi-store owner flow:
    register -> add a second store -> switch between stores -> verify isolation.
    """
    # 1. Register owner (gets store A automatically)
    res = client.post('/api/v1/auth/register_owner', json={
        "store_name": "Store A",
        "name": "Owner A",
        "phone": "9000000001",
        "password": "pass"
    })
    assert res.status_code == 201
    store_a_id = res.get_json()['store']['store_id']

    # 2. List my_stores — should have 1 store
    res_my = client.get('/api/v1/auth/my_stores')
    assert res_my.status_code == 200
    data = res_my.get_json()
    assert data['total'] == 1
    assert data['owned_stores'][0]['is_primary'] is True

    # 3. Add a second store
    res_add = client.post('/api/v1/auth/add_store', json={
        "store_name": "Store B"
    })
    assert res_add.status_code == 201
    store_b_id = res_add.get_json()['store']['store_id']
    assert res_add.get_json()['active_store_id'] == store_b_id

    # 4. Verify /my_stores now shows 2 stores
    res_my2 = client.get('/api/v1/auth/my_stores')
    assert res_my2.get_json()['total'] == 2

    # 5. Switch back to Store A
    res_switch = client.post('/api/v1/auth/switch_store', json={"store_id": store_a_id})
    assert res_switch.status_code == 200
    assert res_switch.get_json()['active_store_id'] == store_a_id

    # 6. Verify /me returns Store A as active
    res_me = client.get('/api/v1/auth/me')
    assert res_me.get_json()['user']['active_store_id'] == store_a_id

    # 7. Try to switch to a non-existent store → should get 403
    res_bad = client.post('/api/v1/auth/switch_store', json={"store_id": 9999})
    assert res_bad.status_code == 403

def test_register_helper_returns_not_implemented(client):
    """Helper registration is out of scope — should return 501."""
    # Register and login as owner first
    client.post('/api/v1/auth/register_owner', json={
        "store_name": "Store A",
        "name": "Owner A",
        "phone": "9000000001",
        "password": "pass"
    })

    res = client.post('/api/v1/auth/register_helper', json={
        "name": "Helper A",
        "phone": "9000000002",
        "password": "pass"
    })
    assert res.status_code == 501
    assert res.get_json()['error']['code'] == 'NOT_IMPLEMENTED'


def test_delete_store_workflow(client):
    """
    Tests deleting a secondary store:
    - Cannot delete primary store.
    - Successfully soft-deletes a secondary store.
    - Cannot delete the last remaining active store.
    """
    # 1. Register owner (Primary Store A)
    res = client.post('/api/v1/auth/register_owner', json={
        "store_name": "Primary Store A",
        "name": "Owner A",
        "phone": "9000000099",
        "password": "pass"
    })
    store_a_id = res.get_json()['store']['store_id']

    # 2. Add Secondary Store B
    res_b = client.post('/api/v1/stores', json={"name": "Secondary Store B"})
    assert res_b.status_code == 201
    store_b_id = res_b.get_json()['store']['store_id']

    # 3. Attempt to delete primary store -> 400
    res_del_pri = client.delete(f'/api/v1/stores/{store_a_id}')
    assert res_del_pri.status_code == 400
    assert res_del_pri.get_json()['error']['code'] == 'CANNOT_DELETE_PRIMARY'

    # 4. Delete secondary store B -> 200
    res_del_b = client.delete(f'/api/v1/stores/{store_b_id}')
    assert res_del_b.status_code == 200

    # 5. List stores -> Store B should not be present
    res_list = client.get('/api/v1/stores')
    store_ids = [s['store_id'] for s in res_list.get_json()['stores']]
    assert store_b_id not in store_ids
    assert store_a_id in store_ids

    # 6. Attempt to delete last remaining active store -> 400
    res_del_last = client.delete(f'/api/v1/stores/{store_a_id}')
    assert res_del_last.status_code == 400
    assert res_del_last.get_json()['error']['code'] == 'CANNOT_DELETE_PRIMARY'
