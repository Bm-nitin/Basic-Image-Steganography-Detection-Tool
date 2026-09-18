"""
Phase G6, Phase 3 — build the machine-readable G6 dataset.

Source: tests/evaluation/g4_results/g4_after_results.json (the existing G4
re-scan over the existing, un-regenerated 92-sample G3 corpus). Spot-checked
against a fresh run of the unmodified current pipeline on 3 random samples
before use (see G6 report Phase 1) -- confirmed no drift since G4/G5 made no
production changes.

This script performs no image analysis itself; it is a pure reshape/subset
of already-computed, already-verified data into the schema Phase 3 asks for.
"""
import json
import os


SOURCE_PATH = 'tests/evaluation/g4_results/g4_after_results.json'
OUT_PATH = 'tests/evaluation/g6_results/g6_dataset.json'


def build_g6_dataset(source_path=SOURCE_PATH, out_path=OUT_PATH):
    with open(source_path) as f:
        recs = json.load(f)

    dataset = []
    for r in recs:
        dataset.append({
            'filename': r['filename'],
            'image_class': r['image_class'],
            'format': r['format'],
            'gt_has_steganography': r['gt_has_steganography'],
            'gt_payload_level': r['gt_payload_level'],
            'gt_embedding_rate': r['gt_embedding_rate'],
            'gt_has_tampering': r['gt_has_tampering'],
            'suspicion_score': r['suspicion_score'],
            'risk_level': r['risk_level'],
            'statistical_score': r['statistical_score'],
            'structural_score': r['structural_score'],
            'metadata_score': r['metadata_score'],
            'visual_score': r['visual_score'],
            'chi_square_max_indicator': r['chi_square_max_indicator'],
            'lsb_entropy_max': r['lsb_entropy_max'],
            'spa_estimated_rate': r['spa_estimated_rate'],
            'spa_suspicion_indicator': r['spa_suspicion_indicator'],
            'rs_estimated_rate': r['rs_estimated_rate'],
            'rs_suspicion_indicator': r['rs_suspicion_indicator'],
            'rs_applicability_diagnostic': r['rs_applicability_diagnostic'],
            'visual_min_balance_delta': r['visual_min_balance_delta'],
            'visual_is_suspicious': r['visual_is_suspicious'],
            'entropy_is_suspicious': r['entropy_is_suspicious'],
            'spa_is_suspicious': r['spa_is_suspicious'],
            'rs_is_suspicious': r['rs_is_suspicious'],
            'chi_square_is_suspicious': r['chi_square_is_suspicious'],
            'pred_stego': r['pred_stego'],
        })

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'note': (
                "G6 LSB/parity evidence dataset. Derived from the existing, "
                "un-regenerated G3/G4 92-sample corpus and the existing G4 "
                "re-scan results (verified against a fresh run of the "
                "current, unmodified pipeline on 3 random samples before "
                "use -- see G6 report Phase 1). No new image analysis was "
                "performed by this script."
            ),
            'sample_count': len(dataset),
            'samples': dataset,
        }, f, indent=2, default=str)

    return dataset


if __name__ == '__main__':
    ds = build_g6_dataset()
    print(f"G6 dataset built: {len(ds)} samples.")
