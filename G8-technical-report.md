# G8 Natural-Photograph False-Positive Investigation

**Evidence labels used throughout:** [MEASURED], [SOURCE-VERIFIED], [INFERRED], [PROPOSED].

## 1. Objective

Investigate, and only if justified, correct the natural-photograph false-positive behavior G7 found in three real natural-texture photographs (brick, grass, gravel). This is explicitly not permission to redesign scoring.

## 2. Baseline

**Repository/git note:** this working directory has no `.git` (extracted from an archive, not cloned) -- `git status`/`git log --oneline -10`/`git diff --stat` could not be run as literal commands, identical to what was reported in G4-G7. The established equivalent (diffing against the preserved pristine archive) was used instead.

[MEASURED]
```
passed: 227
skipped: 1
failed: 0
warnings: 1 (DecompressionBombWarning -- pre-existing, expected per G1-G7)
```
Matches the expected baseline exactly. [MEASURED] Diffing against the pristine archive shows exactly the same 5 files differing as after G7 -- no unrelated modifications found before this phase began.

## 3. G7 False-Positive Reproduction

[MEASURED] Class labels and ground truth for the three target files were verified against `tests/evaluation/g7_results/g7_corpus_inventory.json` (not inferred from filenames -- all three carry `image_class: repeated_texture_real`, `has_steganography: False`, `has_tampering: False`, and are genuinely single-channel (`actual_color_mode: L`) source images, not RGB photos with a derived grayscale channel). Re-running the current, unmodified pipeline reproduced the G7 scores exactly:

| File | Score | Risk | Structural | Metadata | Statistical | Visual | Tampering |
|---|---|---|---|---|---|---|---|
| brick | 40.6 | Medium | 0.0 | 0.0 | 20.6 | 20.0 | 0.4 |
| grass | 55.3 | Medium | 0.0 | 0.0 | 35.3 | 20.0 | 0.1 |
| gravel | 43.5 | Medium | 0.0 | 0.0 | 23.5 | 20.0 | 0.7 |

Detector-level detail (points actually awarded, `detector_breakdown`):

| File | Chi-Square | RS embedding | RS applicability | SPA | LSB Entropy | Visual-balance |
|---|---|---|---|---|---|---|
| brick | 0.0 pts (ind=0.0) | 0.0 pts (rate=0.0) | 0.0 diagnostic | **11.8 pts** (rate=0.63) | **8.8 pts** (max=1.0000) | **20.0 pts** (flagged) |
| grass | **14.7 pts** (ind=0.85) | 0.0 pts (rate=0.17) | ~0.02 diagnostic | **11.8 pts** (rate=0.98) | **8.8 pts** (max=1.0000) | **20.0 pts** (flagged) |
| gravel | **14.7 pts** (ind=0.85) | 0.0 pts (rate=0.0) | ~0.06 diagnostic | 0.0 pts (rate=0.24) | **8.8 pts** (max=1.0000) | **20.0 pts** (flagged) |

**RS never contributes to any of the three** (its embedding-rate estimate stays low, 0.0-0.17, well under its own 0.25 threshold) -- confirmed, source-verified separation between RS's embedding evidence and applicability diagnostic (G4) still holds correctly here. LSB Entropy and Visual-balance are the only two contributors present on **all three** samples; Chi-Square and SPA each fire on 2 of 3, but not the same two.

## 4. Detector Contribution Analysis

See the table in Section 3 for the exact per-detector contribution trace requested. Comparison against representative clean natural photographs that are **not** flagged was attempted, but Section 5 below establishes that **no such comparison sample exists in this corpus** -- every clean natural photograph, real or synthetic, is flagged or entropy-saturated in the same way.

## 5. Natural-Texture Control Group

[MEASURED] All available clean, non-tampered natural-photograph-class samples in the corpus (the 3 G7 targets plus `photograph_real_coffee`, `photograph_real_chelsea`, `photograph_real_rocket`, `photograph_proxy`) -- 7 samples total:

| Sample | LSB entropy max | Edge density | Local-variance flagged? |
|---|---|---|---|
| brick | 1.0000 | 0.404 | No |
| grass | 1.0000 | 0.960 | No |
| gravel | 1.0000 | 0.945 | No |
| coffee | 1.0000 | 0.427 | No |
| chelsea | 1.0000 | 0.685 | No |
| rocket | 1.0000 | 0.158 | No |
| photograph_proxy | 1.0000 | 0.012 | No |

**Central finding [MEASURED]: every single clean natural-photograph sample in this corpus -- without exception, real or synthetic, high-edge-density or nearly flat (edge density ranges from 0.012 to 0.960 with no visible relationship to the outcome) -- saturates LSB entropy at 1.0000.** There is no clean natural-photograph control sample in this corpus that does *not* max out this signal. **The three G7 false positives are therefore not anomalous within the natural-photograph class -- they are representative of it.** This refines G7's own framing: the phenomenon is not specifically about "high local texture" (edge density does not track the outcome at all), it is a broader property shared by every natural-photograph-style sample in this corpus, textured or smooth alike.

For comparison, non-photograph clean samples showed a genuinely different, more varied pattern: `document_real_page` also saturates (1.0000 -- a real scanned document, not a photograph), while `document_proxy` (0.766), `screenshot_proxy` (0.844), and `illustration_real_colorwheel` (0.920) do not. [INFERRED] The distinguishing factor appears closer to "continuous-tone, naturally-varying pixel content" (photographs and a real scan) versus "flat-color/synthetic-geometric content" (illustration, UI, synthetic document) than to "photograph vs. non-photograph" specifically -- this is inferred from the pattern observed, not independently proven by a dedicated mechanism study in this phase.

## 6. Local Texture Analysis

[MEASURED] Block-wise (32x32) LSB density, comparing global vs. local statistics:

| Sample | Global density | Block mean | Block stdev | Block min-max | Fraction of blocks near 0.5 |
|---|---|---|---|---|---|
| brick | 0.4996 | 0.4996 | 0.019 | 0.459-0.537 | 1.00 |
| grass | 0.4976 | 0.4976 | 0.018 | 0.448-0.546 | 0.98 |
| gravel | 0.4973 | 0.4973 | 0.015 | 0.458-0.530 | 1.00 |
| coffee | 0.4998 | 0.4998 | 0.018 | 0.456-0.541 | 1.00 |
| chelsea | 0.5009 | 0.5009 | 0.015 | 0.456-0.528 | 1.00 |
| rocket | 0.5031 | 0.5031 | 0.018 | 0.461-0.537 | 1.00 |
| document_real_page | 0.5036 | 0.5036 | 0.026 | 0.430-0.598 | 0.95 |
| document_proxy | 0.7929 | 0.7929 | 0.159 | 0.545-1.000 | 0.05 |
| screenshot_proxy | 0.3392 | 0.3392 | 0.369 | 0.000-1.000 | 0.03 |
| illustration_real_colorwheel | 0.3988 | 0.3988 | 0.169 | 0.000-0.521 | 0.69 |

**Finding [MEASURED], and it refutes the Phase 5 hypothesis as originally framed:** the near-0.5 LSB density in natural photographs is **not** an artifact of a few extreme local regions averaging out to 0.5 globally -- it is **uniformly near 0.5 at every local block, everywhere in the image** (stdev 0.015-0.026, nearly all blocks within the 0.05 band). This is genuinely different from the synthetic flat-graphic/UI classes, which show large local heterogeneity (stdev 0.16-0.37, many blocks far from 0.5) reflecting their mix of flat solid-color regions and sharp edges. [INFERRED] This is consistent with real photographic sensor/analog noise being spatially pervasive and close to uniformly distributed across an image, rather than concentrated in a few "hot" regions -- a plausible mechanism, not independently proven here via a dedicated noise-model study.

## 7. Channel Analysis

[MEASURED] The three G7 targets are genuinely single-channel source images (`actual_color_mode: L`), confirmed directly (R, G, B channels identical after RGB conversion) -- so there is no "derived-grayscale-from-independently-perturbed-RGB" artifact at play here (the mechanism identified for real photographs in G5's chi-square investigation does not apply to these three specific samples, since they have no true RGB channels to begin with). The false-positive behavior is present in the single available channel, not "concentrated" in one of several -- there is only one. For genuine RGB photographs (coffee/chelsea/rocket), the same LSB-entropy saturation is present in the derived gray channel *and* in R, G, and B individually (confirmed in G5), so it is not concentrated in any one channel there either -- it is pervasive across all channels tested.

## 8. Photograph vs Stego Discrimination

[MEASURED, the most actionable finding of this phase] Using the existing clean/stego pairs for the three real photographs (coffee, chelsea, rocket) at low/medium/high payload:

| Photo | Signal | Clean | Low | Medium | High |
|---|---|---|---|---|---|
| coffee | LSB entropy | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| coffee | Visual-balance flagged | True | True | True | True |
| coffee | **RS embedding rate** | **0.021** | **0.167** | **0.535** | **1.000** |
| chelsea | LSB entropy | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| chelsea | Visual-balance flagged | True | True | True | True |
| chelsea | **RS embedding rate** | **0.075** | **0.265** | **0.495** | **0.894** |
| rocket | LSB entropy | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| rocket | Visual-balance flagged | True | True | True | True |
| rocket | **RS embedding rate** | **0.000** | **0.161** | **0.517** | **0.936** |

**LSB entropy and visual-balance are completely uninformative for this discrimination task on real photographs** -- both are saturated at the clean baseline and stay saturated at every payload level, providing zero separating signal between "natural photographic noise" and "genuine embedding" on this carrier type. **RS's embedding-rate estimate, by contrast, shows a clean, monotonic, well-separated response in all three independently-sourced photographs**, with low clean-baseline values (0.0-0.075) rising smoothly with payload. Chi-square shows a similar but less clean monotonic tendency; SPA does not (it is noisy and in one case -- rocket -- moves in the wrong direction at low payload before recovering).

**Answering Phase 7's key question directly:** [MEASURED] yes, a currently-available signal (RS) can distinguish natural photographic noise from genuine embedding on real photographs, without modifying any detector mathematics. Entropy and visual-balance cannot, on this carrier type, at either extreme of embedding.

## 9. Controlled Paired Experiment

Covered directly above (Section 8) -- the existing corpus already contains the required clean/stego pairs at documented payload levels (15%/50%/100%, from the original G2 generator); no new payload was generated for this phase.

## 10. Candidate Corrections

Per Section 8's finding, two narrowly-scoped candidates were simulated (via the real, unmodified `SuspicionScoringEngine.evaluate()` fed modified inputs, mirroring the G6 ablation discipline -- no production file touched):

- **Candidate D:** visual-balance's 20 points are only awarded if RS's embedding-rate estimate also exceeds 0.25 (the *existing* production RS partial-evidence threshold, not a new invented value) -- i.e., require corroboration from the one detector shown in Section 8 to reliably separate natural noise from genuine embedding on photographs.
- **Candidate E:** replace summing LSB-entropy's category points and visual-balance's separate 20-point category with `max()` of the two, addressing the redundancy established in G5/G6 directly.

An initial version of Candidate D used chi-square and SPA as additional corroboration signals; this was revised after Section 3's reproduction data showed chi-square and SPA are *themselves* already elevated on 2 of the 3 clean target samples (chi2=0.85 on grass/gravel; SPA=0.63-0.98 on brick/grass) -- using them as "corroboration" would be circular, since they are part of the same phenomenon under investigation, not independent of it. This revision is disclosed here explicitly as part of the investigation record, not presented as the first and only attempt.

[MEASURED] Full-corpus simulation results (threshold 20.0):

| Candidate | Overall sensitivity | Overall FPR | Natural-photo FPR (n=17) | Low-payload detection | Original 3 targets fixed |
|---|---|---|---|---|---|
| A (no correction) | 0.864 | 0.667 | 0.941 | 0.632 | -- |
| D (RS corroboration) | 0.797 | 0.455 | 0.706 | 0.421 | **0 of 3** |
| E (max not sum) | 0.864 | 0.667 | 0.941 | 0.632 | **0 of 3** |

**Candidate E has zero effect anywhere in the corpus** -- because in every sample checked, one of {entropy points, visual points} already dominates the other by enough that `max()` and the current sum-then-cap arithmetic happen to agree at the final score level in this corpus (the redundancy is real per G5/G6's decision-level analysis, but replacing sum-with-max does not change any final classification here).

**Candidate D produces a real, broad effect elsewhere in the corpus (7 false positives fixed, FPR 0.667->0.455) but fixes none of the three original motivating samples, and costs real sensitivity (4 true positives lost, low-payload detection dropping from 0.632 to 0.421).**

**Root cause of why no visual-balance-only fix can work, established directly [MEASURED]:** even fully zeroing visual-balance's entire 20-point contribution is arithmetically insufficient to drop any of the three targets below the 20.0 threshold -- the remaining detectors already sum past it:

| Sample | Total | Without visual (-20) | Without visual + entropy (-28.8) |
|---|---|---|---|
| brick | 40.6 | 20.6 (still flagged) | 11.8 (would clear) |
| grass | 55.3 | 35.3 (still flagged) | **26.5 (still flagged)** |
| gravel | 43.5 | 23.5 (still flagged) | 14.7 (would clear) |

**`grass` remains flagged (26.5) even if both entropy and visual-balance are entirely removed** -- its false-positive status is driven independently by Chi-Square (14.7) and SPA (11.8) acting together, a mechanism entirely separate from the entropy/visual-balance redundancy that G5/G6 identified and that Candidates D/E both target. There is no single-mechanism, non-mathematical correction available that addresses this.

## 11. Generalization Analysis

Per the explicit instruction to reject any candidate that only fixes the three original samples: **both candidates fail this test in the opposite direction -- neither fixes even the three original samples**, while Candidate D does generalize (in the sense of having a broad, measurable, non-overfit effect across the corpus) but at a real, non-trivial sensitivity cost and without solving the motivating problem. This is a clean, unambiguous basis for the production decision below -- not a borderline call.

## 12. Production Change Decision

**OPTION A: NO PRODUCTION CHANGE JUSTIFIED.**

Directly from the measured evidence:
1. The two candidates most directly supported by G5/G6's prior findings (entropy/visual-balance redundancy) either have no effect (E) or have a real effect elsewhere but do not fix the problem they were designed for and cost real sensitivity (D).
2. The arithmetic in Section 10 proves no correction touching only the entropy/visual-balance pair -- the only pair with an established, non-mathematical, evidence-backed defect -- can possibly fix all three original samples, since `grass` is independently sustained by Chi-Square and SPA.
3. Correcting Chi-Square's or SPA's behavior on this content would require altering how those detectors interpret their own mathematics on natural-texture input, which is explicitly out of scope ("do not change detector mathematics unless the defect is proven to be mathematical") and no such proof was established or attempted here -- Chi-Square and SPA are behaving exactly as designed; they are also, like entropy, measuring a real property of this content that happens to statistically resemble embedding evidence.
4. Candidate D's real, broad sensitivity cost (4 TPs lost, low-payload detection dropping nearly a third) is not an acceptable trade for zero improvement on the motivating problem, and would itself require touching cross-category detector interactions in `scoring.py` -- a change larger and riskier than "narrowly scoped" permits given it doesn't solve the stated problem.

**No production file is modified. `app/core/scoring.py` and all detector files remain byte-for-byte identical to the G7 state.**

## 13. Regression Testing

No production code was changed, so no regression tests were added -- consistent with the G5/G6/G7 precedent for investigation phases that conclude with Option A. [MEASURED] Full suite re-run after all investigation work: `227 passed, 0 failed, 1 skipped` -- unchanged from the recorded G8 baseline.

## 14. Limitations

- This finding is now confirmed on 3 real natural textures plus 3 real natural photographs (6 genuine real-world samples total) plus 1 synthetic proxy -- still a small sample; the "every natural photograph saturates" finding (Section 5) is striking and consistent but should not be read as a law that holds for all possible photographs, only as accurately describing every sample currently in this corpus.
- The mechanistic explanation in Section 5 ("continuous-tone vs. flat-color content" being the true dividing line, not texture level specifically) is [INFERRED] from the observed pattern, not established via a dedicated sensor-noise or image-statistics study -- flagged as an open question for a future phase, consistent with the discipline used for the RS `sym_diff` and Chi-Square coverage-dilution investigations in G3-G5.
- Only two candidate corrections were simulated in depth (D and E); Candidates B (carrier-type-aware interpretation) and C (local-vs-global consistency) from the spec's suggested list were examined implicitly -- Section 6's local-texture finding (near-uniform local density, not heterogeneous) directly argues against Candidate C being viable, since it shows no local/global inconsistency to exploit -- but neither was separately simulated end-to-end, since the arithmetic argument in Section 10 already rules out any single-detector-family fix regardless.
- The RS-based discrimination signal (Section 8) was demonstrated only on real photographs with existing clean/stego pairs (3 samples); it was not similarly re-verified on the brick/grass/gravel textures with controlled embedding, since no stego version of those specific three images exists in the corpus and creating one was not required to reach the Section 12 decision.

## 15. Conclusion

This investigation reproduced G7's finding precisely, traced it to exact per-detector contributions, and discovered that it is not a texture-specific anomaly but a corpus-wide property of every natural photograph -- real or synthetic -- in this corpus. It also found a genuinely useful discriminating signal (RS) that G5/G6 had not highlighted for this specific purpose, and used it to construct the most evidence-backed narrow correction candidate available. That candidate was tested rigorously, found not to solve the original problem, and was not implemented. **This is reported as the correct outcome of this phase: a real defect exists in the sense that natural photographs are frequently misclassified, but no narrowly-scoped, mathematically-conservative correction currently available fixes it without unacceptable cost -- and forcing one through would have violated this phase's own explicit rules.**

**NO PRODUCTION CHANGE JUSTIFIED.**

---

## Final Output Summary

1. **Baseline:** 227 passed, 0 failed, 1 skipped, 1 expected warning (matches G7 exactly).
2. **Reproduced G7 false positives:** brick 40.6, grass 55.3, gravel 43.5 -- exact match to G7's recorded values.
3. **Detector contributions:** LSB entropy (8.8 pts) and visual-balance (20.0 pts) fire on all 3; Chi-Square and SPA fire on 2 of 3 each (different pairs); RS never fires.
4. **Natural-photo control results:** every clean natural photograph in the corpus (7 of 7) saturates LSB entropy at 1.0000, regardless of measured edge density (0.012-0.960) -- the 3 targets are representative, not anomalous.
5. **Local texture findings:** near-0.5 LSB density is uniform at every local block in natural photographs (stdev 0.015-0.026), not an artifact of heterogeneous regions averaging out.
6. **Channel findings:** the 3 targets are genuinely single-channel source images; the effect is present in the one channel that exists, not concentrated by channel.
7. **Clean/stego paired findings:** RS's embedding-rate estimate cleanly and monotonically separates clean from increasingly-embedded content on real photographs; LSB entropy and visual-balance do not.
8. **Candidate correction comparison:** Candidate E (max not sum) has zero effect; Candidate D (RS corroboration) fixes 7 unrelated false positives but none of the original 3, at a cost of 4 true positives and a third of low-payload sensitivity.
9. **Generalization results:** neither candidate is viable -- see Section 11.
10. **Production decision: NO PRODUCTION CHANGE JUSTIFIED.**
11. **Files changed:** none under `app/`.
12. **Full test result:** 227 passed, 0 failed, 1 skipped (unchanged).
13. **git status:** no `.git` in this environment; pristine-diff equivalent confirms no new production changes.
14. **Confirmation:** no commit or push was performed.
