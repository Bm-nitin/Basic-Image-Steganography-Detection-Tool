"""
Phase G3, Step 4 — copy-move regression tests.

Covers the 10 scenarios required by the G3 spec. Where a false positive is
KNOWN to remain unresolved after the G3 fix (documented explicitly in the G3
report's Limitations section), the test asserts the actual, current,
measured behavior with a comment explaining why -- not a hoped-for result.
This is deliberate: silently asserting the "wrong" (still-buggy) behavior
without explanation would hide a regression; asserting a fixed-but-untrue
behavior would misrepresent the fix. Both are avoided here.
"""
import numpy as np
import pytest
from PIL import Image

from app.core.copy_move_analysis import CopyMoveAnalyzer
from tests.evaluation.g2_corpus_generator import (
    build_photograph_proxy, build_document_proxy, build_screenshot_proxy,
    build_illustration_proxy, build_repeated_structure_proxy, apply_copy_move,
)
from tests.evaluation.g3_corpus_generator import (
    _prep_real_image, apply_copy_move_multi, apply_weak_copy_move,
)
from skimage import data as skdata


class TestCopyMoveCleanContentNotFlagged:
    """Scenarios 1-5: clean content across carrier types."""

    def test_1_clean_photograph_not_flagged(self):
        img = _prep_real_image(skdata.coffee())
        res = CopyMoveAnalyzer.analyze(img)
        assert res['is_suspicious'] is False

    def test_2_clean_document_real_not_flagged(self):
        img = _prep_real_image(skdata.page())
        res = CopyMoveAnalyzer.analyze(img)
        assert res['is_suspicious'] is False

    def test_2b_clean_document_synthetic_now_fixed(self):
        """
        G2 found this synthetic document-proxy clean sample flagged
        (cluster_count=17, indicator=1.0). The G3 periodicity guard fixes
        this specific case (17 clusters is far above the 8-cluster cap).
        """
        img = build_document_proxy()
        res = CopyMoveAnalyzer.analyze(img)
        assert res['is_periodic_like'] is True
        assert res['is_suspicious'] is False

    def test_3_clean_screenshot_not_flagged(self):
        img = build_screenshot_proxy()
        res = CopyMoveAnalyzer.analyze(img)
        assert res['is_suspicious'] is False

    def test_4_clean_illustration_real_checkerboard_now_fixed(self):
        """Extreme periodic case (41 clusters) -- the G3 fix's primary target."""
        img = _prep_real_image(skdata.checkerboard())
        res = CopyMoveAnalyzer.analyze(img)
        assert res['is_periodic_like'] is True
        assert res['is_suspicious'] is False

    def test_4b_clean_illustration_synthetic_KNOWN_UNRESOLVED_false_positive(self):
        """
        KNOWN LIMITATION (see G3 report, Section 10): this sample has only
        1 cluster / 8 clustered blocks -- well below the periodicity guard's
        caps (8 clusters / 50 blocks), because it sits in the same small-
        magnitude range as the corpus's only confirmed genuine small-scale
        copy-move positive (10 blocks). The G3 fix deliberately does not
        touch this range to avoid risking that true positive on the
        evidence available. This test documents the current, unresolved
        behavior rather than hiding it.
        """
        img = build_illustration_proxy()
        res = CopyMoveAnalyzer.analyze(img)
        assert res['is_suspicious'] is True
        assert res['is_periodic_like'] is False

    def test_5_repeated_legitimate_structure_real_textures_not_flagged(self):
        """
        Real, naturally-repeating textures (brick/grass/gravel) -- the
        strongest, most realistic version of the "repeated legitimate
        structure" probe. None trigger copy_move at all (cluster_count=0),
        distinct from the synthetic repeated-structure/illustration cases.
        """
        for loader in [skdata.brick, skdata.grass, skdata.gravel]:
            img = _prep_real_image(loader())
            res = CopyMoveAnalyzer.analyze(img)
            assert res['is_suspicious'] is False, f"{loader.__name__} incorrectly flagged"

    def test_5b_repeated_structure_synthetic_KNOWN_UNRESOLVED_false_positive(self):
        """
        KNOWN LIMITATION, same reasoning as test_4b: 1 cluster / 5 blocks,
        below the periodicity guard's caps. Documented, not hidden.
        """
        img = build_repeated_structure_proxy()
        res = CopyMoveAnalyzer.analyze(img)
        assert res['is_suspicious'] is True
        assert res['is_periodic_like'] is False


class TestCopyMoveGenuinePositivesPreserved:
    """Scenarios 6-7: genuine copy-move must still be detected (sensitivity check)."""

    def test_6_genuine_copy_move_single_region_still_detected(self):
        """
        The ONE confirmed genuine small-scale copy-move positive in the G3
        corpus. This must remain detected after the fix -- it is the primary
        sensitivity check for this change.
        """
        img = _prep_real_image(skdata.coffee())
        tampered = apply_copy_move(img, 'regression_test_cm_single', block=48)
        res = CopyMoveAnalyzer.analyze(tampered)
        assert res['is_periodic_like'] is False
        assert res['is_suspicious'] is True

    def test_7_genuine_copy_move_multiple_regions_KNOWN_PREEXISTING_miss(self):
        """
        KNOWN LIMITATION, NOT introduced by the G3 fix (verified against the
        pre-fix baseline in tests/evaluation/g3_results/g3_before_fix_results.json,
        where this same sample was already undetected: cluster_count=0).
        Root cause (see G3 report): each of the 3 scattered 40x40 regions
        individually produces too few grid-aligned 16x16 sub-blocks to reach
        the existing (pre-G3, unchanged) >=3-blocks-per-cluster significance
        floor. This is a real, pre-existing sensitivity gap for multi-region
        forgeries with small individual region sizes -- documented here so a
        future change cannot silently regress it further without notice.
        """
        img = _prep_real_image(skdata.rocket())
        tampered, n_placed = apply_copy_move_multi(img, 'regression_test_cm_multi', block=40, n_regions=3)
        assert n_placed == 3  # sanity: the forgery itself was applied correctly
        res = CopyMoveAnalyzer.analyze(tampered)
        assert res['is_suspicious'] is False  # documents the current miss, not a desired outcome

    def test_8_weak_insufficient_match_correctly_not_flagged(self):
        """A deliberately tiny (10px) clone -- below reasonable detection capability."""
        img = _prep_real_image(skdata.chelsea())
        tampered = apply_weak_copy_move(img, 'regression_test_cm_weak', block=10)
        res = CopyMoveAnalyzer.analyze(tampered)
        assert res['is_suspicious'] is False


class TestCopyMoveImageSizeEdgeCases:
    """Scenarios 9-10: tiny and large images must not crash and must behave sanely."""

    def test_9_tiny_image_does_not_crash(self):
        img = _prep_real_image(skdata.coffee()).resize((32, 32), Image.LANCZOS)
        res = CopyMoveAnalyzer.analyze(img)
        assert 'available' in res
        # A 32x32 image with 16x16 blocks and 32px min-separation has almost
        # no room for two sufficiently-separated blocks; it should not crash
        # and should not spuriously flag.
        if res['available']:
            assert res['is_suspicious'] is False

    def test_10_large_image_does_not_crash_and_completes(self):
        img = _prep_real_image(skdata.coffee()).resize((1024, 1024), Image.LANCZOS)
        res = CopyMoveAnalyzer.analyze(img)
        assert 'available' in res
        assert res['is_suspicious'] is False


class TestCopyMoveFixDoesNotChangeUnrelatedDetectors:
    """The fix must be scoped to copy_move only -- no accidental cross-detector changes."""

    def test_return_schema_is_additive_only(self):
        img = _prep_real_image(skdata.coffee())
        res = CopyMoveAnalyzer.analyze(img)
        required_keys = {'available', 'total_blocks', 'candidate_matches', 'cluster_count',
                          'anomaly_indicator', 'is_suspicious', 'matches', 'details'}
        assert required_keys.issubset(res.keys())
        assert 'is_periodic_like' in res  # new field, additive

    def test_periodicity_guard_constants_are_class_attributes(self):
        assert hasattr(CopyMoveAnalyzer, 'MAX_CLUSTERS_BEFORE_PERIODICITY')
        assert hasattr(CopyMoveAnalyzer, 'MAX_CLUSTERED_BLOCKS_BEFORE_PERIODICITY')
        assert CopyMoveAnalyzer.MAX_CLUSTERS_BEFORE_PERIODICITY > 3  # above every ambiguous case observed
        assert CopyMoveAnalyzer.MAX_CLUSTERS_BEFORE_PERIODICITY < 15  # below every extreme case observed
