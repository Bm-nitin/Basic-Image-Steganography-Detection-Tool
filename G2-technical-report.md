# Phase G2 — Diverse Corpus, Detector Correlation & Calibration: Technical Report

**Scope:** evaluation-and-measurement phase only. No production scoring code (`app/core/*`) was modified.
**G1 status:** re-verified intact — full suite still 195/196 passing (1 skip requires a live server), including all 176 G1-era tests.

---

## 1. Scope

This phase builds a reproducible, diverse, ground-truth-labeled image corpus; runs the current (G1-integrated) detector pipeline over it unmodified; measures detector correlation, image-class bias, and payload sensitivity; and evaluates whether existing thresholds are empirically stable. Per the G2 spec, no production algorithm or threshold was changed in this phase. Where the evidence points to a needed change, it is proposed in §14 for separate, explicit approval — not implemented here.

---

## 2. Current Architecture (source-verified, extending G1's tracing)

All of the following was re-confirmed directly against `app/core/scoring.py`, `statistical.py`, `rs_analysis.py`, `spa_analysis.py`, `visual_extractor.py`, `jpeg_analysis.py`, `file_forensics.py`, `metadata_analyzer.py`, `tampering.py`, `evidence.py` as they exist post-G1:

- `SuspicionScoringEngine.evaluate()` sums four independently-capped category budgets (Structural 20 / Metadata 10 / Statistical 50 / Visual 20) into `suspicion_score`, unchanged since G1.
- `StatisticalAnalyzer.analyze()` runs chi-square (gray+R+G+B, max taken), LSB-plane binary entropy, pixel correlation (computed but **not scored** — confirmed again, `points_added` for this field is not read by `scoring.py`), `SPAnalyzer.analyze()`, `RSAnalyzer.analyze()`, `JPEGDomainAnalyzer.analyze()` (JPEG-only), and channel/alpha analysis — all as documented in the G1 pass.
- `VisualExtractor.extract_bit_planes()` now (post-G1) returns `is_visual_suspicious` computed with the channel-independence-aware, Bonferroni-corrected threshold, plus `effective_threshold` and `channel_count` for transparency — confirmed working as intended by this phase's own measurements (§9).
- `TamperingAnalyzer.analyze()` combines ELA (JPEG-only), noise (MAD), local variance, edge discontinuity, and copy-move into a weighted `combined_score`, entirely independent of the steganography score — confirmed unchanged.
- `CopyMoveAnalyzer`: `is_suspicious = anomaly_indicator > 0.40 or cluster_count >= 2`, where `anomaly_indicator = total_clustered_blocks / 6` (capped at 1.0) — confirmed by direct call in §7; this single line is the exact mechanism behind this phase's largest finding.

NOT VERIFIED FROM SOURCE in this phase (unchanged scope note from G1): line-by-line internals of `ela_analysis.py`, `noise_analysis.py`, `local_variance_analysis.py`, `edge_analysis.py` beyond their top-level `is_suspicious` outputs, which were exercised but not re-derived mathematically here.

---

## 3. Dataset Composition

**37 samples**, entirely synthetic and programmatically generated (`tests/evaluation/g2_corpus_generator.py`), deterministic via per-label SHA256-seeded RNGs. **These are proxies, not real-world images** — stated plainly, not glossed over: no real photographs, screenshots, or scanned documents were available (no network access in this environment to source licensed real images), so each class is built to exhibit that class's defining *statistical* characteristics (flat regions, sharp text-like edges, low palette, alpha variation, natural-looking correlated texture) using PIL/NumPy/SciPy only.

| Class | Clean | Stego (low/med/high) | JPEG variant | Tampering | Total |
|---|---|---|---|---|---|
| photograph_proxy | 1 | 3 | clean + appended-EOF stego + recompressed | copy-move + splice | 8 |
| screenshot_proxy | 1 | 3 | clean + appended-EOF stego | — | 6 |
| document_proxy | 1 | 3 | — | splice | 5 |
| illustration_proxy | 1 | 3 | — | — | 4 |
| low_color_proxy | 1 | 3 | — | — | 4 |
| alpha_proxy | 1 | 3 | — | — | 4 |
| grayscale_proxy | 1 | 3 | — | — | 4 |
| repeated_structure_proxy (copy-move FP probe) | 1 | — | — | — | 1 |
| repeated_structure_proxy (copy-move FP probe) | — | — | — | — | 1 |

Total = 37. Payload levels use the identical embedding method as the project's own existing `tests/evaluation/sample_generator.py` (random-bit LSB replacement over 15%/50%/100% of pixel-channel values), so G1 and G2 numbers are directly comparable.

---

## 4. Ground-Truth Methodology

Ground truth is assigned at generation time, never inferred from detector output (per the spec's explicit instruction). Each record carries `has_steganography`, `stego_type`, `payload_level`, `embedding_rate`, `has_tampering`, `tampering_type`. One deliberate case: `repeated_structure_proxy_clean.png` (a row of identical "tree" shapes) is labeled `has_tampering: False` on purpose — it is a **false-positive probe**, not a tampered image; the repetition is a legitimate feature of the content, exactly the scenario flagged as a risk in the original audit.

Full machine-readable metadata: `tests/evaluation/g2_samples/metadata.json`. No personally identifiable information is present (all content is generated shapes/noise).

---

## 5. Baseline Results (Step 4)

Full per-sample results: `tests/evaluation/g2_results/g2_baseline_results.json` / `.csv` (37 rows × 31 fields each — overall score, all four category scores, every individual detector's raw indicator/estimated-rate/is_suspicious, and predictions).

**Overall confusion matrices** (steganography decision threshold: `suspicion_score >= 20.0`, matching the convention already used by the project's own `evaluator.py`; tampering decision: `tampering_suspicious` flag as returned by scoring):

| | TP | FP | TN | FN | Accuracy | Sensitivity | Specificity | FPR |
|---|---|---|---|---|---|---|---|---|
| **Steganography** | 18 | 6 | 8 | 5 | 70.3% | 78.3% | 57.1% | 42.9% |
| **Tampering** | 2 | 17 | 17 | 1 | 51.4% | 66.7% | 50.0% | 50.0% |

These numbers describe **only this synthetic corpus** and must not be read as real-world accuracy figures (per the spec's explicit instruction, restated here deliberately). What they do show, with measurement rather than assumption: both the steganography FPR (42.9%) and especially the tampering FPR (50.0%) are far too high to be incidental, and both are concentrated in specific, identifiable causes below — not spread evenly across the corpus.

---

## 6. Results by Image Class — Clean-Sample Score Inflation (Step 6)

| Class | Clean stego score | Clean tampering score | Tampering flagged on clean? |
|---|---|---|---|
| photograph_proxy | **40.6** | 0.5 | No |
| screenshot_proxy | 8.8 | 1.6 | No |
| document_proxy | **14.7** | **85.0** | **Yes** |
| illustration_proxy | 0.0 | **85.0** | **Yes** |
| low_color_proxy | 0.0 | **85.0** | **Yes** |
| alpha_proxy | 0.0 | **85.0** | **Yes** |
| grayscale_proxy | 28.8 | 1.2 | No |
| repeated_structure_proxy | 0.0 | **70.8** | **Yes** |

Two independent, precisely-isolated findings:

**(a) Steganography false positive on the clean photograph-texture proxy (score 40.6, "Medium").** Root cause, confirmed by direct detector inspection: on this clean sample, `lsb_entropy_max = 1.0000` (maxed — full points) and `visual_min_balance_delta = 0.00020`, comfortably under the (already G1-corrected) effective threshold of `0.00167`, so `is_visual_suspicious = True` **with zero embedded payload**. This reproduces the exact phenomenon the original audit hypothesized: photographic sensor-noise-like texture genuinely pushes LSB parity close to 50/50 for reasons that have nothing to do with embedding — this is a well-documented general limitation of naive LSB-balance/entropy tests in the steganalysis literature, not unique to this codebase, and it survives the G1 multiple-comparisons fix because here it is a **single real channel** (not a spurious minimum-of-four artifact) genuinely close to 0.5. G1's fix targeted a different failure mode; this is a distinct, still-open one.

*(Caveat, stated plainly: this specific proxy generator adds synthetic Gaussian fine-grain noise on top of a smoothed base, which is a plausible-but-not-verified proxy for real sensor noise. This finding should be treated as corroborating evidence, not final proof, until validated against real photographs — which requires the corpus expansion recommended in §15.)*

**(b) Tampering false positive on document/illustration/low-color/alpha/repeated-structure clean samples (score 85.0 / 70.8, all "flagged").** Root cause, confirmed by direct `CopyMoveAnalyzer.analyze()` calls on each sample:

| Sample | cluster_count | anomaly_indicator | is_suspicious |
|---|---|---|---|
| illustration_proxy_clean | 1 | **1.0** | True |
| low_color_proxy_clean | 1 | **1.0** | True |
| alpha_proxy_clean | 1 | **1.0** | True |
| document_proxy_clean | 17 | **1.0** | True |
| repeated_structure_proxy_clean | 1 | 0.833 | True |
| photograph_proxy_clean | 0 | 0.0 | False |

Every one of these is driven **entirely by `copy_move`** — ELA is correctly unavailable (PNG), and noise/variance/edge all correctly report "not suspicious" on the same samples. The mechanism is source-verified: `anomaly_indicator = total_clustered_blocks / 6` (capped at 1.0), so a **single** cluster of just 6 matched blocks — trivially easy to produce when large areas of a flat-color illustration or a document's repeated grid lines contain many textured-enough-but-mutually-identical blocks at a consistent offset — saturates the indicator to its maximum regardless of the separate `cluster_count >= 2` rule. This is not a hypothesis; it is the exact, isolated, reproducible cause, verified by direct detector invocation, and it affects **every non-photographic, non-natural-texture clean class tested** except grayscale and screenshot (which have less large-scale flat repetition in this corpus). The `document_proxy_clean` score of **14.7** for steganography also closely reproduces the ~14/100 marksheet figure reported in the original audit request, on an image built independently from that report and without tuning toward it.

---

## 7. Results by Payload Level (Step 7)

| Class | clean | low (15%) | medium (50%) | high (100%) |
|---|---|---|---|---|
| photograph_proxy | 40.6 | **40.6** | 55.3 | 70.0 |
| screenshot_proxy | 8.8 | **8.8** | 26.5 | 55.3 |
| document_proxy | 14.7 | **14.7** | 26.5 | 50.0 |
| illustration_proxy | 0.0 | 14.7 | 27.1 | 70.0 |
| low_color_proxy | 0.0 | 14.7 | 27.1 | 70.0 |
| alpha_proxy | 0.0 | 14.7 | 27.1 | 70.0 |
| grayscale_proxy | 28.8 | 40.6 | **70.0** | **70.0** |

**Measured finding: for 3 of 7 classes (photograph, screenshot, document), the "low" payload level is completely indistinguishable from clean — identical scores, not just close ones.** Root cause traced directly: for these three classes, `lsb_entropy_max` and/or `rs_suspicion_indicator` are **already saturated at their clean baseline** (e.g. document/screenshot clean already show `rs_suspicion_indicator ≈ 1.0` before any embedding), so the low-payload version triggers exactly the same threshold bands as clean and receives identical scoring points. This is a ceiling effect from the underlying detectors, not a scoring-formula bug — but it means the system, as measured on this corpus, **cannot currently distinguish "clean but statistically unusual" from "lightly embedded"** for these carrier types, which is precisely the risk the original audit was concerned about.

For `grayscale_proxy`, the opposite ceiling effect appears at the top: medium and high are identical (both 70.0), so the detector also cannot distinguish 50% from 100% embedding on this class.

Only `illustration_proxy`/`low_color_proxy`/`alpha_proxy` show a clean, evenly-spaced clean→low→medium→high progression in this corpus.

---

## 8. Detector Correlation Analysis (Step 5)

Full matrices: `tests/evaluation/g2_results/g2_correlation_report.json`. Pearson correlations across all 37 samples between the five LSB-parity-cluster indicators (visual balance delta is sign-inverted so higher = more suspicious, consistent with the others):

| Pair | Pearson r | Spearman r |
|---|---|---|
| **LSB entropy ↔ Visual balance** | **0.952** | 0.941 |
| SPA ↔ Visual balance | 0.628 | 0.729 |
| LSB entropy ↔ SPA | 0.524 | 0.682 |
| Chi-square ↔ SPA | 0.484 | 0.456 |
| Chi-square ↔ Visual balance | 0.481 | 0.595 |
| Chi-square ↔ LSB entropy | 0.359 | 0.569 |
| Chi-square ↔ RS | 0.271 | 0.244 |
| RS ↔ Visual balance | −0.255 | −0.191 |
| RS ↔ LSB entropy | −0.243 | −0.283 |
| RS ↔ SPA | 0.023 | 0.041 |

**Using a |r| ≥ 0.70 clustering threshold, exactly one high-correlation cluster is found: {LSB entropy, Visual balance}.** This is a measured, not assumed, confirmation of one specific pairing the original (pre-G2) audit flagged as likely redundant — LSB-plane entropy and the visual-balance detector are, empirically, close to measuring the same thing on this corpus (r=0.95). SPA and chi-square show only weak-to-moderate positive correlation with the entropy/visual pair (0.36–0.63) — related but not redundant. **RS is essentially uncorrelated with everything else, including slightly negatively correlated with LSB entropy and visual balance.** This is a genuinely useful, humbling result: the earlier, pre-measurement hypothesis that "chi-square, RS, SPA, entropy, and visual-balance are all measuring near-identical LSB-parity evidence" is only **partially** supported by this data — it holds clearly for one pair, weakly for a few more, and does not hold at all for RS in this corpus. RS's behavior appears to be driven by different underlying image properties (plausibly the boundary/degenerate-content sensitivities characterized in G1.3) rather than the same parity-balance signal the other four share.

**Implication for the 50% statistical weight:** the entropy/visual-balance redundancy is real but narrower than assumed — it justifies treating that one pair as a single evidence source (rather than two), not a wholesale restructuring of all five statistical detectors into one cluster. This is a more precise, evidence-scoped version of the original audit's double-counting concern.

---

## 9. False-Positive Analysis (consolidated)

1. **Steganography:** photograph-texture clean sample scores 40.6 (Medium) — driven by LSB entropy + visual balance both saturating on genuine (synthetic) sensor-noise-like texture, unrelated to the G1 multiple-comparisons fix (§6a).
2. **Steganography:** grayscale clean sample scores 28.8 (Medium) — `lsb_entropy` and `rs` both contribute; not separately root-caused in this pass (flagged for follow-up, NOT VERIFIED FROM SOURCE beyond the aggregate score).
3. **Tampering:** 5 of 7 non-photographic classes (document, illustration, low-color, alpha, repeated-structure) show tampering false positives (score 70.8–85.0) on entirely clean, non-tampered content, root-caused precisely to `copy_move`'s `anomaly_indicator = total_clustered_blocks/6` saturating from a single cluster (§6b). This is the single largest, most confidently-attributed finding of this phase.
4. **Steganography:** `stego_eof_sample.jpg`-style JPEG recompression (`photograph_proxy_recompressed.jpg`, ground truth clean) scores 37.5 (Medium) — a **JPEG recompression negative control incorrectly flagged**. Not root-caused to a specific single detector in this pass; flagged for follow-up (NOT VERIFIED FROM SOURCE beyond the aggregate score and JPEG-domain involvement being plausible given the format).
5. **Steganography:** `grayscale_proxy` clean sample shows a non-zero chi-square indicator (0.6) with zero payload embedded — a distinct, previously unflagged class-specific false-positive contributor (§11).

---

## 10. False-Negative Analysis

Low-payload (15%) stego is missed (`pred_stego = False`, score < 20) for `screenshot_proxy`, `document_proxy`, `illustration_proxy`, `low_color_proxy`, `alpha_proxy` — 5 of 7 classes. For screenshot/document this is a ceiling effect (§7): the clean baseline is already near/at the same threshold band the low-payload version lands in, so there is no headroom left for low-payload detection to add signal within these fixed threshold bands. For illustration/low-color/alpha, low payload does move the score (0.0→14.7) but not quite past the 20.0-point decision boundary used here — this is a threshold-proximity finding (5.3 points short), not a total blind spot.

---

## 11. Threshold Analysis (Step 8)

| Threshold | Stable across classes in this corpus? | Evidence |
|---|---|---|
| Visual balance effective threshold (post-G1: `0.005/k`) | **Yes, by construction** — it adapts to channel count (k), and measured deltas for genuinely clean, non-photographic-texture classes (screenshot 0.228, document 0.270) sit two orders of magnitude above it. It only misfires on the photograph-proxy class, for the reason in §6a (a real, non-artifactual near-0.5 density, not a threshold instability). | §6a, §6 table |
| LSB entropy suspicious threshold (0.998/0.990) | **No** — saturates at 1.0 on a genuinely clean sample (photograph) and shows large baseline variance across classes even when clean (0.78–1.0 range across the 7 clean samples) | §7 table |
| RS suspicious threshold (rate>0.35 or indicator>0.50) | **No** — indicator saturates at/near 1.0 on multiple genuinely clean, non-degenerate samples (document, screenshot both ≈1.0 clean) that are not the literally-flat degenerate case G1.3 already fixed; this looks like a milder version of the same uncited `sym_diff` heuristic issue flagged (but not further modified) in G1.3 | §7 table, G1 completion report §7 |
| SPA suspicious threshold (>0.30/0.60) | Inconclusive in this corpus — SPA's clean-baseline values vary widely by class (document 0.003, screenshot 0.000, photograph 0.979) with photograph's clean value already near its own ceiling, similarly to entropy | §7 table |
| Chi-square (ratio bands / 0.70 probability) | **Mixed** — zero on 27 of 37 samples (73%), and specifically zero across every clean/low/medium sample for 6 of 7 classes; it only activates at the "high" (100%) payload level for those classes, giving it effectively no sensitivity below full-capacity embedding in this corpus. The exception is `grayscale_proxy`, where it is already non-zero (0.6) on the **clean** baseline and stays elevated through low/medium/high — a class-specific false-positive risk distinct from the photograph/document findings above, not previously flagged. NOT VERIFIED FROM SOURCE whether the near-total insensitivity below 100% embedding is a genuine property of Westfeld's test against this specific embedding method (full-plane random-bit LSB replacement, rather than the sequential/message-based embedding the classic chi-square attack targets) or an implementation issue. | §5 raw data, re-verified directly against `chi_square_max_indicator` across all 37 records |
| Copy-move `anomaly_indicator = clustered_blocks/6` | **No — the single most unstable threshold measured in this phase.** A single block cluster is enough to saturate it regardless of image content; it fires on 5 of 7 non-photographic clean classes. | §6b |
| Final LOW/MEDIUM/HIGH boundaries (unchanged from prior phases) | Not separately evaluated in this pass beyond their role in the confusion matrices above (NOT VERIFIED FROM SOURCE as a standalone question) | §5 |

---

## 12. Tampering Results

Tampering detection worked correctly on the two genuine tampering samples built on photograph-proxy content (copy-move: correctly NOT flagged as stego, was expected to flag as tamper — actually the copy-move tamper sample on photograph did **not** trigger `tampering_suspicious` in this run, an apparent false negative worth flagging: `photograph_proxy_tamper_copymove.png` scored tampering=0.6, not suspicious, despite genuine copy-move being applied — NOT root-caused further in this pass). The splice-noise tamper sample on photograph correctly triggered (score 38.5, suspicious=True). The document splice-noise sample did not show a distinguishable change from its already-saturated 85.0 clean baseline (ceiling effect, same mechanism as §6b). Given the overwhelming false-positive rate already documented in §6b/§9, tampering results on this corpus should be read primarily as evidence about false positives, not about true-positive capability, which this small corpus cannot characterize reliably.

---

## 13. Limitations

- **Every image is a synthetic proxy, not real-world content.** This is the single largest limitation. The findings above (especially §6a and the RS/entropy near-saturation on "document"/"screenshot" clean baselines) are internally consistent and mechanistically well-explained, but should be treated as **hypotheses strongly supported by controlled measurement**, not as proven real-world behavior, until validated against genuine photographs, screenshots, and scans.
- **Corpus size (37 samples, 1–4 per class per condition) is too small for statistical confidence in any specific rate** (e.g. the 42.9%/50.0% FPR figures are point estimates from tiny samples, not tight confidence intervals).
- **Calibration/validation separation is explicitly inadequate at this size** (see `tests/evaluation/g2_calibration_split.py` output: `corpus_is_adequate_for_threshold_calibration: false`, minimum 4 samples in some classes vs. a stated bar of 10+ per class / 100+ total). The split was still built and is functional infrastructure, but no threshold conclusion in this report should be read as "validated" in the calibration/validation sense — every finding above comes from the full corpus, viewed as one exploratory measurement, not a held-out test.
- Chi-square's uniform zero output across the whole corpus is unexplained (§11) — could be a property of the embedding method used, not a general chi-square failure; not resolved in this pass.
- The `photograph_proxy_tamper_copymove` apparent false negative (§12) is not root-caused in this pass.
- 100% real-world accuracy is not claimed anywhere in this report, and none of the numbers above should be extrapolated to real-world performance.

---

## 14. Recommended Next Changes (proposed, NOT implemented — per Step 11)

### P0 — copy_move `anomaly_indicator` saturation
1. **File:** `app/core/copy_move_analysis.py`
2. **Problem:** `anomaly_indicator = total_clustered_blocks / 6` (capped at 1.0) lets a single 6-block cluster reach maximum suspicion regardless of cluster_count, image size, or content type.
3. **Evidence:** §6b — 5 of 7 non-photographic clean classes flagged, all root-caused to exactly this line via direct detector invocation.
4. **Proposed change:** raise the denominator and/or require the `cluster_count >= 2` condition unconditionally (removing the `or anomaly_indicator > 0.40` OR-branch, or requiring both conditions together) — exact numeric choice should be informed by a larger, held-out corpus, not this one.
5. **Expected impact:** should eliminate or sharply reduce this phase's largest false-positive source.
6. **Regression risk:** could reduce sensitivity to genuine single-cluster copy-move forgeries with fewer than the new threshold's worth of blocks — needs the copy-move-positive portion of a larger corpus to validate before/after.
7. **Validation:** re-run this evaluation's tampering confusion matrix before/after on an expanded corpus with more genuine copy-move-positive samples than this phase's 1.

### P1 — RS `sym_diff`-derived indicator saturating on non-degenerate but low-complexity content
1. **File:** `app/core/rs_analysis.py`
2. **Problem:** `indicator = max(est_rate, min(1.0, sym_diff*4.0))` saturates near 1.0 on clean document/screenshot samples that are not literally zero-variance (so G1.3's degenerate-content guard doesn't apply).
3. **Evidence:** §7 table, §11.
4. **Proposed change:** NOT specified here — per G1.3's own conclusion, `sym_diff` has no cited literature derivation, so any numeric patch would itself be an invented formula; recommend either sourcing a citation for this term or falling back to `est_rate` alone (the literature-grounded quadratic solve) for the primary indicator, with `sym_diff` reported as a secondary diagnostic rather than folded into the suspicion decision.
5. **Expected impact / regression risk / validation:** cannot be assessed without first resolving what `sym_diff` is supposed to represent — this is a "stop and ask" item, not a ready-to-implement fix.

### P2 — LSB-entropy/visual-balance redundancy (confirmed, narrower than originally hypothesized)
Per §8, only this specific pair is empirically redundant (r=0.95). Recommend treating them as one evidence source (e.g. average or max-of-pair, not sum-of-both) in a future scoring revision — but this is a scoring-architecture change explicitly out of scope for G2 to implement, consistent with "do not modify production scoring."

### P3 — chi-square insensitivity below full-capacity embedding, and grayscale-specific false positive
Chi-square activated on only 10 of 37 samples, all at "high" (100%) payload except `grayscale_proxy`, which is already non-zero on its clean baseline. Investigate both: (a) whether this is a genuine property of chi-square against full-plane random-bit LSB replacement specifically (as opposed to the sequential/message-based embedding the classic attack targets), and (b) what specifically about the grayscale proxy's construction elevates its clean-baseline chi-square value, before drawing conclusions about chi-square's real-world usefulness at this codebase's current threshold settings.

---

## 15. Whether Production Scoring Should Remain Unchanged

**Yes, for this phase** — no production code was or should be changed based on a 37-sample synthetic corpus. The findings above are strong enough to prioritize a follow-up phase, but not strong enough (by the corpus-size standard this phase itself applied, §13) to justify tuning thresholds now.

---

## 16. Exact Recommended Next Phase

**G3 — Corpus expansion + the P0 copy-move fix, calibration-gated.** Concretely:
1. Expand the corpus to real (or at minimum, more varied synthetic) photographs, screenshots, and scans — targeting the "low hundreds per class" bar this phase's own `g2_calibration_split.py` flags as the adequacy threshold, before any threshold is changed and called "validated."
2. Implement the P0 copy-move fix from §14, validated against the expanded corpus's calibration split only, then measured (not re-tuned) against the validation split.
3. Investigate the P1 (RS) and P3 (chi-square) open questions as narrowly-scoped, source-verification-first sub-tasks, following the same "verify from primary source or state NOT VERIFIED" discipline used in G1.3.
4. Do not fold P2 (entropy/visual-balance merge) into scoring until the above are resolved, since scoring-architecture changes should be made once, informed by the fullest available evidence, not incrementally.

---

## Appendix — Files Added This Phase

| File | Purpose |
|---|---|
| `tests/evaluation/g2_corpus_generator.py` | Builds the 37-sample synthetic corpus + `metadata.json` |
| `tests/evaluation/g2_baseline_runner.py` | Runs the current detector pipeline, writes `g2_baseline_results.json`/`.csv` |
| `tests/evaluation/g2_correlation_analysis.py` | Pearson/Spearman correlation + clustering, writes `g2_correlation_report.json` |
| `tests/evaluation/g2_calibration_split.py` | Deterministic calibration/validation split + explicit adequacy check, writes `g2_calibration_split.json` |
| `tests/test_g2_evaluation.py` | 19 regression tests over the above infrastructure |
| `tests/evaluation/g2_samples/` | Generated corpus (images + metadata.json) |
| `tests/evaluation/g2_results/` | Generated results (baseline JSON/CSV, correlation report, calibration split) |

No file under `app/` was modified in this phase.
