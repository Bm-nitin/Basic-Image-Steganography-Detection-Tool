import numpy as np
import pytest
from PIL import Image

from app.core.copy_move_analysis import CopyMoveAnalyzer


class TestCopyMoveAnalyzer:
    """Test suite for copy-move duplicate block analysis."""

    def test_uniform_image(self):
        img = Image.new('RGB', (100, 100), color=(100, 100, 100))
        res = CopyMoveAnalyzer.analyze(img)
        assert res['available'] is True
        assert res['cluster_count'] == 0
        assert res['anomaly_indicator'] == 0.0
        assert res['is_suspicious'] is False
        assert len(res['matches']) == 0

    def test_insufficient_dimensions(self):
        img = Image.new('RGB', (20, 20), color=(100, 100, 100))
        res = CopyMoveAnalyzer.analyze(img)
        assert res['available'] is False
        assert res['reason'] == 'insufficient_dimensions'

    def test_invalid_input(self):
        res = CopyMoveAnalyzer.analyze(12345)
        assert res['available'] is False
        assert res['reason'] == 'invalid_input_type'

    def test_clean_sample_no_clusters(self):
        img = Image.open('tests/test_samples/clean_sample.png')
        res = CopyMoveAnalyzer.analyze(img)
        assert res['available'] is True
        assert res['cluster_count'] == 0
        assert res['anomaly_indicator'] == 0.0
        assert res['is_suspicious'] is False

    def test_stego_samples_no_clusters(self):
        for path in ['tests/test_samples/stego_eof_sample.jpg', 'tests/test_samples/stego_lsb_sample.png']:
            img = Image.open(path)
            res = CopyMoveAnalyzer.analyze(img)
            assert res['available'] is True
            assert res['cluster_count'] == 0
            assert res['is_suspicious'] is False

    def test_cloned_patch_detection(self):
        # Create an image with complex textured noise
        np.random.seed(123)
        h, w = 256, 256
        arr = np.random.randint(50, 200, (h, w), dtype=np.uint8)

        # Clone a 48x48 region from (48, 48) to (160, 48) with rigid translation (+112, 0)
        source_patch = arr[48:96, 48:96].copy()
        arr[48:96, 160:208] = source_patch

        img = Image.fromarray(arr, mode='L')
        res = CopyMoveAnalyzer.analyze(img)
        assert res['available'] is True
        assert res['cluster_count'] >= 1
        assert res['anomaly_indicator'] > 0.40
        assert res['is_suspicious'] is True
        assert len(res['matches']) > 0

        # Validate match schema
        for m in res['matches']:
            assert 'source' in m and 'target' in m
            assert 'x' in m['source'] and 'y' in m['source']
            assert 'x' in m['target'] and 'y' in m['target']
            assert 'distance' in m and 'similarity' in m
            # Verify spatial separation
            dx = m['source']['x'] - m['target']['x']
            dy = m['source']['y'] - m['target']['y']
            assert np.hypot(dx, dy) >= 32.0
