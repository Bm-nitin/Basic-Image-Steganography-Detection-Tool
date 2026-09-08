import io
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app('testing')
    app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False
    })
    return app.test_client()

class TestMalformedInputs:
    """Rigorous malformed input testing covering F8 requirements."""

    def test_empty_payload_in_api(self, client):
        res = client.post('/api/analyze', data={}, content_type='multipart/form-data')
        assert res.status_code == 400
        json_data = res.get_json()
        assert json_data['code'] == 'MISSING_FILE'
        assert 'error' in json_data

    def test_wrong_form_field_name_in_api(self, client):
        data = {'file': (io.BytesIO(b'dummy'), 'sample.png')}
        res = client.post('/api/analyze', data=data, content_type='multipart/form-data')
        assert res.status_code == 400
        json_data = res.get_json()
        assert json_data['code'] == 'MISSING_FILE'

    def test_zero_byte_file_in_api(self, client):
        data = {'image': (io.BytesIO(b''), 'empty.png')}
        res = client.post('/api/analyze', data=data, content_type='multipart/form-data')
        assert res.status_code == 400
        json_data = res.get_json()
        assert json_data['code'] == 'EMPTY_FILE'

    def test_path_traversal_filename_sanitized(self, client):
        from PIL import Image
        bio = io.BytesIO()
        Image.new('RGB', (16, 16), color='red').save(bio, format='PNG')
        bio.seek(0)
        data = {'image': (bio, '../../../../etc/passwd.png')}
        res = client.post('/api/analyze', data=data, content_type='multipart/form-data')
        assert res.status_code == 200
        json_data = res.get_json()
        # Filename should be sanitized to basename only, no directory traversal
        assert '/' not in json_data['filename']
        assert '\\' not in json_data['filename']
        assert 'passwd.png' in json_data['filename']

    def test_unicode_special_filename(self, client):
        from PIL import Image
        bio = io.BytesIO()
        Image.new('RGB', (16, 16), color='blue').save(bio, format='PNG')
        bio.seek(0)
        data = {'image': (bio, 'forensics_test.png')}
        res = client.post('/api/analyze', data=data, content_type='multipart/form-data')
        assert res.status_code == 200
        json_data = res.get_json()
        assert 'scoring' in json_data

    def test_truncated_jpeg(self, client):
        # Starts with valid SOI marker and JFIF header (>12 bytes), but stream abruptly terminates before image data
        truncated_jpeg = b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xFF\xDB\x00C\x00'
        data = {'image': (io.BytesIO(truncated_jpeg), 'truncated.jpg')}
        res = client.post('/api/analyze', data=data, content_type='multipart/form-data')
        assert res.status_code == 400
        json_data = res.get_json()
        assert json_data['code'] == 'CORRUPT_IMAGE'

    def test_truncated_png(self, client):
        # PNG signature but truncated header
        truncated_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
        data = {'image': (io.BytesIO(truncated_png), 'truncated.png')}
        res = client.post('/api/analyze', data=data, content_type='multipart/form-data')
        assert res.status_code == 400
        json_data = res.get_json()
        assert json_data['code'] == 'CORRUPT_IMAGE'

    def test_binary_garbage_renamed_png(self, client):
        garbage = bytes(range(256))
        data = {'image': (io.BytesIO(garbage), 'random.png')}
        res = client.post('/api/analyze', data=data, content_type='multipart/form-data')
        assert res.status_code == 400
        json_data = res.get_json()
        assert json_data['code'] == 'INVALID_MAGIC_BYTES'

    def test_unsupported_format_gif(self, client):
        gif_bytes = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        data = {'image': (io.BytesIO(gif_bytes), 'animation.gif')}
        res = client.post('/api/analyze', data=data, content_type='multipart/form-data')
        assert res.status_code == 400
        json_data = res.get_json()
        assert json_data['code'] == 'UNSUPPORTED_EXTENSION'
