# Phase G1 — Correctness & Consistency Pass: Completion Report

Scope: G1.1 (visual threshold single source of truth), G1.2 (multiple-comparisons fix),
G1.3 (RS boundary audit). No scoring-system redesign, no ML, no threshold recalibration
based on individual example images. **G2 has NOT been implemented.**

---

## 1. Files Changed

| File | Change type |
|---|---|
| `app/core/visual_extractor.py` | Behavioral fix (G1.1, G1.2) + bug fix (thumbnail/statistics conflation) |
| `app/core/scoring.py` | Consistency fix (G1.1) — defers to authoritative decision |
| `app/core/evidence.py` | Consistency fix (G1.1) — defers to authoritative decision |
| `app/core/rs_analysis.py` | Documentation only for the flip formula (G1.3) + one new correctness fix (degenerate-content guard, discovered by the new regression tests) |
| `tests/test_g1_visual_threshold.py` | New — G1.1/G1.2 regression tests |
| `tests/test_g1_rs_boundary.py` | New — G1.3 regression tests |
| `tests/test_tampering.py` | One hardcoded baseline score updated (41.5 → 21.5), with inline explanation |

Nothing else was touched. Tampering independence, `evidence.py`/`explainability.py` separation, copy-move architecture, JPEG analyzer scope, API structure, frontend, and deployment config are all unmodified.

---

## 2. Exact Problem Fixed in Each File

### `app/core/visual_extractor.py`
1. **G1.1 — duplicated, disagreeing threshold.** Was `0.02` here vs `0.005` in `scoring.py`/`evidence.py`. Now a single `BASE_BALANCE_THRESHOLD = 0.005` class constant is the only place the base value is declared; the module computes and returns the actual `is_visual_suspicious` decision itself.
2. **G1.2 — multiple-comparisons problem.** Was: minimum delta-from-0.5 taken across 4 values (gray, red, green, blue) and compared to one threshold. Now: `gray` (a deterministic linear combination of R/G/B) is excluded from the decision pool; for genuinely grayscale-source images (R==G==B) the pool is 1 channel with no correction; for real color images the pool is {red, green, blue} (k=3) and the flagging threshold is Bonferroni-corrected to `BASE_BALANCE_THRESHOLD / k`.
3. **Bug found and fixed during this pass (not in the original P0 list, but directly in scope — "any values consumed by scoring.py"): statistics were computed on a Lanczos-resampled display thumbnail**, not the original image, for any upload over 800px. Resampling recomputes pixel values via interpolation and does not preserve the LSB plane, so the balance statistic silently measured interpolation artifacts on the majority of realistic uploads. Statistics are now computed from the full-resolution array; the thumbnail is used only for the rendered preview PNGs.

### `app/core/scoring.py` / `app/core/evidence.py`
G1.1 — both previously re-declared their own `0.005` literal independently of the detector. Both now import `VisualExtractor` and use its `is_visual_suspicious` decision when present, falling back to `VisualExtractor.BASE_BALANCE_THRESHOLD` only when given a bare `min_balance_delta` with no attached decision (this fallback path exists solely to keep pre-existing unit tests that construct synthetic partial dicts working, and is documented as such in both files).

### `app/core/rs_analysis.py`
- G1.3, as specified: **no functional change to `_flip_neg1`.** I verified the primary source (Fridrich, Goljan & Du: *F₋₁(x) = F₁(x+1) − 1*, pairs −1↔0, 1↔2, …, 255↔256) via web search rather than assuming. The current implementation's even/odd branching is parity-correct against that formula for every interior value. The formula's own pair partners at the boundary (−1 and 256) are outside the valid 8-bit range — a gap the paper itself doesn't resolve for practical images — and clipping to produce fixed points at 0/255 is the standard practical resolution, not a defect. This correction to my own earlier (unverified) audit finding is stated explicitly in the code docstring, citing the source.
- **A real, separate correctness bug was found by the new regression tests** (not the one originally flagged, and not a recalibration issue): a perfectly flat image (all pixels identical — e.g. all-black or all-white) was scored `is_suspicious = True` with `suspicion_indicator = 1.0`, despite `estimated_embedding_rate = 0.0`. Root cause, confirmed by direct computation: when every group has zero internal variation, the M-mask trivially classifies every group as "regular" (any flip increases the necessarily-zero discrimination value), while the -M mask does nothing at all specifically when pixel values are 0 or 255 (the boundary fixed point), producing a spurious `sym_diff` spike that saturates the (uncited, non-literature) `indicator = max(est_rate, sym_diff*4)` heuristic. This reproduces **only** at pixel values 0/255 — a mid-gray flat image (128) does not trigger it — confirming it is a boundary-handling issue in scope for G1.3, not a general threshold-tuning issue. Fix: when a channel's discrimination function is zero for every group (no natural texture at all, a condition independent of any specific real image and verifiable by definition), the channel is reported as `available: True`, `estimated_embedding_rate: 0.0`, `is_suspicious: False`, with a `degenerate_flat_content: True` flag, bypassing the uncited `sym_diff` heuristic entirely rather than attempting to patch its formula (which has no cited derivation — flagged for separate review, not invented a replacement here).

---

## 3. Mathematical/Algorithmic Reasoning

- **Bonferroni-style correction (G1.2):** dividing the single-test threshold by k (the number of pooled channels) is the standard, conservative first-order correction for controlling the family-wise false-positive rate when flagging on the minimum of k tests. It is generic — applied uniformly based on channel count, not fit to any sample — and conservative by construction, which is the appropriate choice given no calibration corpus exists yet (that's G2).
- **Excluding `gray` from the pool:** justified purely from the code itself — `gray = 0.299R + 0.587G + 0.114B` is a deterministic function of the other three channels, so it contributes no independent information to a "how many independent tests agree" argument, regardless of any statistical modeling assumption.
- **RS boundary handling:** justified by primary-source lookup, not memory or invention; the existing implementation was confirmed correct against the cited formula.
- **Degenerate-content guard:** justified definitionally — the discrimination function `f(G) = Σ|x_{i+1}-x_i|` is 0 for any group with no internal variation, by construction, independent of pixel value or embedding status; RS steganalysis has no basis to operate when there is no natural texture to perturb.

## 4. Tests Added

- `tests/test_g1_visual_threshold.py` — 22 tests: constant/import consistency, fallback-path parity between `scoring.py`/`evidence.py` and the base constant, end-to-end "detector and scoring cannot disagree" check, grayscale-vs-color pooling, the core multiple-comparisons regression (one coincidentally-balanced channel among biased others must not fire under the corrected threshold even though it would have under the old one), preserved single-channel and multi-channel genuine-embedding detection, and the full-resolution-vs-thumbnail statistics check.
- `tests/test_g1_rs_boundary.py` — 11 tests: `_flip_neg1` fixed-point behavior at 0/255, interior-value pairing correctness, range/dtype safety, and no-pathological-behavior checks across all-black, all-white, checkerboard, black-text-on-white, gradient, and the repo's own clean/stego samples.
- One existing test (`test_tampering.py::test_stego_eof_sample_with_jpeg_ela`) updated with an inline explanation rather than left silently broken.

None of the new tests assert against any specific real-world example (marksheet, landscape) — all use synthetic arrays or the repository's own existing controlled samples, per instruction.

## 5. Full Test Results

Environment note: this sandbox has no network access and pytest is not preinstalled, so I built a minimal pytest-compatible shim/runner (fixtures, parametrize, approx, raises, skip, tmp_path, monkeypatch) to execute the suite unmodified. Test *source files* were not altered to accommodate this, aside from the one intentional baseline-value update above.

```
TOTAL: passed=176 failed=0 skipped=1 errors=0
```

- 176 passed across all `tests/test_*.py` files, including every pre-existing test file (`test_detectors.py`, `test_rs_analysis.py`, `test_spa_analysis.py`, `test_jpeg_analysis.py`, `test_tampering.py`, `test_consistency.py`, `test_evidence.py`, `test_evaluation.py`, `test_routes.py`, `test_malformed_inputs.py`, `test_security_config.py`, `test_validation.py`, `test_file_forensics.py`, `test_ela_analysis.py`, `test_noise_analysis.py`, `test_copy_move_analysis.py`, `test_explainability.py`) plus the two new G1 files.
- 1 skipped: `test_live_http.py::test_live_workflow`, which requires a running local server on `127.0.0.1:5000` — not applicable in this environment, not related to G1.
- 0 failures, 0 collection/import errors.
- `tests/verify_samples.py`, `tests/independent_validation.py`, and `tests/check_security_hygiene.py` (the other "sample verification scripts") were also run directly and completed cleanly. `tests/verify_all.py` and `tests/check_remote_live.py` require a running live server and were not run.
- No warnings were introduced by this phase's changes. (One pre-existing, unrelated `PIL.DecompressionBombWarning` from a malformed-input test appears in both before/after runs.)

## 6. Existing Sample Results — Before / After

Run via `tests/independent_validation.py` against the repository's own 11 ground-truth samples:

| Sample | Ground truth | Stego score before | Stego score after | Changed? |
|---|---|---|---|---|
| clean_sample.png | clean | 0.0 | 0.0 | No (score unchanged; underlying visual delta changed from 0.0295→0.1371, see note) |
| clean_carrier.png | clean | 0.0 | 0.0 | No |
| clean_carrier.jpg | clean | 7.5 | 7.5 | No |
| stego_lsb_low.png | stego | 26.5 | 26.5 | No |
| stego_lsb_medium.png | stego | 26.5 | 26.5 | No |
| stego_lsb_high.png | stego | 70.0 | 70.0 | No |
| stego_lsb_sample.png | stego | 70.0 | 70.0 | No |
| **stego_eof_sample.jpg** | stego | **41.5** | **21.5** | **Yes** |
| stego_eof.jpg | stego | 27.5 | 27.5 | No |
| tamper_copymove.png | tampering | 85.0 (tamper score) | 85.0 | No |
| tamper_spliced_noise.png | tampering | 47.2 (tamper score) | 47.2 | No |

All samples remain correctly classified on the right side of ground truth after the change (all stego samples still land Medium/High, all clean samples still Low, both tampering samples still flagged). No true positive was lost and no clean sample flipped to a false positive in this specific 11-sample set — but this is not evidence of general accuracy; it's the expected, narrow, mechanical effect of the specific fix described below, on the only samples that happen to exist in this repository. It does not validate the fix against the classes of image (screenshots, documents, flat graphics) that the original audit's marksheet/landscape false positives actually came from — that validation requires the G2 corpus, which has deliberately not been built in this phase.

**Why `stego_eof_sample.jpg` changed:** its visual-balance delta is `0.00353`. That clears the old, uncorrected single-channel-style threshold (`0.005`) — which is why it previously received a spurious +20 "Visual" category points — but does not clear the new, corrected 3-independent-channel threshold (`0.005/3 ≈ 0.00167`), since it's a genuine RGB image and `gray` is excluded from the pool. This is the multiple-comparisons fix (G1.2) operating exactly as intended on a real sample, not an arbitrary re-tuning: the sample's ground truth is "stego via appended EOF trailing data," not "stego via LSB replacement," so it never should have been flagged by the LSB-parity detector in the first place — its score is still correctly Medium overall (driven by the trailing-data and entropy detectors, which are unaffected by this change) and still correctly lands on the stego side of ground truth.

**Note on the unaffected clean sample:** `clean_sample.png`'s reported visual delta changed from `0.0295` to `0.1371` between runs even though the final score (0.0) didn't move. This is because the old 4-channel pool's minimum happened to be the derived `gray` value, which is now correctly excluded from the pool; the new minimum is the smallest of the three genuinely independent R/G/B deltas. Both values were always far above any relevant threshold, so this is a diagnostic-transparency change only, not a scoring change, for this sample.

## 7. Remaining Uncertainty

- The RS `sym_diff` / `indicator = max(est_rate, sym_diff*4)` heuristic that the degenerate-content guard bypasses in the zero-variance case is itself **uncited and not part of the primary RS literature** (only the quadratic-solve `est_rate` path is). It is not otherwise touched in this phase — this is flagged as a finding for a dedicated review, not patched further here, since doing so would risk exactly the kind of ad hoc formula invention this phase was told to avoid.
- The Bonferroni-style `/k` correction is a standard, conservative, generic choice, but its exact effect on true/false positive rates across real image classes is **not validated** — that requires the G2 corpus. I have not claimed an accuracy improvement; the "before/after" table above is a mechanical trace, not a validation study.
- I could not run this against a real `pytest` (no network access to install it in this sandbox); I built a compatible minimal shim instead. I'm confident in its fidelity for the fixture/parametrize/approx/raises/skip/tmp_path/monkeypatch subset actually used by this suite, but it is not a substitute for running the genuine `pytest` in your own environment before merging — I'd recommend doing that as a final check.
- `ela_analysis.py`, `noise_analysis.py`, `local_variance_analysis.py`, and `edge_analysis.py` were exercised by the test suite (all passing) but were not re-audited line-by-line in this phase — unchanged from the original audit's scope note.

## 8. Confirmation

**G2 has NOT been implemented.** No evaluation corpus was built or modified; `tests/evaluation/sample_generator.py` and `tests/evaluation/evaluator.py` are untouched. No thresholds were tuned against the marksheet, landscape, or any other anecdotal real-world image — the one score that changed (`stego_eof_sample.jpg`) changed as a side effect of a generic, sample-independent correctness fix, verified against the repository's own existing ground-truth sample, not chosen to produce that result.
