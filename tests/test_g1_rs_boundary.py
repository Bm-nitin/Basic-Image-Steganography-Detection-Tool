"""
Phase G1.3 regression tests: RS steganalysis boundary handling at pixel
values 0 and 255.

These lock in behavior that was verified (not assumed) against the primary
source (Fridrich, Goljan & Du) during the G1 audit pass: F_{-1}(x) = x for
x in {0, 255} is the correct practical resolution of the paper's own
out-of-range boundary formula, not a defect. No functional change was made
to rs_analysis.py in this phase; these tests exist to prevent an
undocumented future change from silently altering this verified behavior.
"""
import numpy as np
import pytest
from PIL import Image

from app.core.rs_analysis import RSAnalyzer


class TestRSFlipNeg1Boundary:
    def test_flip_neg1_zero_is_fixed_point(self):
        arr = np.array([[0, 0, 0, 0]], dtype=np.uint8)
        out = RSAnalyzer._flip_neg1(arr)
        assert out[0, 0] == 0

    def test_flip_neg1_255_is_fixed_point(self):
        arr = np.array([[255, 255, 255, 255]], dtype=np.uint8)
        out = RSAnalyzer._flip_neg1(arr)
        assert out[0, 0] == 255

    def test_flip_neg1_interior_values_match_paired_definition(self):
        # F_{-1}: even x -> x-1, odd x -> x+1 for all interior values,
        # per F_{-1}(x) = F_1(x+1) - 1 (Fridrich, Goljan & Du).
        arr = np.array([[1, 2, 3, 4, 253, 254]], dtype=np.uint8)
        out = RSAnalyzer._flip_neg1(arr)
        assert list(out[0]) == [2, 1, 4, 3, 254, 253]

    def test_flip_neg1_output_stays_in_valid_range(self):
        arr = np.arange(256, dtype=np.uint8).reshape(1, 256)
        out = RSAnalyzer._flip_neg1(arr)
        assert out.min() >= 0 and out.max() <= 255
        assert out.dtype == np.uint8


class TestRSBoundaryImages:
    """No pathological (NaN/Inf/out-of-range) behavior on hard-boundary content."""

    def _assert_well_formed(self, res):
        assert res['available'] is True
        assert not np.isnan(res['estimated_embedding_rate'])
        assert not np.isinf(res['estimated_embedding_rate'])
        assert 0.0 <= res['estimated_embedding_rate'] <= 1.0
        assert not np.isnan(res['suspicion_indicator'])
        assert 0.0 <= res['suspicion_indicator'] <= 1.0

    def test_all_black_image(self):
        img = Image.new('L', (64, 64), color=0)
        res = RSAnalyzer.analyze(img)
        self._assert_well_formed(res)
        # A perfectly flat image has zero natural variation; no embedding signal.
        assert res['estimated_embedding_rate'] == 0.0
        assert res['is_suspicious'] is False

    def test_all_white_image(self):
        img = Image.new('L', (64, 64), color=255)
        res = RSAnalyzer.analyze(img)
        self._assert_well_formed(res)
        assert res['estimated_embedding_rate'] == 0.0
        assert res['is_suspicious'] is False

    def test_black_white_checkerboard(self):
        checker = (np.indices((64, 64)).sum(axis=0) % 2 * 255).astype(np.uint8)
        img = Image.fromarray(checker, mode='L')
        res = RSAnalyzer.analyze(img)
        self._assert_well_formed(res)

    def test_black_text_on_white_background(self):
        # Synthetic "document-like" content: a white background with a block
        # of black "text" rows -- exercises hard 0/255 transitions directly.
        arr = np.full((80, 80), 255, dtype=np.uint8)
        arr[20:24, 10:70] = 0
        arr[40:44, 10:70] = 0
        arr[60:64, 10:70] = 0
        img = Image.fromarray(arr, mode='L')
        res = RSAnalyzer.analyze(img)
        self._assert_well_formed(res)

    def test_grayscale_gradient(self):
        gradient = np.tile(np.arange(256, dtype=np.uint8), (64, 1))
        img = Image.fromarray(gradient, mode='L')
        res = RSAnalyzer.analyze(img)
        self._assert_well_formed(res)

    def test_existing_clean_sample_if_available(self):
        import os
        path = os.path.join(os.path.dirname(__file__), 'test_samples', 'clean_sample.png')
        if not os.path.exists(path):
            pytest.skip("clean_sample.png not present in tests/test_samples")
        img = Image.open(path)
        res = RSAnalyzer.analyze(img)
        self._assert_well_formed(res)

    def test_existing_stego_sample_if_available(self):
        import os
        path = os.path.join(os.path.dirname(__file__), 'test_samples', 'stego_lsb_sample.png')
        if not os.path.exists(path):
            pytest.skip("stego_lsb_sample.png not present in tests/test_samples")
        img = Image.open(path)
        res = RSAnalyzer.analyze(img)
        self._assert_well_formed(res)
        assert res['estimated_embedding_rate'] > 0.0
