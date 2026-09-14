"""
Phase G2 — Detector correlation analysis.

Loads the baseline results produced by g2_baseline_runner.py and computes
Pearson and Spearman correlations between the core LSB-parity-cluster
detector indicators, using only NumPy/SciPy (no ML). This does not modify
any production scoring code -- it is read-only analysis of already-recorded
detector outputs.
"""
import os
import json
from typing import Dict, Any, List

import numpy as np
from scipy.stats import pearsonr, spearmanr

DETECTOR_FIELDS = {
    'chi_square': 'chi_square_max_indicator',
    'lsb_entropy': 'lsb_entropy_max',
    'rs_indicator': 'rs_suspicion_indicator',
    'spa_indicator': 'spa_suspicion_indicator',
    'visual_balance_delta_inv': 'visual_min_balance_delta',  # inverted below (smaller delta = more suspicious)
}


def _extract_matrix(records: List[Dict[str, Any]]):
    names = list(DETECTOR_FIELDS.keys())
    cols = {}
    for name, field in DETECTOR_FIELDS.items():
        vals = []
        for r in records:
            v = r.get(field)
            if v is None:
                vals.append(np.nan)
            else:
                vals.append(float(v))
        vals = np.array(vals, dtype=np.float64)
        if name == 'visual_balance_delta_inv':
            # invert so that higher = more suspicious, consistent with the others
            vals = -vals
        cols[name] = vals
    return names, cols


def run_correlation_analysis(results_json: str = 'tests/evaluation/g2_results/g2_baseline_results.json',
                              out_path: str = 'tests/evaluation/g2_results/g2_correlation_report.json') -> Dict[str, Any]:
    with open(results_json, 'r', encoding='utf-8') as f:
        records = json.load(f)

    names, cols = _extract_matrix(records)
    n = len(records)

    pearson_matrix = {}
    spearman_matrix = {}
    pairs_report = []

    for i, a in enumerate(names):
        pearson_matrix[a] = {}
        spearman_matrix[a] = {}
        for j, b in enumerate(names):
            va, vb = cols[a], cols[b]
            valid = ~(np.isnan(va) | np.isnan(vb))
            if valid.sum() < 3 or np.std(va[valid]) == 0 or np.std(vb[valid]) == 0:
                pr, pp = float('nan'), float('nan')
                sr, sp = float('nan'), float('nan')
            else:
                pr, pp = pearsonr(va[valid], vb[valid])
                sr, sp = spearmanr(va[valid], vb[valid])
            pearson_matrix[a][b] = round(float(pr), 4) if pr == pr else None
            spearman_matrix[a][b] = round(float(sr), 4) if sr == sr else None
            if i < j and pr == pr:
                pairs_report.append({
                    'pair': [a, b],
                    'pearson_r': round(float(pr), 4),
                    'pearson_p': round(float(pp), 6),
                    'spearman_r': round(float(sr), 4) if sr == sr else None,
                    'n': int(valid.sum())
                })

    # Simple clustering: group detectors whose pairwise |pearson_r| >= 0.7
    threshold = 0.7
    clusters = []
    assigned = set()
    for a in names:
        if a in assigned:
            continue
        cluster = {a}
        for b in names:
            if b == a:
                continue
            r = pearson_matrix[a].get(b)
            if r is not None and abs(r) >= threshold:
                cluster.add(b)
        if len(cluster) > 1:
            clusters.append(sorted(cluster))
            assigned.update(cluster)

    report = {
        'n_samples': n,
        'detectors_analyzed': names,
        'correlation_threshold_for_clustering': threshold,
        'pearson_matrix': pearson_matrix,
        'spearman_matrix': spearman_matrix,
        'pairwise': sorted(pairs_report, key=lambda p: -abs(p['pearson_r'])),
        'high_correlation_clusters': clusters,
        'note': (
            "visual_balance_delta_inv is the negated min_balance_delta (so that, "
            "like the other four fields, a HIGHER value means MORE suspicious), "
            "to make correlation direction directly comparable across detectors."
        )
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    return report


if __name__ == '__main__':
    report = run_correlation_analysis()
    print(json.dumps({k: v for k, v in report.items() if k != 'pearson_matrix' and k != 'spearman_matrix'}, indent=2))
