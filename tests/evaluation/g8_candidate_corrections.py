"""
Phase G8, Phases 9-10 — candidate correction simulation and generalization
testing.

All candidates are SIMULATED using the actual production scoring.py function
fed modified inputs (mirroring the G6 ablation discipline) -- no production
file is modified by this script. Uses the existing, un-regenerated 92-sample
corpus.
"""
import json
import os
import copy
from PIL import Image

from app.core import (
    MetadataAnalyzer, FileForensicsAnalyzer, VisualExtractor,
    StatisticalAnalyzer, TamperingAnalyzer, SuspicionScoringEngine,
)


def _load_existing_samples():
    samples = []
    with open('tests/evaluation/g3_samples/g3_metadata.json') as f:
        samples.extend(json.load(f)['g3_samples'])
    with open('tests/evaluation/g2_samples/metadata.json') as f:
        samples.extend(json.load(f)['samples'])
    return [s for s in samples if os.path.exists(s['filepath'])]


def _has_family_corroboration(stat_res):
    """
    Corroboration signal = RS only, not chi2/SPA.

    Rationale (established in Phase 8's controlled paired experiment on real
    photographs, BEFORE checking its effect on the three G7 targets): RS's
    estimated_embedding_rate showed a clean, monotonic, well-separated
    response to genuine embedding on all three independently-sourced real
    photographs (coffee, chelsea, rocket), with LOW clean-baseline values
    (0.02-0.17) in every case. Chi-square and SPA did not show this same
    reliable separation and were measured (Phase 2 reproduction) to already
    be elevated on the clean brick/grass/gravel baselines themselves
    (chi2=0.85 on 2 of 3; SPA=0.63-0.98 on 2 of 3) -- i.e. they are
    themselves subject to the same natural-texture false-positive mechanism
    under investigation, so using them as a "corroboration" signal would be
    circular. The 0.25 threshold reused here is the EXISTING production RS
    partial-evidence threshold (scoring.py's own 60%-tier cutoff), not a
    new invented value.
    """
    rs = stat_res.get('rs_analysis', {})
    rs_rate = rs.get('estimated_embedding_rate', 0.0)
    return bool(rs_rate > 0.25)


def candidate_D_visual_requires_corroboration(visual_res, stat_res):
    v = copy.deepcopy(visual_res)
    if v.get('is_visual_suspicious') and not _has_family_corroboration(stat_res):
        v['is_visual_suspicious'] = False
        v['min_balance_delta'] = 1.0
    return v


def candidate_E_max_not_sum_entropy_visual(stat_res, visual_res, base_score_result):
    entropy_pts = None
    for d in base_score_result['detector_breakdown']:
        if 'Shannon Entropy' in d['detector']:
            entropy_pts = d['points_added']
    visual_pts = base_score_result['category_scores'].get('visual', 0.0)
    if entropy_pts is None:
        return base_score_result['suspicion_score']
    combined = max(entropy_pts, visual_pts)
    old_combined = entropy_pts + visual_pts
    return base_score_result['suspicion_score'] - old_combined + combined


def run_candidates(out_path='tests/evaluation/g8_results/g8_candidate_corrections.json'):
    samples = _load_existing_samples()

    per_sample = []
    for s in samples:
        path = s['filepath']
        with open(path, 'rb') as f:
            file_bytes = f.read()
        img = Image.open(path)

        meta = MetadataAnalyzer.analyze(file_bytes, s['filename'])
        forensics = FileForensicsAnalyzer.analyze(file_bytes, meta)
        visual = VisualExtractor.extract_bit_planes(img)
        statistical = StatisticalAnalyzer.analyze(img, file_bytes=file_bytes, image_format=meta.get('detected_format'))
        tampering = TamperingAnalyzer.analyze(img, file_bytes=file_bytes, image_format=meta.get('detected_format'))

        base = SuspicionScoringEngine.evaluate(meta, visual, statistical, forensics_res=forensics, tampering_res=tampering)

        score_A = base['suspicion_score']

        visual_D = candidate_D_visual_requires_corroboration(visual, statistical)
        score_D_result = SuspicionScoringEngine.evaluate(meta, visual_D, statistical, forensics_res=forensics, tampering_res=tampering)
        score_D = score_D_result['suspicion_score']

        score_E = candidate_E_max_not_sum_entropy_visual(statistical, visual, base)

        gt = s['ground_truth']
        per_sample.append({
            'filename': s['filename'],
            'image_class': s['image_class'],
            'gt_has_steganography': gt['has_steganography'],
            'gt_payload_level': gt['payload_level'],
            'score_A_no_correction': score_A,
            'score_D_visual_corroboration': round(score_D, 2),
            'score_E_max_not_sum': round(score_E, 2),
        })

    def confusion(key, threshold=20.0):
        tp = fp = tn = fn = 0
        for r in per_sample:
            gt = r['gt_has_steganography']
            pred = r[key] >= threshold
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

    def confusion_by_payload(key, level, threshold=20.0):
        subset = [r for r in per_sample if r['gt_has_steganography'] and r['gt_payload_level'] == level]
        if not subset:
            return None
        det = sum(1 for r in subset if r[key] >= threshold) / len(subset)
        return {'n': len(subset), 'detection_rate': round(det, 4)}

    natural_photo_classes = {'photograph_real', 'photograph_proxy', 'repeated_texture_real'}
    def natural_photo_fpr(key, threshold=20.0):
        subset = [r for r in per_sample if not r['gt_has_steganography'] and r['image_class'] in natural_photo_classes]
        if not subset:
            return None
        fp = sum(1 for r in subset if r[key] >= threshold)
        return {'n': len(subset), 'fpr': round(fp / len(subset), 4)}

    results = {}
    for label, key in [('A_no_correction', 'score_A_no_correction'),
                        ('D_visual_requires_corroboration', 'score_D_visual_corroboration'),
                        ('E_max_not_sum_entropy_visual', 'score_E_max_not_sum')]:
        results[label] = {
            'overall_confusion': confusion(key),
            'natural_photo_fpr': natural_photo_fpr(key),
            'by_payload': {lvl: confusion_by_payload(key, lvl) for lvl in ['low', 'medium', 'high']},
        }

    for label, key in [('D_visual_requires_corroboration', 'score_D_visual_corroboration'),
                        ('E_max_not_sum_entropy_visual', 'score_E_max_not_sum')]:
        changed = sum(1 for r in per_sample if (r[key] >= 20.0) != (r['score_A_no_correction'] >= 20.0))
        tps_lost = sum(1 for r in per_sample if r['gt_has_steganography'] and r['score_A_no_correction'] >= 20.0 and r[key] < 20.0)
        fps_fixed = sum(1 for r in per_sample if not r['gt_has_steganography'] and r['score_A_no_correction'] >= 20.0 and r[key] < 20.0)
        target_fixed = [r['filename'] for r in per_sample
                         if r['image_class'] == 'repeated_texture_real' and not r['gt_has_steganography']
                         and r['score_A_no_correction'] >= 20.0 and r[key] < 20.0]
        results[label]['classification_changes_vs_A'] = changed
        results[label]['unique_tps_lost_vs_A'] = tps_lost
        results[label]['fps_fixed_vs_A'] = fps_fixed
        results[label]['original_g7_targets_fixed'] = target_fixed
        results[label]['original_g7_targets_fixed_count'] = len(target_fixed)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'note': ("Candidates simulated by feeding the REAL, unmodified "
                     "SuspicionScoringEngine.evaluate() modified inputs (D) "
                     "or by adjusting recorded category points post-hoc in a "
                     "way that mirrors what the real formula would do (E). "
                     "No production file was changed by this script."),
            'per_sample': per_sample,
            'results': results,
        }, f, indent=2, default=str)

    return results


if __name__ == '__main__':
    r = run_candidates()
    for label, v in r.items():
        print(label)
        print('  overall:', v['overall_confusion'])
        print('  natural_photo_fpr:', v['natural_photo_fpr'])
        print('  by_payload:', v['by_payload'])
        if 'classification_changes_vs_A' in v:
            print('  changes vs A:', v['classification_changes_vs_A'], 'tps_lost:', v['unique_tps_lost_vs_A'],
                  'fps_fixed:', v['fps_fixed_vs_A'], 'g7_targets_fixed:', v['original_g7_targets_fixed_count'])
