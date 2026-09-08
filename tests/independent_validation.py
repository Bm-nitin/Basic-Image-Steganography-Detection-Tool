import os
import sys
import json
from typing import Dict, Any, List
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core import (
    MetadataAnalyzer,
    FileForensicsAnalyzer,
    VisualExtractor,
    StatisticalAnalyzer,
    TamperingAnalyzer,
    SuspicionScoringEngine
)

def run_independent_validation(report_path='tests/independent_validation_report.json'):
    print("=" * 72)
    print("INDEPENDENT SAMPLE VALIDATION PROCEDURE (PHASE F)")
    print("Evaluating all genuinely available project ground-truth images")
    print("=" * 72)

    samples = [
        {
            'path': 'tests/test_samples/clean_sample.png',
            'category': 'A. Known Clean PNG',
            'ground_truth': {'steganography': False, 'stego_type': 'none', 'tampering': False, 'tampering_type': 'none'}
        },
        {
            'path': 'tests/evaluation/samples/clean_carrier.png',
            'category': 'A. Known Clean PNG',
            'ground_truth': {'steganography': False, 'stego_type': 'none', 'tampering': False, 'tampering_type': 'none'}
        },
        {
            'path': 'tests/evaluation/samples/clean_carrier.jpg',
            'category': 'B. Known Clean JPEG',
            'ground_truth': {'steganography': False, 'stego_type': 'none', 'tampering': False, 'tampering_type': 'none'}
        },
        {
            'path': 'tests/evaluation/samples/stego_lsb_low.png',
            'category': 'C. Controlled LSB Stego (Low ~15%)',
            'ground_truth': {'steganography': True, 'stego_type': 'spatial_lsb', 'embedding_rate': 0.15, 'tampering': False, 'tampering_type': 'none'}
        },
        {
            'path': 'tests/evaluation/samples/stego_lsb_medium.png',
            'category': 'C. Controlled LSB Stego (Med ~50%)',
            'ground_truth': {'steganography': True, 'stego_type': 'spatial_lsb', 'embedding_rate': 0.50, 'tampering': False, 'tampering_type': 'none'}
        },
        {
            'path': 'tests/evaluation/samples/stego_lsb_high.png',
            'category': 'C. Controlled LSB Stego (High 100%)',
            'ground_truth': {'steganography': True, 'stego_type': 'spatial_lsb', 'embedding_rate': 1.0, 'tampering': False, 'tampering_type': 'none'}
        },
        {
            'path': 'tests/test_samples/stego_lsb_sample.png',
            'category': 'C. Controlled LSB Stego (100% Deterministic)',
            'ground_truth': {'steganography': True, 'stego_type': 'spatial_lsb', 'embedding_rate': 1.0, 'tampering': False, 'tampering_type': 'none'}
        },
        {
            'path': 'tests/test_samples/stego_eof_sample.jpg',
            'category': 'D. Controlled JPEG Stego (Appended 82B)',
            'ground_truth': {'steganography': True, 'stego_type': 'appended_eof', 'embedding_rate': 0.0, 'tampering': False, 'tampering_type': 'none'}
        },
        {
            'path': 'tests/evaluation/samples/stego_eof.jpg',
            'category': 'D. Controlled JPEG Stego (Appended 780B)',
            'ground_truth': {'steganography': True, 'stego_type': 'appended_eof', 'embedding_rate': 0.0, 'tampering': False, 'tampering_type': 'none'}
        },
        {
            'path': 'tests/evaluation/samples/tamper_copymove.png',
            'category': 'E. Controlled Tampering (Copy-Move)',
            'ground_truth': {'steganography': False, 'stego_type': 'none', 'tampering': True, 'tampering_type': 'copy_move'}
        },
        {
            'path': 'tests/evaluation/samples/tamper_spliced_noise.png',
            'category': 'E. Controlled Tampering (Spliced Noise)',
            'ground_truth': {'steganography': False, 'stego_type': 'none', 'tampering': True, 'tampering_type': 'noise_disparity'}
        }
    ]

    records = []

    for s in samples:
        path = s['path']
        if not os.path.exists(path):
            print(f"Skipping missing sample: {path}")
            continue

        filename = os.path.basename(path)
        with open(path, 'rb') as f:
            file_bytes = f.read()

        meta = MetadataAnalyzer.analyze(file_bytes, filename)
        forensics = FileForensicsAnalyzer.analyze(file_bytes, meta)
        img = Image.open(path)
        visual = VisualExtractor.extract_bit_planes(img)
        stat = StatisticalAnalyzer.analyze(img, file_bytes=file_bytes, image_format=meta.get('detected_format'))
        tampering = TamperingAnalyzer.analyze(img, file_bytes=file_bytes, image_format=meta.get('detected_format'))
        scoring = SuspicionScoringEngine.evaluate(meta, visual, stat, forensics_res=forensics, tampering_res=tampering)

        explain = scoring.get('explainability', {})
        stego_exp = explain.get('steganography', {})
        tamper_exp = explain.get('tampering', {})

        primary_ev = stego_exp.get('primary_evidence', []) + tamper_exp.get('primary_evidence', [])

        # Extract major indicators
        major_indicators = {
            'rs_rate': stat.get('rs_analysis', {}).get('estimated_embedding_rate', 0.0),
            'spa_rate': stat.get('spa_analysis', {}).get('estimated_embedding_rate', 0.0),
            'chi_square_indicator': stat.get('chi_square', {}).get('max_probability', 0.0),
            'max_lsb_entropy': stat.get('entropy', {}).get('lsb_entropy', {}).get('max', 0.0),
            'trailing_bytes': meta.get('trailing_data', {}).get('trailing_bytes_count', 0),
            'tampering_indicator': scoring.get('tampering_indicator', 0.0),
            'tampering_is_suspicious': scoring.get('tampering_suspicious', False)
        }

        rec = {
            'filename': filename,
            'path': path,
            'category': s['category'],
            'format': meta.get('detected_format', 'UNKNOWN'),
            'file_size_bytes': len(file_bytes),
            'ground_truth': s['ground_truth'],
            'steganography': {
                'score': scoring['suspicion_score'],
                'risk': scoring['risk_level'],
                'summary': stego_exp.get('summary', '')
            },
            'tampering': {
                'score': scoring.get('tampering_score', 0.0),
                'status': tamper_exp.get('status', 'NOT SUSPICIOUS'),
                'summary': tamper_exp.get('summary', '')
            },
            'primary_evidence_count': len(primary_ev),
            'primary_evidence': [
                {
                    'category': it.get('category'),
                    'detector': it.get('detector'),
                    'severity': it.get('severity'),
                    'observed': it.get('observed_value'),
                    'threshold': it.get('threshold'),
                    'explanation': it.get('explanation')
                } for it in primary_ev
            ],
            'major_indicators': major_indicators
        }
        records.append(rec)

        print(f"[{rec['category'][:30]:30}] {filename:22} | Stego: {scoring['suspicion_score']:5.1f} ({scoring['risk_level']:6}) | Tamper: {scoring.get('tampering_score', 0.0):5.1f} ({tamper_exp.get('status'):14})")

    report = {
        'evaluation_scope': 'Phase F Independent Sample Validation',
        'sample_count': len(records),
        'records': records
    }

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    print(f"\nSuccessfully validated {len(records)} independent ground-truth samples.")
    print(f"Validation report saved to: {report_path}")
    print("=" * 72)
    return report

if __name__ == '__main__':
    run_independent_validation()
