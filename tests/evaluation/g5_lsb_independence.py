"""
Phase G5, Target B — LSB entropy vs visual-balance independence analysis.

Uses the EXISTING G4 re-scan results (tests/evaluation/g4_results/g4_after_results.json,
already computed over the existing, un-regenerated 92-sample corpus) -- no new
images are generated or scored; this is pure analysis of already-recorded data.
"""
import json
import os
import collections
import numpy as np
from scipy.stats import pearsonr, spearmanr


def _corr(xs, ys):
    xs = np.array(xs, dtype=np.float64)
    ys = np.array(ys, dtype=np.float64)
    if len(xs) < 3 or np.std(xs) == 0 or np.std(ys) == 0:
        return None, None, len(xs)
    pr, _ = pearsonr(xs, ys)
    sr, _ = spearmanr(xs, ys)
    return round(float(pr), 4), round(float(sr), 4), len(xs)


def run_lsb_independence_analysis(
    results_path='tests/evaluation/g4_results/g4_after_results.json',
    out_path='tests/evaluation/g5_results/g5_lsb_independence.json'
):
    with open(results_path) as f:
        recs = json.load(f)

    entropy = [r['lsb_entropy_max'] for r in recs]
    balance = [-r['visual_min_balance_delta'] for r in recs]
    overall_r, overall_s, n_overall = _corr(entropy, balance)

    by_class = collections.defaultdict(list)
    for r in recs:
        by_class[r['image_class']].append(r)
    class_corr = {}
    for cls, items in by_class.items():
        e = [r['lsb_entropy_max'] for r in items]
        b = [-r['visual_min_balance_delta'] for r in items]
        pr, sr, n = _corr(e, b)
        class_corr[cls] = {'pearson': pr, 'spearman': sr, 'n': n}

    clean = [r for r in recs if not r['gt_has_steganography']]
    stego = [r for r in recs if r['gt_has_steganography']]
    clean_r, clean_s, n_clean = _corr([r['lsb_entropy_max'] for r in clean], [-r['visual_min_balance_delta'] for r in clean])
    stego_r, stego_s, n_stego = _corr([r['lsb_entropy_max'] for r in stego], [-r['visual_min_balance_delta'] for r in stego])

    by_payload = collections.defaultdict(list)
    for r in stego:
        by_payload[r['gt_payload_level']].append(r)
    payload_corr = {}
    for lvl, items in by_payload.items():
        pr, sr, n = _corr([r['lsb_entropy_max'] for r in items], [-r['visual_min_balance_delta'] for r in items])
        payload_corr[lvl] = {'pearson': pr, 'spearman': sr, 'n': n}

    def classify(r):
        gt = r['gt_has_steganography']
        e_flag = bool(r.get('entropy_is_suspicious'))
        b_flag = bool(r.get('visual_is_suspicious'))
        return gt, e_flag, b_flag

    overlap = {
        'tp_both': 0, 'tp_entropy_only': 0, 'tp_balance_only': 0, 'tp_neither': 0,
        'fp_both': 0, 'fp_entropy_only': 0, 'fp_balance_only': 0, 'fp_neither': 0,
    }
    for r in recs:
        gt, e_flag, b_flag = classify(r)
        if gt:
            if e_flag and b_flag:
                overlap['tp_both'] += 1
            elif e_flag and not b_flag:
                overlap['tp_entropy_only'] += 1
            elif b_flag and not e_flag:
                overlap['tp_balance_only'] += 1
            else:
                overlap['tp_neither'] += 1
        else:
            if e_flag and b_flag:
                overlap['fp_both'] += 1
            elif e_flag and not b_flag:
                overlap['fp_entropy_only'] += 1
            elif b_flag and not e_flag:
                overlap['fp_balance_only'] += 1
            else:
                overlap['fp_neither'] += 1

    class_overlap = {}
    for cls, items in by_class.items():
        c = {'tp_both': 0, 'tp_entropy_only': 0, 'tp_balance_only': 0,
             'fp_both': 0, 'fp_entropy_only': 0, 'fp_balance_only': 0, 'n': len(items)}
        for r in items:
            gt, e_flag, b_flag = classify(r)
            if gt:
                if e_flag and b_flag:
                    c['tp_both'] += 1
                elif e_flag:
                    c['tp_entropy_only'] += 1
                elif b_flag:
                    c['tp_balance_only'] += 1
            else:
                if e_flag and b_flag:
                    c['fp_both'] += 1
                elif e_flag:
                    c['fp_entropy_only'] += 1
                elif b_flag:
                    c['fp_balance_only'] += 1
        class_overlap[cls] = c

    result = {
        'n_total_samples': len(recs),
        'overall_correlation': {'pearson': overall_r, 'spearman': overall_s, 'n': n_overall},
        'correlation_by_class': class_corr,
        'correlation_clean_only': {'pearson': clean_r, 'spearman': clean_s, 'n': n_clean},
        'correlation_stego_only': {'pearson': stego_r, 'spearman': stego_s, 'n': n_stego},
        'correlation_by_payload_level': payload_corr,
        'error_overlap_overall': overlap,
        'error_overlap_by_class': class_overlap,
        'note': (
            "visual balance delta is sign-inverted (negated) so that, like "
            "entropy, a higher value means more suspicious, for comparable "
            "correlation direction. 'flagged' uses each detector's own "
            "is_suspicious decision as computed by the unmodified production "
            "pipeline, independent of scoring.py's combined category logic."
        )
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)

    return result


if __name__ == '__main__':
    r = run_lsb_independence_analysis()
    print(f"Overall correlation: pearson={r['overall_correlation']['pearson']} (n={r['overall_correlation']['n']})")
    print(f"Error overlap: {r['error_overlap_overall']}")
