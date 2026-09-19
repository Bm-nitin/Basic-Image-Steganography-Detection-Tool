"""
Phase G7, Phases 4-9 — clean-carrier evaluation, stego evaluation, payload
analysis, clean/stego pair analysis, false-positive and false-negative
forensics.

Uses tests/evaluation/g4_results/g4_after_results.json -- the existing
evaluation of the existing, un-regenerated 92-sample corpus by the current,
unmodified pipeline (freshness re-verified below by spot-checking 3 random
samples against a live re-run, mirroring the discipline used in G6).

No production code is touched. No new image analysis is performed beyond
the freshness spot-check.
"""
import json
import os
import random
import statistics
import collections
from PIL import Image

from app.core import (
    MetadataAnalyzer, FileForensicsAnalyzer, VisualExtractor,
    StatisticalAnalyzer, TamperingAnalyzer, SuspicionScoringEngine,
)

SOURCE = 'tests/evaluation/g4_results/g4_after_results.json'
INVENTORY = 'tests/evaluation/g7_results/g7_corpus_inventory.json'
OUT_DIR = 'tests/evaluation/g7_results'

TAXONOMY_MAP = {
    'photograph_real': 'Natural photograph',
    'photograph_proxy': 'Natural photograph (synthetic proxy)',
    'screenshot_proxy': 'Screenshot / UI',
    'document_real': 'Scanned document',
    'document_proxy': 'Marksheet/document-like (synthetic)',
    'illustration_real': 'Synthetic illustration / flat graphic',
    'illustration_proxy': 'Synthetic illustration / flat graphic (synthetic proxy)',
    'low_color_proxy': 'Low-color PNG',
    'grayscale_real': 'Grayscale',
    'grayscale_proxy': 'Grayscale (synthetic proxy)',
    'alpha_real': 'Alpha-channel PNG',
    'alpha_proxy': 'Alpha-channel PNG (synthetic proxy)',
    'repeated_texture_real': 'Other (repeated/self-similar natural texture)',
    'repeated_structure_proxy': 'Other (repeated/self-similar synthetic structure)',
}


def _freshness_check(n=3, seed=7):
    with open(SOURCE) as f:
        recs = {r['filename']: r for r in json.load(f)}
    random.seed(seed)
    sample_fns = random.sample(list(recs.keys()), n)
    results = []
    for fn in sample_fns:
        import glob
        paths = glob.glob(f'tests/evaluation/g3_samples/{fn}') + glob.glob(f'tests/evaluation/g2_samples/{fn}')
        path = paths[0]
        with open(path, 'rb') as f:
            b = f.read()
        img = Image.open(path)
        meta = MetadataAnalyzer.analyze(b, fn)
        forensics = FileForensicsAnalyzer.analyze(b, meta)
        visual = VisualExtractor.extract_bit_planes(img)
        stat = StatisticalAnalyzer.analyze(img, file_bytes=b, image_format=meta.get('detected_format'))
        tamp = TamperingAnalyzer.analyze(img, file_bytes=b, image_format=meta.get('detected_format'))
        score = SuspicionScoringEngine.evaluate(meta, visual, stat, forensics_res=forensics, tampering_res=tamp)
        match = (score['suspicion_score'] == recs[fn]['suspicion_score'])
        results.append({'filename': fn, 'stored': recs[fn]['suspicion_score'], 'fresh': score['suspicion_score'], 'match': match})
    return results


def _stats(values):
    if not values:
        return None
    return {
        'n': len(values),
        'mean': round(statistics.mean(values), 3),
        'median': round(statistics.median(values), 3),
        'stdev': round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
        'min': round(min(values), 3),
        'max': round(max(values), 3),
    }


def run_all():
    with open(SOURCE) as f:
        recs = json.load(f)

    fresh_check = _freshness_check()
    if not all(r['match'] for r in fresh_check):
        raise RuntimeError(f"FRESHNESS CHECK FAILED: {fresh_check}")

    for r in recs:
        r['taxonomy_class'] = TAXONOMY_MAP.get(r['image_class'], r['image_class'])

    clean = [r for r in recs if not r['gt_has_steganography'] and not r['gt_has_tampering']]
    by_class_clean = collections.defaultdict(list)
    for r in clean:
        by_class_clean[r['image_class']].append(r)

    clean_results = {}
    for cls, items in sorted(by_class_clean.items()):
        scores = [r['suspicion_score'] for r in items]
        fpr = sum(1 for s in scores if s >= 20.0) / len(scores)
        clean_results[cls] = {
            'taxonomy_class': TAXONOMY_MAP.get(cls, cls),
            'n': len(items),
            'suspicion_score_stats': _stats(scores),
            'structural_score_stats': _stats([r['structural_score'] for r in items]),
            'metadata_score_stats': _stats([r['metadata_score'] for r in items]),
            'statistical_score_stats': _stats([r['statistical_score'] for r in items]),
            'visual_score_stats': _stats([r['visual_score'] for r in items]),
            'tampering_score_stats': _stats([r['tampering_score'] for r in items]),
            'false_positive_rate_at_20': round(fpr, 4),
            'risk_level_distribution': dict(collections.Counter(r['risk_level'] for r in items)),
            'samples': [r['filename'] for r in items],
        }

    with open(os.path.join(OUT_DIR, 'g7_clean_results.json'), 'w') as f:
        json.dump({'note': 'Clean (non-stego, non-tampered) samples only, grouped by actual corpus image_class.',
                    'per_class': clean_results}, f, indent=2, default=str)

    stego = [r for r in recs if r['gt_has_steganography']]
    by_class_stego = collections.defaultdict(list)
    for r in stego:
        by_class_stego[r['image_class']].append(r)

    stego_results = {}
    for cls, items in sorted(by_class_stego.items()):
        by_payload = collections.defaultdict(list)
        for r in items:
            by_payload[r['gt_payload_level']].append(r)
        payload_breakdown = {}
        for lvl, sub in sorted(by_payload.items()):
            scores = [r['suspicion_score'] for r in sub]
            det_rate = sum(1 for s in scores if s >= 20.0) / len(scores)
            payload_breakdown[lvl] = {
                'n': len(sub),
                'score_stats': _stats(scores),
                'detection_rate_at_20': round(det_rate, 4),
            }
        all_scores = [r['suspicion_score'] for r in items]
        overall_det = sum(1 for s in all_scores if s >= 20.0) / len(all_scores)
        stego_results[cls] = {
            'taxonomy_class': TAXONOMY_MAP.get(cls, cls),
            'n': len(items),
            'embedding_methods': dict(collections.Counter(r['gt_stego_type'] for r in items)),
            'overall_detection_rate_at_20': round(overall_det, 4),
            'overall_false_negative_rate_at_20': round(1 - overall_det, 4),
            'by_payload_level': payload_breakdown,
        }

    with open(os.path.join(OUT_DIR, 'g7_stego_results.json'), 'w') as f:
        json.dump({'note': 'Stego samples only, grouped by actual corpus image_class and payload level.',
                    'per_class': stego_results}, f, indent=2, default=str)

    global_by_payload = collections.defaultdict(list)
    for r in stego:
        global_by_payload[r['gt_payload_level']].append(r['suspicion_score'])
    payload_order = ['low', 'medium', 'high']
    global_payload_curve = {
        lvl: _stats(global_by_payload[lvl]) for lvl in payload_order if lvl in global_by_payload
    }
    means = [global_payload_curve[lvl]['mean'] for lvl in payload_order if lvl in global_payload_curve]
    is_monotonic = all(means[i] <= means[i + 1] for i in range(len(means) - 1))

    def source_key(fn):
        import re
        return re.sub(r'_(clean|stego_low|stego_medium|stego_high)(\.\w+)?$', '', fn)

    by_source = collections.defaultdict(dict)
    for r in recs:
        if r['gt_stego_type'] not in ('spatial_lsb', 'none'):
            continue
        key = source_key(r['filename'])
        level = r['gt_payload_level'] if r['gt_has_steganography'] else 'clean'
        by_source[key][level] = r

    pair_analysis = []
    for src, levels in sorted(by_source.items()):
        if 'clean' not in levels:
            continue
        clean_r = levels['clean']
        entry = {'source': src, 'image_class': clean_r['image_class'],
                 'clean_score': clean_r['suspicion_score']}
        for lvl in ['low', 'medium', 'high']:
            if lvl in levels:
                r = levels[lvl]
                entry[f'{lvl}_score'] = r['suspicion_score']
                entry[f'{lvl}_delta'] = round(r['suspicion_score'] - clean_r['suspicion_score'], 3)
        pair_analysis.append(entry)

    with open(os.path.join(OUT_DIR, 'g7_pair_analysis.json'), 'w') as f:
        json.dump({'note': 'Per-source clean-vs-stego score deltas across payload levels.',
                    'global_payload_curve': global_payload_curve,
                    'payload_curve_monotonic_increasing': is_monotonic,
                    'pairs': pair_analysis}, f, indent=2, default=str)

    fp_samples = [r for r in clean if r['risk_level'] in ('Medium', 'High')]
    fp_details = []
    for r in fp_samples:
        associated = []
        if r['statistical_score'] > 0:
            associated.append('statistical_detector_interaction')
            if r.get('lsb_entropy_max', 0) and r['lsb_entropy_max'] >= 0.99:
                associated.append('high_LSB_entropy')
            if r.get('rs_estimated_rate', 0) and r['rs_estimated_rate'] > 0.25:
                associated.append('RS_signal')
            if r.get('spa_estimated_rate', 0) and r['spa_estimated_rate'] > 0.30:
                associated.append('SPA_signal')
            if r.get('chi_square_max_indicator', 0) and r['chi_square_max_indicator'] > 0.60:
                associated.append('chi_square_signal')
        if r['visual_score'] > 0:
            associated.append('high_LSB_balance_anomaly')
        if r['metadata_score'] > 0:
            associated.append('metadata_or_trailing_bytes')
        if r['structural_score'] > 0:
            associated.append('structural_detector_interaction')
        if r['image_class'] in ('document_proxy', 'document_real'):
            associated.append('document_structure')
        if r['image_class'] in ('low_color_proxy', 'illustration_proxy', 'illustration_real'):
            associated.append('low_color_carrier')
        if r['has_alpha']:
            associated.append('alpha_channel')

        fp_details.append({
            'filename': r['filename'],
            'image_class': r['image_class'],
            'taxonomy_class': r['taxonomy_class'],
            'final_score': r['suspicion_score'],
            'risk_level': r['risk_level'],
            'structural_score': r['structural_score'],
            'metadata_score': r['metadata_score'],
            'statistical_score': r['statistical_score'],
            'visual_score': r['visual_score'],
            'associated_signals': associated,
        })

    cause_counts = collections.Counter()
    for d in fp_details:
        for a in d['associated_signals']:
            cause_counts[a] += 1

    with open(os.path.join(OUT_DIR, 'g7_false_positive_analysis.json'), 'w') as f:
        json.dump({
            'note': ("Clean (non-stego, non-tampered) samples scored Medium or High. "
                     "'associated_signals' describes which detector categories were "
                     "elevated for that sample -- this is an association, not a "
                     "demonstrated causal claim, per the phase's wording rule."),
            'count': len(fp_details),
            'total_clean_samples': len(clean),
            'false_positive_rate_medium_or_high': round(len(fp_details) / len(clean), 4),
            'associated_signal_frequency': dict(cause_counts.most_common()),
            'details': fp_details,
        }, f, indent=2, default=str)

    fn_samples = [r for r in stego if r['risk_level'] == 'Low']
    fn_details = []
    for r in fn_samples:
        non_responding = []
        if not r.get('chi_square_is_suspicious'):
            non_responding.append('chi_square')
        if not r.get('rs_is_suspicious'):
            non_responding.append('rs')
        if not r.get('spa_is_suspicious'):
            non_responding.append('spa')
        if not r.get('entropy_is_suspicious'):
            non_responding.append('lsb_entropy')
        if not r.get('visual_is_suspicious'):
            non_responding.append('visual_balance')
        fn_details.append({
            'filename': r['filename'],
            'image_class': r['image_class'],
            'taxonomy_class': r['taxonomy_class'],
            'embedding_method': r['gt_stego_type'],
            'payload_level': r['gt_payload_level'],
            'final_score': r['suspicion_score'],
            'risk_level': r['risk_level'],
            'non_responding_detectors': non_responding,
        })

    with open(os.path.join(OUT_DIR, 'g7_false_negative_analysis.json'), 'w') as f:
        json.dump({
            'note': ("Stego samples (ground truth) scored Low. 'non_responding_detectors' "
                     "lists detectors whose own is_suspicious flag did not fire; whether "
                     "this reflects a defect, an inherent applicability limit (as "
                     "established for several detectors in G3-G6), or expected behavior "
                     "at low payload is [INFERRED] per-case in the report, not asserted here."),
            'count': len(fn_details),
            'total_stego_samples': len(stego),
            'false_negative_rate_at_low_risk': round(len(fn_details) / len(stego), 4),
            'details': fn_details,
        }, f, indent=2, default=str)

    tp = sum(1 for r in stego if r['suspicion_score'] >= 20.0)
    fn = len(stego) - tp
    fp = sum(1 for r in clean if r['suspicion_score'] >= 20.0)
    tn = len(clean) - fp
    sens = tp / (tp + fn) if (tp + fn) else None
    spec = tn / (tn + fp) if (tn + fp) else None
    fpr_overall = fp / (fp + tn) if (fp + tn) else None
    fnr_overall = fn / (fn + tp) if (fn + tp) else None
    prec = tp / (tp + fp) if (tp + fp) else None
    bal_acc = (sens + spec) / 2 if (sens is not None and spec is not None) else None

    summary = {
        'freshness_check': fresh_check,
        'corpus_total': len(recs),
        'clean_of_both_count': len(clean),
        'stego_count': len(stego),
        'overall_metrics_at_threshold_20': {
            'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
            'sensitivity': round(sens, 4) if sens is not None else None,
            'specificity': round(spec, 4) if spec is not None else None,
            'fpr': round(fpr_overall, 4) if fpr_overall is not None else None,
            'fnr': round(fnr_overall, 4) if fnr_overall is not None else None,
            'precision': round(prec, 4) if prec is not None else None,
            'balanced_accuracy': round(bal_acc, 4) if bal_acc is not None else None,
        },
        'independent_validation_set_available': False,
        'independent_validation_note': (
            "No independent held-out validation set exists in this corpus. The "
            "G3 calibration/validation split (g3_calibration_split.json) was "
            "explicitly marked inadequate for this purpose at generation time "
            "(see G3 report) and no threshold or parameter has ever been tuned "
            "against a held-out portion of this corpus in any phase -- so while "
            "no split-based independent validation exists, no result reported "
            "here has been circularly validated against a tuning set either."
        ),
    }
    with open(os.path.join(OUT_DIR, 'g7_summary.json'), 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    return {
        'clean_results': clean_results,
        'stego_results': stego_results,
        'pair_analysis': pair_analysis,
        'fp_details': fp_details,
        'fn_details': fn_details,
        'summary': summary,
    }


if __name__ == '__main__':
    r = run_all()
    print("Freshness check:", r['summary']['freshness_check'])
    print("Overall metrics:", r['summary']['overall_metrics_at_threshold_20'])
    print(f"FP (Medium/High clean): {len(r['fp_details'])}")
    print(f"FN (Low-risk stego): {len(r['fn_details'])}")
