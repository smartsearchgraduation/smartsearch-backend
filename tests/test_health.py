import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import patch


def test_health_db_reachable(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert 'database' in data


def test_health_db_unreachable(client):
    with patch('routes.health.db.session.execute') as mock_exec:
        mock_exec.side_effect = Exception('DB unavailable')
        response = client.get('/health')
        assert response.status_code == 503
        data = response.get_json()
        assert 'unhealthy' in data['database']
