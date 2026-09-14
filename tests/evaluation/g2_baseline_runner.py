"""
Phase G2 — Baseline evaluation runner.

Runs the CURRENT, unmodified production detector pipeline (as integrated
after G1) over every sample in the G2 corpus and records the full set of
fields requested in the G2 spec (Step 4). This makes NO changes to
app/core/* -- it only calls the existing public analyze()/evaluate() methods
and records their outputs.
"""
import os
import sys
import json
import csv
from typing import Dict, Any, List
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.core import (
    MetadataAnalyzer,
    FileForensicsAnalyzer,
    VisualExtractor,
    StatisticalAnalyzer,
    TamperingAnalyzer,
    SuspicionScoringEngine,
)
from tests.evaluation.g2_corpus_generator import generate_g2_corpus


def _flatten_record(sample_meta: Dict[str, Any], scoring: Dict[str, Any],
                     statistical: Dict[str, Any], visual: Dict[str, Any],
                     tampering: Dict[str, Any]) -> Dict[str, Any]:
    gt = sample_meta['ground_truth']
    chi2 = statistical.get('chi_square', {})
    entropy = statistical.get('entropy', {})
    spa = statistical.get('sample_pair_analysis', {})
    rs = statistical.get('rs_analysis', {})
    jpeg = statistical.get('jpeg_analysis', {})

    return {
        # --- sample identity / ground truth ---
        'filename': sample_meta['filename'],
        'image_class': sample_meta['image_class'],
        'format': sample_meta['format'],
        'color_mode': sample_meta['color_mode'],
        'has_alpha': sample_meta['has_alpha'],
        'gt_has_steganography': gt['has_steganography'],
        'gt_stego_type': gt['stego_type'],
        'gt_payload_level': gt['payload_level'],
        'gt_embedding_rate': gt['embedding_rate'],
        'gt_has_tampering': gt['has_tampering'],
        'gt_tampering_type': gt['tampering_type'],

        # --- overall scoring (Step 4) ---
        'suspicion_score': scoring.get('suspicion_score'),
        'risk_level': scoring.get('risk_level'),
        'structural_score': scoring.get('category_scores', {}).get('structural'),
        'metadata_score': scoring.get('category_scores', {}).get('metadata'),
        'statistical_score': scoring.get('category_scores', {}).get('statistical'),
        'visual_score': scoring.get('category_scores', {}).get('visual'),
        'tampering_score': scoring.get('tampering_score'),
        'tampering_indicator': scoring.get('tampering_indicator'),
        'tampering_suspicious': scoring.get('tampering_suspicious'),

        # --- individual detector outputs (Step 4) ---
        'chi_square_max_indicator': chi2.get('max_indicator'),
        'chi_square_is_suspicious': chi2.get('is_suspicious'),
        'lsb_entropy_max': entropy.get('lsb_entropy', {}).get('max'),
        'entropy_is_suspicious': entropy.get('is_suspicious'),
        'rs_estimated_rate': rs.get('estimated_embedding_rate'),
        'rs_suspicion_indicator': rs.get('suspicion_indicator'),
        'rs_is_suspicious': rs.get('is_suspicious'),
        'spa_estimated_rate': spa.get('estimated_embedding_rate'),
        'spa_suspicion_indicator': spa.get('suspicion_indicator'),
        'spa_is_suspicious': spa.get('is_suspicious'),
        'visual_min_balance_delta': visual.get('min_balance_delta'),
        'visual_effective_threshold': visual.get('effective_threshold'),
        'visual_channel_count': visual.get('channel_count'),
        'visual_is_suspicious': visual.get('is_visual_suspicious'),
        'jpeg_available': jpeg.get('available'),
        'jpeg_structural_indicator': jpeg.get('jpeg_structural_indicator'),
        'combined_statistical_indicator': statistical.get('combined_indicator'),

        # --- predictions (>=20.0 matches the convention used by the
        # project's own existing evaluator.py for consistency) ---
        'pred_stego': bool(scoring.get('suspicion_score', 0.0) >= 20.0),
        'pred_tamper': bool(scoring.get('tampering_suspicious', False)),
    }


def run_g2_baseline(corpus_dir: str = 'tests/evaluation/g2_samples',
                     results_dir: str = 'tests/evaluation/g2_results') -> List[Dict[str, Any]]:
    os.makedirs(results_dir, exist_ok=True)
    samples = generate_g2_corpus(corpus_dir)

    flat_records = []
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
        scoring = SuspicionScoringEngine.evaluate(meta, visual, statistical, forensics_res=forensics, tampering_res=tampering)

        flat_records.append(_flatten_record(s, scoring, statistical, visual, tampering))

    json_path = os.path.join(results_dir, 'g2_baseline_results.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(flat_records, f, indent=2, default=str)

    csv_path = os.path.join(results_dir, 'g2_baseline_results.csv')
    if flat_records:
        fieldnames = list(flat_records[0].keys())
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_records)

    return flat_records


if __name__ == '__main__':
    recs = run_g2_baseline()
    print(f"Evaluated {len(recs)} G2 corpus samples. Results written to tests/evaluation/g2_results/")
