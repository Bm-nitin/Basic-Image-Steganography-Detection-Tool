import pytest
from app.core.evidence import EvidenceItem, EvidenceCollector


class TestEvidenceFramework:
    """Test suite for Phase E Evidence Representation and Collection."""

    def test_evidence_item_creation_and_serialization(self):
        item = EvidenceItem(
            category='statistical',
            detector='RS Steganalysis',
            severity='anomaly',
            indicator=0.854321,
            observed_value='75.4% estimated capacity',
            threshold='< 25.0% capacity',
            explanation='RS curves demonstrate severe group count convergence.',
            supporting_details={'rate': 0.7543}
        )

        d = item.to_dict()
        assert d['category'] == 'statistical'
        assert d['detector'] == 'RS Steganalysis'
        assert d['severity'] == 'anomaly'
        assert d['indicator'] == 0.8543  # Rounded to 4 decimal places
        assert d['observed_value'] == '75.4% estimated capacity'
        assert d['threshold'] == '< 25.0% capacity'
        assert 'convergence' in d['explanation']
        assert d['supporting_details']['rate'] == 0.7543

    def test_collect_steganography_evidence_clean(self):
        meta_res = {
            'metadata': {'dimensions': (100, 100), 'suspicious_signatures': []},
            'trailing_data': {'has_trailing_data': False, 'trailing_bytes_count': 0}
        }
        visual_res = {'min_balance_delta': 0.035}
        statistical_res = {
            'entropy': {'global_entropy': 6.5, 'lsb_entropy': {'max': 0.94}},
            'chi_square': {'max_indicator': 0.05, 'max_probability': 0.05},
            'spa_analysis': {'estimated_embedding_rate': 0.05, 'estimated_percentage': 5.0},
            'rs_analysis': {'estimated_embedding_rate': 0.02, 'suspicion_indicator': 0.02, 'estimated_percentage': 2.0}
        }

        items = EvidenceCollector.collect_steganography_evidence(meta_res, visual_res, statistical_res)
        assert len(items) >= 5
        # All items should have severity 'clean'
        for item in items:
            assert item['severity'] == 'clean'
            assert item['indicator'] <= 0.30

    def test_collect_steganography_evidence_stego_lsb(self):
        meta_res = {
            'metadata': {'dimensions': (100, 100), 'suspicious_signatures': []},
            'trailing_data': {'has_trailing_data': False, 'trailing_bytes_count': 0}
        }
        visual_res = {'min_balance_delta': 0.0005}
        statistical_res = {
            'entropy': {'global_entropy': 7.9, 'lsb_entropy': {'max': 1.0000}},
            'chi_square': {'max_indicator': 0.95, 'max_probability': 0.95},
            'spa_analysis': {'estimated_embedding_rate': 0.72, 'estimated_percentage': 72.0},
            'rs_analysis': {'estimated_embedding_rate': 0.78, 'suspicion_indicator': 0.85, 'estimated_percentage': 78.0}
        }

        items = EvidenceCollector.collect_steganography_evidence(meta_res, visual_res, statistical_res)
        severities = [it['severity'] for it in items]
        assert 'anomaly' in severities
        # First items must be anomalies due to severity sort order
        assert items[0]['severity'] == 'anomaly'

    def test_collect_tampering_evidence_handling(self):
        # Unavailable tampering
        assert EvidenceCollector.collect_tampering_evidence(None) == []
        assert EvidenceCollector.collect_tampering_evidence({'available': False}) == []

        # Available clean tampering
        clean_tamper = {
            'available': True,
            'detectors': {
                'ela': {'available': False},
                'noise': {'available': True, 'is_suspicious': False, 'anomaly_indicator': 0.05, 'global_noise_std': 0.3, 'outlier_region_fraction': 0.0, 'details': 'clean'},
                'local_variance': {'available': True, 'is_suspicious': False, 'anomaly_indicator': 0.08, 'global_variance': 500.0, 'outlier_region_fraction': 0.02, 'details': 'clean'},
                'edge': {'available': True, 'is_suspicious': False, 'anomaly_indicator': 0.02, 'mean_gradient': 10.0, 'edge_density': 0.02, 'details': 'clean'},
                'copy_move': {'available': True, 'is_suspicious': False, 'anomaly_indicator': 0.0, 'candidate_matches': 0, 'cluster_count': 0, 'details': 'clean'}
            }
        }
        items = EvidenceCollector.collect_tampering_evidence(clean_tamper)
        assert len(items) == 5
        for it in items:
            assert it['severity'] in ('clean', 'info')

    def test_evidence_severity_sorting(self):
        meta_res = {
            'metadata': {'dimensions': (100, 100), 'suspicious_signatures': ['OpenStego v0.8']},
            'trailing_data': {'has_trailing_data': True, 'trailing_bytes_count': 120}
        }
        visual_res = {'min_balance_delta': 0.035}
        statistical_res = {
            'entropy': {'global_entropy': 6.5, 'lsb_entropy': {'max': 0.94}},
            'chi_square': {'max_indicator': 0.05, 'max_probability': 0.05},
            'spa_analysis': {'estimated_embedding_rate': 0.05, 'estimated_percentage': 5.0},
            'rs_analysis': {'estimated_embedding_rate': 0.02, 'suspicion_indicator': 0.02, 'estimated_percentage': 2.0}
        }

        items = EvidenceCollector.collect_steganography_evidence(meta_res, visual_res, statistical_res)
        order = {'anomaly': 3, 'suspicious': 2, 'clean': 1, 'info': 0}
        for i in range(len(items) - 1):
            curr_sev = order.get(items[i]['severity'], 0)
            next_sev = order.get(items[i+1]['severity'], 0)
            assert curr_sev >= next_sev
