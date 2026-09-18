# G6 Statistical Evidence Aggregation Investigation

**Evidence labels used throughout:** [MEASURED], [SOURCE-VERIFIED], [INFERRED], [PROPOSED].

## 1. Objective

Investigate whether the current scoring system double-counts correlated evidence within the LSB/parity detector family (Chi-Square, RS, SPA, LSB entropy, visual-balance), and determine whether a narrowly-scoped aggregation change is justified. This is an investigation phase; a production change is made only if the evidence clearly supports one (Phase 8, Option A vs B).

## 2. Baseline

**Repository/git note:** this working directory has no `.git` (extracted from an archive, not cloned) -- `git status`/`git log --oneline -5`/`git diff --stat` could not be run as literal commands. This has been true and reported identically in G4 and G5. The established equivalent (diffing against a preserved pristine extraction of the original archive) was used instead.

[MEASURED]
```
[G6 BASELINE]
passed: 227
skipped: 1
failed: 0
warnings: 1 (DecompressionBombWarning, pre-existing/expected per prior phases)
runtime: ~81s
```
Matches the expected G4/G5 baseline exactly. [MEASURED] Diffing against the pristine archive shows exactly the same 5 files differing as after G5 (`visual_extractor.py`, `scoring.py`, `evidence.py`, `rs_analysis.py` from G1/G4; `copy_move_analysis.py` from G3) -- no unrelated modifications found before this phase began.

**Data-freshness check:** before reusing the existing G4 dataset for this phase's analysis, 3 randomly-selected samples were re-scored from scratch with the current, unmodified pipeline and compared byte-for-byte against the stored G4 values. [MEASURED] All 3 matched exactly, confirming no drift since G4/G5 (consistent with G5 having made no production changes).

## 3. Current Scoring Architecture

Traced directly from `app/core/scoring.py` (unchanged since G4):

`image -> detector outputs (statistical.py, visual_extractor.py, rs_analysis.py) -> SuspicionScoringEngine.evaluate() -> category points summed -> suspicion_score (0-100) -> risk_level`

The five categories are: Structural (20 pts), Metadata (10 pts), **Statistical Steganalysis (50 pts)**, **Visual Steganalysis (20 pts)**, and Tampering (fully independent, not summed into the stego score). [SOURCE-VERIFIED against code] The LSB/parity cluster under investigation **spans two of these categories**: Chi-Square, RS, SPA, and LSB entropy are scored inside the 50-point Statistical category; visual-balance is scored inside its own, separate 20-point Visual category. This cross-category split is architecturally significant for Phase 6 (see below).

Within the Statistical category, weights are dynamically redistributed depending on JPEG vs. non-JPEG (JPEG carriers get a 5th slot for JPEG-structural analysis). For non-JPEG (the majority of this corpus): Chi-Square 14.7, LSB Entropy 8.8, SPA 11.8, RS 14.7 (sums to 50.0).

**Each detector's contribution is independently tiered, not a smooth function of its raw signal:**

| Detector | Raw signal | Normalization | Threshold tiers | Weight (non-JPEG) | Evidence type |
|---|---|---|---|---|---|
| Chi-Square | `max_indicator` (max of `probability_stego` across gray/R/G/B) | Already ~[0,1] | >=0.85->100%; >0.60->60%; else 0 | 14.7 | 3-tier discretized |
| LSB Entropy | `lsb_entropy.max` (Shannon entropy of LSB plane, bits/pixel) | Already [0,1] | >=0.998->100%; >=0.990->60%; else 0 | 8.8 | 3-tier discretized |
| SPA | `estimated_embedding_rate` (or `suspicion_indicator` fallback) | Already [0,1] | >0.60->100%; >0.30->60%; else 0 | 11.8 | 3-tier discretized |
| RS | `estimated_embedding_rate` **and** `suspicion_indicator`, combined via OR | Already [0,1] | rate>0.50 **or** ind>0.70->100%; rate>0.25 **or** ind>0.40->60%; else 0 | 14.7 | 3-tier discretized |
| Visual-balance | `is_visual_suspicious` (already a bounded, Bonferroni-corrected boolean decision -- see G1) | Boolean | flagged->100%; else 0 | 20.0 (separate category) | 2-tier (binary) |

**[MEASURED, new finding this phase] Post-G4, RS's OR-condition contains dead logic.** Since G4 separated `suspicion_indicator := estimated_embedding_rate` exactly (no longer inflated by `sym_diff`), `rs_ind` and `rs_rate` are now **always numerically identical**. The `or rs_ind > 0.70` / `or rs_ind > 0.40` clauses are therefore always subsumed by the `rs_rate > 0.50` / `rs_rate > 0.25` clauses (whenever the `ind` clause could fire, the `rate` clause already fired, since they're equal and the `rate` threshold is lower). This is **not a functional bug** -- it doesn't change scoring behavior, since the redundant clause can never independently trigger anything the other doesn't already cover -- but it is dead code directly attributable to the G4 change, worth noting for future cleanup. **Not modified in this phase**, per the instruction to preserve the G4 RS separation exactly and change only what's evidence-justified.

Each category's points are summed and capped (`min(50.0, ...)` for Statistical); the four category totals (Structural + Metadata + Statistical + Visual) sum to `suspicion_score`, independent of Tampering.

## 4. Detector Evidence Mapping

See the table in Section 3. All five signals are, in principle, measuring aspects of "how randomized/equalized does the LSB plane look" -- the shared conceptual ground that motivates this investigation.

## 5. Correlation Analysis

[MEASURED] Full 92-sample corpus, `tests/evaluation/g6_results/g6_correlation.json`. Pearson correlations (RS uses `estimated_embedding_rate`, the embedding-evidence-only field per the G4 separation; visual-balance uses `-min_balance_delta`, sign-inverted so higher = more suspicious, consistent with the other four):

| Pair | Pearson | Spearman |
|---|---|---|
| **LSB entropy <-> visual-balance** | **0.9469** | 0.8046 |
| **Chi-Square <-> RS** | **0.6709** | 0.6309 |
| Chi-Square <-> visual-balance | 0.4503 | 0.3568 |
| SPA <-> visual-balance | 0.4034 | 0.3883 |
| SPA <-> LSB entropy | 0.3841 | 0.4002 |
| Chi-Square <-> LSB entropy | 0.3520 | 0.5315 |
| RS <-> visual-balance | 0.3479 | 0.3087 |
| RS <-> LSB entropy | 0.3146 | 0.3799 |
| RS <-> SPA | 0.2526 | 0.2969 |
| Chi-Square <-> SPA | 0.2295 | 0.2507 |

[MEASURED] Only one pair exceeds 0.7 (the entropy/visual-balance pair, already established in G3/G5 and reconfirmed here). **A second, previously unexamined pair -- Chi-Square <-> RS -- shows moderate correlation (0.67)**, not reported in prior phases because G3/G5's correlation work focused on the entropy/balance pair specifically. All other pairs are weak-to-moderate (0.23-0.45). Per the spec's explicit caution, **correlation alone is not treated as proof of redundancy** -- see Sections 6 and 7 for decision-level and ablation evidence, which tell a more complete and in places different story.

Decision-level (each detector's own `is_suspicious` flag vs. ground truth), 92 samples:

| Detector | TP | FP | TN | FN | Sensitivity | Specificity | FPR | Precision |
|---|---|---|---|---|---|---|---|---|
| Chi-Square | 25 | 3 | 30 | 34 | 0.424 | 0.909 | 0.091 | 0.893 |
| RS | 33 | 1 | 32 | 26 | 0.559 | 0.970 | 0.030 | 0.971 |
| SPA | 43 | 21 | 12 | 16 | 0.729 | 0.364 | 0.636 | 0.672 |
| LSB entropy | 44 | 23 | 10 | 15 | 0.746 | 0.303 | 0.697 | 0.657 |
| Visual-balance | 43 | 18 | 15 | 16 | 0.729 | 0.455 | 0.545 | 0.705 |

[MEASURED] **Chi-Square and RS are the two most precise, most conservative detectors** (precision 0.89 and 0.97 respectively, FPR 0.09 and 0.03). SPA, LSB entropy, and visual-balance form a second cluster: higher sensitivity but much higher FPR (0.55-0.70) -- they trigger far more readily. This split does not track the correlation clusters found above (e.g. Chi-Square correlates most with RS, yet the two show very different sensitivity).

## 6. Decision-Level Redundancy

[MEASURED] Full 5-detector unique-contribution analysis (a sample counts as a detector's "unique" TP/FP only if **no other of the 5** also flags it), `tests/evaluation/g6_results/g6_correlation.json`:

| Detector | Unique TP | Unique FP | Note |
|---|---|---|---|
| Chi-Square | 0 | 0 | Never uniquely flags anything |
| RS | 3 | 0 | Some unique true-positive value; never uniquely wrong |
| SPA | 4 | 2 | Most unique true-positive value; also the only detector with unique false positives |
| LSB entropy | 0 | 0 | **Every** entropy flag is co-flagged by at least one other detector |
| Visual-balance | 0 | 0 | Confirms and extends the G5 finding |

[MEASURED] This refines the G5 finding (which only compared entropy vs. balance pairwise and found entropy had "1 unique TP, 5 unique FP"): once the **full 5-detector cluster** is considered, entropy's previously-apparent uniqueness (relative to balance alone) turns out to always be covered by SPA, RS, or Chi-Square too. **Chi-Square, LSB entropy, and visual-balance each contribute zero decision-level-unique detections** in this corpus; RS and SPA retain genuine (if modest) unique value.

## 7. Leave-One-Detector-Out Analysis

[MEASURED] For each detector, its raw signal was zeroed in a copy of the real `statistical_res`/`visual_res` dict fed to the actual, unmodified `SuspicionScoringEngine.evaluate()` -- this measures the detector's **point-contribution impact on the final weighted-sum score**, which is a different (and in places more informative) lens than the decision-flag overlap in Section 6, since it captures cases where a detector's points tip the aggregate threshold even when its own flag was "redundant." Full 92-sample corpus:

| Removed detector | TP | FP | TN | FN | Sensitivity | FPR | Classification changes | Unique TPs lost |
|---|---|---|---|---|---|---|---|---|
| (none -- full) | 51 | 22 | 11 | 8 | 0.864 | 0.667 | -- | -- |
| Chi-Square | 51 | 22 | 11 | 8 | 0.864 | 0.667 | **0** | 0 |
| RS | 45 | 22 | 11 | 14 | 0.763 | 0.667 | 6 | **6** |
| SPA | 48 | 19 | 14 | 11 | 0.814 | 0.576 | 6 | 3 |
| LSB entropy | 51 | 19 | 14 | 8 | 0.864 | 0.576 | 3 | **0** |
| Visual-balance | 47 | 15 | 18 | 12 | 0.797 | 0.455 | 11 | 4 |

[MEASURED] **Chi-Square's removal changes zero classifications, in the aggregate and in every one of the 14 corpus classes individually** (verified per-class, `tests/evaluation/g6_results/g6_lodo_ablation.json`) -- a complete, exception-free result, not a marginal one. Despite having the second-best precision of the five (Section 5), Chi-Square's point contribution never tips the final threshold either way in this corpus.

[MEASURED] **RS's removal is the most costly for sensitivity** (6 unique TPs lost) -- more than its decision-level unique-flag count (3, Section 6) suggested, because RS's *points* matter in additional cases where its own boolean flag overlapped with another detector's, but the combined total still needed RS's contribution to cross 20.0.

[MEASURED] **LSB entropy's removal costs zero true positives while fixing 3 false positives** -- a strictly one-directional improvement in this corpus, the cleanest result of the five. This is a stronger, more decisive version of the G5 finding.

[MEASURED] **Visual-balance's removal has the largest overall effect** (11 classification changes) despite contributing zero *unique* decision-level flags (Section 6) -- its point contribution provides real "weight" in the sum even in samples where its own threshold-crossing was redundant with entropy's.

**Per-class detail** (number of classification changes per detector, only classes with at least one change shown; full data in the JSON artifact):

| Class | n | Chi2 | RS | SPA | Entropy | Balance |
|---|---|---|---|---|---|---|
| photograph_real | 18 | 0 | 0 | 2 | 2 | 3 |
| grayscale_real | 4 | 0 | 0 | 0 | 0 | 2 |
| illustration_real | 8 | 0 | 0 | 0 | 0 | 2 |
| photograph_proxy | 9 | 0 | 0 | 0 | 0 | 2 |
| document_real | 9 | 0 | 0 | 1 | 1 | 0 |
| alpha_real, document_proxy, illustration_proxy, low_color_proxy, screenshot_proxy | 4-6 each | 0 | 1 | 0-1 | 0 | 0 |
| repeated_texture_real, grayscale_proxy | 4-12 | 0 | 0 | 0 | 0 | 0-1 |
| repeated_structure_proxy | 1 | 0 | 0 | 0 | 0 | 0 |

[MEASURED] Chi-Square's zero impact holds without a single exception across every class, confirming it is not merely averaging out to zero overall while mattering in a specific subgroup.

## 8. Cluster Aggregation Experiments

**Architectural scope note:** the spec's 5-member cluster spans two scoring categories (Section 3). Merging visual-balance's 20-point budget into the 50-point statistical budget would be a broader architectural change than "narrowly scoped." The **primary experiment** below therefore aggregates only the 4 same-category detectors (Chi-Square, RS, SPA, LSB entropy) within their existing shared 50-point budget -- a genuinely narrow candidate change. A full 5-detector merge is also computed and reported, but explicitly labeled **exploratory-only, not proposed** (see below).

[MEASURED] Primary experiment, `tests/evaluation/g6_aggregation_experiment.py`, replacing the current independently-tiered-and-summed 4-detector score with `aggregation_fn(chi2, rs, spa, entropy) * 50.0`, structural/metadata/visual/tampering unchanged:

| Method | Formula | TP | FP | TN | FN | Sensitivity | FPR | Precision | vs. current |
|---|---|---|---|---|---|---|---|---|---|
| **Current (production)** | independently tiered, summed, capped at 50 | 51 | 22 | 11 | 8 | 0.864 | 0.667 | 0.699 | -- |
| A. Arithmetic mean | `mean(4) x 50` | 54 | 25 | 8 | 5 | 0.915 | 0.758 | 0.684 | +3 TP, **+3 FP** (worse FPR) |
| B. Median | `median(4) x 50` | 53 | 23 | 10 | 6 | 0.898 | 0.697 | 0.697 | +2 TP, +1 FP (net worse FPR) |
| C. Trimmed mean | `mean(middle 2 of sorted 4) x 50` | 53 | 23 | 10 | 6 | 0.898 | 0.697 | 0.697 | identical to B (degenerate with only 4 values) |
| D. Maximum | `max(4) x 50` | 59 | 33 | 0 | 0 | **1.000** | **1.000** | 0.641 | flags every sample -- unusable |
| E. Agreement-weighted mean | `mean(4) x fraction(>0.30) x 50` | 48 | 20 | 13 | 11 | 0.814 | 0.606 | 0.706 | **-3 TP**, -2 FP |

[MEASURED] **No candidate improves both sensitivity and FPR simultaneously.** Method D is unusable (degenerates to flagging everything, since any single detector firing floods the mean once weighted by itself). Method A improves sensitivity only by accepting a worse FPR -- exactly the trade-off the spec explicitly forbids treating as a win ("never sacrifice false-positive control merely to increase sensitivity"). Methods B/C are marginal (small gains and small losses in the same direction, netting to essentially a wash). Method E is the mirror-image forbidden trade (sacrifices sensitivity for FPR) -- not clearly wrong, but not a clean win either, and not something to adopt unilaterally without explicit design sign-off.

[MEASURED, EXPLORATORY ONLY, NOT PROPOSED] Full 5-detector merge across the category boundary (70-point combined budget):

| Method | Sensitivity | FPR |
|---|---|---|
| mean | 0.949 | 0.879 |
| median | 0.898 | 0.667 |
| max | 1.000 | 1.000 |

Even in this broader, out-of-scope exploration, no method achieves a clean win -- the pattern from the primary experiment holds.

## 9. Results by Corpus Class

Covered inline in Section 7's per-class table (the most information-dense way to present this per the actual findings -- no detector's aggregate behavior changes materially when broken out by class, except that Chi-Square's zero-impact and visual-balance's broader impact both hold with unusual consistency across classes rather than being concentrated in one).

## 10. False-Positive Impact

[MEASURED] Of the individual-detector removals (Section 7), only LSB entropy's removal is a pure FP improvement (3 fixed, 0 TPs lost). Visual-balance's removal fixes the most FPs (7) but at a real sensitivity cost (4 TPs lost). None of the Phase 6 aggregation formulas improve FPR without also either losing sensitivity (E) or being neutral-to-worse (B/C), except by accepting one of those trade-offs.

## 11. Sensitivity Impact

[MEASURED] RS carries the most weight-bearing sensitivity value of the five (6 TPs depend on its contribution) despite being the most conservative/precise individual detector -- an apparent tension that is fully explained: RS is precise on its own terms (rarely wrong when it fires) but its point contribution is often the deciding weight in borderline sums, which a purely flag-based redundancy view (Section 6) would not reveal.

## 12. Independent Evidence Assessment

Using the spec's own four-way framing (A: redundant, B: partially complementary, C: class-dependent, D: genuinely independent):

- **Chi-Square: (A) redundant**, and unusually cleanly so -- [MEASURED] zero unique decision-level detections, zero classification-changing impact, in every class without exception. This is a stronger and more specific finding than "correlated": Chi-Square's *entire* contribution to final outcomes in this corpus is currently absorbed by other detectors.
- **RS: (B) partially complementary.** [MEASURED] Moderately correlated with Chi-Square (0.67) but decision-level and ablation evidence both show it carries real, load-bearing unique value (3 unique flags, 6 ablation-sensitive TPs) -- the correlation with Chi-Square does not translate into redundant *decisions*.
- **SPA: (B) partially complementary**, with the important caveat that its unique contribution is not one-directional -- [MEASURED] 4 unique TPs but also 2 unique FPs.
- **LSB entropy: (A) redundant** with the broader cluster (not just visual-balance) -- [MEASURED] zero unique flags against the full 5-detector set, and its ablation removal is a strict one-directional improvement.
- **Visual-balance: (A) redundant** at the decision-flag level, but [MEASURED] its point-contribution still measurably affects final classification (11 changes) -- an important nuance meaning "redundant" here describes its *flag*, not its *point weight*.

No detector in this cluster meets the bar for **(D) genuinely independent** evidence in this corpus.

## 13. Production Change Decision

**OPTION A: NO PRODUCTION CHANGE JUSTIFIED.**

Reasoning, directly from the measured evidence:
1. The only individually clean, one-directional finding (LSB entropy: 0 TPs lost, 3 FPs fixed on its own) is real, but acting on it alone would require deciding how to redistribute its 8.8-point weight and would still leave the deeper cross-category redundancy with visual-balance unaddressed -- a decision that itself needs explicit design sign-off, not a unilateral drop.
2. None of the five candidate replacement aggregation formulas for the four same-category detectors improves both sensitivity and FPR simultaneously (Section 8) -- every option that helps one axis measurably hurts the other, which is exactly one of this phase's explicit hard-stop conditions ("results require threshold manipulation to improve" / no option that isn't a trade-off).
3. The one genuinely broader option (merging across the Statistical/Visual category boundary) was explicitly ruled out of scope as a "broader redesign" per the hard-stop conditions, and even that exploratory calculation did not produce a clean win.
4. The corpus (92 samples, small per-class counts) is not large enough to distinguish "this aggregation method is genuinely better" from "this aggregation method happened to move a handful of borderline samples in this specific sample set" -- adopting any of the tested formulas now would risk exactly the circular-validation risk Phase 7 warns against.

**Production code is preserved byte-for-byte. `app/core/scoring.py` is not modified.**

## 14. Regression Testing

No production code was changed, so per the phase's own instruction ("if production code changes, add tests"), **no new regression tests were added**. The investigation's evaluation scripts (`g6_dataset_builder.py`, `g6_correlation_analysis.py`, `g6_lodo_ablation.py`, `g6_aggregation_experiment.py`) are analysis tools, not test files, consistent with the G5 precedent for investigation-only phases.

[MEASURED] Full suite re-run after all investigation work: `227 passed, 0 failed, 1 skipped` -- unchanged from the recorded G6 baseline.

## 15. Limitations

- All findings are specific to this 92-sample, partly-synthetic corpus (per the repeated instruction across G2-G6, not real-world accuracy). Per-class sample counts are small (as low as n=1) and stated explicitly wherever used.
- The ablation (Section 7) zeroes each detector's raw signal independently; it does not model how the *other* detectors' thresholds might have been tuned differently had this detector never existed -- it measures marginal, not counterfactually-redesigned, impact.
- The aggregation experiment (Section 8) tests only 5 simple, literature-plausible candidate formulas; more sophisticated (e.g. learned or calibrated) combinations were explicitly out of scope (no ML permitted) and were not tried.
- "Redundant" throughout this report is a decision-level, corpus-specific, threshold-specific finding -- it is not a claim that Chi-Square or LSB entropy are conceptually meaningless steganalysis techniques (per the phase's explicit interpretation rules, "did not provide unique positive detections in this corpus" is used in place of "is useless").
- The Chi-Square/RS correlation (0.67, Section 5) is newly observed and not yet investigated for a mechanistic cause (unlike the entropy/visual-balance pair, which has been mechanistically explained since G1-G5) -- flagged as an open question, not resolved here.

## 16. Final Recommendation

[PROPOSED]
1. Do not implement any of the five tested aggregation formulas as-is; none clears the bar of "improves both false-positive control and sensitivity" that this phase's own principle requires.
2. If future work pursues Target A/B from G5's own recommendation (merging LSB entropy and visual-balance), this phase's evidence sharpens the case: LSB entropy specifically (not just its correlation with visual-balance) is now shown to be fully redundant at the decision level against the *entire* cluster, not only against visual-balance -- worth carrying into that future design phase as additional, more specific evidence.
3. Chi-Square's complete, exception-free classification-inertness in this corpus (Section 7) is the most decisive single finding of this phase and is worth a dedicated, narrowly-scoped follow-up: is this corpus simply too small/homogeneous to exercise Chi-Square's genuine strengths, or is its current threshold/weight miscalibrated for this scoring model specifically? This phase cannot distinguish between those explanations and does not attempt to.
4. The newly observed Chi-Square/RS correlation (0.67) should be mechanistically investigated in a future phase, following the same primary-source-first discipline used for the entropy/visual-balance and RS/sym_diff investigations in G3-G5.

---

## Final Output Summary

1. **Baseline test result:** 227 passed, 0 failed, 1 skipped (matches expected G4/G5 baseline).
2. **Files inspected:** `scoring.py`, `statistical.py`, `visual_extractor.py`, `rs_analysis.py`, `spa_analysis.py`, `evidence.py`, existing G3/G4 corpus metadata and results.
3. **Files changed:** none under `app/`.
4. **Exact production changes:** none (Option A selected).
5-8. Correlation, decision-level, ablation, and aggregation findings: Sections 5-8 above.
9. **Before/after metrics:** not applicable -- no production change made.
10. **Full test result:** 227 passed, 0 failed, 1 skipped (unchanged).
11. **Exact artifact filenames:** see the file list in the accompanying message.
12. **git status:** no `.git` in this environment (see Section 2); pristine-diff equivalent shows no new production changes.
13. **Confirmation:** no commit or push was performed (none was possible or attempted; this environment has no version control).
