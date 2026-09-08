import os
import pytest
from app.core.jpeg_analysis import JPEGDomainAnalyzer

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), 'test_samples')


class TestJPEGDomainAnalyzer:
    @pytest.fixture
    def jpeg_bytes(self):
        path = os.path.join(SAMPLE_DIR, 'stego_eof_sample.jpg')
        with open(path, 'rb') as f:
            return f.read()

    @pytest.fixture
    def png_bytes(self):
        path = os.path.join(SAMPLE_DIR, 'clean_sample.png')
        with open(path, 'rb') as f:
            return f.read()

    def test_jpeg_valid_image(self, jpeg_bytes):
        res = JPEGDomainAnalyzer.analyze(jpeg_bytes, image_format='JPEG')
        assert res['available'] is True
        assert res['components'] == 3
        assert 'Y' in res['sampling_factors']
        assert res['subsampling'] in ('4:2:0', '4:2:2', '4:4:4')
        assert res['quantization_tables_count'] >= 1
        assert res['sos_entropy'] > 6.0
        assert 1 <= res['estimated_quality'] <= 100
        assert res['is_suspicious'] is False

    def test_jpeg_rejected_for_png_format(self, png_bytes):
        res = JPEGDomainAnalyzer.analyze(png_bytes, image_format='PNG')
        assert res['available'] is False
        assert res['reason'] == 'not_jpeg'
        assert res['jpeg_structural_indicator'] == 0.0

    def test_jpeg_rejected_for_bmp_format(self):
        fake_bmp = b'BM' + b'\x00' * 100
        res = JPEGDomainAnalyzer.analyze(fake_bmp, image_format='BMP')
        assert res['available'] is False
        assert res['reason'] == 'not_jpeg'

    def test_jpeg_corrupt_truncated_bytes(self):
        corrupt_data = b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00'  # Truncated
        res = JPEGDomainAnalyzer.analyze(corrupt_data, image_format='JPEG')
        # Should gracefully handle without exception
        assert isinstance(res, dict)
        assert 'available' in res

    def test_jpeg_missing_soi_marker(self):
        invalid_bytes = b'\x00\x00\x00\x00' + b'\xFF' * 50
        res = JPEGDomainAnalyzer.analyze(invalid_bytes, image_format='JPEG')
        assert res['available'] is False
        assert res['reason'] == 'not_jpeg'

    def test_jpeg_alias_backward_compatibility(self, jpeg_bytes):
        res = JPEGDomainAnalyzer.analyze(jpeg_bytes, image_format='JPEG')
        assert 'dct_suspicion_indicator' in res
        assert 'jpeg_structural_indicator' in res
        assert res['dct_suspicion_indicator'] == res['jpeg_structural_indicator']
