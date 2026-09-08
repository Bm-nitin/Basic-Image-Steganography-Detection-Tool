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

    print("=" * 65)
    print("CONTROLLED SAMPLE FORENSIC VERIFICATION (PHASE E)")
    print("Evaluating Ground Truth Controlled Test Samples")
    print("=" * 65)

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

        explainability = scoring.get('explainability', {})
        stego_exp = explainability.get('steganography', {})
        tamper_exp = explainability.get('tampering', {})

        print(f"\n" + "-" * 65)
        print(f"CONTROLLED SAMPLE: {title}")
        print(f"File: {filename} ({meta['detected_format']}, {len(file_bytes):,} bytes)")
        print(f"MD5:  {meta['hashes']['md5']}")
        print(f"STEGANOGRAPHY SUSPICION INDEX: {scoring['suspicion_score']} / 100 [{scoring['risk_level'].upper()}]")
        print(f"  Explainability: {stego_exp.get('summary', scoring['risk_summary'])}")
        print(f"TAMPERING INDEPENDENT INDEX:    {scoring.get('tampering_score', 0.0)} / 100 [{tamper_exp.get('status', 'NOT SUSPICIOUS')}]")
        print(f"  Explainability: {tamper_exp.get('summary', 'N/A')}")
        print("-" * 65)

        primary_ev = stego_exp.get('primary_evidence', []) + tamper_exp.get('primary_evidence', [])
        if primary_ev:
            print("Primary Key Evidence Items:")
            for ev in primary_ev:
                sev = ev.get('severity', 'clean').upper()
                print(f"  [{sev:9}] {ev.get('detector'):30} | {ev.get('observed_value')} (Threshold: {ev.get('threshold')})")
                print(f"             Explanation: {ev.get('explanation')}")
        else:
            print("Primary Key Evidence Items: None (All evaluated detectors conform to clean carrier baseline)")

        print("\nDetector Mathematical Breakdown:")
        for d in scoring['detector_breakdown']:
            status_symbol = "[ANOMALY]" if d['status'] == 'Anomaly' else ("[SUSPICIOUS]" if d['status'] == 'Suspicious' else "[CLEAN]")
            pts = f"(+{d['points_added']} pts)" if d['points_added'] > 0 else "(+0.0 pts)"
            print(f"  {status_symbol:12} {d['detector']:32} {pts:10} -> {d['details']}")

        # Verify PDF report generation
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
        print(f"\n  [PDF REPORT] Successfully compiled {len(pdf):,} bytes of PDF forensic documentation.")

if __name__ == '__main__':
    run_verification()
