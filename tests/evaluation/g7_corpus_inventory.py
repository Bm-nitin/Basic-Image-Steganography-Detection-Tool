"""
Phase G7, Phase 2 — corpus inventory.

Reads the EXISTING corpus metadata files (g3_metadata.json, g2 metadata.json)
and the actual image files on disk (for dimensions/mode, not assumed from
filenames) to build a precise, verified inventory. No corpus regeneration.
"""
import json
import os
import collections
from PIL import Image


def _load_existing_samples():
    samples = []
    with open('tests/evaluation/g3_samples/g3_metadata.json') as f:
        samples.extend(json.load(f)['g3_samples'])
    with open('tests/evaluation/g2_samples/metadata.json') as f:
        samples.extend(json.load(f)['samples'])
    return samples


def build_inventory(out_path='tests/evaluation/g7_results/g7_corpus_inventory.json'):
    samples = _load_existing_samples()

    missing = [s for s in samples if not os.path.exists(s['filepath'])]
    present = [s for s in samples if os.path.exists(s['filepath'])]

    records = []
    for s in present:
        img = Image.open(s['filepath'])
        w, h = img.size
        gt = s['ground_truth']
        records.append({
            'filename': s['filename'],
            'image_class': s['image_class'],
            'format': s['format'],
            'declared_color_mode': s['color_mode'],
            'actual_color_mode': img.mode,
            'width': w,
            'height': h,
            'pixel_count': w * h,
            'has_alpha': img.mode in ('RGBA', 'LA'),
            'has_steganography': gt['has_steganography'],
            'stego_type': gt['stego_type'],
            'payload_level': gt['payload_level'],
            'embedding_rate': gt['embedding_rate'],
            'has_tampering': gt['has_tampering'],
            'tampering_type': gt['tampering_type'],
            'corpus_source': s.get('corpus_source', 'G2_synthetic_proxy'),
        })

    n = len(records)
    n_stego = sum(1 for r in records if r['has_steganography'])
    n_tamper = sum(1 for r in records if r['has_tampering'])
    n_clean_of_both = sum(1 for r in records if not r['has_steganography'] and not r['has_tampering'])

    fmt_counts = collections.Counter(r['format'] for r in records)
    class_counts = collections.Counter(r['image_class'] for r in records)
    mode_counts = collections.Counter(r['actual_color_mode'] for r in records)
    payload_counts = collections.Counter(r['payload_level'] for r in records if r['has_steganography'])
    embedding_method_counts = collections.Counter(r['stego_type'] for r in records if r['has_steganography'])
    tamper_type_counts = collections.Counter(r['tampering_type'] for r in records if r['has_tampering'])
    dims = [(r['width'], r['height']) for r in records]
    source_counts = collections.Counter(r['corpus_source'] for r in records)

    inventory = {
        'total_samples_in_metadata': len(samples),
        'total_samples_present_on_disk': n,
        'missing_from_disk': [s['filename'] for s in missing],
        'clean_of_both_stego_and_tampering': n_clean_of_both,
        'has_steganography_count': n_stego,
        'has_tampering_count': n_tamper,
        'format_distribution': dict(fmt_counts),
        'image_class_distribution': dict(sorted(class_counts.items())),
        'color_mode_distribution': dict(mode_counts),
        'payload_level_distribution_stego_only': dict(payload_counts),
        'embedding_method_distribution': dict(embedding_method_counts),
        'tampering_type_distribution': dict(tamper_type_counts),
        'corpus_source_distribution': dict(source_counts),
        'dimension_range': {
            'min_width': min(d[0] for d in dims), 'max_width': max(d[0] for d in dims),
            'min_height': min(d[1] for d in dims), 'max_height': max(d[1] for d in dims),
            'unique_dimensions': sorted(set(dims)),
        },
        'records': records,
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(inventory, f, indent=2, default=str)

    return inventory


if __name__ == '__main__':
    inv = build_inventory()
    print(f"Total in metadata: {inv['total_samples_in_metadata']}, present on disk: {inv['total_samples_present_on_disk']}")
    if inv['missing_from_disk']:
        print("MISSING:", inv['missing_from_disk'])
    print("Classes:", inv['image_class_distribution'])
    print("Formats:", inv['format_distribution'])
    print("Color modes:", inv['color_mode_distribution'])
