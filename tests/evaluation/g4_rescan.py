"""
Phase G4 — re-score the EXISTING G3 corpus (images already on disk, not
regenerated) with the current codebase, to measure the isolated effect of
the G4 Target A (RS) and Target B (copy-move, reverted -- see report) changes
against the preserved G3 baseline. Does not overwrite any G3 file.
"""
import os
import sys
import json
import csv
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.core import (
    MetadataAnalyzer, FileForensicsAnalyzer, VisualExtractor,
    StatisticalAnalyzer, TamperingAnalyzer, SuspicionScoringEngine,
)
from tests.evaluation.g2_baseline_runner import _flatten_record


def _load_existing_samples():
    samples = []
    g3_meta_path = 'tests/evaluation/g3_samples/g3_metadata.json'
    with open(g3_meta_path) as f:
        g3_meta = json.load(f)
    samples.extend(g3_meta['g3_samples'])

    g2_meta_path = 'tests/evaluation/g2_samples/metadata.json'
    with open(g2_meta_path) as f:
        g2_meta = json.load(f)
    samples.extend(g2_meta['samples'])

    return [s for s in samples if os.path.exists(s['filepath'])]


def run_g4_rescan(results_dir='tests/evaluation/g4_results', tag='g4_after'):
    os.makedirs(results_dir, exist_ok=True)
    samples = _load_existing_samples()

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

        flat = _flatten_record(s, scoring, statistical, visual, tampering)
        cm = tampering.get('detectors', {}).get('copy_move', {})
        flat['cm_cluster_count'] = cm.get('cluster_count')
        flat['cm_anomaly_indicator'] = cm.get('anomaly_indicator')
        flat['cm_is_suspicious'] = cm.get('is_suspicious')
        flat['rs_applicability_diagnostic'] = statistical.get('rs_analysis', {}).get('rs_applicability_diagnostic')
        flat_records.append(flat)

    json_path = os.path.join(results_dir, f'{tag}_results.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(flat_records, f, indent=2, default=str)
    csv_path = os.path.join(results_dir, f'{tag}_results.csv')
    if flat_records:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(flat_records[0].keys()))
            writer.writeheader()
            writer.writerows(flat_records)

    return flat_records


if __name__ == '__main__':
    recs = run_g4_rescan()
    print(f"Re-scored {len(recs)} existing samples (no regeneration).")
