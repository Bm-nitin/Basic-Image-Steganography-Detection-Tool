import os
import pytest
import numpy as np
from PIL import Image

from app.core.rs_analysis import RSAnalyzer

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), 'test_samples')


class TestRSAnalyzer:
    @pytest.fixture
    def clean_image(self):
        path = os.path.join(SAMPLE_DIR, 'clean_sample.png')
        return Image.open(path)

    @pytest.fixture
    def stego_lsb_image(self):
        path = os.path.join(SAMPLE_DIR, 'stego_lsb_sample.png')
        return Image.open(path)

    def test_rs_clean_image_baseline(self, clean_image):
        res = RSAnalyzer.analyze(clean_image)
        assert res['available'] is True
        assert 0.0 <= res['estimated_embedding_rate'] < 0.20
        assert res['is_suspicious'] is False
        assert res['group_size'] == 4
        assert res['regular'] > 0.0

    def test_rs_synthetic_lsb_embedding(self, stego_lsb_image):
        res = RSAnalyzer.analyze(stego_lsb_image)
        assert res['available'] is True
        assert res['estimated_embedding_rate'] > 0.40
        assert res['is_suspicious'] is True
        assert res['suspicion_indicator'] > 0.50

    def test_rs_constant_uniform_image(self):
        # Image of identical pixels (zero natural variation)
        flat_img = Image.new('L', (64, 64), color=128)
        res = RSAnalyzer.analyze(flat_img)
        assert res['available'] is True
        assert res['estimated_embedding_rate'] == 0.0
        assert res['is_suspicious'] is False

    def test_rs_tiny_dimensions_rejected(self):
        tiny_img = Image.new('RGB', (2, 2), color=(100, 150, 200))
        res = RSAnalyzer.analyze(tiny_img)
        assert res['available'] is False
        assert res['reason'] in ('insufficient_dimensions', 'insufficient_groups')
        assert res['estimated_embedding_rate'] == 0.0

    def test_rs_grayscale_numpy_array(self):
        # 2D NumPy array input
        arr = np.random.randint(50, 200, (64, 64), dtype=np.uint8)
        res = RSAnalyzer.analyze(arr)
        assert res['available'] is True
        assert 0.0 <= res['estimated_embedding_rate'] <= 1.0

    def test_rs_rgb_channel_breakdown(self, clean_image):
        res = RSAnalyzer.analyze(clean_image)
        assert 'channel_breakdown' in res
        channels = res['channel_breakdown']
        assert 'red' in channels
        assert 'green' in channels
        assert 'blue' in channels
        for ch_name, ch_res in channels.items():
            assert ch_res['available'] is True
            assert 0.0 <= ch_res['estimated_embedding_rate'] <= 1.0

    def test_rs_rgba_image_handling(self):
        rgba = Image.new('RGBA', (64, 64), (120, 140, 160, 255))
        res = RSAnalyzer.analyze(rgba)
        assert res['available'] is True
        assert 0.0 <= res['estimated_embedding_rate'] <= 1.0

    def test_rs_numerical_stability_guarantees(self):
        # Extreme checkerboard pattern
        checker = np.indices((64, 64)).sum(axis=0) % 2 * 255
        res = RSAnalyzer.analyze(checker.astype(np.uint8))
        assert not np.isnan(res['estimated_embedding_rate'])
        assert not np.isinf(res['estimated_embedding_rate'])
        assert 0.0 <= res['estimated_embedding_rate'] <= 1.0
        assert not np.isnan(res['suspicion_indicator'])
        assert 0.0 <= res['suspicion_indicator'] <= 1.0
