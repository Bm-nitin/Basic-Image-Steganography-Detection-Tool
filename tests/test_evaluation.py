import os
import pytest
from tests.evaluation.sample_generator import generate_evaluation_dataset
from tests.evaluation.evaluator import ControlledEvaluator


class TestControlledEvaluation:
    """Test suite for Phase E Controlled Evaluation Framework."""

    def test_sample_generator(self, tmp_path):
        out_dir = str(tmp_path / 'eval_samples')
        samples = generate_evaluation_dataset(out_dir)
        assert len(samples) == 8
        for s in samples:
            assert os.path.exists(s['filepath'])
            assert 'ground_truth' in s
            assert 'has_steganography' in s['ground_truth']
            assert 'has_tampering' in s['ground_truth']

    def test_evaluator_execution(self, tmp_path):
        out_dir = str(tmp_path / 'samples')
        report_file = str(tmp_path / 'report.json')
        report = ControlledEvaluator.run_evaluation(output_dir=out_dir, report_path=report_file)

        assert os.path.exists(report_file)
        assert report['sample_count'] == 8
        assert 'steganography_performance' in report
        assert 'tampering_performance' in report

        stego_p = report['steganography_performance']
        assert stego_p['accuracy'] >= 0.75
        assert stego_p['false_positive_rate'] <= 0.25

        tamper_p = report['tampering_performance']
        assert tamper_p['accuracy'] >= 0.75
        assert tamper_p['false_positive_rate'] <= 0.25
