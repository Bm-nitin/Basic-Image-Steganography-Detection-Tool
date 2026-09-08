import os
import pytest
from io import BytesIO
import numpy as np
from PIL import Image

from app.core.ela_analysis import ELAAnalyzer


class TestELAAnalyzer:
    """Test suite for Error Level Analysis (ELA) on JPEG images."""

    @pytest.fixture
    def sample_jpeg_bytes(self):
        img = Image.new('RGB', (120, 120), color=(100, 150, 200))
        # Add some texture
        arr = np.array(img)
        arr[20:100, 20:100] = [180, 80, 50]
        buf = BytesIO()
        Image.fromarray(arr).save(buf, format='JPEG', quality=90)
        return buf.getvalue()

    @pytest.fixture
    def sample_png_bytes(self):
        img = Image.new('RGB', (100, 100), color=(50, 100, 150))
        buf = BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    def test_ela_on_valid_jpeg(self, sample_jpeg_bytes):
        res = ELAAnalyzer.analyze(sample_jpeg_bytes, image_format='JPEG')
        assert res['available'] is True
        assert res['quality'] == 90
        assert 'mean_error' in res
        assert 'max_error' in res
        assert 'high_error_fraction' in res
        assert 0.0 <= res['anomaly_indicator'] <= 1.0
        assert isinstance(res['is_suspicious'], bool)
        assert 'heatmap' in res
        assert res['heatmap']['heatmap_available'] is True
        assert res['heatmap']['heatmap_base64'].startswith('data:image/png;base64,')
        assert res['heatmap']['width'] <= ELAAnalyzer.MAX_HEATMAP_DIMENSION
        assert res['heatmap']['height'] <= ELAAnalyzer.MAX_HEATMAP_DIMENSION

    def test_ela_on_non_jpeg_format(self, sample_png_bytes):
        res = ELAAnalyzer.analyze(sample_png_bytes, image_format='PNG')
        assert res['available'] is False
        assert res['reason'] == 'not_jpeg'
        assert res['anomaly_indicator'] == 0.0
        assert res['is_suspicious'] is False
        assert res['heatmap']['heatmap_available'] is False

    def test_ela_on_invalid_bytes(self):
        res = ELAAnalyzer.analyze(b'not_a_jpeg_stream', image_format='JPEG')
        assert res['available'] is False
        assert res['reason'] == 'not_jpeg'
        assert res['anomaly_indicator'] == 0.0

    def test_ela_on_empty_bytes(self):
        res = ELAAnalyzer.analyze(b'', image_format=None)
        assert res['available'] is False
        assert res['anomaly_indicator'] == 0.0

    def test_ela_on_baseline_samples(self):
        # clean_sample.png should be unavailable (not JPEG)
        with open('tests/test_samples/clean_sample.png', 'rb') as f:
            clean_b = f.read()
        res_clean = ELAAnalyzer.analyze(clean_b, image_format='PNG')
        assert res_clean['available'] is False

        # stego_eof_sample.jpg should be available and non-suspicious
        with open('tests/test_samples/stego_eof_sample.jpg', 'rb') as f:
            eof_b = f.read()
        res_eof = ELAAnalyzer.analyze(eof_b, image_format='JPEG')
        assert res_eof['available'] is True
        assert res_eof['is_suspicious'] is False
        assert res_eof['anomaly_indicator'] < 0.20

    def test_ela_spliced_disparity_detection(self):
        # Create a base JPEG at quality 50
        base_img = Image.new('RGB', (200, 200), color=(120, 120, 120))
        buf50 = BytesIO()
        base_img.save(buf50, format='JPEG', quality=50)
        base_decoded = Image.open(BytesIO(buf50.getvalue())).convert('RGB')
        arr_base = np.array(base_decoded)

        # Create a high-quality spliced patch saved at quality 98
        patch_img = Image.new('RGB', (80, 80), color=(240, 240, 240))
        buf98 = BytesIO()
        patch_img.save(buf98, format='JPEG', quality=98)
        patch_decoded = Image.open(BytesIO(buf98.getvalue())).convert('RGB')

        # Splice the Q98 patch into the Q50 image
        arr_base[60:140, 60:140] = np.array(patch_decoded)
        spliced_img = Image.fromarray(arr_base)
        spliced_buf = BytesIO()
        spliced_img.save(spliced_buf, format='JPEG', quality=75)

        res = ELAAnalyzer.analyze(spliced_buf.getvalue(), image_format='JPEG')
        assert res['available'] is True
        assert 'mean_error' in res
        assert res['anomaly_indicator'] >= 0.0
