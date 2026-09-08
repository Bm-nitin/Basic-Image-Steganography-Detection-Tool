import os
import numpy as np
import pytest
from PIL import Image

from app.core.tampering import TamperingAnalyzer
from app.core.scoring import SuspicionScoringEngine
from app.core.metadata_analyzer import MetadataAnalyzer
from app.core.visual_extractor import VisualExtractor
from app.core.statistical import StatisticalAnalyzer
from app.core.file_forensics import FileForensicsAnalyzer


class TestTamperingAnalyzer:
    """Test suite for the orchestrator TamperingAnalyzer and scoring integration."""

    def test_clean_sample_pipeline(self):
        path = 'tests/test_samples/clean_sample.png'
        with open(path, 'rb') as f:
            b = f.read()
        im = Image.open(path)
        meta = MetadataAnalyzer.analyze(b, 'clean_sample.png')
        forensics = FileForensicsAnalyzer.analyze(b, meta)
        vis = VisualExtractor.extract_bit_planes(im)
        stat = StatisticalAnalyzer.analyze(im, file_bytes=b, image_format='PNG')
        tamp = TamperingAnalyzer.analyze(im, file_bytes=b, image_format='PNG')

        assert tamp['available'] is True
        assert 0.0 <= tamp['combined_indicator'] <= 1.0
        assert 0.0 <= tamp['combined_score'] <= 100.0
        assert tamp['is_suspicious'] is False
        assert len(tamp['flagged_detectors']) == 0

        # Verify scoring integration: tampering adds zero points to overall score
        score = SuspicionScoringEngine.evaluate(meta, vis, stat, forensics_res=forensics, tampering_res=tamp)
        assert score['suspicion_score'] == 0.0
        assert score['risk_level'] == 'Low'
        assert score['tampering_score'] == tamp['combined_score']
        assert score['tampering_indicator'] == tamp['combined_indicator']
        assert score['tampering_suspicious'] is False

        # Verify detector breakdown contains informational tampering entries with points_added == 0.0
        tampering_entries = [d for d in score['detector_breakdown'] if d['category'] == 'Tampering & Manipulation Forensics']
        assert len(tampering_entries) >= 4  # Noise, Var, Edge, CopyMove
        for entry in tampering_entries:
            assert entry['points_added'] == 0.0

    def test_stego_eof_sample_with_jpeg_ela(self):
        path = 'tests/test_samples/stego_eof_sample.jpg'
        with open(path, 'rb') as f:
            b = f.read()
        im = Image.open(path)
        tamp = TamperingAnalyzer.analyze(im, file_bytes=b, image_format='JPEG')

        assert tamp['available'] is True
        assert tamp['detectors']['ela']['available'] is True
        assert tamp['is_suspicious'] is False

        meta = MetadataAnalyzer.analyze(b, 'stego_eof_sample.jpg')
        forensics = FileForensicsAnalyzer.analyze(b, meta)
        vis = VisualExtractor.extract_bit_planes(im)
        stat = StatisticalAnalyzer.analyze(im, file_bytes=b, image_format='JPEG')
        score = SuspicionScoringEngine.evaluate(meta, vis, stat, forensics_res=forensics, tampering_res=tamp)

        # Baseline overall score preserved
        assert score['suspicion_score'] == 41.5
        assert score['risk_level'] == 'Medium'
        assert score['tampering_score'] == tamp['combined_score']

    def test_spliced_tampered_image(self):
        # Create an image with textured pattern
        np.random.seed(123)
        h, w = 256, 256
        arr = np.random.randint(50, 200, (h, w), dtype=np.uint8)

        # Clone a 48x48 region from (48, 48) to (160, 48) with rigid translation (+112, 0)
        source_patch = arr[48:96, 48:96].copy()
        arr[48:96, 160:208] = source_patch

        # Also inject extreme localized noise into another section
        noisy_patch = np.clip(arr[160:220, 48:108] + np.random.normal(0, 50, (60, 60)), 0, 255).astype(np.uint8)
        arr[160:220, 48:108] = noisy_patch

        im = Image.fromarray(arr, mode='L')
        tamp = TamperingAnalyzer.analyze(im, file_bytes=None, image_format='PNG')

        assert tamp['available'] is True
        assert tamp['combined_indicator'] > 0.40
        assert tamp['combined_score'] > 40.0
        assert tamp['is_suspicious'] is True
        assert len(tamp['suspicious_regions']) > 0
        assert len(tamp['suspicious_regions']) <= TamperingAnalyzer.MAX_SUSPICIOUS_REGIONS

