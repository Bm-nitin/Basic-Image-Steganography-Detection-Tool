import os
import pytest
import numpy as np
from PIL import Image

from app.core import (
    MetadataAnalyzer,
    VisualExtractor,
    StatisticalAnalyzer,
    SuspicionScoringEngine,
    ReportGenerator
)

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), 'test_samples')

@pytest.fixture
def clean_image_bytes():
    path = os.path.join(SAMPLE_DIR, 'clean_sample.png')
    with open(path, 'rb') as f:
        return f.read()

@pytest.fixture
def stego_lsb_bytes():
    path = os.path.join(SAMPLE_DIR, 'stego_lsb_sample.png')
    with open(path, 'rb') as f:
        return f.read()

@pytest.fixture
def stego_eof_bytes():
    path = os.path.join(SAMPLE_DIR, 'stego_eof_sample.jpg')
    with open(path, 'rb') as f:
        return f.read()


class TestMetadataAnalyzer:
    def test_magic_bytes_valid_png(self, clean_image_bytes):
        is_valid, fmt, msg = MetadataAnalyzer.verify_magic_bytes(clean_image_bytes, 'sample.png')
        assert is_valid is True
        assert fmt == 'PNG'

    def test_magic_bytes_valid_jpeg(self, stego_eof_bytes):
        is_valid, fmt, msg = MetadataAnalyzer.verify_magic_bytes(stego_eof_bytes, 'sample.jpg')
        assert is_valid is True
        assert fmt == 'JPEG'

    def test_magic_bytes_invalid_binary(self):
        fake_bytes = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00"  # Windows PE binary header
        is_valid, fmt, msg = MetadataAnalyzer.verify_magic_bytes(fake_bytes, 'fake.png')
        assert is_valid is False
        assert fmt == 'unknown'

    def test_hashes_calculation(self, clean_image_bytes):
        hashes = MetadataAnalyzer.calculate_hashes(clean_image_bytes)
        assert 'md5' in hashes and len(hashes['md5']) == 32
        assert 'sha256' in hashes and len(hashes['sha256']) == 64

    def test_eof_trailing_detection_clean(self, clean_image_bytes):
        res = MetadataAnalyzer.detect_trailing_data(clean_image_bytes, 'PNG')
        assert res['has_trailing_data'] is False
        assert res['trailing_bytes_count'] == 0

    def test_eof_trailing_detection_tampered(self, stego_eof_bytes):
        res = MetadataAnalyzer.detect_trailing_data(stego_eof_bytes, 'JPEG')
        assert res['has_trailing_data'] is True
        assert res['trailing_bytes_count'] > 0
        assert 'SECRET' in res['preview_ascii']


class TestVisualExtractor:
    def test_bit_plane_extraction(self, clean_image_bytes):
        from io import BytesIO
        img = Image.open(BytesIO(clean_image_bytes))
        result = VisualExtractor.extract_bit_planes(img)

        assert 'previews' in result
        previews = result['previews']
        assert 'gray_lsb' in previews
        assert 'gray_msb' in previews
        assert 'red_lsb' in previews
        assert 'green_lsb' in previews
        assert 'blue_lsb' in previews
        assert 'rgb_lsb' in previews

        # Verify all are valid base64 data URIs
        for k, uri in previews.items():
            assert uri.startswith('data:image/png;base64,')


class TestStatisticalAnalyzer:
    def test_shannon_entropy_calculation(self):
        # Array of identical values should have 0 entropy
        zeros = np.zeros((50, 50), dtype=np.uint8)
        assert StatisticalAnalyzer.calculate_shannon_entropy(zeros) == 0.0

        # Uniform distribution across all 256 values should have ~8.0 bits entropy
        uniform = np.arange(256, dtype=np.uint8).reshape((16, 16))
        ent = StatisticalAnalyzer.calculate_shannon_entropy(uniform)
        assert pytest.approx(ent, 0.01) == 8.0

    def test_chi_square_detection(self, clean_image_bytes, stego_lsb_bytes):
        from io import BytesIO
        clean_img = Image.open(BytesIO(clean_image_bytes))
        stego_img = Image.open(BytesIO(stego_lsb_bytes))

        clean_chi2 = StatisticalAnalyzer.chi_square_attack(np.array(clean_img)[:, :, 0])
        stego_chi2 = StatisticalAnalyzer.chi_square_attack(np.array(stego_img)[:, :, 0])

        assert 'probability_stego' in clean_chi2
        assert 'probability_stego' in stego_chi2
        # Stego image with uniform random LSB replacement must have elevated stego probability
        assert stego_chi2['probability_stego'] > clean_chi2['probability_stego']
        assert stego_chi2['is_suspicious'] is True

    def test_histogram_generation(self, clean_image_bytes):
        from io import BytesIO
        img = Image.open(BytesIO(clean_image_bytes))
        hist_uri = StatisticalAnalyzer.generate_histogram_plot(np.array(img))
        assert hist_uri.startswith('data:image/png;base64,')


class TestSuspicionScoring:
    def test_clean_image_scoring(self, clean_image_bytes):
        from io import BytesIO
        img = Image.open(BytesIO(clean_image_bytes))
        meta = MetadataAnalyzer.analyze(clean_image_bytes, 'clean_sample.png')
        visual = VisualExtractor.extract_bit_planes(img)
        stat = StatisticalAnalyzer.analyze(img)

        score_res = SuspicionScoringEngine.evaluate(meta, visual, stat)
        assert 0.0 <= score_res['suspicion_score'] <= 100.0
        assert score_res['risk_level'] in ['Low', 'Medium', 'High']
        assert len(score_res['detector_breakdown']) > 0

    def test_eof_tampered_scoring(self, stego_eof_bytes):
        from io import BytesIO
        img = Image.open(BytesIO(stego_eof_bytes))
        meta = MetadataAnalyzer.analyze(stego_eof_bytes, 'stego_eof_sample.jpg')
        visual = VisualExtractor.extract_bit_planes(img)
        stat = StatisticalAnalyzer.analyze(img)

        score_res = SuspicionScoringEngine.evaluate(meta, visual, stat)
        # Should detect trailing bytes and add at least 25 points
        assert any(d['detector'] == 'Appended Trailing Data' and d['status'] == 'Anomaly'
                   for d in score_res['detector_breakdown'])


class TestReportGenerator:
    def test_pdf_generation(self, clean_image_bytes):
        from io import BytesIO
        img = Image.open(BytesIO(clean_image_bytes))
        meta = MetadataAnalyzer.analyze(clean_image_bytes, 'clean_sample.png')
        visual = VisualExtractor.extract_bit_planes(img)
        stat = StatisticalAnalyzer.analyze(img)
        scoring = SuspicionScoringEngine.evaluate(meta, visual, stat)

        payload = {
            'filename': 'clean_sample.png',
            'metadata': meta,
            'visual': visual,
            'statistical': stat,
            'scoring': scoring
        }

        pdf_bytes = ReportGenerator.generate_pdf_bytes(payload)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
        # Valid PDF header
        assert pdf_bytes.startswith(b'%PDF')
