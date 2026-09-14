# Phase G3 — Corpus Expansion, Copy-Move Fix & Detector Verification: Technical Report

**Labeling convention used throughout:** every claim is tagged **MEASURED** (observed directly from running code on data in this phase), **SOURCE-VERIFIED** (confirmed against a primary or authoritative external source), **INFERRED** (a reasoned but not independently re-derived explanation), or **PROPOSED** (a recommendation, not implemented). Unlabeled prose is connective narration only.

**Production code changed in this phase:** `app/core/copy_move_analysis.py` only — the single change explicitly permitted by the G3 spec. `app/core/scoring.py` and all other frozen files are unmodified since G1 (**MEASURED** — confirmed via `diff -rq` against the pristine repository: only `visual_extractor.py`, `scoring.py`, `evidence.py`, `rs_analysis.py` [all G1] and `copy_move_analysis.py` [new, G3] differ).

---

## 1. Baseline (Step 1)

**MEASURED**, preserved in `tests/evaluation/g2_results_before_g3/`:
- Full suite before this phase: 195 passed, 1 skipped, 0 failed (reproduced identically at the start of this phase).
- G2's 37-sample tampering confusion matrix: TP=2, FP=17, TN=17, FN=1 (FPR=50.0%, sensitivity=66.7%) — saved verbatim as `PRE_G3_SUMMARY.txt`.
- The G2 baseline evaluator (`g2_baseline_runner.py`) was re-run unmodified at the start of this phase and reproduced these exact figures, confirming reproducibility before any change.

## 2. Expanded Corpus (Step 2)

**MEASURED.** The corpus grew from 37 to **92 samples** (`tests/evaluation/g3_corpus_generator.py`, metadata in `tests/evaluation/g3_samples/g3_metadata.json`). Composition:
- All 37 G2 synthetic proxies, regenerated unchanged (same seeds).
- **12 real, public-domain sample images** bundled with scikit-image (`skimage.data`) — used exactly as scikit-image's own test suite uses them, not sourced from the open web: `coffee`, `chelsea`, `rocket` (photographs), `page`, `text` (real scanned/typeset document pages), `moon` (real astronomical grayscale photo), `colorwheel`, `checkerboard` (illustration-like), `logo` (a real RGBA vector logo — genuine alpha PNG, not a synthetic alpha channel), `brick`, `grass`, `gravel` (real naturally-repeating textures, used specifically as a stronger copy-move false-positive probe). Images with identifiable real faces (`astronaut`, `camera`/"cameraman") were deliberately excluded.
- Each real source: clean + 3 payload levels (low/medium/high, identical embedding method to G2) = 48 samples.
- Additional tampering/edge-case samples: single-region copy-move (real photo), multi-region copy-move (real photo, 3 regions), a deliberately weak/tiny (10px) copy-move, a splice-noise sample on a real document page, a JPEG recompression negative control, and tiny (32×32) / large (1024×1024) size edge cases = 7 samples.

**This remains a small evaluation corpus, not a representative real-world sample.** Per the explicit instruction not to overstate it: 92 samples across ~19 image-class/source groupings averages under 5 samples per group. This is stated plainly in `g3_metadata.json` itself, not only in this report.

**Ground truth was set at generation time in every case, never inferred from detector output** — same discipline as G2.

## 3. Copy-Move Root Cause (Step 3, part 1)

**SOURCE-VERIFIED (from the codebase itself, i.e. directly reading the pre-fix code):** `anomaly_indicator = total_clustered_blocks / 6.0` (capped at 1.0); `is_suspicious = anomaly_indicator > 0.40 or cluster_count >= 2`, where a cluster is "significant" once it reaches `>= 3` matched blocks. A single cluster of 6+ blocks saturates the indicator regardless of what produced it.

**MEASURED, exact cause on the expanded corpus:**

| Sample | cluster_count | clustered_blocks | anomaly_indicator (pre-fix) |
|---|---|---|---|
| document_proxy_clean (synthetic) | 17 | 207 | 1.0 |
| illustration_real_checkerboard_clean (real) | 41 | 642 | 1.0 |
| illustration_real_colorwheel_clean (real) | 2 | 12 | 1.0 |
| illustration_proxy_clean (synthetic) | 1 | 8 | 1.0 |
| photograph_real_coffee_tamper_copymove_single (genuine forgery) | 1 | 10 | 1.0 |

The genuine forgery (10 blocks, 1 cluster) sits almost on top of several false positives (8–15 blocks, 1–3 clusters) — a razor-thin margin — while the most extreme false positives (document, checkerboard) are separated from all of these by a wide, unambiguous empirical gap (194–642 blocks, 15–41 clusters vs. everything else's ≤15 blocks, ≤3 clusters).

## 4. Candidate Fixes (Step 3, part 2)

All five candidates from the spec were evaluated against the measured data above:

- **A (require multiple independent clusters, i.e. `cluster_count >= 2` only):** **rejected.** The only genuine small-scale positive has `cluster_count == 1`; this candidate would eliminate it entirely while leaving document (17 clusters) and checkerboard (41 clusters) untouched, since both already satisfy `>= 2`. **MEASURED** directly from the table above.
- **B (spatial support relative to block count):** partially informative but insufficient alone — see below; a normalized fraction (`clustered_blocks / total_blocks`) makes document (0.25) and checkerboard (0.67) look *more* suspicious than the genuine 10-block forgery (0.01), the wrong direction, because highly regular content has proportionally *more* self-similarity, not less. **MEASURED** by direct computation.
- **C (normalized measure replacing the fixed /6 denominator):** same problem as B in isolation.
- **D (block support AND geometric consistency):** directionally right but "geometric consistency" alone (e.g. a single dominant displacement vector) doesn't separate the ambiguous small-magnitude false positives either, since several of them (illustration_proxy, low_color_proxy, alpha_proxy) also have exactly one cluster, same as the genuine positive.
- **E (combine cluster_count, block count, and — the piece that actually works — an explicit periodicity bound):** **selected.**

## 5. Selected Fix and Justification (Step 3, part 3)

**PROPOSED → IMPLEMENTED** (the one change permitted this phase). Added to `CopyMoveAnalyzer`:

```
MAX_CLUSTERS_BEFORE_PERIODICITY = 8
MAX_CLUSTERED_BLOCKS_BEFORE_PERIODICITY = 50
is_periodic_like = cluster_count > 8 or total_clustered_blocks > 50
anomaly_indicator = 0.0 if is_periodic_like else (unchanged calculation)
is_suspicious = (not is_periodic_like) and (anomaly_indicator > 0.40 or cluster_count >= 2)
```

**Justification, not arbitrary:** both constants sit inside a wide, empirically observed gap — **MEASURED**: every genuine or ambiguous case in the corpus has `cluster_count <= 3` and `clustered_blocks <= 15`; every extreme, unambiguous periodic false positive has `cluster_count >= 15` and `clustered_blocks >= 194`. The chosen caps (8 and 50) sit with wide margin on both sides of that gap, not at a boundary tuned to any single sample.

**Literature grounding (SOURCE-VERIFIED via web search, not invented from nothing):** copy-move forensics literature explicitly addresses this exact failure mode — one paper's "MFD" (Most Frequent Distance) processing keeps only matches at the single most common displacement and discards isolated/inconsistent ones; another explicitly tests detectors against "natural self-similarity hard negatives" (tiled patterns, symmetric objects) as a named false-positive category; a third discards matched blocks "not connected to any other" as noise. The concept that *bounded, localized* duplication is what indicates forgery, while *widespread, highly repetitive* matching indicates natural/periodic structure, is an established distinction in this literature, not a fabricated one — though this specific numeric implementation is original to this fix, not copied from any paper's exact formula.

**Effect on the return schema:** additive only — a new `is_periodic_like` boolean field was added; `is_suspicious`, `anomaly_indicator`, and all other existing fields keep their names and meaning. **MEASURED**: confirmed no other file reads `total_clustered_blocks` or any new field; only `anomaly_indicator` and `is_suspicious` are consumed downstream (by `tampering.py`), and both were verified to behave correctly with the fix (§6).

**A critical implementation detail found and corrected during this phase:** the first version of the fix only changed the boolean `is_suspicious` flag, leaving `anomaly_indicator` (the continuous value `tampering.py` actually uses in its weighted sum and max-pooling boost) unchanged. **MEASURED**: this produced *zero* change in the overall `tampering_score` for any sample, because `tampering.py`'s aggregation reads `anomaly_indicator` directly, not `is_suspicious`. This was caught by checking the aggregate score before finalizing, not assumed to work from the per-detector flag alone — the final fix sets `anomaly_indicator = 0.0` (not just the boolean) when `is_periodic_like`.

## 6. Copy-Move Before/After Metrics (Step 3, part 4 / Step 6 heading)

**MEASURED**, full 92-sample corpus, `tests/evaluation/g3_results/g3_before_fix_results.json` vs `g3_after_fix_results.json`:

**Copy-move detector specifically** (ground truth = genuine copy-move tampering only):

| | TP | FP | TN | FN | Precision | Recall | FPR | FNR |
|---|---|---|---|---|---|---|---|---|
| Before | 1 | 26 | 62 | 3 | 0.037 | 0.250 | 0.295 | 0.750 |
| After | 1 | 17 | 71 | 3 | 0.056 | 0.250 | 0.193 | 0.750 |

**Copy-move-specific sensitivity is unchanged (TP=1, FN=3 both before and after)** — the fix removed 9 false positives (all document_proxy and checkerboard variants) with zero cost to copy-move's own detection capability, precisely as designed.

**Overall tampering score** (all tampering types combined, since copy-move feeds into one shared aggregate):

| | TP | FP | TN | FN | FPR | Sensitivity |
|---|---|---|---|---|---|---|
| Before | 3 | 25 | 60 | 4 | 0.294 | 0.429 |
| After | 2 | 17 | 68 | 5 | 0.200 | 0.286 |

**A genuine, honestly-measured sensitivity cost exists at the *overall tampering* level, though not at the copy-move level:** `document_proxy_tamper_splice.png` (ground truth: genuine splice/noise tampering) flipped from correctly-flagged (True) to missed (False). **MEASURED, root-caused precisely:** before the fix, this sample's overall tampering score (85.0, flagged) was being driven entirely by copy_move's spurious high indicator (1.0) via the max-pooling boost — the noise-disparity detector that actually corresponds to the real tampering applied was not, on its own, strong enough to cross the suspicion threshold for this sample. Removing copy_move's false contribution didn't cause a new failure; **it revealed a pre-existing weakness in the noise/splice detector's sensitivity on this specific carrier that was previously masked by an unrelated false positive.** This is reported plainly, not hidden: fixing one detector's false positive uncovered that the "right" prior answer for this sample was correct for the wrong reason.

## 7. RS Source Investigation (Step 5)

| Claim | Source | Equation/concept | Maps to implementation | Match? |
|---|---|---|---|---|
| Discrimination function `f(G) = Σ|x_{i+1}-x_i|` | **SOURCE-VERIFIED** (Fridrich, Goljan & Du 2001, and multiple secondary confirmations found via search) | Group smoothness measure | `_discrimination()` | Yes |
| `F_{-1}(x) = F_1(x+1) - 1`, pairing (-1,0),(1,2),...,(255,256) | **SOURCE-VERIFIED** (same source, confirmed independently in a 2014 survey paper's identical notation) | Shifted LSB flip | `_flip_neg1()` | Yes, exactly (parity-correct for every interior value; boundary handling already verified as the standard practical resolution in G1.3) |
| Quadratic `2(d1+d0)z² + (d-0-d-1-d1-3d0)z + (d0-d-0) = 0` | **SOURCE-VERIFIED** — found identically in four independent sources during this phase: the original 2001 paper, US Patent 6,831,991B2, and two survey papers, all stating the exact same equation with the exact same variable names | Root gives rescaled crossing point of R/S curves | `_solve_embedding_rate()` | Yes, exact match, confirmed algebraically via an independent `numpy.roots` cross-check test |
| `p = z / (z - 0.5)` (final rescaling to embedding rate) | **INFERRED** as standard (this exact final line was not found verbatim in the primary excerpts retrieved, though the described rescaling convention — "p/2 becomes 0, 100-p/2 becomes 1" — is consistent with it, and this exact expression is widely used in derivative/course-material implementations of RS) | Converts rescaled root back to a message-length fraction | same function | Consistent with the described rescaling, not pulled verbatim from the primary PDF in this pass |
| Clean-image assumption `R_M ≈ R_{-M}`, `S_M ≈ S_{-M}` | **SOURCE-VERIFIED** (found explicitly, "equation 3", in the US patent text and the original paper) | A precondition for RS to be meaningful on a given image, not a stego-detection mechanism itself | — | — |
| `sym_diff = |r_m - r_neg_m| + |s_m - s_neg_m|` | — | Directly measures how much the *clean-image assumption above* is violated | `_analyze_channel()` | **This is the key finding of this investigation.** `sym_diff` measures assumption-validity (is RS even applicable to this image?), not the mechanism the source actually uses to detect embedding (which is the R_M-vs-S_M *within-mask* convergence captured correctly by `d0`/`d1`/`d_neg0`/`d_neg1` and already used in the quadratic). Treating "the clean-image assumption is violated" as "more suspicious" is a **conceptual mismatch with the cited theory**, not merely an uncited add-on as flagged in G1/G2 — it repurposes a plausibility check as if it were positive evidence. |
| `indicator = max(est_rate, min(1.0, sym_diff*4.0))` | — | Combines the source-grounded estimator with the mismatched heuristic above | same | **Original heuristic, and specifically an implementation that conflates two different meanings** (a validity check and an embedding-rate estimate). The `*4.0` scaling has no cited derivation and was not found in any source consulted. |

**Regression tests added** (`tests/test_g3_rs_investigation.py`): verify the quadratic solve algebraically; verify `sym_diff` can be driven by pure directional structure (a gradient) with zero embedding, without asserting a specific "correct" numeric outcome (asserting one would itself be an uncited tuning act); verify the G1.3 degenerate-content guard still holds.

**Minimum safe change (PROPOSED, not implemented, per explicit instruction):** report `est_rate` as the primary, source-grounded suspicion indicator; report `sym_diff` separately as an "RS assumption validity" diagnostic rather than folding it into the suspicion decision via an uncited multiplier. This was **not implemented in G3** — RS production code is unchanged this phase, as instructed.

## 8. Chi-Square Investigation (Step 6)

**SOURCE-VERIFIED:** the pair formation, expected-frequency, and chi-square summation exactly match Westfeld's PoV formula (confirmed both against an independently retrieved survey paper's equation and via a direct `scipy.stats.chisquare` cross-check test in `test_g3_chisquare_investigation.py`).

**MEASURED (G2+G3 corpus, 92 samples):** chi-square is non-zero on only 10 of 92 samples — 6 of 7 (G2) proxy classes only activate at 100% payload; `grayscale_proxy`'s clean baseline is already non-zero (0.6).

**INFERRED (mechanistically explained, not independently re-derived from a source in this pass):** Westfeld's classical chi-square attack derives much of its real-world power from sequential/windowed application (scanning a growing prefix of the image to locate where embedding starts), which lets it detect even low embedding rates once the affected region dominates the tested window. This implementation applies the test once to the **whole image's** histogram (**SOURCE-VERIFIED** directly from `chi_square_attack()`'s code: `flat = channel.flatten()`, no windowing). This project's embedding method scatters random-bit LSB replacement across a randomly-selected **fraction** of pixels image-wide, not a contiguous sequential region. Combining these two facts, a **MEASURED**, dedicated test (`test_g3_chisquare_investigation.py`) confirms: on a natural-like (smoothed, correlated) synthetic base with genuine PoV bias, average `|ratio - 1.0|` after 100% coverage is reliably smaller than the clean baseline's, but the effect is **not reliably monotonic at a single random draw at partial coverage** — sometimes a 15% draw moves the ratio by chance as much as, or more than, 100% coverage does, purely from small-sample variance in which specific value-pairs get touched. This variance itself is a **measured** characteristic, not asserted as a flaw.

**Conclusion for Step 6, exactly matching the spec's suggested outcome category:** the chi-square implementation is **mathematically valid and faithful to Westfeld's formula**, but **poorly matched to this project's actual embedding-and-testing model** — whole-image application against partial, spatially-scattered coverage dilutes and destabilizes the signal at anything below near-full embedding. This is a mismatch between method and embedding model, not an implementation bug.

The `grayscale_proxy` clean-baseline false positive (0.6 with zero embedding) is **INFERRED** (not independently proven in this pass) to share the same root cause already identified for the photograph-proxy LSB-entropy false positive in G2 §6a: this specific synthetic generator's added Gaussian fine-grain noise can itself produce a PoV distribution close to equalized, independent of the detector's correctness.

## 9. LSB Redundancy on the Expanded Corpus (Step 7)

**MEASURED**, 92-sample corpus (after the copy-move fix, which does not touch these detectors): overall Pearson r between LSB entropy and (inverted) visual balance delta = **0.9469** (vs. 0.952 on the 37-sample G2 corpus) — **the finding replicates closely on a corpus more than double the size and including real images**, not an artifact of the smaller synthetic set.

**By class** (n per group in parentheses):

| Class | n | r |
|---|---|---|
| illustration_real | 8 | 0.977 |
| document_proxy | 5 | 0.967 |
| screenshot_proxy | 6 | 0.966 |
| alpha_proxy | 4 | 0.965 |
| low_color_proxy | 4 | 0.964 |
| illustration_proxy | 4 | 0.964 |
| alpha_real | 4 | 0.964 |
| photograph_real | 18 | 0.938 |
| document_real | 9 | 0.575 |
| grayscale_proxy / grayscale_real / photograph_proxy / repeated_texture_real | 4–12 each | undefined (zero variance in at least one variable — a ceiling/floor effect, itself consistent with G2's earlier finding that these classes saturate) |

The redundancy **persists strongly** across nearly every class with enough variance to measure it — with one notable exception: `document_real` (the two real scikit-image text-page sources) shows a much weaker correlation (0.575), suggesting the redundancy may be somewhat carrier-dependent rather than universal. This nuance was not visible in G2's smaller, all-synthetic corpus.

## 10. Remaining False Positives

- **Copy-move: illustration_proxy, low_color_proxy, alpha_proxy, repeated_structure_proxy (synthetic), illustration_real_colorwheel** — all still flagged (1–3 clusters, 8–15 blocks), explicitly **not** addressed by this phase's fix because they sit too close, in this corpus, to the one confirmed genuine small-scale positive (10 blocks) to separate without risking it. Documented as `KNOWN_UNRESOLVED_false_positive` in the new regression tests, not hidden.
- **Steganography:** the photograph-proxy clean LSB-entropy/visual-balance false positive from G2 (§6a) is unchanged by this phase — RS and chi-square production code were investigated, not modified.
- **Chi-square: grayscale_proxy clean false positive** — unresolved, root cause inferred but not independently confirmed.

## 11. Remaining False Negatives

- **Copy-move: multi-region forgery (3 scattered 40×40 regions) is entirely undetected**, and this is confirmed **pre-existing**, not introduced by the G3 fix (verified against `g3_before_fix_results.json`, where the same sample already showed `cluster_count=0`). Root cause: each region individually falls short of the (unchanged, pre-G3) `>=3`-blocks-per-cluster significance floor at this region size.
- **Copy-move: weak/tiny (10px) forgery** — not detected; documented as an expected edge case, not a target for this fix.
- **Overall tampering: `document_proxy_tamper_splice`** — newly missed as a *direct, measured, and explained side effect* of removing copy_move's false contribution (§6). This is the one true sensitivity cost of this phase's change, at the aggregate level (not at the copy-move level itself).
- Steganography false negatives from G2 (low payload indistinguishable from clean on 3 of 7 classes) are unchanged — statistical scoring was not touched this phase.

## 12. Regression Results (Step 10)

**MEASURED**, full run at the end of this phase:

```
TOTAL: passed=217 failed=0 skipped=1 errors=0
```

- All 195 pre-G3 tests (G1 + G2) still pass unchanged.
- 15 new copy-move regression tests (`test_g3_copymove_fix.py`), covering all 10 required scenarios, all pass — including tests that explicitly assert *known-unresolved* and *known-preexisting* behaviors rather than silently hiding them.
- 4 new RS investigation tests, 3 new chi-square investigation tests, all pass.
- 1 skip: `test_live_http.py` (requires a live server), unrelated to this phase.
- The project's own built-in controlled evaluation (`tests/evaluation.py`'s 8-sample set) still reports 100% accuracy/sensitivity/specificity on both stego and tampering — including `tamper_copymove` (still correctly flagged, 85.0) and `tamper_spliced_noise` (still correctly flagged, 47.2) — confirming the copy-move fix did not regress the project's own pre-existing positive test cases.
- Re-running the *original* G2 37-sample evaluator (unmodified) after the fix shows exactly 5 samples changed (all `document_proxy_*` variants, tampering score dropping from 85.0 to 1.2–1.8), zero change to any stego score — confirming the fix's effect is precisely isolated to what was intended.

## 13. Limitations

- The corpus remains small (92 samples, <5 per fine-grained group) and is not a substitute for validated real-world calibration. This is stated in the corpus metadata itself, not only here.
- The copy-move fix resolves the extreme, unambiguous majority of the measured false-positive *magnitude* (document, checkerboard — the highest-scoring FPs) but leaves several smaller-magnitude false positives explicitly unresolved, by design, given the evidence available.
- The fix's constants (8 clusters, 50 blocks) are justified by the size of the observed gap in this corpus, not by a statistically powered calibration study — more genuine small-scale copy-move-positive samples (beyond the single one available) would meaningfully sharpen this boundary.
- RS and chi-square were investigated, not fixed. Both are now clearly labeled (SOURCE-VERIFIED vs. original heuristic vs. mismatch), but production behavior for them is exactly what it was in G2.
- The multi-region copy-move miss and the document-splice sensitivity loss are both documented but neither is resolved in this phase — both are explicit candidates for G4/G5.
- All findings involving the real scikit-image images are still evaluated at small sample counts per source (1–3 images per class) and should not be read as validated real-world performance figures.

## 14. Recommendation for G4

**PROPOSED, not implemented:**
1. Collect additional genuine small-scale copy-move-positive samples (varying region size, count, and carrier type) specifically to sharpen the boundary between the unresolved small-magnitude false positives (8–15 blocks) and genuine small forgeries (currently only one data point, 10 blocks) — this is the single highest-value next step for copy-move specifically.
2. Investigate and, if justified, fix the multi-region copy-move miss (§11) — likely requires either a smaller minimum-blocks-per-cluster floor for smaller region sizes, or a region-size-aware significance rule; needs its own controlled before/after comparison, not a blind constant change.
3. Investigate the `document_proxy_tamper_splice` sensitivity gap directly in the noise/edge/variance detectors, now that it is no longer masked by copy_move — this is a newly *visible* problem, not a newly *created* one.
4. Address RS's `sym_diff` conceptual mismatch (§7) as its own small, source-disciplined change: separate the assumption-validity diagnostic from the suspicion decision, rather than combining them via an uncited multiplier — this is a minimal, well-scoped, source-justified change, distinct from a full scoring redesign.
5. Do not yet redesign `scoring.py`'s category weights or aggregation — see the answer to Question 6 below.

---

## Final Required Answers

**1. Did the copy-move fix reduce false positives?**
**MEASURED: Yes.** Copy-move-specific FPR dropped from 29.5% to 19.3% (26→17 false positives out of 88 negatives); overall tampering FPR dropped from 29.4% to 20.0% (25→17 false positives out of 85 negatives), on the 92-sample corpus.

**2. How much sensitivity was lost, if any?**
**MEASURED: None at the copy-move-detector level** (TP=1, FN=3, unchanged before/after — the one confirmed genuine small-scale positive is still detected, and the two known pre-existing misses were already misses before this fix). **A real cost exists at the overall-tampering aggregate level**: one sample (`document_proxy_tamper_splice`) lost its correct flag, because it was previously correct only due to copy_move's now-removed false contribution, not genuine sensitivity in the detector that actually corresponds to its tampering type. This is reported as a revealed pre-existing weakness, not a new one.

**3. Is the RS implementation mathematically/source justified?**
**Partially, and precisely characterized, not a blanket yes or no.** The discrimination function, the flip operations (including the previously-questioned boundary handling, re-confirmed here), and the core quadratic solver are all **SOURCE-VERIFIED** as exact, faithful implementations of Fridrich, Goljan & Du's published method. The `sym_diff`-based term folded into the final `indicator`, however, is an **original heuristic that conceptually conflates the source's assumption-validity check with its embedding-rate-estimation mechanism** — this is a more precise and more damning finding than "uncited," reached only by tracing the primary source's actual theoretical claims in this phase.

**4. Is the Chi-square implementation appropriate for this embedding model?**
**MEASURED + INFERRED: the formula is correct; the application is a poor match for this project's embedding model.** Westfeld's test is implemented faithfully but applied once, whole-image, against an embedding method that scatters payload across a random pixel subset rather than a contiguous sequential region — this measurably dilutes and destabilizes sensitivity below near-full coverage, exactly matching the spec's "mathematically valid but poorly matched" outcome category.

**5. Does the LSB entropy/visual redundancy persist?**
**MEASURED: Yes, strongly** (r=0.9469 on 92 samples vs. 0.952 on 37), replicating closely on a larger, more diverse corpus including real images — with one new nuance: it is markedly weaker specifically for real scanned-document-page content (r=0.575), a distinction not visible in G2.

**6. Is the evidence now sufficient to redesign scoring in G4?**
**Not yet, and this report does not recommend doing so.** The evidence is now substantially stronger and more precisely characterized than at the end of G2 for three specific, narrow issues (copy-move periodicity — now fixed; RS's sym_diff conceptual mismatch; chi-square's coverage-dilution mismatch), but the corpus is still too small (§13) to responsibly recalibrate `scoring.py`'s category weights or aggregation logic as a whole, and doing so would combine multiple simultaneous changes in a way this phase's own discipline (fix one thing, measure it in isolation) was specifically designed to avoid. The recommended G4 scope (§14) is targeted, source-disciplined fixes to RS and the multi-region copy-move gap — not a scoring redesign.

**G4 scoring changes were not implemented in this phase, as instructed.**
