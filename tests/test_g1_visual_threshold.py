"""
Phase G1 regression tests: Visual LSB balance threshold consistency (G1.1)
and multiple-comparisons correction (G1.2).

These tests do not assert against any specific real-world sample image
(marksheet, landscape, etc.) — they use small synthetic arrays constructed
to exercise the detector's logic directly, per the audit's instruction not
to calibrate against individual example images.
"""
import numpy as np
import pytest
from PIL import Image

from app.core.visual_extractor import VisualExtractor
from app.core.scoring import SuspicionScoringEngine
from app.core.evidence import EvidenceCollector


def _rgb_image_from_channels(r, g, b):
    arr = np.stack([r, g, b], axis=2).astype(np.uint8)
    return Image.fromarray(arr, mode='RGB')


def _perfectly_balanced_channel(h, w, seed):
    """Deterministic array whose LSB plane is exactly 50/50 (even count of pixels)."""
    rng = np.random.RandomState(seed)
    base = rng.randint(0, 128, size=(h, w), dtype=np.uint16) * 2  # all even
    n = base.size
    flat = base.flatten()
    flat[: n // 2] += 1  # exactly half become odd -> exact 50/50 LSB split
    return flat.reshape(h, w).astype(np.uint8)


def _biased_channel(h, w, seed, bias=0.2):
    """Array whose LSB plane is deliberately far from 50/50."""
    rng = np.random.RandomState(seed)
    base = rng.randint(0, 128, size=(h, w), dtype=np.uint16) * 2
    n = base.size
    flat = base.flatten()
    n_odd = int(n * bias)
    flat[:n_odd] += 1
    return flat.reshape(h, w).astype(np.uint8)


class TestG11ThresholdSingleSourceOfTruth:
    """G1.1: detector output and scoring/evidence must not be able to silently disagree."""

    def test_constant_exists_and_is_single_value(self):
        assert hasattr(VisualExtractor, 'BASE_BALANCE_THRESHOLD')
        assert isinstance(VisualExtractor.BASE_BALANCE_THRESHOLD, float)

    def test_scoring_and_evidence_import_same_constant(self):
        from app.core import scoring as scoring_mod
        from app.core import evidence as evidence_mod
        assert scoring_mod.VisualExtractor.BASE_BALANCE_THRESHOLD == VisualExtractor.BASE_BALANCE_THRESHOLD
        assert evidence_mod.VisualExtractor.BASE_BALANCE_THRESHOLD == VisualExtractor.BASE_BALANCE_THRESHOLD

    @pytest.mark.parametrize("min_delta", [0.0001, 0.001, 0.0049, 0.0051, 0.02, 0.05])
    def test_scoring_fallback_matches_base_constant(self, min_delta):
        """
        When scoring.py receives a bare min_balance_delta with no attached
        decision (legacy-style call), its fallback decision must match a
        direct comparison against VisualExtractor.BASE_BALANCE_THRESHOLD.
        """
        meta = {'metadata': {}}
        visual = {'min_balance_delta': min_delta}  # no is_visual_suspicious key
        stat = {
            'chi_square': {'max_indicator': 0.0},
            'entropy': {'lsb_entropy': {'max': 0.0}},
            'spa_analysis': {'estimated_embedding_rate': 0.0},
            'rs_analysis': {'estimated_embedding_rate': 0.0},
            'jpeg_analysis': {'available': False, 'reason': 'not_jpeg'},
            'channel_analysis': {'channel_anomaly_indicator': 0.0}
        }
        score_res = SuspicionScoringEngine.evaluate(meta, visual, stat)
        expected_suspicious = min_delta < VisualExtractor.BASE_BALANCE_THRESHOLD
        expected_pts = 20.0 if expected_suspicious else 0.0
        assert score_res['category_scores']['visual'] == expected_pts

    @pytest.mark.parametrize("min_delta", [0.0001, 0.001, 0.0049, 0.0051, 0.02, 0.05])
    def test_evidence_fallback_matches_base_constant(self, min_delta):
        visual_res = {'min_balance_delta': min_delta}
        stat_res = {
            'entropy': {'lsb_entropy': {'max': 0.0}},
            'chi_square': {'max_indicator': 0.0, 'red': {}, 'green': {}, 'blue': {}, 'gray': {}},
            'sample_pair_analysis': {'estimated_embedding_rate': 0.0},
            'rs_analysis': {'estimated_embedding_rate': 0.0, 'suspicion_indicator': 0.0},
            'jpeg_analysis': {'available': False},
        }
        meta_res = {'trailing_data': {}, 'metadata': {}}
        evidence = EvidenceCollector.collect_all(meta_res, visual_res, stat_res)
        visual_items = [
            e for e in evidence['steganography']
            if e.get('detector') == 'LSB Parity Distribution'
        ]
        assert len(visual_items) == 1
        expected_suspicious = min_delta < VisualExtractor.BASE_BALANCE_THRESHOLD
        expected_severity = 'suspicious' if expected_suspicious else 'clean'
        assert visual_items[0]['severity'] == expected_severity

    def test_detector_and_scoring_cannot_disagree_on_real_output(self):
        """
        Full end-to-end: whatever VisualExtractor.extract_bit_planes() decides
        as is_visual_suspicious must be exactly what scoring.py awards points
        for -- no independent re-derivation.
        """
        rng = np.random.RandomState(7)
        arr = rng.randint(0, 256, (48, 48, 3), dtype=np.uint8)
        img = Image.fromarray(arr, mode='RGB')
        visual_res = VisualExtractor.extract_bit_planes(img)

        meta = {'metadata': {}}
        stat = {
            'chi_square': {'max_indicator': 0.0},
            'entropy': {'lsb_entropy': {'max': 0.0}},
            'spa_analysis': {'estimated_embedding_rate': 0.0},
            'rs_analysis': {'estimated_embedding_rate': 0.0},
            'jpeg_analysis': {'available': False, 'reason': 'not_jpeg'},
            'channel_analysis': {'channel_anomaly_indicator': 0.0}
        }
        score_res = SuspicionScoringEngine.evaluate(meta, visual_res, stat)
        vis_row = next(d for d in score_res['detector_breakdown'] if d['detector'] == 'LSB Parity Distribution')
        expected_pts = 20.0 if visual_res['is_visual_suspicious'] else 0.0
        assert vis_row['points_added'] == expected_pts
        assert score_res['category_scores']['visual'] == expected_pts


class TestG12MultipleComparisonsFix:
    """G1.2: gray excluded from the independent-evidence pool; k-channel correction applied."""

    def test_grayscale_source_uses_single_channel_no_correction(self):
        gray_plane = _perfectly_balanced_channel(64, 64, seed=1)
        img = _rgb_image_from_channels(gray_plane, gray_plane, gray_plane)
        res = VisualExtractor.extract_bit_planes(img)
        assert res['is_effectively_grayscale'] is True
        assert res['channel_count'] == 1
        assert res['tested_channels'] == ['gray']
        assert res['effective_threshold'] == pytest.approx(VisualExtractor.BASE_BALANCE_THRESHOLD)

    def test_color_source_pools_only_rgb_not_gray(self):
        r = _biased_channel(64, 64, seed=2, bias=0.30)
        g = _biased_channel(64, 64, seed=3, bias=0.35)
        b = _biased_channel(64, 64, seed=4, bias=0.40)
        img = _rgb_image_from_channels(r, g, b)
        res = VisualExtractor.extract_bit_planes(img)
        assert res['is_effectively_grayscale'] is False
        assert res['channel_count'] == 3
        assert set(res['tested_channels']) == {'red', 'green', 'blue'}
        assert res['effective_threshold'] == pytest.approx(VisualExtractor.BASE_BALANCE_THRESHOLD / 3.0)

    def test_single_coincidentally_balanced_channel_among_biased_others_is_not_flagged(self):
        """
        The core multiple-comparisons regression: one channel landing very
        close to 0.5 while the other two are clearly biased must NOT trigger
        suspicion under the corrected (k=3) threshold, if its delta does not
        clear the corrected bar -- even though it would have cleared the old
        uncorrected 0.02 threshold used in visual_extractor.py previously.
        """
        balanced = _perfectly_balanced_channel(80, 80, seed=5)  # delta == 0.0 exactly on this one channel
        # Perturb the "coincidentally balanced" channel slightly so its delta
        # sits between the corrected (0.005/3 ~= 0.00167) and base (0.005)
        # thresholds, isolating the multiple-comparisons effect itself.
        flat = balanced.flatten().astype(np.int32)
        n_flip = int(0.003 * flat.size)  # nudges density delta to ~0.003
        flat[:n_flip] = flat[:n_flip] ^ 1
        near_balanced = flat.reshape(balanced.shape).astype(np.uint8)

        r = near_balanced
        g = _biased_channel(80, 80, seed=6, bias=0.15)
        b = _biased_channel(80, 80, seed=7, bias=0.10)
        img = _rgb_image_from_channels(r, g, b)
        res = VisualExtractor.extract_bit_planes(img)

        # Sanity: the coincidentally-balanced channel is indeed the minimum.
        assert res['min_balance_channel'] == 'red'
        # It clears the OLD single-test-style threshold (0.005) ...
        assert res['min_balance_delta'] < VisualExtractor.BASE_BALANCE_THRESHOLD
        # ... but must NOT clear the corrected 3-channel threshold, and must
        # therefore not be flagged suspicious.
        assert res['min_balance_delta'] >= res['effective_threshold']
        assert res['is_visual_suspicious'] is False

    def test_genuine_full_strength_single_channel_lsb_is_still_detected(self):
        """
        Preserve single-channel detection: a channel with a true, tight
        50/50 LSB split (as produced by full-capacity random LSB embedding)
        must still be flagged even under the corrected 3-channel threshold.
        """
        embedded_channel = _perfectly_balanced_channel(128, 128, seed=8)  # exact 50/50
        g = _biased_channel(128, 128, seed=9, bias=0.15)
        b = _biased_channel(128, 128, seed=10, bias=0.20)
        img = _rgb_image_from_channels(embedded_channel, g, b)
        res = VisualExtractor.extract_bit_planes(img)
        assert res['min_balance_channel'] == 'red'
        assert res['is_visual_suspicious'] is True

    def test_multi_channel_lsb_embedding_detected(self):
        """All three channels genuinely balanced (e.g. full RGB LSB embedding)."""
        r = _perfectly_balanced_channel(64, 64, seed=11)
        g = _perfectly_balanced_channel(64, 64, seed=12)
        b = _perfectly_balanced_channel(64, 64, seed=13)
        img = _rgb_image_from_channels(r, g, b)
        res = VisualExtractor.extract_bit_planes(img)
        assert res['is_visual_suspicious'] is True

    def test_clean_biased_image_not_flagged(self):
        r = _biased_channel(64, 64, seed=14, bias=0.15)
        g = _biased_channel(64, 64, seed=15, bias=0.20)
        b = _biased_channel(64, 64, seed=16, bias=0.25)
        img = _rgb_image_from_channels(r, g, b)
        res = VisualExtractor.extract_bit_planes(img)
        assert res['is_visual_suspicious'] is False

    def test_statistics_computed_on_full_resolution_not_thumbnail(self):
        """
        Regression for the thumbnail/statistics conflation bug: a large
        image's balance statistics must match what is computed directly from
        its full-resolution array, not a resampled preview copy.
        """
        big = VisualExtractor.MAX_DISPLAY_DIMENSION + 200
        r = _perfectly_balanced_channel(big, big, seed=17)
        g = _biased_channel(big, big, seed=18, bias=0.15)
        b = _biased_channel(big, big, seed=19, bias=0.20)
        img = _rgb_image_from_channels(r, g, b)
        res = VisualExtractor.extract_bit_planes(img)

        # Independently recompute from the full-resolution source array.
        expected_density = float(np.mean((r & 1) == 1))
        expected_delta = abs(expected_density - 0.5)
        assert res['stats']['red_lsb_mean'] == pytest.approx(expected_density)
        assert res['min_balance_delta'] == pytest.approx(expected_delta, abs=1e-9)
