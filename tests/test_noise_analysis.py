import numpy as np
import pytest
from PIL import Image

from app.core.noise_analysis import NoiseAnalyzer


class TestNoiseAnalyzer:
    """Test suite for local residual noise consistency analysis."""

    def test_uniform_image(self):
        img = Image.new('RGB', (100, 100), color=(128, 128, 128))
        res = NoiseAnalyzer.analyze(img)
        assert res['available'] is True
        assert res['global_noise_std'] == 0.0
        assert res['anomaly_indicator'] == 0.0
        assert res['is_suspicious'] is False
        assert len(res['regions']) == 0

    def test_insufficient_dimensions(self):
        img = Image.new('RGB', (10, 10), color=(100, 100, 100))
        res = NoiseAnalyzer.analyze(img)
        assert res['available'] is False
        assert res['reason'] == 'insufficient_dimensions'

    def test_invalid_input(self):
        res = NoiseAnalyzer.analyze("not_an_image")
        assert res['available'] is False
        assert res['reason'] == 'invalid_input_type'

    def test_numpy_array_input(self):
        arr = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        res = NoiseAnalyzer.analyze(arr)
        assert res['available'] is True
        assert 0.0 <= res['anomaly_indicator'] <= 1.0

    def test_clean_sample_non_suspicious(self):
        img = Image.open('tests/test_samples/clean_sample.png')
        res = NoiseAnalyzer.analyze(img)
        assert res['available'] is True
        assert res['anomaly_indicator'] < 0.15
        assert res['is_suspicious'] is False
        assert res['outlier_region_fraction'] == 0.0

    def test_spliced_noise_patch_detection(self):
        # Create a smooth image with a sharp noisy patch injected
        w, h = 256, 256
        smooth_arr = np.zeros((h, w), dtype=np.float32)
        for y in range(h):
            for x in range(w):
                smooth_arr[y, x] = 50 + 100 * (y / h)

        # Inject extreme localized gaussian noise patch
        np.random.seed(42)
        noisy_patch = np.random.normal(0, 30, (80, 80)).astype(np.float32)
        smooth_arr[64:144, 64:144] += noisy_patch
        clamped = np.clip(smooth_arr, 0, 255).astype(np.uint8)

        img = Image.fromarray(clamped, mode='L')
        res = NoiseAnalyzer.analyze(img)
        assert res['available'] is True
        assert res['anomaly_indicator'] > 0.35
        assert len(res['regions']) > 0

        # Verify region coordinate schema (no file paths, valid bounds)
        for r in res['regions']:
            assert 'x' in r and isinstance(r['x'], int) and 0 <= r['x'] <= w
            assert 'y' in r and isinstance(r['y'], int) and 0 <= r['y'] <= h
            assert 'width' in r and isinstance(r['width'], int) and r['width'] > 0
            assert 'height' in r and isinstance(r['height'], int) and r['height'] > 0
            assert 'indicator' in r and 0.0 <= r['indicator'] <= 1.0
