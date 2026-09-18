"""
Phase G6, Phase 6 — clustered aggregation experiment.

IMPORTANT SCOPE NOTE: the spec's 5-member cluster (Chi-Square, RS, SPA, LSB
entropy, visual-balance) spans TWO current scoring categories -- chi2/RS/SPA/
entropy live in "Statistical Steganalysis" (50 pts), visual-balance lives in
its own separate "Visual Steganalysis" (20 pts) category. Merging all 5 into
one aggregate would cross that category boundary, which is a broader
architectural change than "narrowly scoped" -- see G6 report Phase 6/13.

This script therefore runs the PRIMARY, in-bounds experiment on the 4
same-category detectors (chi2, RS, SPA, LSB entropy) using their existing
combined 50-point budget, and separately reports the full 5-detector merge
as an EXPLORATORY-ONLY calculation, clearly labeled, not proposed.

This is exploratory analysis only -- it does not modify scoring.py. Uses the
existing G6 dataset (itself derived from existing, un-regenerated corpus
data).
"""
import json
import os
import numpy as np


def _load(dataset_path='tests/evaluation/g6_results/g6_dataset.json'):
    with open(dataset_path) as f:
        return json.load(f)['samples']


def _confusion(scores, gts, threshold=20.0):
    tp = fp = tn = fn = 0
    for s, gt in zip(scores, gts):
        pred = s >= threshold
        if gt and pred:
            tp += 1
        elif gt and not pred:
            fn += 1
        elif not gt and pred:
            fp += 1
        else:
            tn += 1
    sens = tp / (tp + fn) if (tp + fn) else None
    spec = tn / (tn + fp) if (tn + fp) else None
    fpr = fp / (fp + tn) if (fp + tn) else None
    prec = tp / (tp + fp) if (tp + fp) else None
    return {'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
            'sensitivity': round(sens, 4) if sens is not None else None,
            'specificity': round(spec, 4) if spec is not None else None,
            'fpr': round(fpr, 4) if fpr is not None else None,
            'precision': round(prec, 4) if prec is not None else None}


def _agreement_weighted_mean(vals, threshold=0.30):
    vals = np.array(vals)
    agreement = np.mean(vals > threshold)
    return float(np.mean(vals) * agreement)


def run_aggregation_experiment(dataset_path='tests/evaluation/g6_results/g6_dataset.json',
                                out_path='tests/evaluation/g6_results/g6_aggregation_experiment.json'):
    recs = _load(dataset_path)
    gts = [r['gt_has_steganography'] for r in recs]

    chi2 = np.array([r['chi_square_max_indicator'] for r in recs])
    rs = np.array([r['rs_estimated_rate'] for r in recs])
    spa = np.array([r['spa_estimated_rate'] for r in recs])
    entropy = np.array([r['lsb_entropy_max'] for r in recs])
    stat4 = np.stack([chi2, rs, spa, entropy], axis=1)

    other_score = np.array([
        r['structural_score'] + r['metadata_score'] + r['visual_score']
        for r in recs
    ])

    methods = {}
    methods['A_arithmetic_mean'] = stat4.mean(axis=1) * 50.0
    methods['B_median'] = np.median(stat4, axis=1) * 50.0
    sorted_vals = np.sort(stat4, axis=1)
    methods['C_trimmed_mean'] = sorted_vals[:, 1:3].mean(axis=1) * 50.0
    methods['D_maximum'] = stat4.max(axis=1) * 50.0
    methods['E_agreement_weighted_mean'] = np.array([_agreement_weighted_mean(row) for row in stat4]) * 50.0

    current_stat = np.array([r['statistical_score'] for r in recs])

    results = {}
    current_total = current_stat + other_score
    results['CURRENT_production'] = {
        'formula': 'existing tiered thresholds, independently summed, capped at 50.0',
        'confusion': _confusion(current_total, gts),
    }

    formulas = {
        'A_arithmetic_mean': 'mean(chi2, rs, spa, entropy) * 50',
        'B_median': 'median(chi2, rs, spa, entropy) * 50',
        'C_trimmed_mean': 'mean(2 middle values of sorted [chi2, rs, spa, entropy]) * 50',
        'D_maximum': 'max(chi2, rs, spa, entropy) * 50',
        'E_agreement_weighted_mean': 'mean(vals) * fraction(vals > 0.30) * 50',
    }
    for name, agg in methods.items():
        total = agg + other_score
        results[name] = {
            'formula': formulas[name],
            'confusion': _confusion(total, gts),
        }

    current_pred = current_total >= 20.0
    for name, agg in methods.items():
        total = agg + other_score
        pred = total >= 20.0
        changed = int(np.sum(pred != current_pred))
        tps_lost = int(np.sum((np.array(gts)) & current_pred & (~pred)))
        fps_fixed = int(np.sum((~np.array(gts)) & current_pred & (~pred)))
        results[name]['classification_changes_vs_current'] = changed
        results[name]['unique_tps_lost_vs_current'] = tps_lost
        results[name]['fps_fixed_vs_current'] = fps_fixed

    balance_inv = np.array([1.0 - min(1.0, r['visual_min_balance_delta'] / 0.005) for r in recs])
    balance_inv = np.clip(balance_inv, 0.0, 1.0)
    stat5 = np.stack([chi2, rs, spa, entropy, balance_inv], axis=1)
    other_score_no_visual = np.array([r['structural_score'] + r['metadata_score'] for r in recs])
    combined_budget = 70.0

    exploratory = {}
    for label, fn in [
        ('mean', lambda a: a.mean(axis=1)),
        ('median', lambda a: np.median(a, axis=1)),
        ('max', lambda a: a.max(axis=1)),
    ]:
        agg = fn(stat5) * combined_budget
        total = agg + other_score_no_visual
        exploratory[label] = _confusion(total, gts)

    results['EXPLORATORY_ONLY_full_5_detector_merge'] = {
        'warning': (
            "NOT PROPOSED. This merges chi2/RS/SPA/entropy (Statistical, "
            "50 pts) with visual-balance (Visual, 20 pts) into one 70-point "
            "aggregate, crossing the existing category boundary -- a "
            "broader architectural change than this phase's 'narrowly "
            "scoped' mandate permits. Shown for completeness only, since "
            "the spec named visual-balance as a cluster member."
        ),
        'results': exploratory,
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)

    return results


if __name__ == '__main__':
    r = run_aggregation_experiment()
    for name, v in r.items():
        if name == 'EXPLORATORY_ONLY_full_5_detector_merge':
            continue
        print(name, v.get('confusion'), 'changes=', v.get('classification_changes_vs_current'),
              'tps_lost=', v.get('unique_tps_lost_vs_current'), 'fps_fixed=', v.get('fps_fixed_vs_current'))
