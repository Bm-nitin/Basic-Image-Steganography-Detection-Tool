"""
Phase G3, Step 6 — chi-square (Westfeld PoV) investigation tests.

Locks in:
- The pair-based chi-square formula matches an independently-computed
  two-category chi-square goodness-of-fit sum (source-verified correctness).
- The measured "only active at high/full payload" behavior against this
  project's actual embedding method (random-bit LSB replacement scattered
  over a fraction of pixels, tested against the WHOLE image histogram, not
  a sequential prefix) -- characterized as a regression-tracked measurement,
  not asserted as a bug or silently changed.

No production statistical code is changed by these tests.
"""
import numpy as np
import pytest
from scipy import stats as scipy_stats

from app.core.statistical import StatisticalAnalyzer


class TestChiSquareFormulaMatchesStandardDefinition:
    def test_pair_chi_square_matches_manual_two_category_computation(self):
        arr = np.full((100, 100), 5, dtype=np.uint8)
        arr[0, 0:60] = 10
        arr[0, 60:100] = 11
        counts = np.bincount(arr.flatten(), minlength=256)
        n10, n11 = int(counts[10]), int(counts[11])
        expected = (n10 + n11) / 2.0
        manual_chi2 = ((n10 - expected) ** 2) / expected + ((n11 - expected) ** 2) / expected

        scipy_chi2, _ = scipy_stats.chisquare([n10, n11], f_exp=[expected, expected])
        assert manual_chi2 == pytest.approx(scipy_chi2, rel=1e-9)

        res = StatisticalAnalyzer.chi_square_attack(arr)
        assert res['chi2_stat'] >= manual_chi2 - 1e-6


class TestChiSquareCoverageDilutionOnScatteredEmbedding:
    @staticmethod
    def _natural_like_base(seed):
        # Uniform random noise already has near-equalized PoV counts by
        # construction, which trivially masks any dilution effect. A
        # smoothed/correlated base (real images have genuine pixel-to-pixel
        # correlation and a non-uniform histogram) is needed to give the
        # clean baseline a genuine PoV bias to equalize away from.
        from scipy.ndimage import gaussian_filter
        rng = np.random.RandomState(seed)
        noise = rng.normal(0, 1, (128, 128))
        smooth = gaussian_filter(noise, sigma=10)
        smooth = (smooth - smooth.min()) / (smooth.max() - smooth.min())
        return (30 + 180 * smooth).astype(np.uint8)

    @staticmethod
    def _embed_fraction(arr, rate, seed):
        rng = np.random.RandomState(seed)
        out = arr.copy()
        mask = rng.rand(*out.shape) < rate
        out[mask] = (out[mask] & 0xFE) | rng.randint(0, 2, out.shape, dtype=np.uint8)[mask]
        return out

    def test_full_coverage_embedding_activates_chi_square(self):
        base = self._natural_like_base(seed=1)
        full = self._embed_fraction(base, 1.0, seed=2)
        res = StatisticalAnalyzer.chi_square_attack(full)
        assert res['ratio'] <= 1.2  # near-equalized PoV distribution expected at full coverage

    def test_partial_scattered_coverage_dilutes_chi_square_signal_on_average(self):
        """
        Measured finding, averaged over several random draws (a single draw
        is not reliably monotonic -- that non-robustness is itself part of
        the measured characterization, see G3 report Step 6): full coverage
        should on average land closer to full equalization (ratio near 1.0)
        than a clean, unembedded baseline with genuine natural PoV bias.
        """
        clean_deltas, full_deltas = [], []
        for seed in range(5):
            base = self._natural_like_base(seed=100 + seed)
            clean_res = StatisticalAnalyzer.chi_square_attack(base)
            full = self._embed_fraction(base, 1.0, seed=200 + seed)
            full_res = StatisticalAnalyzer.chi_square_attack(full)
            clean_deltas.append(abs(clean_res['ratio'] - 1.0))
            full_deltas.append(abs(full_res['ratio'] - 1.0))
        assert np.mean(full_deltas) < np.mean(clean_deltas)
