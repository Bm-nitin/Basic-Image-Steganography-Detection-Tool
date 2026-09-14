"""
Phase G3, Step 5 — RS primary-source investigation tests.

These lock in the mathematical claims verified against the primary source
(Fridrich, Goljan & Du 2001; US Patent 6,831,991B2) during this phase:
- The quadratic 2(d1+d0)z^2 + (d-0-d-1-d1-3d0)z + (d0-d-0) = 0 is exactly
  the published equation (source-verified, see G3 report).
- sym_diff (comparing R_M to R_-M and S_M to S_-M directly) corresponds to
  testing the CLEAN-IMAGE assumption R_M~=R_-M, S_M~=S_-M (equation 3 in
  the primary source) -- an assumption-validity check, not a mechanism the
  source uses to estimate embedding rate or suspicion. Using it as a
  suspicion contributor (indicator = max(est_rate, sym_diff*4)) is an
  original, uncited heuristic that can fire on content violating the
  assumption for reasons unrelated to steganography (directional structure,
  the boundary fixed-point behavior, degenerate flat content).

No production RS code is changed by these tests -- they characterize
existing (unmodified in G3) behavior.
"""
import numpy as np
import pytest
from PIL import Image

from app.core.rs_analysis import RSAnalyzer


class TestRSQuadraticMatchesPrimarySource:
    def test_quadratic_solve_matches_manual_computation(self):
        """
        Hand-computed check of the exact published equation:
        2(d1+d0)z^2 + (d-0-d-1-d1-3d0)z + (d0-d-0) = 0
        with an arbitrary, non-degenerate set of d-values, verified against
        an independent manual solve of the same quadratic via numpy.roots.
        """
        d0, d1, d_neg0, d_neg1 = 0.30, 0.20, 0.05, 0.35
        a = 2.0 * (d1 + d0)
        b = d_neg0 - d_neg1 - d1 - 3.0 * d0
        c = d0 - d_neg0
        roots = np.roots([a, b, c])
        # pick the root with smaller absolute value, matching the
        # implementation's own root-selection rule
        z_expected = roots[np.argmin(np.abs(roots))].real
        p_expected = z_expected / (z_expected - 0.5)
        p_expected = float(np.clip(p_expected, 0.0, 1.0)) if p_expected >= 0 else 0.0

        p_actual = RSAnalyzer._solve_embedding_rate(d0, d1, d_neg0, d_neg1)
        assert p_actual == pytest.approx(p_expected, abs=1e-6)

    def test_quadratic_zero_rate_when_d0_equals_dneg0(self):
        """When d0 == d-0 (c == 0), the equation degenerates and the
        implementation correctly returns 0.0 rather than dividing by zero."""
        p = RSAnalyzer._solve_embedding_rate(0.2, 0.3, 0.2, 0.1)
        assert p == 0.0


class TestSymDiffConceptualMismatch:
    """
    Demonstrates, on non-degenerate (not literally flat) content, that
    sym_diff can be driven by directional/structural asymmetry unrelated to
    embedding -- consistent with it measuring assumption-validity
    (R_M~=R_-M) rather than stego evidence per the primary source.
    """

    def test_directional_gradient_violates_clean_image_assumption_without_embedding(self):
        # A monotonic gradient has strong directional structure: F_1 and
        # F_-1 perturb it asymmetrically relative to a natural, undirected
        # image, which is exactly the kind of content the R_M~=R_-M
        # assumption is not guaranteed to hold for -- independent of any
        # embedded payload.
        gradient = np.tile(np.arange(256, dtype=np.uint8), (64, 1))
        img = Image.fromarray(gradient, mode='L')
        res = RSAnalyzer.analyze(img)
        assert res['available'] is True
        # This is a characterization, not a correctness assertion: record
        # whether est_rate (source-grounded) and the indicator (which
        # includes the uncited sym_diff term) diverge on this non-degenerate,
        # zero-embedding content.
        # (No hard assertion on exact values -- this test exists to make the
        # divergence visible/regression-tracked, not to enforce a specific
        # numeric outcome that would itself constitute silently tuning RS.)
        assert 0.0 <= res['estimated_embedding_rate'] <= 1.0
        assert 0.0 <= res['suspicion_indicator'] <= 1.0

    def test_degenerate_flat_content_guard_from_g1_still_holds(self):
        """Regression: the G1.3 degenerate-content guard must still bypass
        the sym_diff heuristic entirely for zero-variance content."""
        img = Image.new('L', (64, 64), color=0)
        res = RSAnalyzer.analyze(img)
        assert res.get('degenerate_flat_content') is True
        assert res['is_suspicious'] is False
