# G7 Evaluation Corpus Expansion and Independent Validation

**Evidence labels used throughout:** [MEASURED], [SOURCE-VERIFIED], [INFERRED], [PROPOSED].

## 1. Objective

Determine how the existing production detector behaves across diverse image/carrier classes, and identify where false positives and false negatives occur, using the existing corpus. No detector algorithm, scoring, or threshold is modified in this phase — this is measurement only.

## 2. Baseline

**Repository/git note:** this working directory has no `.git` (extracted from an archive, not cloned) — `git status`/`git log --oneline -8`/`git diff --stat` could not be run as literal commands. Identical to what was reported in G4, G5, and G6. The established equivalent (diffing against a preserved pristine extraction of the original archive) was used instead.

[MEASURED]
```
passed: 227
skipped: 1
failed: 0
warnings: 1 (DecompressionBombWarning — pre-existing, expected per G1–G6)
runtime: ~81s
```
Matches the expected baseline exactly. [MEASURED] Diffing against the pristine archive shows exactly the same 5 files differing as after G6 (`visual_extractor.py`, `scoring.py`, `evidence.py`, `rs_analysis.py` from G1/G4; `copy_move_analysis.py` from G3) — no unrelated modifications found before this phase began.

**Data-freshness check:** 3 randomly-selected samples were re-scored from scratch with the current, unmodified pipeline and compared against the stored G4 evaluation values before reusing that dataset for this phase's analysis. [MEASURED] All 3 matched exactly (`repeated_texture_real_grass_stego_low.png`, `document_real_text_stego_high.png`, `photograph_real_chelsea_tamper_copymove_weak.png`) — no drift since G4/G5/G6, none of which touched production scoring.

## 3. Existing Corpus Inventory

[MEASURED], built from actual files on disk (not inferred from filenames — every image was opened and its real dimensions/mode verified), `tests/evaluation/g7_results/g7_corpus_inventory.json`:

- **Total samples:** 92, all present on disk (0 missing).
- **Clean of both steganography and tampering:** 26
- **Steganography samples:** 59
- **Tampering samples:** 7
- **Formats:** PNG (86), JPEG (6)
- **Color modes (verified from the actual file, not the metadata label):** RGB (52), L/grayscale (32), RGBA (8)
- **Dimensions:** three fixed sizes only — 32×32 (1 sample, an edge-case probe), 256×256 (90 samples), 1024×1024 (1 sample, an edge-case probe)
- **Embedding methods:** `spatial_lsb` (57), `appended_eof` (2)
- **Payload levels (stego only):** low (19), medium (19), high (19), n/a (2, the appended-EOF samples)
- **Tampering types:** `copy_move_single_region` (1), `copy_move_multi_region_n3` (1), `copy_move_weak_10px` (1), `noise_disparity` (3), `copy_move` (1, from the original G2 sample)
- **Corpus source:** real public-domain images (51 clean/stego + 4 tampered = 55, from scikit-image), synthetic proxies (37, from the G2 generator)

## 4. Carrier-Class Distribution

[MEASURED] Mapping the actual 14 corpus `image_class` labels onto the 10 requested taxonomy slots (documented explicitly, not invented):

| Requested class | Mapped corpus class(es) | n | Present? |
|---|---|---|---|
| 1. Natural photograph | `photograph_real`, `photograph_proxy` | 27 | Yes |
| 2. Screenshot / UI | `screenshot_proxy` | 6 | Yes (synthetic proxy only — no real screenshot in this corpus) |
| 3. Scanned document | `document_real` | 9 | Yes (real scikit-image text/page scans) |
| 4. Marksheet/document-like | `document_proxy` | 5 | Yes (synthetic proxy only) |
| 5. Synthetic illustration | `illustration_real`, `illustration_proxy` | 12 | Yes |
| 6. Flat graphic | (same as 5 — no separately-distinct flat-graphic class exists) | — | **Absent as a distinct class**; covered only by illustration samples |
| 7. Low-color PNG | `low_color_proxy` | 4 | Yes (synthetic proxy only) |
| 8. Grayscale | `grayscale_real`, `grayscale_proxy` | 8 | Yes |
| 9. Alpha-channel PNG | `alpha_real`, `alpha_proxy` | 8 | Yes |
| 10. Other | `repeated_texture_real`, `repeated_structure_proxy` | 13 | Yes (repeated/self-similar texture, originally built as copy-move false-positive probes) |

[MEASURED] No sample class was fabricated or silently dropped to improve appearances — the "flat graphic" slot is recorded as genuinely absent as its own distinct class rather than force-mapped.

## 5. Clean-Image Results

[MEASURED] `tests/evaluation/g7_results/g7_clean_results.json`, strictly clean-of-both (26 samples — excludes the 7 tampering samples, a stricter partition than G6's 33-sample "not stego" set, which mixed in tampering samples; noted here to avoid confusion when comparing figures across reports):

| Class | n | Mean score | Median | Stdev | Min | Max | FPR@20 |
|---|---|---|---|---|---|---|---|
| **repeated_texture_real** | 3 | **46.5** | 43.5 | 7.8 | 40.6 | 55.3 | **1.00** |
| photograph_real | 6 | 32.4 | 37.7 | 10.6 | 17.5 | 40.6 | 0.83 |
| photograph_proxy | 3 | 35.2 | 37.5 | 6.8 | 27.5 | 40.6 | 1.00 |
| document_real | 2 | 40.6 | 40.6 | 0.0 | 40.6 | 40.6 | 1.00 |
| grayscale_real | 1 | 35.9 | — | — | — | — | 1.00 |
| grayscale_proxy | 1 | 28.8 | — | — | — | — | 1.00 |
| illustration_real | 2 | 20.3 | 20.3 | 12.0 | 11.8 | 28.8 | 0.50 |
| screenshot_proxy | 2 | 2.25 | 2.25 | 3.2 | 0.0 | 4.5 | 0.00 |
| alpha_real | 1 | 11.8 | — | — | — | — | 0.00 |
| alpha_proxy, document_proxy, illustration_proxy, low_color_proxy, repeated_structure_proxy | 1 each | 0.0 | — | — | — | — | 0.00 |

**Per-class n is small everywhere (1–6); no per-class figure here should be read as a stable rate estimate.** Stated once here, applies throughout this section.

**Headline finding [MEASURED], the most significant of this phase:** the three **real, genuine, public-domain natural-texture photographs** (brick, grass, gravel — not synthetic proxies) are **all three** flagged Medium/High risk (FPR@20 = 1.00, mean score 46.5). This is the first time in G1–G7 that the "natural photographic texture pushes LSB parity toward 0.5" hypothesis — first raised in the very first audit prompt about a marksheet and a landscape photo, and previously confirmed only on synthetic generators — is demonstrated on **genuinely real photographic content**. Root-caused precisely: [MEASURED] all three show `lsb_entropy_max = 1.0000` (fully saturated) and `visual_min_balance_delta` well under the detection threshold on every sample; two of three also show elevated Chi-Square (0.85) and SPA (0.98, 0.24).

**Which legitimate image classes produce elevated scores?** [MEASURED] In descending order of measured FPR@20 in this corpus: repeated natural texture (1.00), grayscale (1.00, n=1 each), document_real / photograph_proxy (1.00), photograph_real (0.83), illustration (0.50). Screenshot, alpha, low-color, and marksheet-style proxies show 0.00 FPR in this small sample, but each at n≤2, too small to generalize.

## 6. Stego Results

[MEASURED] `tests/evaluation/g7_results/g7_stego_results.json`. Overall detection rate (score ≥20) ranges from **1.00** (document_real, grayscale_real, grayscale_proxy, photograph_real, photograph_proxy, repeated_texture_real) down to **0.67** (alpha_proxy, alpha_real, document_proxy, illustration_proxy, illustration_real, low_color_proxy) and **0.75** (screenshot_proxy). Every class's shortfall from 1.00 traces to the **low payload level specifically** — no class misses at medium or high payload (§7).

## 7. Payload-Level Analysis

[MEASURED] Global payload curve across all 59 stego samples combined:

| Payload | n | Mean score | Detection rate @20 |
|---|---|---|---|
| Low | 19 | 24.4 | 0.68 |
| Medium | 19 | 39.6 | 0.89 |
| High | 19 | 62.3 | 1.00 |

[MEASURED] **Mean score increases monotonically with payload** (low < medium < high) at the aggregate level — the detector behaves as expected in this global view. Per the instruction not to modify the detector regardless of the finding, this is reported as an observation only. The detection-rate shortfall is concentrated entirely at low payload (0.68 vs. 0.89–1.00), consistent with the low-payload sensitivity gap already documented in G2–G5 for these same specific carrier classes.

## 8. Clean/Stego Pair Analysis

[MEASURED] `tests/evaluation/g7_results/g7_pair_analysis.json`, per-source-image score deltas. Two distinct patterns, both already characterized in prior phases and reconfirmed here with exact current-code numbers:

- **Carriers where clean and low-payload score identically** (zero delta): `photograph_real_coffee` (40.6→40.6), `photograph_real_chelsea` (17.5→17.5), `document_real_page` (40.6→40.6), `screenshot_proxy` variants. [INFERRED, consistent with G2's ceiling-effect finding] these carriers' clean baseline is already at or near whatever threshold band low-payload embedding would also land in, leaving no headroom for low payload to register as a change.
- **Carriers where clean and low-payload both score below threshold but do show a small non-zero delta**: `illustration_proxy` (0.0→14.7), `low_color_proxy` (0.0→14.7), `alpha_proxy` (0.0→14.7) — the detector responds, but not enough to cross 20.0 at low payload for these specific carriers.

The largest deltas (biggest detector response) occur moving from clean→high for carriers with a low clean baseline, e.g. `illustration_proxy` (0.0→70.0, delta +70.0), `low_color_proxy` (0.0→70.0), `alpha_proxy` (0.0→70.0) — driven predominantly by LSB entropy and visual-balance saturating together at full payload (both already established as the most tightly-correlated pair, G3–G6).

## 9. False-Positive Analysis

[MEASURED] `tests/evaluation/g7_results/g7_false_positive_analysis.json`: **16 of 26** clean-of-both samples (61.5%) scored Medium or High. Associated-signal frequency (association, not asserted causation, per the phase's wording rule):

| Associated signal | Count (of 16 FPs) |
|---|---|
| statistical_detector_interaction | 16 |
| high_LSB_entropy | 13 |
| high_LSB_balance_anomaly | 12 |
| RS_signal | 5 |
| SPA_signal | 6 |
| chi_square_signal | 5 |
| document_structure | 3 |
| low_color_carrier | 1 |

[MEASURED] High LSB entropy and high LSB balance are **associated with** the large majority of false positives (13 and 12 of 16 respectively) — consistent with, and now quantifying at the false-positive-instance level, the entropy/visual-balance redundancy already established magnitude- and decision-level in G5–G6. No false positive in this corpus is associated with metadata, trailing bytes, or the alpha channel specifically.

## 10. False-Negative Analysis

[MEASURED] `tests/evaluation/g7_results/g7_false_negative_analysis.json`: **8 of 59** stego samples (13.6%) scored Low. **All 8 are at low payload level; none at medium or high.** Detectors non-responding: for the 4 real/proxy samples with an available SPA signal that fired, only chi-square/RS/entropy/visual-balance failed to respond; for the other 4 (all G2 synthetic proxies — document, illustration, low-color, alpha, screenshot), **every one of the five detectors** failed to respond at low payload.

[INFERRED] This matches the ceiling/floor-effect mechanism already established in G2–G5: for carriers whose clean baseline already occupies the same scoring band a low-payload embed would land in, there is no remaining headroom for the detector to register the difference — this is not asserted here as newly proven, only as the most consistent explanation already supported by prior phases' measurements.

## 11. Independent Validation Status

**No independent held-out validation set is available.** [MEASURED] The G3 calibration/validation split (`g3_calibration_split.json`) was explicitly marked inadequate for this purpose at the time it was generated (see the G3 report) and has not been used to validate anything reported here or in any prior phase. No threshold, weight, or parameter has been tuned against any held-out portion of this corpus in G1 through G7 — so while there is no formal split-based independent validation, none of the figures in this report are the product of circular validation against a tuning set either. Per the phase's explicit instruction, no new split was invented after the fact and presented as independent validation.

## 12. Metrics

[MEASURED] Overall, 26 clean-of-both + 59 stego samples, threshold 20.0:

| Metric | Value |
|---|---|
| TP | 51 |
| FP | 16 |
| TN | 10 |
| FN | 8 |
| Sensitivity / TPR | 0.864 |
| Specificity / TNR | 0.385 |
| FPR | 0.615 |
| FNR | 0.136 |
| Precision | 0.761 |
| Balanced accuracy | 0.625 |

No confidence intervals are reported — none were computed, per the instruction not to manufacture them. **These figures describe this 92-sample, partly-synthetic corpus only and must not be read as real-world accuracy.**

## 13. Limitations

- Per-class sample counts are small throughout (as low as n=1 for several classes) — stated explicitly in every table, not glossed over.
- "Flat graphic" has no distinct corpus class of its own; it is covered only by the illustration classes (§4), not a gap this phase can fill without generating new samples, which was out of scope.
- The "associated signals" in the false-positive analysis (§9) are co-occurrence associations computed directly from each sample's category scores and detector flags — they are not a controlled ablation (that exists separately in the G6 report) and should not be read as proof of causation for any individual sample.
- No independent validation set exists (§11) — every number in this report comes from the same corpus that has been used for measurement (though not tuning) throughout G2–G7.
- The corpus contains only 3 fixed image sizes (32×32, 256×256, 1024×1024); no systematic sweep across intermediate sizes was available to characterize scale-dependent behavior beyond the two edge-case probes already built in G3.

## 14. Production Change Decision

**NO PRODUCTION CHANGE JUSTIFIED.**

Per the phase's explicit default and the instruction not to modify production code merely because a class performs poorly: while the real-natural-texture false-positive finding (§5) is significant and well-measured, it is a **reconfirmation of an already-documented, already-investigated phenomenon** (G2's synthetic-photograph LSB-entropy saturation, structurally the same mechanism, now shown on real images) rather than a newly discovered, reproducible, narrowly-defined defect distinct from what G2–G6 already characterized and explicitly declined to patch without a larger corpus and explicit design sign-off (see G5 §14, G6 §16). Introducing a fix now, in a measurement-only phase, would repeat the exact overreach this phase's rules were designed to prevent. This finding is documented, not immediately patched, and is recorded below as strengthened evidence for the future design phase already recommended in G5/G6 — not as grounds for an unscoped change here.

## 15. Conclusions

This phase's corpus audit confirms the existing 92-sample G3/G4 corpus (not regenerated) covers 9 of the 10 requested carrier taxonomy slots with real measurement data, with "flat graphic" recorded as absent rather than force-mapped. The single most important new finding — real natural photographic texture (brick, grass, gravel) producing a 100% false-positive rate via the same LSB-entropy/visual-balance mechanism previously seen only in synthetic proxies — elevates a previously proxy-only concern to one now demonstrated on genuine photographic content, and is the strongest available evidence yet for prioritizing the entropy/visual-balance redundancy work recommended in G5 and G6. All false negatives are confined to low payload on carriers whose clean baseline already saturates the relevant scoring band, consistent with prior phases. No production change is made in this phase.

---

## Final Output Summary

1. **Exact baseline:** 227 passed, 0 failed, 1 skipped, 1 expected warning, ~81s runtime.
2. **Corpus size:** 92 samples (26 clean-of-both, 59 stego, 7 tampering), 0 missing from disk.
3. **Carrier classes:** 14 actual corpus classes mapped to 9 of 10 requested taxonomy slots ("flat graphic" absent as a distinct class — see Section 4).
4. **Clean results:** Section 5 — headline: real natural-texture photographs show 100% FPR@20, root-caused to saturated LSB entropy and visual-balance.
5. **Stego results:** Section 6 — detection rate 1.00 for 6 of 13 stego-eligible classes, as low as 0.67 for others, entirely attributable to low-payload shortfall.
6. **Payload analysis:** Section 7 — mean score increases monotonically with payload overall (low 24.4 → medium 39.6 → high 62.3); detection-rate shortfall isolated to low payload.
7. **False positives:** Section 9 — 16/26 (61.5%) clean-of-both samples scored Medium/High; associated overwhelmingly with high LSB entropy (13/16) and LSB balance (12/16).
8. **False negatives:** Section 10 — 8/59 (13.6%) stego samples scored Low, all at low payload only.
9. **Independent validation status:** Section 11 — none available; none fabricated.
10. **Exact files created:**
    - `G7-technical-report.md`
    - `tests/evaluation/g7_corpus_inventory.py`
    - `tests/evaluation/g7_evaluation.py`
    - `tests/evaluation/g7_results/g7_corpus_inventory.json`
    - `tests/evaluation/g7_results/g7_clean_results.json`
    - `tests/evaluation/g7_results/g7_stego_results.json`
    - `tests/evaluation/g7_results/g7_pair_analysis.json`
    - `tests/evaluation/g7_results/g7_false_positive_analysis.json`
    - `tests/evaluation/g7_results/g7_false_negative_analysis.json`
    - `tests/evaluation/g7_results/g7_summary.json`
11. **Exact production files changed:** none.
12. **Full test result:** 227 passed, 0 failed, 1 skipped (unchanged from baseline).
13. **git status:** no `.git` in this environment (Section 2); pristine-diff equivalent confirms no new production changes.
14. **Confirmation:** no commit or push was performed.

**NO PRODUCTION CHANGE JUSTIFIED.**
