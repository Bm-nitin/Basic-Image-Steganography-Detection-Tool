import os
from io import BytesIO
import pytest
from app import create_app

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), 'test_samples')

@pytest.fixture
def app():
    app = create_app('testing')
    app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False
    })
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def clean_image_file():
    path = os.path.join(SAMPLE_DIR, 'clean_sample.png')
    with open(path, 'rb') as f:
        return BytesIO(f.read()), 'clean_sample.png'


class TestRoutes:
    def test_index_route(self, client):
        response = client.get('/')
        assert response.status_code == 200
        assert b'Basic Image Steganography Detection Tool' in response.data
        assert b'Drag &amp; Drop Carrier Image Here' in response.data

    def test_health_route(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['status'] == 'healthy'

    def test_analyze_without_file(self, client):
        response = client.post('/analyze', data={}, follow_redirects=True)
        assert response.status_code == 200
        assert b'No image file selected' in response.data

    def test_analyze_invalid_extension(self, client):
        data = {
            'image': (BytesIO(b'malicious content'), 'test.exe')
        }
        response = client.post('/analyze', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        assert b'Unsupported file extension' in response.data

    def test_analyze_spoofed_magic_bytes(self, client):
        # Named .png, but content is text/binary garbage
        data = {
            'image': (BytesIO(b'THIS_IS_NOT_A_VALID_IMAGE_HEADER_12345'), 'spoofed.png')
        }
        response = client.post('/analyze', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        assert b'Magic byte verification failed' in response.data

    def test_analyze_clean_image_success(self, client, clean_image_file):
        bio, name = clean_image_file
        data = {
            'image': (bio, name)
        }
        response = client.post('/analyze', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        assert b'Steganography Suspicion Index' in response.data
        assert b'Visual Bit-Plane Decomposition' in response.data
        assert b'Download Forensic PDF' in response.data

    def test_download_report_invalid_id(self, client):
        response = client.get('/download-report/invalid-uuid-1234', follow_redirects=True)
        assert response.status_code == 200
        assert b'Report session expired or not found' in response.data

    def test_analyze_and_download_pdf(self, client, clean_image_file):
        bio, name = clean_image_file
        data = {'image': (bio, name)}
        res_post = client.post('/analyze', data=data, content_type='multipart/form-data')
        assert res_post.status_code == 200

        # Extract analysis ID from rendered HTML
        html = res_post.data.decode('utf-8')
        import re
        match = re.search(r'/download-report/([a-f0-9\-]+)', html)
        assert match is not None
        analysis_id = match.group(1)

        # Download report
        res_pdf = client.get(f'/download-report/{analysis_id}')
        assert res_pdf.status_code == 200
        assert res_pdf.mimetype == 'application/pdf'
        assert res_pdf.data.startswith(b'%PDF')

    def test_api_analyze_endpoint(self, client, clean_image_file):
        bio, name = clean_image_file
        data = {'image': (bio, name)}
        res = client.post('/api/analyze', data=data, content_type='multipart/form-data')
        assert res.status_code == 200
        json_res = res.get_json()
        assert 'scoring' in json_res
        assert 'metadata' in json_res
        assert 'statistical' in json_res
        assert 'tampering' in json_res
        assert 'combined_indicator' in json_res['tampering']
        assert 'combined_score' in json_res['tampering']
        assert 'is_suspicious' in json_res['tampering']
        assert 'detectors' in json_res['tampering']
        assert json_res['scoring']['risk_level'] in ['Low', 'Medium', 'High']

