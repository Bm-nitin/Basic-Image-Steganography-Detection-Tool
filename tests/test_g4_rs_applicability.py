"""
Phase G4, Target A — regression tests for separating RS applicability
diagnostic (sym_diff) from embedding evidence (estimated_embedding_rate /
suspicion_indicator).

No RS mathematical formula (discrimination function, flip operations,
quadratic solve) is changed by this fix -- these tests verify the
separation itself, not a re-derivation of the math (already covered by
test_g3_rs_investigation.py, which continues to pass unchanged).
"""
import os
import numpy as np
import pytest
from PIL import Image

from app.core.rs_analysis import RSAnalyzer


class TestRSSymDiffRemainsAvailable:
    def test_sym_diff_field_present_on_normal_image(self):
        gradient = np.tile(np.arange(256, dtype=np.uint8), (64, 1))
        img = Image.fromarray(gradient, mode='L')
        res = RSAnalyzer.analyze(img)
        assert 'sym_diff' in res
        assert 'rs_applicability_diagnostic' in res
        assert res['sym_diff'] >= 0.0
        assert 0.0 <= res['rs_applicability_diagnostic'] <= 1.0

    def test_applicability_diagnostic_present_on_degenerate_flat_content(self):
        img = Image.new('L', (64, 64), color=0)
        res = RSAnalyzer.analyze(img)
        assert res.get('degenerate_flat_content') is True
        assert res['sym_diff'] == 0.0
        assert res['rs_applicability_diagnostic'] == 0.0


class TestApplicabilityNotConfusedWithEmbeddingEvidence:
    def test_suspicion_indicator_equals_estimated_rate(self):
        rng = np.random.RandomState(42)
        arr = rng.randint(0, 256, (80, 80), dtype=np.uint8)
        img = Image.fromarray(arr, mode='L')
        res = RSAnalyzer.analyze(img)
        assert res['suspicion_indicator'] == pytest.approx(res['estimated_embedding_rate'], abs=1e-9)

    def test_high_applicability_diagnostic_with_zero_embedding_does_not_inflate_indicator(self):
        gradient = np.tile(np.arange(256, dtype=np.uint8), (64, 1))
        img = Image.fromarray(gradient, mode='L')
        res = RSAnalyzer.analyze(img)
        assert res['suspicion_indicator'] == pytest.approx(res['estimated_embedding_rate'], abs=1e-9)

    def test_channel_level_separation_holds_per_channel(self):
        gradient = np.tile(np.arange(256, dtype=np.uint8), (64, 1)).astype(np.uint8)
        ch = RSAnalyzer._analyze_channel(gradient)
        assert ch['suspicion_indicator'] == pytest.approx(ch['estimated_embedding_rate'], abs=1e-9)
        assert 'rs_applicability_diagnostic' in ch


class TestExistingRSBehaviorIntact:
    def test_strong_embedding_still_flagged(self):
        path = os.path.join(os.path.dirname(__file__), 'test_samples', 'stego_lsb_sample.png')
        img = Image.open(path)
        res = RSAnalyzer.analyze(img)
        assert res['estimated_embedding_rate'] > 0.40
        assert res['suspicion_indicator'] > 0.40
        assert res['is_suspicious'] is True

    def test_clean_sample_still_not_flagged(self):
        path = os.path.join(os.path.dirname(__file__), 'test_samples', 'clean_sample.png')
        img = Image.open(path)
        res = RSAnalyzer.analyze(img)
        assert res['is_suspicious'] is False

    def test_valid_images_do_not_break(self):
        for mode, arr in [
            ('L', np.random.RandomState(1).randint(0, 256, (100, 100), dtype=np.uint8)),
            ('RGB', np.random.RandomState(2).randint(0, 256, (100, 100, 3), dtype=np.uint8)),
        ]:
            img = Image.fromarray(arr, mode=mode)
            res = RSAnalyzer.analyze(img)
            assert res['available'] is True
            assert 0.0 <= res['estimated_embedding_rate'] <= 1.0
            assert 0.0 <= res['suspicion_indicator'] <= 1.0
            assert 0.0 <= res['rs_applicability_diagnostic'] <= 1.0

    def test_boundary_behavior_intact_checkerboard(self):
        checker = (np.indices((64, 64)).sum(axis=0) % 2 * 255).astype(np.uint8)
        img = Image.fromarray(checker, mode='L')
        res = RSAnalyzer.analyze(img)
        assert res['available'] is True
        assert not np.isnan(res['estimated_embedding_rate'])
        assert not np.isnan(res['suspicion_indicator'])
        assert not np.isnan(res['rs_applicability_diagnostic'])


class TestScoringAndEvidenceConsumeCorrectedIndicatorWithoutCodeChange:
    def test_scoring_no_longer_over_scores_from_applicability_alone(self):
        from app.core.scoring import SuspicionScoringEngine
        gradient = np.tile(np.arange(256, dtype=np.uint8), (64, 1))
        img = Image.fromarray(gradient, mode='L')
        rs_res = RSAnalyzer.analyze(img)

        meta = {'metadata': {}}
        visual = {'min_balance_delta': 1.0}
        stat = {
            'chi_square': {'max_indicator': 0.0},
            'entropy': {'lsb_entropy': {'max': 0.0}},
            'spa_analysis': {'estimated_embedding_rate': 0.0},
            'rs_analysis': rs_res,
            'jpeg_analysis': {'available': False, 'reason': 'not_jpeg'},
            'channel_analysis': {'channel_anomaly_indicator': 0.0}
        }
        score_res = SuspicionScoringEngine.evaluate(meta, visual, stat)
        rs_row = next(d for d in score_res['detector_breakdown'] if 'RS Steganalysis' in d['detector'])
        if rs_res['estimated_embedding_rate'] <= 0.25:
            assert rs_row['points_added'] == 0.0
