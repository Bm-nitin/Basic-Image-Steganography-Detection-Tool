import os
import pytest
from PIL import Image
from app.core import (
    MetadataAnalyzer, FileForensicsAnalyzer, VisualExtractor,
    StatisticalAnalyzer, TamperingAnalyzer, SuspicionScoringEngine,
    ReportGenerator
)

class TestScoreConsistency:
    """Test suite for Phase F Score Consistency Audit."""

    @pytest.mark.parametrize("path,label", [
        ("tests/test_samples/clean_sample.png", "Clean PNG"),
        ("tests/test_samples/stego_lsb_sample.png", "LSB Stego PNG"),
        ("tests/test_samples/stego_eof_sample.jpg", "EOF Stego JPEG"),
        ("tests/evaluation/samples/tamper_copymove.png", "Copy-Move Tampered PNG")
    ])
    def test_score_and_explainability_consistency(self, path, label):
        filename = os.path.basename(path)
        with open(path, "rb") as f:
            file_bytes = f.read()

        meta = MetadataAnalyzer.analyze(file_bytes, filename)
        forensics = FileForensicsAnalyzer.analyze(file_bytes, meta)
        img = Image.open(path)
        visual = VisualExtractor.extract_bit_planes(img)
        stat = StatisticalAnalyzer.analyze(img, file_bytes=file_bytes, image_format=meta.get("detected_format"))
        tampering = TamperingAnalyzer.analyze(img, file_bytes=file_bytes, image_format=meta.get("detected_format"))

        scoring = SuspicionScoringEngine.evaluate(meta, visual, stat, forensics_res=forensics, tampering_res=tampering)

        # 1. Verify breakdown sum equals total score
        stego_pts = sum(d["points_added"] for d in scoring["detector_breakdown"] if d["category"] != "Tampering & Manipulation Forensics")
        clamped_pts = round(max(0.0, min(100.0, stego_pts)), 1)
        assert abs(scoring["suspicion_score"] - clamped_pts) < 0.05

        # 2. Verify tampering detectors contribute exactly 0.0 pts
        tamper_pts = sum(d["points_added"] for d in scoring["detector_breakdown"] if d["category"] == "Tampering & Manipulation Forensics")
        assert tamper_pts == 0.0

        # 3. Verify explainability score equals scoring score
        explain = scoring["explainability"]
        assert explain["steganography"]["score"] == scoring["suspicion_score"]
        assert explain["tampering"]["score"] == scoring["tampering_score"]

        # 4. Verify PDF report generates with identical payload
        payload = {
            "filename": filename,
            "metadata": meta,
            "file_forensics": forensics,
            "visual": visual,
            "statistical": stat,
            "tampering": tampering,
            "scoring": scoring
        }
        pdf_bytes = ReportGenerator.generate_pdf_bytes(payload)
        assert len(pdf_bytes) > 20000
