"""
Phase G8, Phase 2 — reproduce the G7 natural-texture false positives with
full detector detail (channel-level, evidence items, RS applicability vs
embedding evidence, etc.). Uses the EXISTING corpus images (verified via the
G7 inventory, not filenames alone). No production code touched.
"""
import json
import os
from PIL import Image

from app.core import (
    MetadataAnalyzer, FileForensicsAnalyzer, VisualExtractor,
    StatisticalAnalyzer, TamperingAnalyzer, SuspicionScoringEngine,
)
from app.core.evidence import EvidenceCollector

TARGET_FILES = [
    'repeated_texture_real_brick_clean.png',
    'repeated_texture_real_grass_clean.png',
    'repeated_texture_real_gravel_clean.png',
]


def _verify_from_inventory(fn):
    with open('tests/evaluation/g7_results/g7_corpus_inventory.json') as f:
        inv = json.load(f)
    rec = next((r for r in inv['records'] if r['filename'] == fn), None)
    if rec is None:
        raise RuntimeError(f"{fn} not found in G7 inventory -- cannot verify class label")
    return rec


def _find_path(fn):
    import glob
    paths = glob.glob(f'tests/evaluation/g3_samples/{fn}') + glob.glob(f'tests/evaluation/g2_samples/{fn}')
    if not paths:
        raise RuntimeError(f"{fn} not found on disk")
    return paths[0]


def run_reproduction(out_path='tests/evaluation/g8_results/g8_reproduction.json'):
    results = []
    for fn in TARGET_FILES:
        inv_rec = _verify_from_inventory(fn)
        assert inv_rec['image_class'] == 'repeated_texture_real', f"{fn} class label mismatch: {inv_rec['image_class']}"
        assert inv_rec['has_steganography'] is False and inv_rec['has_tampering'] is False, f"{fn} ground truth mismatch"

        path = _find_path(fn)
        with open(path, 'rb') as f:
            file_bytes = f.read()
        img = Image.open(path)

        meta = MetadataAnalyzer.analyze(file_bytes, fn)
        forensics = FileForensicsAnalyzer.analyze(file_bytes, meta)
        visual = VisualExtractor.extract_bit_planes(img)
        statistical = StatisticalAnalyzer.analyze(img, file_bytes=file_bytes, image_format=meta.get('detected_format'))
        tampering = TamperingAnalyzer.analyze(img, file_bytes=file_bytes, image_format=meta.get('detected_format'))
        scoring = SuspicionScoringEngine.evaluate(meta, visual, statistical, forensics_res=forensics, tampering_res=tampering)
        evidence = EvidenceCollector.collect_all(meta, visual, statistical)

        rs = statistical.get('rs_analysis', {})
        spa = statistical.get('sample_pair_analysis', statistical.get('spa_analysis', {}))
        chi2 = statistical.get('chi_square', {})
        entropy = statistical.get('entropy', {})

        results.append({
            'filename': fn,
            'verified_image_class': inv_rec['image_class'],
            'verified_actual_color_mode': inv_rec['actual_color_mode'],
            'verified_ground_truth': {'has_steganography': inv_rec['has_steganography'], 'has_tampering': inv_rec['has_tampering']},
            'final_score': scoring['suspicion_score'],
            'risk_level': scoring['risk_level'],
            'category_scores': scoring['category_scores'],
            'tampering_score': scoring.get('tampering_score'),
            'chi_square': {
                'gray': chi2.get('gray', {}),
                'red': chi2.get('red', {}),
                'green': chi2.get('green', {}),
                'blue': chi2.get('blue', {}),
                'max_indicator': chi2.get('max_indicator'),
            },
            'rs_analysis': {
                'estimated_embedding_rate': rs.get('estimated_embedding_rate'),
                'suspicion_indicator': rs.get('suspicion_indicator'),
                'rs_applicability_diagnostic': rs.get('rs_applicability_diagnostic'),
                'sym_diff': rs.get('sym_diff'),
                'is_suspicious': rs.get('is_suspicious'),
                'channel_breakdown': rs.get('channel_breakdown', {}),
            },
            'spa_analysis': {
                'estimated_embedding_rate': spa.get('estimated_embedding_rate'),
                'suspicion_indicator': spa.get('suspicion_indicator'),
                'is_suspicious': spa.get('is_suspicious'),
            },
            'entropy': entropy,
            'visual': {
                'stats': visual.get('stats'),
                'min_balance_delta': visual.get('min_balance_delta'),
                'min_balance_channel': visual.get('min_balance_channel'),
                'tested_channels': visual.get('tested_channels'),
                'channel_count': visual.get('channel_count'),
                'effective_threshold': visual.get('effective_threshold'),
                'is_visual_suspicious': visual.get('is_visual_suspicious'),
                'is_effectively_grayscale': visual.get('is_effectively_grayscale'),
            },
            'evidence_items': evidence.get('steganography', []),
        })

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'note': 'G7 false-positive reproduction with full detector detail. Class labels and ground truth verified against g7_corpus_inventory.json, not inferred from filenames.',
            'samples': results,
        }, f, indent=2, default=str)

    return results


if __name__ == '__main__':
    results = run_reproduction()
    for r in results:
        print(r['filename'], 'score=', r['final_score'], 'risk=', r['risk_level'])
        print('  categories:', r['category_scores'])
        print('  entropy_max:', r['entropy'].get('lsb_entropy', {}).get('max'))
        print('  visual delta/thresh:', r['visual']['min_balance_delta'], r['visual']['effective_threshold'], r['visual']['is_visual_suspicious'])
        print('  rs rate/applicability:', r['rs_analysis']['estimated_embedding_rate'], r['rs_analysis']['rs_applicability_diagnostic'])
        print('  spa rate:', r['spa_analysis']['estimated_embedding_rate'])
        print('  chi2 max:', r['chi_square']['max_indicator'])
