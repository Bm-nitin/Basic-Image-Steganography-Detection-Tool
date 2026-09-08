import os
import io
import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app import create_app
from app.core.image_validator import ImageValidator

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), 'test_samples')

@pytest.fixture
def app():
    app_instance = create_app('testing')
    app_instance.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False
    })
    yield app_instance

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def clean_png_bytes():
    path = os.path.join(SAMPLE_DIR, 'clean_sample.png')
    with open(path, 'rb') as f:
        return f.read()

@pytest.fixture
def clean_jpeg_bytes():
    bio = io.BytesIO()
    img = Image.new('RGB', (64, 64), color=(70, 130, 180))
    img.save(bio, format='JPEG')
    return bio.getvalue()

@pytest.fixture
def clean_bmp_bytes():
    bio = io.BytesIO()
    img = Image.new('RGB', (32, 32), color=(34, 139, 34))
    img.save(bio, format='BMP')
    return bio.getvalue()

@pytest.fixture
def clean_webp_bytes():
    bio = io.BytesIO()
    img = Image.new('RGB', (32, 32), color=(255, 99, 71))
    img.save(bio, format='WEBP')
    return bio.getvalue()


class TestImageValidator:
    # 1. Valid PNG upload
    def test_valid_png_validation(self, clean_png_bytes):
        result = ImageValidator.validate(clean_png_bytes, filename='sample.png')
        assert result['valid'] is True
        assert result['format'] == 'PNG'
        assert result['extension'] == 'png'
        assert result['mime'] == 'image/png'
        assert result['width'] > 0
        assert result['height'] > 0
        assert result['pil_image'] is not None
        assert len(result['errors']) == 0

    # 2. Valid JPEG upload
    def test_valid_jpeg_validation(self, clean_jpeg_bytes):
        result = ImageValidator.validate(clean_jpeg_bytes, filename='photo.jpg')
        assert result['valid'] is True
        assert result['format'] == 'JPEG'
        assert result['extension'] == 'jpg'
        assert result['mime'] == 'image/jpeg'
        assert len(result['errors']) == 0

    # 3. Valid BMP upload
    def test_valid_bmp_validation(self, clean_bmp_bytes):
        result = ImageValidator.validate(clean_bmp_bytes, filename='graphic.bmp')
        assert result['valid'] is True
        assert result['format'] == 'BMP'
        assert result['extension'] == 'bmp'
        assert result['mime'] == 'image/bmp'
        assert len(result['errors']) == 0

    # 4. Valid WebP upload
    def test_valid_webp_validation(self, clean_webp_bytes):
        result = ImageValidator.validate(clean_webp_bytes, filename='banner.webp')
        assert result['valid'] is True
        assert result['format'] == 'WEBP'
        assert result['extension'] == 'webp'
        assert result['mime'] == 'image/webp'
        assert len(result['errors']) == 0

    # 5. Empty file (0 bytes)
    def test_empty_file_validation(self):
        result = ImageValidator.validate(b'', filename='empty.png')
        assert result['valid'] is False
        assert result['error_code'] == 'EMPTY_FILE'
        assert any('empty' in err.lower() for err in result['errors'])

    # 6. Unsupported file extension (.exe, .pdf, .txt)
    @pytest.mark.parametrize('filename', ['malware.exe', 'document.pdf', 'notes.txt'])
    def test_unsupported_extension_validation(self, filename, clean_png_bytes):
        result = ImageValidator.validate(clean_png_bytes, filename=filename)
        assert result['valid'] is False
        assert result['error_code'] == 'UNSUPPORTED_EXTENSION'
        assert any('unsupported' in err.lower() for err in result['errors'])

    # 7. Invalid magic bytes (renamed text file)
    def test_invalid_magic_bytes(self):
        fake_data = b"This is a plaintext file renamed to look like a PNG image."
        result = ImageValidator.validate(fake_data, filename='fake.png')
        assert result['valid'] is False
        assert result['error_code'] == 'INVALID_MAGIC_BYTES'
        assert any('magic byte' in err.lower() for err in result['errors'])

    # 8. Extension spoofing (PNG renamed to .jpg generates warning, parses validly)
    def test_extension_spoofing_warning(self, clean_png_bytes):
        result = ImageValidator.validate(clean_png_bytes, filename='spoofed_name.jpg')
        assert result['valid'] is True
        assert result['format'] == 'PNG'
        assert result['extension'] == 'jpg'
        assert result['format_consistency']['extension_mismatch'] is True
        assert len(result['warnings']) > 0
        assert any('format spoofing' in w.lower() or 'mismatch' in w.lower() for w in result['warnings'])

    # 9. Oversized file (> 10 MB)
    def test_oversized_file_validation(self):
        # Configure custom boundary for fast testing
        custom_config = {'MAX_CONTENT_LENGTH': 1024 * 1024}  # 1 MB limit
        oversized_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * (1024 * 1024 + 100)
        result = ImageValidator.validate(oversized_data, filename='large.png', config=custom_config)
        assert result['valid'] is False
        assert result['error_code'] == 'FILE_TOO_LARGE'
        assert any('exceeds maximum' in err.lower() for err in result['errors'])

    # 10. Excessive dimensions (> 4096px)
    def test_excessive_dimensions_validation(self):
        custom_config = {'MAX_IMAGE_DIMENSION': 100, 'MAX_IMAGE_PIXELS': 25_000_000}
        bio = io.BytesIO()
        img = Image.new('RGB', (150, 50), color='blue')
        img.save(bio, format='PNG')
        result = ImageValidator.validate(bio.getvalue(), filename='wide.png', config=custom_config)
        assert result['valid'] is False
        assert result['error_code'] == 'IMAGE_DIMENSION_LIMIT'
        assert any('dimension' in err.lower() for err in result['errors'])

    # 11. Excessive pixel count (> 25M pixels)
    def test_excessive_pixel_count_validation(self):
        custom_config = {'MAX_IMAGE_DIMENSION': 1000, 'MAX_IMAGE_PIXELS': 5000}
        bio = io.BytesIO()
        img = Image.new('RGB', (100, 100), color='white')  # 10,000 pixels > 5,000 max
        img.save(bio, format='PNG')
        result = ImageValidator.validate(bio.getvalue(), filename='pixel_flood.png', config=custom_config)
        assert result['valid'] is False
        assert result['error_code'] == 'PIXEL_COUNT_LIMIT'
        assert any('pixel count' in err.lower() for err in result['errors'])

    # 12. Corrupt / truncated image data
    def test_corrupt_truncated_image(self):
        # Starts with valid PNG header but followed by corrupt chunks
        corrupt_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' + b'CORRUPT_DATA_SEGMENT'
        result = ImageValidator.validate(corrupt_data, filename='corrupt.png')
        assert result['valid'] is False
        assert result['error_code'] == 'CORRUPT_IMAGE'
        assert any('corrupt' in err.lower() or 'malformed' in err.lower() for err in result['errors'])


class TestAPIAndRouteValidation:
    # 13. API endpoint receives oversized image (HTTP 413)
    def test_api_oversized_image_returns_413(self, client, app):
        app.config['MAX_CONTENT_LENGTH'] = 500  # 500 bytes ceiling
        data = {'image': (io.BytesIO(b'A' * 1000), 'large.png')}
        res = client.post('/api/analyze', data=data, content_type='multipart/form-data')
        assert res.status_code == 413
        json_data = res.get_json()
        assert json_data['code'] == 'FILE_TOO_LARGE'
        assert 'error' in json_data

    # 14. API endpoint receives dimension-exceeding image (HTTP 400, IMAGE_DIMENSION_LIMIT)
    def test_api_dimension_limit_returns_400(self, client, app):
        app.config['MAX_IMAGE_DIMENSION'] = 50  # 50px limit
        bio = io.BytesIO()
        img = Image.new('RGB', (80, 80), color='red')
        img.save(bio, format='PNG')
        bio.seek(0)
        data = {'image': (bio, 'large_dim.png')}
        res = client.post('/api/analyze', data=data, content_type='multipart/form-data')
        assert res.status_code == 400
        json_data = res.get_json()
        assert json_data['code'] == 'IMAGE_DIMENSION_LIMIT'
        assert 'Image validation failed' in json_data['error']

    # 15. API endpoint receives invalid magic bytes (HTTP 400, INVALID_MAGIC_BYTES)
    def test_api_invalid_magic_bytes_returns_400(self, client):
        data = {'image': (io.BytesIO(b"NOT_A_REAL_IMAGE_HEADER_XYZ"), 'fake.png')}
        res = client.post('/api/analyze', data=data, content_type='multipart/form-data')
        assert res.status_code == 400
        json_data = res.get_json()
        assert json_data['code'] == 'INVALID_MAGIC_BYTES'
        assert 'Image validation failed' in json_data['error']

    # 16. Normal valid API analysis succeeds (HTTP 200)
    def test_api_valid_analysis_succeeds(self, client, clean_png_bytes):
        data = {'image': (io.BytesIO(clean_png_bytes), 'clean_sample.png')}
        res = client.post('/api/analyze', data=data, content_type='multipart/form-data')
        assert res.status_code == 200
        json_data = res.get_json()
        assert json_data['filename'] == 'clean_sample.png'
        assert 'metadata' in json_data
        assert 'statistical' in json_data
        assert 'scoring' in json_data
        assert json_data['scoring']['risk_level'] == 'Low'

    # 17. Normal valid Web analysis succeeds (HTTP 200)
    def test_web_valid_analysis_succeeds(self, client, clean_png_bytes):
        data = {'image': (io.BytesIO(clean_png_bytes), 'clean_sample.png')}
        res = client.post('/analyze', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert res.status_code == 200
        assert b'Steganography Suspicion Index' in response_data if 'response_data' in locals() else b'Steganography Suspicion Index' in res.data
        assert b'Visual Bit-Plane Decomposition' in res.data
