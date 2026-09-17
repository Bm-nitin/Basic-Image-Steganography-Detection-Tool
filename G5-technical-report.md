# G5 Technical Report

**Evidence labels used throughout:** [MEASURED], [SOURCE-VERIFIED], [INFERRED], [PROPOSED] — as defined in the G5 spec.

## 1. Objective

Investigate two questions without redesigning scoring: (A) whether the whole-image chi-square application is appropriate for this project's random-subset LSB embedding model, and (B) whether LSB entropy and visual-balance provide sufficiently independent evidence to justify treating them as separate scoring signals. Both are investigation targets; a production change is only justified if the evidence clearly supports one.

## 2. G4 Baseline

[MEASURED] Reproduced at the start of this phase: `227 passed, 0 failed, 1 skipped`. Matches the stated G4 baseline exactly.

**Repository/git note:** this working directory has no `.git` (it was extracted from an uploaded archive, not cloned) — `git status`/`git log`/`git diff --stat` could not be run as literal commands. This was already true and reported in G4. The equivalent safety check used since G1 (diffing against a preserved pristine extraction of the original archive) was used instead: [MEASURED] exactly the 5 expected files differ from pristine (`visual_extractor.py`, `scoring.py`, `evidence.py`, `rs_analysis.py` from G1/G4, `copy_move_analysis.py` from G3) — no unrelated modifications found. This is recorded as the G5 starting baseline.

## 3. Chi-Square Source Verification

[SOURCE-VERIFIED, carried forward from G3, re-confirmed by direct inspection this phase] `chi_square_attack()` implements Westfeld's Pairs-of-Values test exactly: pairs `(2k, 2k+1)` for `k in [0,127]`, expected frequency `= pair_sum/2`, and the standard two-category chi-square goodness-of-fit sum. `p_val = stats.chi2.sf(chi2_sum, df)`. This is unchanged in G5 and was not touched.

[MEASURED, this phase] The implementation analyzes the **whole flattened channel** (`flat = channel.flatten()`) — every pixel of one channel, no spatial blocks, no sequential windowing. It is applied **per channel**: gray, red, green, blue independently (`analyze()` in `statistical.py`, lines ~403-414), then the max of `probability_stego` across all four is taken as `max_chi2_indicator`.

[INFERRED, consistent with well-established steganalysis literature] Westfeld's classical attack derives much of its practical power from **sequential/windowed** application — scanning a growing prefix of the image to localize where embedding starts and stops. The whole-image, single-application variant implemented here is the degenerate case of that windowed algorithm (window = entire image), valid but with reduced sensitivity to partial-coverage embedding, since an unmodified majority of pixels dilutes the statistic.

## 4. Chi-Square Applicability Investigation

Answering the nine questions from the spec directly:

1. **Formulation:** Westfeld PoV chi-square, exact match. [SOURCE-VERIFIED]
2. **Assumptions:** the tested channel's own LSBs are being randomized (classical LSB replacement); pair-of-values counts are expected to equalize toward 50/50 within each pair as the randomized fraction grows. [SOURCE-VERIFIED]
3. **Population analyzed:** every pixel of one channel, whole image. [MEASURED from source]
4. **Applied how:** globally per channel (not by block, not sequentially), max across 4 channels. [MEASURED from source]
5. **Embedding model assumed by the source:** direct LSB replacement, classically over a sequential/contiguous region. [SOURCE-VERIFIED]
6. **This project's actual model:** LSB replacement over a **randomly-selected, spatially-scattered subset** of pixel values per channel, at a configurable rate (`embed_lsb()` in `g2_corpus_generator.py`, unchanged since G2). [MEASURED from source]
7. **Effect of random-subset embedding on signal strength:** [MEASURED, new and more precise this phase — see §5] the effect is not uniform. For a channel that is **directly** embedded (a real color image's R/G/B, or a genuinely grayscale source's single channel), the ratio moves monotonically toward 1.0 as coverage increases, exactly as theory predicts — confirmed on real photographs' individual R/G/B channels showing clean monotonic convergence (e.g. coffee: blue channel ratio 21.24 -> 15.60 -> 6.48 -> 0.97 across clean->low->medium->high). But this is measurably **diluted or destabilized** at partial coverage, and for **derived** channels — see finding below — direct embedding-rate reasoning does not apply at all.
8. **Can the whole-image statistic reasonably detect partial/random embedding?** [MEASURED] Yes for direct-embedded channels, with reduced sensitivity below full coverage (consistent with G3); the aggregate (max-across-channels) production behavior for RGB photos still activates correctly at medium/high payload because at least one of R/G/B usually crosses threshold, even when others don't.
9. **Is the resulting value's interpretation technically justified?** Mostly [SOURCE-VERIFIED] for `chi2_stat`/`p_value`; `probability_stego`'s artificial floor (`max(p_val, 0.85)` etc.) was already flagged as misleadingly-named in G1 and is unchanged/out of scope here.

## 5. Chi-Square Measurements

[MEASURED] All measurements use the **existing** 92-sample G3 corpus (`tests/evaluation/g3_samples/`, `tests/evaluation/g2_samples/` — not regenerated), re-analyzed with the unmodified `chi_square_attack()` via a new read-only script, `tests/evaluation/g5_chisquare_analysis.py`, writing to `tests/evaluation/g5_results/g5_chisquare_analysis.json`.

**Per-source-image ratio trend (gray channel), tracked individually rather than averaged across different base images within a class (an averaging artifact was caught and corrected during this phase — see note below):**

| Source | clean | low | medium | high | Monotonic toward 1.0? |
|---|---|---|---|---|---|
| document_real_page | 2.23 | 1.81 | 1.23 | 0.91 | Yes |
| document_real_text | 2.00 | 1.96 | 1.27 | 0.99 | Yes |
| grayscale_real_moon | 10.11 | 8.00 | 3.21 | 1.14 | Yes |
| illustration_real_checkerboard | 2487.78 | 1795.18 | 624.74 | 1.44 | Yes |
| illustration_real_colorwheel | 103.71 | 74.37 | 27.09 | 0.78 | Yes |
| repeated_texture_real_gravel | 1.02 | 1.04 | 1.08 | 0.91 | Roughly flat near 1.0 (little room to move) |
| repeated_texture_real_grass | 0.99 | 0.85 | 1.00 | 1.11 | Roughly flat near 1.0 |
| **photograph_real_coffee (gray)** | 4.77 | 5.02 | 4.99 | 6.45 | **No — moves away from 1.0** |
| **photograph_real_chelsea (gray)** | 1.58 | 1.56 | 1.76 | 2.04 | **No — moves away from 1.0** |
| **photograph_real_rocket (gray)** | 2.79 | 3.20 | 4.63 | 6.12 | **No — moves away from 1.0** |

[MEASURED] 11 of 19 fully-populated per-source series were monotonic toward equalization; the 8 non-monotonic cases are **fully explained** by two mechanisms found this phase, not left as unexplained noise (see below).

**New finding 1 [MEASURED, root-caused] — the derived-grayscale artifact:** for the three real photographs, the **gray channel's** ratio moves *away* from 1.0 as payload increases (the anomaly in the table above), while each photo's **individual R, G, B channels** (directly embedded) show clean, textbook-correct monotonic convergence toward 1.0. Example, `coffee`:

| Channel | clean | low | medium | high |
|---|---|---|---|---|
| gray (derived) | 4.77 | 5.02 | 4.99 | 6.45 |
| red | 5.76 | 4.27 | 1.89 | 1.00 |
| green | 9.89 | 7.79 | 2.94 | 1.17 |
| blue | 21.24 | 15.60 | 6.48 | 0.97 |

[INFERRED, mechanistically explained] `StatisticalAnalyzer.analyze()` computes gray via `rgb_img.convert('L')` **after** R/G/B have already been independently LSB-randomized. Grayscale conversion is a rounded weighted average (`0.299R+0.587G+0.114B`) of three independently-perturbed channels — this is not itself a direct LSB-randomization process, so Westfeld's theoretical prediction (which assumes the *tested* channel's own bits are being randomized) does not apply to it. This explains all 3 non-monotonic real-photo cases precisely.

**Is this artifact harmful in production?** [MEASURED] No, in this corpus. Checked directly: on every clean sample, `gray`'s `probability_stego` never exceeds the max of `red`/`green`/`blue`'s while itself being >0.5 (0 such cases found across all 33 clean samples). Since the pipeline takes the **max across all 4 channels**, and the correctly-behaving R/G/B channels dominate for genuine RGB photos, the derived-gray artifact is currently masked, not actionable. This is why **no code change is proposed** for it (§10).

**New finding 2 [MEASURED, root-caused] — low-color-diversity collapses degrees of freedom:** `illustration_proxy`, `alpha_proxy`, `low_color_proxy`, `document_proxy`, `repeated_structure_proxy` (all G2 synthetic proxies with few unique colors) show `df=3-6` (vs. `df=124-127` for real photographs) — meaning only 4-7 of the 128 possible value-pairs contain enough pixels (`pair_sum > 4`) to even enter the test. [MEASURED] This gives the test very little discriminating power below full-capacity embedding for this specific class of carrier: `illustration_proxy`'s `max_chi2_indicator` is exactly `0.0` at clean/low/medium and only activates (`0.89`) at high (100%) payload. This is a distinct mechanism from finding 1 and from the whole-image dilution effect already known from G3 — it is a fundamental applicability limit of chi-square specifically for low-unique-color content, not a bug: with so few populated pairs, the statistic is nearly always dominated by one or two hugely-imbalanced natural pairs (`chi2_sum` exactly `65536.00` — the total pixel count — confirming one pair holds almost the entire image), and `p_val` correctly ends up near zero regardless (no false positive results from this specific mechanism in the corpus, confirmed).

**Clean-image false positives:** [MEASURED] `grayscale_proxy`'s clean sample shows a non-zero `max_chi2_indicator` — carried over from G3, unchanged and not re-investigated further in this pass, since it was previously attributed (inferred) to the synthetic generator's added Gaussian fine-grain noise, not chi-square's implementation itself.

## 6. LSB Entropy vs Visual-Balance Investigation

[MEASURED] Uses the existing G4 re-scan (`tests/evaluation/g4_results/g4_after_results.json`, 92 samples, already computed by the unmodified pipeline — no new scoring runs were performed). New analysis script: `tests/evaluation/g5_lsb_independence.py`, writing to `tests/evaluation/g5_results/g5_lsb_independence.json`.

## 7. Correlation and Error Overlap

**Correlation (Pearson / Spearman, visual-balance delta sign-inverted so higher = more suspicious in both):**

| Split | n | Pearson | Spearman |
|---|---|---|---|
| Overall | 92 | 0.9469 | 0.8046 |
| Clean only | 33 | 0.9595 | 0.8617 |
| Stego only | 59 | 0.9434 | 0.7651 |
| Payload: low | 19 | 0.9498 | 0.8655 |
| Payload: medium | 19 | 0.9553 | 0.8650 |
| Payload: high | 19 | n/a (zero variance — both saturate) | n/a |

[MEASURED] The strong correlation (r≈0.947, matching G3's 0.952 and G4's 0.947) **persists** across every split with enough variance to measure it — clean-only, stego-only, and both non-saturated payload levels. It is not an artifact of pooling clean and stego samples together.

**Error overlap (each detector's own `is_suspicious` decision, independent of `scoring.py`'s combined logic), full 92-sample corpus:**

| | Both flag | Entropy only | Balance only | Neither |
|---|---|---|---|---|
| True positives (59 stego samples) | 43 | 1 | **0** | 15 |
| False positives (33 clean samples) | 18 | 5 | **0** | 10 |

[MEASURED] **`balance_only = 0` in both rows, across the entire corpus.** Visual-balance never independently flags a single sample — true positive or false positive — that LSB entropy does not also flag. Entropy, by contrast, has a small independent contribution: 1 unique true positive (`document_proxy`, high payload) and 5 unique false positives (4 in `photograph_real`, 1 in `document_real`).

This was checked at the per-class level too (§8) — the `balance_only = 0` result holds in **every one of the 14 classes**, without exception, including the one class with markedly weaker continuous correlation (`document_real`, r=0.575): even there, `fp_balance_only=0` and `tp_balance_only=0`. This is an important, precise nuance: the *magnitude* of agreement (correlation coefficient) can be imperfect while the *decision-level* redundancy (which samples get flagged) is still complete — the two metrics' continuous values don't move in lockstep on `document_real`, but they still cross their respective suspicion thresholds together (or not at all) every single time in this corpus.

## 8. Carrier-Class Analysis

| Class | n | Pearson r | balance-only flags (TP+FP) |
|---|---|---|---|
| photograph_real | 18 | 0.938 | 0 |
| photograph_proxy | 9 | n/a (no variance) | 0 |
| document_real | 9 | 0.575 | 0 |
| document_proxy | 5 | 0.967 | 0 |
| screenshot_proxy | 6 | 0.966 | 0 |
| illustration_real | 8 | 0.977 | 0 |
| illustration_proxy | 4 | 0.964 | 0 |
| low_color_proxy | 4 | 0.964 | 0 |
| alpha_real | 4 | 0.964 | 0 |
| alpha_proxy | 4 | 0.965 | 0 |
| grayscale_real | 4 | n/a (no variance) | 0 |
| grayscale_proxy | 4 | n/a (no variance) | 0 |
| repeated_texture_real | 12 | n/a (no variance) | 0 |
| repeated_structure_proxy | 1 | n/a (n too small) | 0 |

[MEASURED] The zero-variance ("n/a") classes are themselves informative, not missing data: they indicate both metrics are simultaneously saturated (all samples read as maximally suspicious or all as clean) for that class — a ceiling/floor effect already partly documented in G2/G3, now confirmed to affect *both* metrics identically in lockstep for these classes, which is itself further evidence of redundancy rather than a gap in the analysis. **No class of any size shows a meaningful `balance_only` contribution.**

**Answering the spec's specific questions directly:**
- *Does visual-balance identify samples entropy does not?* [MEASURED] No — zero instances, overall or in any class.
- *Does entropy identify samples visual-balance does not?* [MEASURED] Yes, a small number (1 TP, 5 FP) — entropy is the (slightly) more sensitive of the two, not the other way around.
- *Are their errors overlapping?* [MEASURED] Yes, heavily — the 18 shared false positives account for the large majority of both metrics' false-positive burden.
- *Do they produce independent false positives?* [MEASURED] Essentially no — every one of visual-balance's false positives is also one of entropy's; entropy has a few (5) that balance misses (correctly, i.e. balance is the more conservative one, not that it finds different ones).

## 9. Root Causes / Findings — Summary

| # | Finding | Label |
|---|---|---|
| 1 | Chi-square formula exactly matches Westfeld's PoV test | [SOURCE-VERIFIED] |
| 2 | Whole-image (not windowed) application dilutes partial-coverage sensitivity | [SOURCE-VERIFIED assumption] + [MEASURED effect] |
| 3 | Derived-grayscale channel breaks the direct-embedding assumption for real RGB photos, causing non-monotonic chi-square behavior specific to that one channel | [MEASURED, root-caused] |
| 4 | That artifact is currently masked/harmless in production due to max-aggregation across channels | [MEASURED] |
| 5 | Low-unique-color synthetic carriers collapse chi-square's degrees of freedom, giving near-zero power below full-capacity embedding | [MEASURED, root-caused] |
| 6 | LSB entropy and visual-balance are highly correlated in every measurable split (overall, clean-only, stego-only, by payload) | [MEASURED] |
| 7 | Visual-balance contributes **zero** unique detections (TP or FP) beyond LSB entropy, in every class | [MEASURED] |
| 8 | This holds even where continuous correlation is weaker (document_real, r=0.575) — decision-level redundancy exceeds magnitude-level correlation | [MEASURED] |

## 10. Production Changes

**None made in G5.** For Target A: the one theoretically actionable finding (excluding the derived-gray channel from chi-square's max-aggregation, mirroring the G1.2 visual-balance fix) was evaluated and found to have **no measurable benefit** in this corpus — the artifact is already harmless — so implementing it would be a change with no evidenced payoff, not a minimal justified fix. For Target B: the evidence strongly and consistently supports classifying LSB entropy and visual-balance as **redundant** (option A of the spec's A/B/C/D framing) at the decision level, but the spec explicitly directs that high correlation/redundancy alone is not sufficient grounds to remove a metric or reweight scoring within this investigation-only phase — that requires its own deliberate design phase (how to merge two signals without breaking `scoring.py`'s category structure, what to do with the 5 samples where entropy alone is currently useful, etc.), which is out of scope here. **This is reported as the correct G5 outcome per the spec's explicit allowance:** "No production change justified yet" for Target A (no benefit), and "evidence is sufficient to justify design work, but not to skip straight to implementation" for Target B.

## 11. Regression Tests

**None added.** No production code was changed this phase. Per the spec ("if no production code is changed: add tests only if they validate a newly established invariant... do not manufacture tests simply to increase test count"), no new test file was created — the findings in this report are evaluation/analysis conclusions, not code invariants to lock in via unit tests. The full existing suite was re-run and confirmed unchanged (§2, §12).

## 12. G4 vs G5 Results

No production scoring, RS, or copy-move code changed — **G4 and G5 production behavior are identical.** [MEASURED] Full suite: `227 passed, 0 failed, 1 skipped`, unchanged from G4. `diff -rq` against the pristine archive shows the same 5 files differing as after G4, with no new production diffs.

New evaluation artifacts (all in `tests/evaluation/g5_results/`, none overwriting G3/G4 data):
- `g5_chisquare_analysis.json` — per-channel, per-sample chi-square detail for all 92 existing corpus images.
- `g5_lsb_independence.json` — correlation and error-overlap analysis.

## 13. Limitations

- The 92-sample corpus remains small; per-class sample counts (as low as 1, mostly 4-18) limit statistical confidence in every number reported here — stated explicitly per class throughout (§7, §8), not glossed over.
- The chi-square monotonicity analysis by individual source image (rather than by class-level averaging) was necessary after an early aggregation script incorrectly averaged different base photographs together within the `photograph_real` class, producing a misleading non-monotonic artifact; this was caught and corrected before being reported, and is noted here for transparency about the investigation process itself.
- "Redundant" (Target B) is a decision-level, corpus-specific finding under the current thresholds — it does not prove the two detectors are conceptually redundant in general (e.g. under different thresholds, or on carrier types not in this corpus, their independence could differ).
- The derived-grayscale chi-square artifact (finding 3) has only been checked for harm on this 33-sample clean set; a larger corpus could reveal a case where it does independently cause a false positive.
- No statistical significance testing (e.g. confidence intervals on the correlation coefficients) was performed; per the spec's instruction, no significance claim is made — the Pearson/Spearman values are reported as point estimates on this corpus only.

## 14. Recommended Next Phase

[PROPOSED]
1. If Target B's redundancy finding is to be acted on, a dedicated design phase (not an investigation phase) should decide how to represent LSB entropy and visual-balance as one evidence source in `scoring.py` without silently changing the 5 samples currently caught only by entropy — this is a scoring-architecture decision requiring explicit sign-off, consistent with G3/G4's discipline.
2. The derived-grayscale chi-square artifact (finding 3) does not need fixing now, but should be re-checked if the corpus grows — a larger, more diverse set of real photographs could reveal a case where it does cause an independent false positive, unlike the (currently harmless) 3-photo sample here.
3. No further action is proposed for the low-color-diversity chi-square limitation (finding 5) — it is a fundamental applicability boundary of the method, not a defect, and does not currently cause false positives.

---

## Git Safety

As in G4, this environment has no `.git`; `git status`/`git diff --stat` could not be run as literal git commands. Using the established pristine-diff equivalent: **no production file under `app/` changed in this phase.** Files added: `tests/evaluation/g5_chisquare_analysis.py`, `tests/evaluation/g5_lsb_independence.py`, `tests/evaluation/g5_results/g5_chisquare_analysis.json`, `tests/evaluation/g5_results/g5_lsb_independence.json`. No G3 or G4 file, result, or report was modified or overwritten.
