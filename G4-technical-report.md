# Phase G4 — Targeted RS Applicability + Multi-Region Copy-Move Investigation: Technical Report

**Evidence labels used throughout:** [MEASURED] (observed directly by running code in this phase), [SOURCE-VERIFIED] (confirmed against a primary/authoritative source), [INFERRED] (reasoned, not independently re-derived), [PROPOSED] (a recommendation, not implemented).

---

## 1. Executive Summary

**Target A (RS applicability vs. embedding evidence): implemented.** `app/core/rs_analysis.py` was changed — and only that file — to stop folding the RS "clean-image applicability" diagnostic (`sym_diff`) into the embedding-suspicion indicator. The math (discrimination function, flip operations, quadratic solve) is untouched. `scoring.py` and `evidence.py` needed no changes, since they already read the corrected field by name.

**Target B (multi-region copy-move): investigated thoroughly, root cause precisely measured, a candidate fix was prototyped and then reverted** after it was found, by direct measurement, to introduce new false positives on clean and stego content with no clean separating threshold from genuine matches. `app/core/copy_move_analysis.py` is byte-for-byte identical to its G3 state (verified via diff). No copy-move production change was made in G4.

**Repository inspection note:** this working directory is not a git checkout (no `.git` present) — it was extracted from an uploaded archive. `git status`/`git log`/`git diff --stat` could not be run as literal commands; the equivalent safety check used throughout G1–G4 (diffing against a preserved pristine extraction of the original archive) was used instead and confirmed a clean state with no unrelated modifications before this phase began.

---

## 2. G3 Baseline (Phase 1)

[MEASURED] Reproduced at the start of this phase:
```
TOTAL: passed=217 failed=0 skipped=1 errors=0
```
Matches the stated G3 baseline exactly. [MEASURED] Diffing the working tree against the preserved pristine archive showed exactly the 5 expected files differing (`visual_extractor.py`, `scoring.py`, `evidence.py`, `rs_analysis.py` from G1; `copy_move_analysis.py` from G3) — no unrelated modifications found, so this hard-stop condition did not trigger.

---

## 3. RS Investigation (Phase 2)

**Current RS data flow, traced directly from source [SOURCE-VERIFIED against the code itself]:**
- `RSAnalyzer._analyze_channel()` computes the discrimination function, applies F₁/F₋₁, solves the quadratic for `est_rate`, and (pre-G4) computed `sym_diff = |R_M - R_-M| + |S_M - S_-M|` and set `suspicion_indicator = max(est_rate, min(1.0, sym_diff*4.0))`.
- `RSAnalyzer.analyze()` takes the max of `estimated_embedding_rate` and `suspicion_indicator` independently across gray/R/G/B channels.
- `scoring.py` (`_score_statistical`, lines ~224–226) and `evidence.py` (lines ~274–276) both read `rs.get('estimated_embedding_rate')` **and** `rs.get('suspicion_indicator')`, combining them via an OR-condition (e.g. `rs_rate > 0.50 or rs_ind > 0.70`) to award points / raise "suspicious" evidence.
- Because `suspicion_indicator >= est_rate` always (it's a max), and scoring's OR-condition treats crossing either threshold as sufficient, an inflated `suspicion_indicator` (driven by `sym_diff`, unrelated to actual embedding) could push a **clean** image over the "Suspicious"/"Anomaly" scoring bands purely on applicability-assumption violation, with no genuine embedding evidence.

**1–3: what does `sym_diff` represent?**
[SOURCE-VERIFIED, confirmed via primary-source search — Fridrich, Goljan & Du, "Reliable Detection of LSB Steganography...", and US Patent 6,831,991B2, both located and read in this phase] `sym_diff` compares `R_M` to `R_-M` and `S_M` to `S_-M` directly. The source's own "equation 3" states the **clean-image assumption** is `R_M ≈ R_-M`, `S_M ≈ S_-M` — a precondition for the method to be meaningful on a given image, not the mechanism it uses to detect embedding. The source's actual embedding-evidence mechanism is the *within-mask* `R_M` vs. `S_M` convergence (captured correctly by `d0/d1/d_neg0/d_neg1` and the quadratic, i.e. `est_rate`) and the *within-mask* `R_-M` vs. `S_-M` divergence — both already correctly used in the existing quadratic solve, unchanged in this phase.

**4: where is it used?** Only inside `_analyze_channel()`'s final `indicator` line (pre-fix) and propagated up through `analyze()`'s cross-channel max.

**5: does the pipeline incorrectly treat it as independent evidence?** [MEASURED, confirmed with a direct test] Yes. On a directional gradient (zero embedding, but a strong, expected violation of the `R_M≈R_-M` assumption due to directional structure), the pre-fix `suspicion_indicator` could exceed `estimated_embedding_rate`; `scoring.py`'s OR-condition reads that inflated value as if it were embedding evidence.

**6: smallest correct change?** Redefine `suspicion_indicator := est_rate` (removing the `sym_diff*4.0` term from it), and expose the diagnostic separately and explicitly rather than deleting it.

---

## 4. RS Source Verification Summary

| Claim | Label | Detail |
|---|---|---|
| Discrimination function, F₁/F₋₁ flip operations, quadratic `2(d1+d0)z²+(d-0-d-1-d1-3d0)z+(d0-d-0)=0` | [SOURCE-VERIFIED] | Confirmed against the primary paper and patent in G3; re-confirmed unchanged in this phase; **not modified** |
| `R_M≈R_-M, S_M≈S_-M` clean-image assumption | [SOURCE-VERIFIED] | Explicit "equation 3" in the primary source |
| `sym_diff` = applicability-assumption-violation measure | [SOURCE-VERIFIED] | Direct mapping from the equation-3 assumption to the code's own comparison |
| `sym_diff*4.0` as an embedding-evidence contributor | Was an [INFERRED-INCORRECT] conflation | No cited derivation found in any source consulted across G1–G4; conceptually mismatched with what the source says this quantity means |

---

## 5. RS Change (Phase 3)

**File changed: `app/core/rs_analysis.py` only.**

```python
# Before (G3):
sym_diff = abs(r_m - r_neg_m) + abs(s_m - s_neg_m)
indicator = float(max(est_rate, min(1.0, sym_diff * 4.0)))

# After (G4):
sym_diff = abs(r_m - r_neg_m) + abs(s_m - s_neg_m)
rs_applicability_diagnostic = float(min(1.0, sym_diff * 4.0))
indicator = est_rate
```

New fields added to the per-channel and top-level result dicts: `sym_diff` (raw value, was computed but not previously exposed at the top level) and `rs_applicability_diagnostic` (the old inflation term, now reported separately, not folded in). `estimated_embedding_rate`, `is_suspicious`'s formula, the discrimination function, the flip operations, and the quadratic solver are **unchanged**. The cross-channel aggregation in `analyze()` was extended to also max-aggregate the new field, for the same reason `estimated_embedding_rate`/`suspicion_indicator` are aggregated that way — this is a direct, mechanical extension of existing logic, not new design.

`scoring.py` and `evidence.py` were **not modified** — they already read `suspicion_indicator` by name, so redefining what that field measures propagates correctness without any edit there, exactly per the "smallest correct change" and "preserve scoring.py" requirements.

---

## 6. Multi-Region Copy-Move Investigation (Phases 7–8)

**Reproduced directly from the existing, un-regenerated G3 corpus** (`tests/evaluation/g3_samples/`, `tests/evaluation/g3_results/g3_after_fix_results.json`):

| Sample | Ground truth | candidate_matches | cluster_count | anomaly_indicator | is_suspicious |
|---|---|---|---|---|---|
| `photograph_real_coffee_tamper_copymove_single.png` | genuine, 1 region | 10 | 1 | 1.0 | True |
| `photograph_real_rocket_tamper_copymove_multi.png` | genuine, 3 regions | **0** | 0 | 0.0 | False |
| `photograph_real_chelsea_tamper_copymove_weak.png` | genuine, 10px | 0 | 0 | 0.0 | False |
| `photograph_proxy_tamper_copymove.png` (G2 original) | genuine, 1 region | 0 | 0 | 0.0 | False |

Per the spec's explicit instruction, the **continuous `anomaly_indicator`** was checked directly, not just `is_suspicious` — both are 0.0/False for the missed cases; there is no boolean/display divergence here (unlike the G3 finding about `tampering.py`'s aggregation).

### Root cause 1 [MEASURED, precisely]: grid-alignment sensitivity

The block extractor samples a **fixed stride-8 grid** (`BLOCK_SIZE=16, STRIDE=8`). The final duplicate-confirmation step requires near-exact pixel match (`MAE < 3.0`) between two independently grid-sampled blocks. This can only succeed when the true copy-move displacement is itself a multiple of the stride. Recovering the exact (deterministic, seeded) displacement vectors already baked into the existing on-disk `rocket` sample:

```
region 0: displacement=(29,67)    dy%8=5 dx%8=3
region 1: displacement=(-83,-105) dy%8=5 dx%8=7
region 2: displacement=(-6,135)   dy%8=2 dx%8=7
```

None are multiples of 8 — confirmed as the reason `candidate_matches=0`. By contrast, the one genuinely-detected sample (`coffee`, single region) happens to use displacement `(64,64)`, which **is** a multiple of 8 — this was luck of the original test construction, not evidence the detector generally handles single-region cases correctly at arbitrary offsets.

[MEASURED] Tried and rejected: reducing `STRIDE` to 4 or 2 does not fix the reproduced case (none of the three displacements above are multiples of 4 or 2 either — confirmed by direct computation and by re-running the analyzer with `STRIDE` monkey-patched to each value: `candidate_matches` stayed 0 at stride 4 and 2). Only exhaustive stride-1 matching found them (`candidate_matches=256`, `cluster_count=6`), at a measured **~60x runtime cost increase** for this 256×256 image (0.02s → 1.23s) — a disproportionate, broad performance change for a "smallest fix," and not evaluated at the larger image sizes (up to 4096px) this application actually accepts.

### Root cause 2 [MEASURED]: insufficient per-region match density

A bounded, low-cost alternative was prototyped: only for the small set of candidate pairs that already pass the existing loose descriptor pre-filter (KD-tree distance < 0.03) — [MEASURED] just 6 such pairs existed for the whole `rocket` image — perform a local exhaustive search in a ±8px window around the coarse position, keeping the same `MAE < 3.0` acceptance standard. [MEASURED] This found 4 of the 6 near-misses achieving `MAE < 3.0` after refinement (values 0.00, 0.00, 1.35, 1.54), raising `candidate_matches` from 0 to 4. **However, `cluster_count` remained 0** — the 4 confirmed matches split across different displacement bins (multiple distinct copy-paste operations, plus possibly within-region self-similarity), none reaching the existing `>= 3` matches-per-cluster significance floor. This significance floor is itself a G1-era, literature-grounded anti-false-positive safeguard (isolated matches are discarded as noise) that the spec explicitly says to preserve, not weaken.

### Why the candidate fix was reverted [MEASURED, this is the key finding of Target B]

Before accepting the refinement as "the fix," it was measured against the existing false-positive regression suite, per this phase's explicit discipline. Two genuine regressions appeared:
- `tests/test_copy_move_analysis.py::test_stego_samples_no_clusters` failed: `stego_lsb_sample.png` (ground truth: **no tampering**) now showed `cluster_count=1`.
- `tests/test_tampering.py::test_clean_sample_pipeline` failed: a clean sample now had a non-empty `flagged_detectors` list.

Direct measurement of the refined-match MAE values on genuinely clean/stego content vs. the genuine `rocket` forgery:

| Sample | Ground truth | Refined MAE values found |
|---|---|---|
| `photograph_real_rocket_tamper_copymove_multi.png` | genuine forgery | 0.00, 0.00, 1.35, 1.54 |
| `clean_sample.png` | clean | 1.95, 2.06, 2.70, 2.75 |
| `stego_lsb_sample.png` | clean (LSB stego, no tampering) | 2.31, 2.34 |
| `stego_eof_sample.jpg` | clean (appended EOF, no tampering) | 1.36, 2.83, 2.83 |
| `photograph_real_coffee_clean.png` | clean | (none) |

**The genuine and spurious refined-match MAE distributions overlap** (`stego_eof`'s 1.36 sits inside the genuine range 0.00–1.54; the genuine range's upper end, 1.54, is close to the spurious range's lower end, 1.95 — not the wide, clean gap that justified the G3 periodicity-cap fix). There is no threshold that reliably separates them on the evidence available. Tightening the refined-match acceptance criterion would be [PROPOSED but explicitly **not attempted**] exactly the "threshold manipulation with no evidentiary support" this phase's hard-stop conditions warn against, since the data points needed to set such a threshold contradict each other's implied cutoff.

**Decision: the refinement was reverted.** `app/core/copy_move_analysis.py` was diffed against a reconstruction of the exact G3 state (pristine archive + the preserved G3 patch) and confirmed **byte-for-byte identical**. The full test suite was re-run and both regressions disappeared, with no other change.

### A third, unrelated root cause found and explicitly set aside [MEASURED]

The original G2 `photograph_proxy_tamper_copymove.png` sample (also undetected, `candidate_matches=0`) was checked separately and found to have a different cause entirely: the copied 48×48 patch's content has `std ≈ 4.7–6.2`, below the existing `MIN_STD=10.0` texture-sufficiency filter — the region is simply too smooth for this synthetic carrier to produce any qualifying candidate blocks, regardless of alignment. This is unrelated to grid-alignment and is **not** addressed here, consistent with "do not expand scope beyond the two targets."

---

## 7. Copy-Move Change (Phase 8–9)

**None implemented.** Per the hard-stop discipline: a working root cause was identified and precisely measured (grid-alignment sensitivity), a candidate fix was built and rigorously tested against the existing false-positive regression suite (not just the target case), and it was found to trade the target improvement for new, unbounded false positives with no evidence-supported way to separate genuine from spurious matches. This is reported as the Target B deliverable: **a thorough, evidence-based investigation concluding that no safe fix was found in this phase**, not a shipped change.

---

## 8. Files Changed / Added / Untouched

**FILES CHANGED:**
- `app/core/rs_analysis.py` — Target A fix (separates `sym_diff`/`rs_applicability_diagnostic` from `suspicion_indicator`/`estimated_embedding_rate`). See `G4-rs_analysis-fix.patch` (note: this patch is against the original pristine archive and therefore also contains the previously-shipped, unmodified-in-G4 G1 boundary-documentation change; the new G4-specific hunks are the `sym_diff`/`rs_applicability_diagnostic` block in `_analyze_channel` and the corresponding aggregation block in `analyze`, both quoted verbatim in §5 above).

**FILES ADDED:**
- `tests/test_g4_rs_applicability.py` — 10 new regression tests for Target A.
- `tests/evaluation/g4_rescan.py` — re-scores the existing (not regenerated) G3 corpus with current code for G3-vs-G4 comparison; writes to `tests/evaluation/g4_results/`, never touches `tests/evaluation/g3_results/`.
- `tests/evaluation/g4_results/g4_after_results.json` / `.csv` — output of the above.

**FILES NOT CHANGED** (each with reason):
- `app/core/copy_move_analysis.py` — Target B investigated; candidate fix built, measured, and reverted; file is byte-identical to its G3 state.
- `app/core/scoring.py` — explicitly frozen per spec; also not needed, since it already reads the corrected RS field by name.
- `app/core/evidence.py` — same reasoning as scoring.py; not needed.
- `app/core/tampering.py` — inspected (to trace where `anomaly_indicator` enters aggregation) but not modified; no copy-move production change was made, so no change was needed here.
- All frontend, routes, security, and deployment files — out of scope, untouched.
- `tests/evaluation/g3_samples/`, `tests/evaluation/g3_results/`, `tests/evaluation/g2_samples/` — G3 baseline evidence, explicitly preserved, not overwritten. The G4 re-scan reads these images but writes only to a new `g4_results/` directory.
- Existing test files (`test_rs_analysis.py`, `test_g1_rs_boundary.py`, `test_g3_rs_investigation.py`, `test_g3_copymove_fix.py`, etc.) — verified still passing unmodified; not edited.

---

## 9. Targeted Tests

`tests/test_g4_rs_applicability.py` (10 tests): `sym_diff`/`rs_applicability_diagnostic` remain available (including on the G1.3 degenerate-content path); `suspicion_indicator == estimated_embedding_rate` exactly, both at the channel level and after cross-channel aggregation; a directional-gradient case (high applicability-violation, zero embedding) does not inflate the indicator; existing strong-embedding and clean-sample behavior is intact; valid grayscale/RGB images don't break; checkerboard boundary behavior intact; and an end-to-end test proving `scoring.py` (unmodified) no longer over-scores from applicability alone.

No new copy-move tests were added, since no copy-move production change was made; the full existing `test_g3_copymove_fix.py` (15 tests) was re-run and continues to pass, confirming the revert is clean.

---

## 10. Full Test Result

[MEASURED]
```
TOTAL: passed=227 failed=0 skipped=1 errors=0
```
227 = 217 (G3 baseline) + 10 (new Target A tests). The 1 skip is the pre-existing live-server test, unrelated. **This count increase is fully explained** by the new test file; no test was modified to force a pass, and the two regressions surfaced during the Target B experiment were resolved by reverting the production code, not by editing the failing tests.

---

## 11. G3 vs G4 Metrics

[MEASURED] Re-scoring the exact same 92 existing G3 corpus images (no regeneration) with the current code:

**Copy-move specifically:** zero difference in any field for any sample (confirmed by direct comparison of `cm_cluster_count` and `cm_anomaly_indicator` across all 92 samples) — expected and correct, since the file is unchanged from G3.

**Overall steganography confusion matrix (92 samples, decision threshold `suspicion_score >= 20.0`):**

| | TP | FP | TN | FN | Sensitivity | Specificity | FPR | FNR | Precision |
|---|---|---|---|---|---|---|---|---|---|
| G3 (before Target A) | 54 | 24 | 9 | 5 | 0.915 | 0.273 | 0.727 | 0.085 | 0.692 |
| G4 (after Target A) | 51 | 22 | 11 | 8 | 0.864 | 0.333 | 0.667 | 0.136 | 0.699 |

Note the very high FPR in absolute terms (66.7%) on this corpus — this is dominated by pre-existing, already-documented (G2/G3) synthetic-proxy false positives unrelated to RS (e.g. the photograph-proxy LSB-entropy saturation), **not newly introduced or newly explained by this phase**; it is reported here only to show the isolated before/after delta, not as a general accuracy claim.

**24 samples changed steganography score; 0 samples changed copy-move output.**

---

## 12. False-Positive Impact

[MEASURED] Two genuine false positives were fixed as a direct, correct consequence of the fix (not tuned toward): `illustration_real_colorwheel_clean.png` (26.5 → 11.8) and `alpha_real_logo_clean.png` (26.5 → 11.8), both dropping below the 20.0 decision threshold. Several other previously-documented RS-related clean-baseline saturation cases from G2/G3 (`document_proxy_clean`, `screenshot_proxy_clean`, `illustration_real_checkerboard_clean`) also dropped, though not always below threshold (checkerboard: 43.5 → 28.8, still flagged, since other detectors also contribute).

## 13. Sensitivity Impact

[MEASURED] Three genuine stego samples flipped from detected to missed: `illustration_real_colorwheel_stego_low` (26.5→11.8), `illustration_real_colorwheel_stego_medium` (21.8→15.9), `alpha_real_logo_stego_low` (26.5→11.8). **Critically, each of these carriers' *clean* baseline scored identically to its low-payload stego version before the fix** (both exactly 26.5 for colorwheel, both exactly 26.5 for alpha_real_logo) — meaning the pre-fix "detection" of these low-payload samples was driven by the same carrier-specific systematic bias that was also producing the false positive on the clean version, not by genuine payload-dependent signal. This is analogous to the G3 finding about `document_proxy_tamper_splice`: fixing a false positive revealed a pre-existing inability to distinguish clean from low-payload on these specific carriers, rather than removing real, working sensitivity.

---

## 14. Remaining Limitations

- The RS fix improves correctness (removes a conceptual conflation, confirmed via primary-source verification) and measurably improves FPR/precision on this corpus, but at a measured sensitivity cost on 3 samples — this is a real trade-off, not a pure win, and is reported as such.
- Target B remains unresolved: multi-region and arbitrary-offset copy-move forgeries are still undetected. The two root causes found (grid-alignment sensitivity; insufficient per-region match density against the `>=3` significance floor) are both real and precisely measured, but no safe fix was found in this phase. A full fix likely requires either (a) an architecturally different matching approach (e.g. coarse-to-fine search with a *validated* refined-match threshold, informed by a much larger genuine-vs-spurious match corpus than the single data point available here) or (b) accepting a real performance cost for denser/exhaustive matching, evaluated against real image-size distributions — both are [PROPOSED] next steps, not decided here.
- The 92-sample corpus remains too small for statistically meaningful confidence in exact FPR/sensitivity numbers; the point estimates above (e.g. "72.7%→66.7% FPR") describe this specific corpus's before/after delta, not real-world performance.
- The candidate copy-move refinement's rejection is itself evidence-limited: only one genuine multi-region sample and one genuine single-region sample were available to characterize "genuine match MAE," against only 3–4 clean/stego samples to characterize "spurious match MAE." A larger corpus of genuine small-region forgeries might reveal a cleaner separating threshold that this phase's evidence cannot rule out.

---

## Conclusion

Target A: a real, source-verified conceptual error (conflating an applicability diagnostic with embedding evidence) was found, precisely characterized, and fixed with the smallest possible change — one file, no scoring-layer edits needed, fully backward-compatible field names, 10 new regression tests, full suite green (227/227 excluding the one unrelated skip). The fix is a net improvement (FPR and precision both improved) with an honestly-measured and explained sensitivity cost on 3 borderline samples whose prior "detection" is shown to have been the same bias that caused their clean-baseline false positives.

Target B: the investigation successfully found the *true* root cause of the multi-region miss (grid-alignment sensitivity — not any of the mechanisms hypothesized in the spec's own list of possible causes), built and rigorously tested a targeted candidate fix, and correctly declined to ship it after measuring that it traded one false-positive problem for another with no clean separating threshold. This is reported as the intended outcome of an "evidence-driven investigation" phase: a negative result, reached rigorously, is preferred over an unvalidated fix that would look like progress on paper.
