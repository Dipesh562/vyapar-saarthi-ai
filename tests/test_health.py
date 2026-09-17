import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.test_client() as client:
        yield client

def test_health_check(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert data['service'] == 'Vyapar Saarthi AI API'

def test_index_page(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Vyapar Saarthi" in response.data
