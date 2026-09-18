"""
Phase G6, Phase 5 — leave-one-detector-out (LODO) ablation.

For each of the 5 LSB/parity cluster detectors, zero out ONLY that
detector's raw signal in a COPY of the statistical_res dict, then call the
REAL, unmodified SuspicionScoringEngine.evaluate() to get a virtual score.
This uses production scoring code exactly as-is -- no production file is
modified; only the input dict fed to it is altered, per sample, in memory.

Uses the EXISTING G3/G4 corpus images (not regenerated).
"""
import os
import json
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


def _zero_out(stat_res, detector):
    s = copy.deepcopy(stat_res)
    if detector == 'chi_square':
        s.setdefault('chi_square', {})['max_indicator'] = 0.0
        s['chi_square']['max_probability'] = 0.0
    elif detector == 'rs':
        s.setdefault('rs_analysis', {})['estimated_embedding_rate'] = 0.0
        s['rs_analysis']['suspicion_indicator'] = 0.0
    elif detector == 'spa':
        for key in ('spa_analysis', 'sample_pair_analysis'):
            if key in s:
                s[key]['estimated_embedding_rate'] = 0.0
                s[key]['suspicion_indicator'] = 0.0
    elif detector == 'lsb_entropy':
        s.setdefault('entropy', {}).setdefault('lsb_entropy', {})['max'] = 0.0
    return s


def _zero_out_visual(visual_res):
    v = copy.deepcopy(visual_res)
    v['min_balance_delta'] = 1.0
    v['is_visual_suspicious'] = False
    return v


DETECTORS = ['chi_square', 'rs', 'spa', 'lsb_entropy', 'visual_balance']


def run_lodo_ablation(out_path='tests/evaluation/g6_results/g6_lodo_ablation.json'):
    samples = _load_existing_samples()
    records = []

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

        full_score = SuspicionScoringEngine.evaluate(meta, visual, statistical, forensics_res=forensics, tampering_res=tampering)

        variant_scores = {}
        for det in DETECTORS:
            if det == 'visual_balance':
                v_visual = _zero_out_visual(visual)
                v_stat = statistical
            else:
                v_visual = visual
                v_stat = _zero_out(statistical, det)
            v_score = SuspicionScoringEngine.evaluate(meta, v_visual, v_stat, forensics_res=forensics, tampering_res=tampering)
            variant_scores[det] = {
                'suspicion_score': v_score['suspicion_score'],
                'risk_level': v_score['risk_level'],
            }

        gt = s['ground_truth']
        records.append({
            'filename': s['filename'],
            'image_class': s['image_class'],
            'gt_has_steganography': gt['has_steganography'],
            'gt_payload_level': gt['payload_level'],
            'full_suspicion_score': full_score['suspicion_score'],
            'full_risk_level': full_score['risk_level'],
            'full_pred_stego': bool(full_score['suspicion_score'] >= 20.0),
            'without': variant_scores,
        })

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'note': (
                "Leave-one-detector-out ablation. Each 'without' entry is "
                "the REAL SuspicionScoringEngine.evaluate() output when that "
                "one detector's raw signal is zeroed in a copy of the input "
                "dict -- production code itself is unmodified."
            ),
            'sample_count': len(records),
            'samples': records,
        }, f, indent=2, default=str)

    return records


if __name__ == '__main__':
    recs = run_lodo_ablation()
    print(f"LODO ablation complete: {len(recs)} samples.")
