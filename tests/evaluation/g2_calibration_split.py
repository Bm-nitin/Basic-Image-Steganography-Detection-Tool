"""
Phase G2 — Calibration / validation split.

Per the G2 spec (Step 9): do not tune thresholds against the same samples
used for final validation. This module produces an explicit, deterministic
split and states plainly whether the corpus is large enough to support a
meaningful separation.
"""
import json
import os
from typing import Dict, Any, List


def build_split(metadata_path: str = 'tests/evaluation/g2_samples/metadata.json',
                 out_path: str = 'tests/evaluation/g2_results/g2_calibration_split.json') -> Dict[str, Any]:
    with open(metadata_path, 'r', encoding='utf-8') as f:
        corpus = json.load(f)
    samples = corpus['samples']

    # Deterministic split: alternate by index within each image_class so both
    # sets see every class, rather than a random split (reproducibility).
    by_class: Dict[str, List[dict]] = {}
    for s in samples:
        by_class.setdefault(s['image_class'], []).append(s)

    calibration, validation = [], []
    for cls, items in by_class.items():
        for i, s in enumerate(items):
            (calibration if i % 2 == 0 else validation).append(s['filename'])

    n_total = len(samples)
    n_cal = len(calibration)
    n_val = len(validation)
    per_class_counts = {cls: len(items) for cls, items in by_class.items()}
    min_class_count = min(per_class_counts.values()) if per_class_counts else 0

    # Explicit adequacy assessment -- not a judgment call left implicit.
    ADEQUATE_MIN_PER_CLASS = 10  # a conventional minimum for even coarse per-class threshold tuning
    is_adequate = min_class_count >= ADEQUATE_MIN_PER_CLASS and n_total >= 100

    result = {
        'total_samples': n_total,
        'calibration_count': n_cal,
        'validation_count': n_val,
        'per_class_sample_counts': per_class_counts,
        'minimum_per_class_count': min_class_count,
        'adequacy_threshold_used': {
            'min_samples_per_class': ADEQUATE_MIN_PER_CLASS,
            'min_total_samples': 100
        },
        'corpus_is_adequate_for_threshold_calibration': is_adequate,
        'adequacy_statement': (
            "INADEQUATE: this corpus (37 samples total, 4-7 per class) is far "
            "too small to support statistically meaningful threshold "
            "calibration separate from validation. The split below exists as "
            "reproducible evaluation infrastructure and to demonstrate the "
            "methodology, but no threshold should be tuned against the "
            "'calibration' half and reported as validated against the "
            "'validation' half at this corpus size. A corpus at least in the "
            "low hundreds per class, across genuinely varied real-world "
            "instances (not just this generator's parameterizations), would "
            "be needed before that separation is meaningful."
            if not is_adequate else
            "Corpus meets the minimum adequacy bar used here for a coarse "
            "calibration/validation split."
        ),
        'calibration_filenames': sorted(calibration),
        'validation_filenames': sorted(validation),
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)

    return result


if __name__ == '__main__':
    r = build_split()
    print(f"Calibration: {r['calibration_count']}, Validation: {r['validation_count']}")
    print(f"Adequate for threshold calibration: {r['corpus_is_adequate_for_threshold_calibration']}")
    print(r['adequacy_statement'])
