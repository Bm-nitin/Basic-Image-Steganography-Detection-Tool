import os
import pytest
import numpy as np
from PIL import Image

from app.core import (
    MetadataAnalyzer,
    VisualExtractor,
    StatisticalAnalyzer,
    SuspicionScoringEngine,
    ReportGenerator,
    LocalVarianceAnalyzer,
    EdgeAnalyzer
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
        # Should detect trailing bytes and add anomaly status
        assert any(d['detector'] == 'Appended Trailing Data' and d['status'] == 'Anomaly'
                   for d in score_res['detector_breakdown'])

    def test_statistical_category_budget_cap_50(self):
        # Synthetic worst-case where all detectors trigger maximum anomaly
        meta = {'trailing_data': {'has_trailing_data': False, 'size': 0}, 'metadata': {}}
        visual = {'min_balance_delta': 0.0001}
        extreme_stat = {
            'chi_square': {'max_indicator': 1.0, 'max_probability': 1.0},
            'entropy': {'lsb_entropy': {'max': 1.0}},
            'spa_analysis': {'estimated_embedding_rate': 1.0, 'suspicion_indicator': 1.0},
            'rs_analysis': {'estimated_embedding_rate': 1.0, 'suspicion_indicator': 1.0},
            'jpeg_analysis': {'available': True, 'jpeg_structural_indicator': 1.0},
            'channel_analysis': {'channel_anomaly_indicator': 1.0, 'alpha_analysis': {'suspicious': True}}
        }
        score_res = SuspicionScoringEngine.evaluate(meta, visual, extreme_stat)
        assert score_res['category_scores']['statistical'] <= 50.0
        assert score_res['suspicion_score'] <= 100.0

    def test_composite_score_hard_ceiling_100(self):
        # Synthetic worst-case where all 4 layers fire maximum points
        meta = {
            'trailing_data': {'has_trailing_data': True, 'trailing_bytes_count': 10000},
            'metadata': {'suspicious_signatures': ['steghide', 'outguess']}
        }
        forensics = {
            'trailing_data': {'has_trailing_data': True, 'trailing_bytes_count': 10000},
            'embedded_signatures': [{'type': 'ZIP archive', 'offset': 500, 'evidence_strength': 'high'}],
            'polyglot_suspected': True,
            'polyglot_reason': 'ZIP in JPEG',
            'structural_anomaly_indicator': 1.0
        }
        visual = {'min_balance_delta': 0.00001}
        extreme_stat = {
            'chi_square': {'max_indicator': 1.0, 'max_probability': 1.0},
            'entropy': {'lsb_entropy': {'max': 1.0}},
            'spa_analysis': {'estimated_embedding_rate': 1.0, 'suspicion_indicator': 1.0},
            'rs_analysis': {'estimated_embedding_rate': 1.0, 'suspicion_indicator': 1.0},
            'jpeg_analysis': {'available': True, 'jpeg_structural_indicator': 1.0},
            'channel_analysis': {'channel_anomaly_indicator': 1.0}
        }
        score_res = SuspicionScoringEngine.evaluate(meta, visual, extreme_stat, forensics_res=forensics)
        assert score_res['suspicion_score'] == 100.0
        assert score_res['category_scores']['structural'] <= 20.0
        assert score_res['category_scores']['metadata'] <= 10.0
        assert score_res['category_scores']['statistical'] <= 50.0
        assert score_res['category_scores']['visual'] <= 20.0

    def test_dynamic_non_jpeg_weight_redistribution(self):
        meta = {'metadata': {}}
        visual = {'min_balance_delta': 0.05}
        non_jpeg_stat = {
            'chi_square': {'max_indicator': 0.90},
            'entropy': {'lsb_entropy': {'max': 0.999}},
            'spa_analysis': {'estimated_embedding_rate': 0.80},
            'rs_analysis': {'estimated_embedding_rate': 0.80},
            'jpeg_analysis': {'available': False, 'reason': 'not_jpeg'},
            'channel_analysis': {'channel_anomaly_indicator': 0.0}
        }
        score_res = SuspicionScoringEngine.evaluate(meta, visual, non_jpeg_stat)
        # JPEG structural detector should NOT appear in breakdown for non-JPEG
        detectors = [d['detector'] for d in score_res['detector_breakdown']]
        assert 'JPEG Structural Analysis' not in detectors
        # Statistical category should receive full 50.0 pts from proportional redistribution
        assert score_res['category_scores']['statistical'] == 50.0


class TestMultiChannelAnalysis:
    def test_analyze_channels_rgb(self, clean_image_bytes):
        from io import BytesIO
        img = Image.open(BytesIO(clean_image_bytes))
        res = StatisticalAnalyzer.analyze_channels(img)
        assert res['has_alpha'] is False
        assert 'red' in res['channel_metrics']
        assert 'green' in res['channel_metrics']
        assert 'blue' in res['channel_metrics']
        assert 'rg' in res['cross_channel_correlations']
        assert 'rg' in res['cross_channel_lsb_xor_entropy']

    def test_analyze_channels_rgba_constant(self):
        rgba = Image.new('RGBA', (64, 64), (100, 150, 200, 255))
        res = StatisticalAnalyzer.analyze_channels(rgba)
        assert res['has_alpha'] is True
        assert res['alpha_analysis']['is_constant'] is True
        assert res['alpha_analysis']['suspicious'] is False

    def test_analyze_channels_rgba_modulated_alpha(self):
        rgba = Image.new('RGBA', (64, 64), (100, 150, 200, 255))
        noisy_alpha = np.random.randint(180, 256, (64, 64), dtype=np.uint8)
        rgba.putalpha(Image.fromarray(noisy_alpha))
        res = StatisticalAnalyzer.analyze_channels(rgba)
        assert res['has_alpha'] is True
        assert res['alpha_analysis']['is_constant'] is False
        assert res['alpha_analysis']['suspicious'] is True


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


class TestLocalVarianceAnalyzer:
    def test_uniform_image(self):
        img = Image.new('RGB', (100, 100), color=(120, 120, 120))
        res = LocalVarianceAnalyzer.analyze(img)
        assert res['available'] is True
        assert res['global_variance'] == 0.0
        assert res['anomaly_indicator'] == 0.0
        assert res['is_suspicious'] is False

    def test_clean_sample(self):
        img = Image.open('tests/test_samples/clean_sample.png')
        res = LocalVarianceAnalyzer.analyze(img)
        assert res['available'] is True
        assert res['anomaly_indicator'] < 0.35
        assert res['is_suspicious'] is False

    def test_insufficient_dimensions(self):
        img = Image.new('RGB', (10, 10), color=(100, 100, 100))
        res = LocalVarianceAnalyzer.analyze(img)
        assert res['available'] is False
        assert res['reason'] == 'insufficient_dimensions'


class TestEdgeAnalyzer:
    def test_uniform_image(self):
        img = Image.new('RGB', (100, 100), color=(120, 120, 120))
        res = EdgeAnalyzer.analyze(img)
        assert res['available'] is True
        assert res['mean_gradient'] == 0.0
        assert res['anomaly_indicator'] == 0.0
        assert res['is_suspicious'] is False

    def test_clean_sample(self):
        img = Image.open('tests/test_samples/clean_sample.png')
        res = EdgeAnalyzer.analyze(img)
        assert res['available'] is True
        assert res['anomaly_indicator'] < 0.30
        assert res['is_suspicious'] is False

    def test_insufficient_dimensions(self):
        img = Image.new('RGB', (10, 10), color=(100, 100, 100))
        res = EdgeAnalyzer.analyze(img)
        assert res['available'] is False
        assert res['reason'] == 'insufficient_dimensions'

