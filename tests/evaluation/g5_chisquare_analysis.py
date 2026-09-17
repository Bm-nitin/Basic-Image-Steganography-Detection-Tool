"""
Phase G5, Target A — detailed chi-square measurement.

Loads the EXISTING G3/G4 corpus images (already on disk under
tests/evaluation/g3_samples/ and tests/evaluation/g2_samples/ -- not
regenerated) and calls the unmodified StatisticalAnalyzer.chi_square_attack()
directly per channel, recording full detail (chi2_stat, df, ratio, p_value,
indicator) that the production pipeline's flattened evaluation records did
not previously capture. This is read-only measurement; no production code
is touched by this script.
"""
import os
import json
from PIL import Image
import numpy as np

from app.core.statistical import StatisticalAnalyzer


def _load_existing_samples():
    samples = []
    with open('tests/evaluation/g3_samples/g3_metadata.json') as f:
        g3_meta = json.load(f)
    samples.extend(g3_meta['g3_samples'])
    with open('tests/evaluation/g2_samples/metadata.json') as f:
        g2_meta = json.load(f)
    samples.extend(g2_meta['samples'])
    return [s for s in samples if os.path.exists(s['filepath'])]


def run_chisquare_analysis(out_path='tests/evaluation/g5_results/g5_chisquare_analysis.json'):
    samples = _load_existing_samples()
    records = []

    for s in samples:
        img = Image.open(s['filepath'])
        rgb_img = img.convert('RGB')
        img_np = np.array(rgb_img, dtype=np.uint8)
        gray_np = np.array(rgb_img.convert('L'), dtype=np.uint8)
        w, h = img.size

        per_channel = {}
        for name, arr in [('gray', gray_np), ('red', img_np[:, :, 0]),
                           ('green', img_np[:, :, 1]), ('blue', img_np[:, :, 2])]:
            res = StatisticalAnalyzer.chi_square_attack(arr)
            per_channel[name] = res

        max_indicator = max(c['probability_stego'] for c in per_channel.values())

        gt = s['ground_truth']
        records.append({
            'filename': s['filename'],
            'image_class': s['image_class'],
            'format': s['format'],
            'width': w,
            'height': h,
            'pixel_count': w * h,
            'color_mode': s['color_mode'],
            'gt_has_steganography': gt['has_steganography'],
            'gt_payload_level': gt['payload_level'],
            'gt_embedding_rate': gt['embedding_rate'],
            'gt_has_tampering': gt['has_tampering'],
            'max_chi2_indicator': round(max_indicator, 4),
            'channels': per_channel,
        })

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'note': (
                "Detailed chi-square measurement over the EXISTING G3 corpus "
                "(not regenerated). Read-only measurement; chi_square_attack() "
                "itself is unmodified."
            ),
            'sample_count': len(records),
            'samples': records,
        }, f, indent=2, default=str)

    return records


if __name__ == '__main__':
    recs = run_chisquare_analysis()
    print(f"Measured chi-square detail for {len(recs)} existing samples.")
