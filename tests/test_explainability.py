import pytest
from app.core.explainability import ExplainabilityEngine
from app.core.evidence import EvidenceCollector


class TestExplainabilityEngine:
    """Test suite for Phase E Explainability Engine."""

    def test_steganography_explanation_clean(self):
        evidence_items = [
            {'detector': 'RS Steganalysis', 'severity': 'clean', 'indicator': 0.01},
            {'detector': 'Shannon Entropy', 'severity': 'clean', 'indicator': 0.0}
        ]
        scoring_res = {
            'suspicion_score': 0.0,
            'risk_level': 'Low',
            'detector_breakdown': [
                {'category': 'Statistical Analysis', 'detector': 'RS Steganalysis', 'status': 'Clean', 'points_added': 0.0, 'details': 'clean'}
            ]
        }

        res = ExplainabilityEngine.generate_steganography_explanation(evidence_items, scoring_res)
        assert res['score'] == 0.0
        assert res['risk'] == 'LOW'
        assert 'Low suspicion' in res['summary']
        assert len(res['primary_evidence']) == 0
        assert len(res['supporting_evidence']) == 2
        assert len(res['detector_contributions']) == 1

    def test_steganography_explanation_high_risk(self):
        evidence_items = [
            {'detector': 'RS Steganalysis', 'severity': 'anomaly', 'indicator': 0.85},
            {'detector': 'Chi-Square Attack (PoVs)', 'severity': 'anomaly', 'indicator': 0.90},
            {'detector': 'Shannon Entropy', 'severity': 'clean', 'indicator': 0.0}
        ]
        scoring_res = {
            'suspicion_score': 70.0,
            'risk_level': 'High',
            'detector_breakdown': [
                {'category': 'Statistical Analysis', 'detector': 'RS Steganalysis', 'status': 'Anomaly', 'points_added': 14.7, 'details': 'high rate'},
                {'category': 'Statistical Analysis', 'detector': 'Chi-Square Attack (PoVs)', 'status': 'Anomaly', 'points_added': 14.7, 'details': 'high prob'}
            ]
        }

        res = ExplainabilityEngine.generate_steganography_explanation(evidence_items, scoring_res)
        assert res['score'] == 70.0
        assert res['risk'] == 'HIGH'
        assert 'Strong statistical anomalies' in res['summary']
        assert 'RS Steganalysis' in res['summary']
        assert len(res['primary_evidence']) == 2
        assert len(res['supporting_evidence']) == 1
        assert len(res['detector_contributions']) == 2

    def test_tampering_explanation_suspicious(self):
        evidence_items = [
            {'detector': 'Copy-Move Duplicate Detection', 'severity': 'anomaly', 'indicator': 0.85},
            {'detector': 'Texture Variance Disparity', 'severity': 'clean', 'indicator': 0.05}
        ]
        tampering_res = {
            'available': True,
            'combined_score': 85.0,
            'is_suspicious': True,
            'flagged_detectors': ['copy_move'],
            'detectors': {
                'copy_move': {'available': True, 'is_suspicious': True, 'details': '1 cluster detected'},
                'local_variance': {'available': True, 'is_suspicious': False, 'details': 'normal'}
            }
        }

        res = ExplainabilityEngine.generate_tampering_explanation(evidence_items, tampering_res)
        assert res['score'] == 85.0
        assert res['status'] == 'SUSPICIOUS'
        assert 'duplicate block clusters' in res['summary'].lower() or 'copy-move' in res['summary'].lower()
        assert len(res['primary_evidence']) == 1

        # Check that tampering contributions always have points_added == 0.0
        for contrib in res['detector_contributions']:
            assert contrib['points_added'] == 0.0

    def test_tampering_explanation_unavailable(self):
        res = ExplainabilityEngine.generate_tampering_explanation([], None)
        assert res['status'] == 'NOT AVAILABLE'
        assert res['score'] == 0.0
        assert len(res['primary_evidence']) == 0

    def test_engine_generate_orchestration(self):
        evidence_dict = {
            'steganography': [{'detector': 'RS Steganalysis', 'severity': 'clean', 'indicator': 0.0}],
            'tampering': [{'detector': 'Copy-Move', 'severity': 'clean', 'indicator': 0.0}]
        }
        scoring_res = {'suspicion_score': 0.0, 'risk_level': 'Low', 'detector_breakdown': []}
        tampering_res = {'available': True, 'combined_score': 3.5, 'is_suspicious': False, 'detectors': {}}

        full_exp = ExplainabilityEngine.generate(evidence_dict, scoring_res, tampering_res)
        assert 'steganography' in full_exp
        assert 'tampering' in full_exp
        assert full_exp['steganography']['risk'] == 'LOW'
        assert full_exp['tampering']['status'] == 'NOT SUSPICIOUS'
