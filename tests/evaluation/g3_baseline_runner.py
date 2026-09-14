"""
Phase G3 — Baseline evaluation runner over the expanded (G2 + G3) corpus.
Same structure as g2_baseline_runner.py, pointed at the larger corpus.
"""
import os
import sys
import json
import csv
import re
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
from tests.evaluation.g3_corpus_generator import generate_g3_corpus
from tests.evaluation.g2_baseline_runner import _flatten_record


def run_g3_baseline(output_dir: str = 'tests/evaluation/g3_samples',
                     results_dir: str = 'tests/evaluation/g3_results',
                     tag: str = 'baseline') -> List[Dict[str, Any]]:
    os.makedirs(results_dir, exist_ok=True)
    samples = generate_g3_corpus(output_dir)

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
        flat['corpus_source'] = s.get('corpus_source', 'unknown')
        flat['source_id'] = s.get('source_id', s.get('image_class'))

        # Copy-move-specific detail, recorded directly (needed for Step 3's
        # candidate-fix comparison independent of the overall tampering score).
        cm = tampering.get('detectors', {}).get('copy_move', {})
        flat['cm_available'] = cm.get('available')
        flat['cm_cluster_count'] = cm.get('cluster_count')
        flat['cm_anomaly_indicator'] = cm.get('anomaly_indicator')
        flat['cm_total_blocks'] = cm.get('total_blocks')
        flat['cm_candidate_matches'] = cm.get('candidate_matches')
        flat['cm_is_suspicious'] = cm.get('is_suspicious')
        m = re.search(r'\((\d+) clustered blocks\)', cm.get('details', '') or '')
        flat['cm_total_clustered_blocks'] = int(m.group(1)) if m else 0

        flat_records.append(flat)

    json_path = os.path.join(results_dir, f'g3_{tag}_results.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(flat_records, f, indent=2, default=str)

    csv_path = os.path.join(results_dir, f'g3_{tag}_results.csv')
    if flat_records:
        fieldnames = list(flat_records[0].keys())
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_records)

    return flat_records


if __name__ == '__main__':
    tag = sys.argv[1] if len(sys.argv) > 1 else 'baseline'
    recs = run_g3_baseline(tag=tag)
    print(f"Evaluated {len(recs)} G3 corpus samples (tag={tag}).")
