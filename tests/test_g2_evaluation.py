"""
Phase G2 regression tests: evaluation infrastructure only.

These tests exercise the new G2 corpus/evaluation/analysis scripts. They do
not assert anything about production scoring thresholds (no such assertions
belong in this phase) -- they check that the infrastructure runs correctly,
produces well-formed output, and that ground truth / metadata are internally
consistent.
"""
import os
import json
import pytest

from tests.evaluation.g2_corpus_generator import generate_g2_corpus, CLASS_BUILDERS, PAYLOAD_LEVELS
from tests.evaluation.g2_baseline_runner import run_g2_baseline
from tests.evaluation.g2_correlation_analysis import run_correlation_analysis
from tests.evaluation.g2_calibration_split import build_split


@pytest.fixture(scope='module')
def corpus(tmp_path_factory):
    out_dir = str(tmp_path_factory.mktemp('g2_samples'))
    return generate_g2_corpus(out_dir), out_dir


class TestG2CorpusGenerator:
    def test_generates_all_seven_classes(self, corpus):
        records, _ = corpus
        classes_present = {r['image_class'] for r in records}
        expected = set(CLASS_BUILDERS.keys())
        assert expected.issubset(classes_present)

    def test_every_class_has_clean_and_three_payload_levels(self, corpus):
        records, _ = corpus
        for cls in CLASS_BUILDERS.keys():
            cls_records = [r for r in records if r['image_class'] == cls and r['format'] == 'PNG']
            levels = {r['ground_truth']['payload_level'] for r in cls_records}
            assert 'none' in levels  # clean
            for level in PAYLOAD_LEVELS.keys():
                assert level in levels

    def test_ground_truth_is_internally_consistent(self, corpus):
        records, _ = corpus
        for r in records:
            gt = r['ground_truth']
            if gt['has_steganography']:
                assert gt['stego_type'] != 'none'
            else:
                assert gt['stego_type'] == 'none'
                assert gt['embedding_rate'] == 0.0
            if gt['has_tampering']:
                assert gt['tampering_type'] != 'none'
            else:
                assert gt['tampering_type'] == 'none'

    def test_alpha_class_has_alpha_channel(self, corpus):
        records, out_dir = corpus
        from PIL import Image
        alpha_clean = [r for r in records if r['image_class'] == 'alpha_proxy' and r['ground_truth']['payload_level'] == 'none'][0]
        img = Image.open(alpha_clean['filepath'])
        assert img.mode == 'RGBA'
        assert alpha_clean['has_alpha'] is True

    def test_grayscale_class_is_actually_single_channel(self, corpus):
        records, _ = corpus
        from PIL import Image
        gray_clean = [r for r in records if r['image_class'] == 'grayscale_proxy' and r['ground_truth']['payload_level'] == 'none'][0]
        img = Image.open(gray_clean['filepath'])
        assert img.mode == 'L'

    def test_low_color_class_has_few_colors(self, corpus):
        records, _ = corpus
        from PIL import Image
        lc = [r for r in records if r['image_class'] == 'low_color_proxy' and r['ground_truth']['payload_level'] == 'none'][0]
        img = Image.open(lc['filepath']).convert('RGB')
        n_colors = len(img.getcolors(maxcolors=1_000_000))
        assert n_colors <= 8

    def test_repeated_structure_probe_is_ground_truth_clean(self, corpus):
        records, _ = corpus
        probe = [r for r in records if r['image_class'] == 'repeated_structure_proxy'][0]
        assert probe['ground_truth']['has_tampering'] is False

    def test_metadata_json_matches_generated_records(self, corpus):
        records, out_dir = corpus
        meta_path = os.path.join(out_dir, 'metadata.json')
        assert os.path.exists(meta_path)
        with open(meta_path) as f:
            meta = json.load(f)
        assert meta['sample_count'] == len(records)
        assert len(meta['samples']) == len(records)

    def test_generation_is_deterministic(self, tmp_path_factory):
        d1 = str(tmp_path_factory.mktemp('g2_a'))
        d2 = str(tmp_path_factory.mktemp('g2_b'))
        r1 = generate_g2_corpus(d1)
        r2 = generate_g2_corpus(d2)
        assert len(r1) == len(r2)
        from PIL import Image
        import numpy as np
        for a, b in zip(sorted(r1, key=lambda x: x['filename']), sorted(r2, key=lambda x: x['filename'])):
            assert a['filename'] == b['filename']
            if a['format'] == 'PNG':
                arr_a = np.array(Image.open(a['filepath']))
                arr_b = np.array(Image.open(b['filepath']))
                assert np.array_equal(arr_a, arr_b)


class TestG2BaselineRunner:
    @pytest.fixture(scope='class')
    def baseline(self, tmp_path_factory):
        corpus_dir = str(tmp_path_factory.mktemp('g2_corpus'))
        results_dir = str(tmp_path_factory.mktemp('g2_results'))
        records = run_g2_baseline(corpus_dir, results_dir)
        return records, results_dir

    def test_runs_without_modifying_production_scoring(self, baseline):
        # Sanity: importing and calling the runner must not raise, and must
        # produce one flattened record per corpus sample.
        records, _ = baseline
        assert len(records) >= 37

    def test_every_record_has_required_fields(self, baseline):
        records, _ = baseline
        required = [
            'filename', 'image_class', 'format', 'color_mode', 'has_alpha',
            'gt_has_steganography', 'gt_stego_type', 'gt_payload_level',
            'gt_embedding_rate', 'gt_has_tampering', 'gt_tampering_type',
            'suspicion_score', 'risk_level', 'structural_score', 'metadata_score',
            'statistical_score', 'visual_score', 'tampering_score', 'tampering_indicator',
            'chi_square_max_indicator', 'lsb_entropy_max', 'rs_estimated_rate',
            'rs_suspicion_indicator', 'spa_estimated_rate', 'spa_suspicion_indicator',
            'visual_min_balance_delta', 'visual_effective_threshold', 'jpeg_available',
        ]
        for r in records:
            for field in required:
                assert field in r, f"missing field {field} in record {r.get('filename')}"

    def test_output_files_written(self, baseline):
        _, results_dir = baseline
        assert os.path.exists(os.path.join(results_dir, 'g2_baseline_results.json'))
        assert os.path.exists(os.path.join(results_dir, 'g2_baseline_results.csv'))

    def test_scores_are_in_valid_range(self, baseline):
        records, _ = baseline
        for r in records:
            assert 0.0 <= r['suspicion_score'] <= 100.0
            assert 0.0 <= r['tampering_score'] <= 100.0
            assert r['risk_level'] in ('Low', 'Medium', 'High')


class TestG2CorrelationAnalysis:
    @pytest.fixture(scope='class')
    def corr_report(self, tmp_path_factory):
        corpus_dir = str(tmp_path_factory.mktemp('g2_corpus2'))
        results_dir = str(tmp_path_factory.mktemp('g2_results2'))
        run_g2_baseline(corpus_dir, results_dir)
        out_path = os.path.join(results_dir, 'corr.json')
        return run_correlation_analysis(os.path.join(results_dir, 'g2_baseline_results.json'), out_path)

    def test_matrix_is_symmetric(self, corr_report):
        names = corr_report['detectors_analyzed']
        m = corr_report['pearson_matrix']
        for a in names:
            for b in names:
                va, vb = m[a][b], m[b][a]
                if va is not None and vb is not None:
                    assert abs(va - vb) < 1e-9

    def test_self_correlation_is_one(self, corr_report):
        names = corr_report['detectors_analyzed']
        m = corr_report['pearson_matrix']
        for a in names:
            assert abs(m[a][a] - 1.0) < 1e-6

    def test_produces_pairwise_list(self, corr_report):
        assert len(corr_report['pairwise']) == 10  # C(5,2) for 5 detectors


class TestG2CalibrationSplit:
    @pytest.fixture(scope='class')
    def split(self, tmp_path_factory):
        corpus_dir = str(tmp_path_factory.mktemp('g2_corpus3'))
        generate_g2_corpus(corpus_dir)
        out_path = os.path.join(str(tmp_path_factory.mktemp('g2_split_out')), 'split.json')
        return build_split(os.path.join(corpus_dir, 'metadata.json'), out_path)

    def test_calibration_and_validation_are_disjoint(self, split):
        cal = set(split['calibration_filenames'])
        val = set(split['validation_filenames'])
        assert cal.isdisjoint(val)

    def test_calibration_and_validation_cover_all_samples(self, split):
        cal = set(split['calibration_filenames'])
        val = set(split['validation_filenames'])
        assert len(cal) + len(val) == split['total_samples']

    def test_adequacy_is_explicitly_flagged(self, split):
        # At this corpus size the split must be flagged inadequate --
        # this test locks in that the honesty requirement isn't silently
        # dropped in a future edit.
        assert split['corpus_is_adequate_for_threshold_calibration'] is False
        assert 'INADEQUATE' in split['adequacy_statement']
