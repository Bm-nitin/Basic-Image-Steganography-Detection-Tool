"""
Phase G6, Phase 4 — correlation analysis (magnitude-level) and decision-level
redundancy analysis for the 5-detector LSB/parity evidence cluster:
Chi-Square, RS (embedding evidence), SPA, LSB entropy, visual-balance.

Uses the G6 dataset built by g6_dataset_builder.py (itself derived from the
existing, un-regenerated 92-sample corpus and verified-current G4 results).
No production code is touched here; this is read-only analysis.
"""
import json
import os
import collections
import numpy as np
from scipy.stats import pearsonr, spearmanr


SIGNALS = {
    'chi_square': 'chi_square_max_indicator',
    'rs': 'rs_estimated_rate',
    'spa': 'spa_estimated_rate',
    'lsb_entropy': 'lsb_entropy_max',
    'visual_balance': 'visual_min_balance_delta',
}

FLAG_FIELDS = {
    'chi_square': 'chi_square_is_suspicious',
    'rs': 'rs_is_suspicious',
    'spa': 'spa_is_suspicious',
    'lsb_entropy': 'entropy_is_suspicious',
    'visual_balance': 'visual_is_suspicious',
}


def _extract(recs):
    cols = {}
    for name, field in SIGNALS.items():
        vals = np.array([r[field] for r in recs], dtype=np.float64)
        if name == 'visual_balance':
            vals = -vals
        cols[name] = vals
    return cols


def _corr_matrix(cols, n):
    names = list(cols.keys())
    pearson = {a: {} for a in names}
    spearman = {a: {} for a in names}
    pairs = []
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            va, vb = cols[a], cols[b]
            if np.std(va) == 0 or np.std(vb) == 0 or n < 3:
                pr, sr = None, None
            else:
                pr = round(float(pearsonr(va, vb)[0]), 4)
                sr = round(float(spearmanr(va, vb)[0]), 4)
            pearson[a][b] = pr
            spearman[a][b] = sr
            if i < j:
                pairs.append({'pair': [a, b], 'pearson': pr, 'spearman': sr, 'n': n})
    return pearson, spearman, sorted(pairs, key=lambda p: -(abs(p['pearson']) if p['pearson'] is not None else -1))


def run_correlation_and_overlap(dataset_path='tests/evaluation/g6_results/g6_dataset.json',
                                 out_path='tests/evaluation/g6_results/g6_correlation.json'):
    with open(dataset_path) as f:
        recs = json.load(f)['samples']

    cols = _extract(recs)
    pearson, spearman, pairs = _corr_matrix(cols, len(recs))

    decision = {}
    flags_by_sample = collections.defaultdict(dict)
    for name, field in FLAG_FIELDS.items():
        tp = fp = tn = fn = 0
        for r in recs:
            gt = r['gt_has_steganography']
            flagged = bool(r[field])
            flags_by_sample[r['filename']][name] = flagged
            if gt and flagged:
                tp += 1
            elif gt and not flagged:
                fn += 1
            elif not gt and flagged:
                fp += 1
            else:
                tn += 1
        sens = tp / (tp + fn) if (tp + fn) else None
        spec = tn / (tn + fp) if (tn + fp) else None
        fpr = fp / (fp + tn) if (fp + tn) else None
        prec = tp / (tp + fp) if (tp + fp) else None
        decision[name] = {'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
                           'sensitivity': round(sens, 4) if sens is not None else None,
                           'specificity': round(spec, 4) if spec is not None else None,
                           'fpr': round(fpr, 4) if fpr is not None else None,
                           'precision': round(prec, 4) if prec is not None else None}

    names = list(SIGNALS.keys())
    unique_contrib = {name: {'unique_tp': 0, 'unique_fp': 0, 'tp_also_flagged_by': collections.Counter(),
                              'fp_also_flagged_by': collections.Counter()} for name in names}
    for r in recs:
        gt = r['gt_has_steganography']
        fn_ = r['filename']
        flagged_by = [n for n in names if flags_by_sample[fn_][n]]
        for name in flagged_by:
            others_flagging = [o for o in flagged_by if o != name]
            if gt:
                if not others_flagging:
                    unique_contrib[name]['unique_tp'] += 1
                for o in others_flagging:
                    unique_contrib[name]['tp_also_flagged_by'][o] += 1
            else:
                if not others_flagging:
                    unique_contrib[name]['unique_fp'] += 1
                for o in others_flagging:
                    unique_contrib[name]['fp_also_flagged_by'][o] += 1

    for name in names:
        unique_contrib[name]['tp_also_flagged_by'] = dict(unique_contrib[name]['tp_also_flagged_by'])
        unique_contrib[name]['fp_also_flagged_by'] = dict(unique_contrib[name]['fp_also_flagged_by'])

    result = {
        'n_samples': len(recs),
        'pearson_matrix': pearson,
        'spearman_matrix': spearman,
        'pairwise_sorted_by_abs_pearson': pairs,
        'decision_level_per_detector': decision,
        'unique_contribution': unique_contrib,
        'note': (
            "visual_balance uses -min_balance_delta (sign-inverted) so higher "
            "= more suspicious, matching the other four signals' direction. "
            "'rs' uses rs_estimated_rate (embedding evidence only, per the "
            "G4 applicability/evidence separation) -- rs_applicability_diagnostic "
            "is intentionally excluded from this cluster, since G4 established "
            "it is not embedding evidence."
        )
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)

    return result


if __name__ == '__main__':
    r = run_correlation_and_overlap()
    print(f"n={r['n_samples']}")
    for p in r['pairwise_sorted_by_abs_pearson']:
        print(p)
    print()
    for name, d in r['decision_level_per_detector'].items():
        print(name, d)
