import os
import pytest
import numpy as np
from PIL import Image

from app.core.spa_analysis import SPAnalyzer

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), 'test_samples')


class TestSPAnalyzer:
    @pytest.fixture
    def clean_image(self):
        path = os.path.join(SAMPLE_DIR, 'clean_sample.png')
        return Image.open(path)

    @pytest.fixture
    def stego_lsb_image(self):
        path = os.path.join(SAMPLE_DIR, 'stego_lsb_sample.png')
        return Image.open(path)

    def test_spa_clean_image_baseline(self, clean_image):
        res = SPAnalyzer.analyze(clean_image)
        assert res['available'] is True
        assert 0.0 <= res['estimated_embedding_rate'] < 0.30
        assert res['is_suspicious'] is False
        assert res['pair_count'] > 1000
        assert res['same_pairs'] > 0

    def test_spa_synthetic_lsb_embedding(self, stego_lsb_image):
        res = SPAnalyzer.analyze(stego_lsb_image)
        assert res['available'] is True
        assert res['estimated_embedding_rate'] > 0.40
        assert res['is_suspicious'] is True

    def test_spa_constant_uniform_image(self):
        flat = Image.new('L', (64, 64), color=200)
        res = SPAnalyzer.analyze(flat)
        assert res['available'] is True
        assert res['estimated_embedding_rate'] == 0.0
        assert res['is_suspicious'] is False

    def test_spa_insufficient_samples(self):
        tiny = Image.new('L', (3, 3), color=100)
        res = SPAnalyzer.analyze(tiny)
        assert res['available'] is False
        assert res['reason'] in ('insufficient_dimensions', 'insufficient_sample_pairs')
        assert res['estimated_embedding_rate'] == 0.0

    def test_spa_deterministic_repeatability(self, clean_image):
        res1 = SPAnalyzer.analyze(clean_image)
        res2 = SPAnalyzer.analyze(clean_image)
        assert res1['estimated_embedding_rate'] == res2['estimated_embedding_rate']
        assert res1['same_pairs'] == res2['same_pairs']
        assert res1['different_pairs'] == res2['different_pairs']

    def test_spa_numerical_stability(self):
        # Random noise array
        noisy = np.random.randint(0, 256, (120, 120), dtype=np.uint8)
        res = SPAnalyzer.analyze(noisy)
        assert not np.isnan(res['estimated_embedding_rate'])
        assert not np.isinf(res['estimated_embedding_rate'])
        assert 0.0 <= res['estimated_embedding_rate'] <= 1.0
        assert 0.0 <= res['suspicion_indicator'] <= 1.0
