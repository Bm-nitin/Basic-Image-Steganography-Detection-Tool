import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PIL import Image
from app.core import (
    MetadataAnalyzer,
    VisualExtractor,
    StatisticalAnalyzer,
    SuspicionScoringEngine,
    ReportGenerator,
    FileForensicsAnalyzer,
    TamperingAnalyzer
)

def run_verification():
    samples = [
        ('Clean Carrier Baseline', 'tests/test_samples/clean_sample.png'),
        ('LSB Steganography Payload', 'tests/test_samples/stego_lsb_sample.png'),
        ('Appended EOF Trailing Data', 'tests/test_samples/stego_eof_sample.jpg')
    ]

    for title, path in samples:
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

        print(f"==================================================")
        print(f"TEST: {title}")
        print(f"File: {filename} ({meta['detected_format']}, {len(file_bytes):,} bytes)")
        print(f"MD5:  {meta['hashes']['md5']}")
        print(f"SUSPICION SCORE: {scoring['suspicion_score']} / 100")
        print(f"RISK LEVEL:      {scoring['risk_level'].upper()}")
        print(f"SUMMARY:         {scoring['risk_summary']}")
        print(f"TAMPERING SCORE: {scoring.get('tampering_score', 0.0)} / 100 (Indicator: {scoring.get('tampering_indicator', 0.0)})")
        print(f"--------------------------------------------------")
        print("Detailed Detector Findings:")
        for d in scoring['detector_breakdown']:
            status_symbol = "[ANOMALY]" if d['status'] == 'Anomaly' else ("[SUSPICIOUS]" if d['status'] == 'Suspicious' else "[CLEAN]")
            pts = f"(+{d['points_added']} pts)" if d['points_added'] > 0 else ""
            print(f"  {status_symbol:12} {d['detector']:32} {pts:12} -> {d['details']}")

        # Verify PDF report generation as well
        payload = {
            'filename': filename,
            'metadata': meta,
            'file_forensics': forensics,
            'visual': visual,
            'statistical': stat,
            'tampering': tampering,
            'scoring': scoring
        }
        pdf = ReportGenerator.generate_pdf_bytes(payload)
        print(f"  [PDF REPORT] Successfully generated {len(pdf):,} bytes of PDF.")
        print()

if __name__ == '__main__':
    run_verification()
