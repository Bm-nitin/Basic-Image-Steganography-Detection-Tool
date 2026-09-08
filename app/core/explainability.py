from typing import Dict, Any, List, Optional


class ExplainabilityEngine:
    """
    Transforms quantitative detector outputs and evidence items into structured,
    human-readable, explainable forensic assessments.

    Core Principles:
    1. Transparency: Answers 'Why did this image receive this score?'
    2. Traceability: Every summary and explanation directly traces to actual detector measurements.
    3. Non-conclusive: Never claims proof of steganography, manipulation, or malicious intent.
    4. Independence: Evaluates Steganography and Tampering as distinct, independent dimensions.
    """

    @classmethod
    def generate_steganography_explanation(
        cls,
        evidence_items: List[Dict[str, Any]],
        scoring_res: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Synthesizes explainability data for the steganography assessment.
        """
        score = float(scoring_res.get('suspicion_score', 0.0))
        risk = str(scoring_res.get('risk_level', 'Low')).upper()

        primary: List[Dict[str, Any]] = []
        supporting: List[Dict[str, Any]] = []

        for item in evidence_items:
            if item.get('severity') in ('anomaly', 'suspicious'):
                primary.append(item)
            else:
                supporting.append(item)

        # Build dynamic, traceable explanation summary
        summary_parts = []
        if risk == 'HIGH':
            anom_detectors = [item['detector'] for item in primary if item.get('severity') == 'anomaly']
            if anom_detectors:
                summary_parts.append(
                    f"Strong statistical anomalies observed across {', '.join(anom_detectors[:3])}, "
                    f"indicating elevated characteristics consistent with possible spatial LSB payload embedding."
                )
            else:
                summary_parts.append(
                    "Multiple elevated forensic indicators observed across statistical and visual bit-plane layers."
                )
        elif risk == 'MEDIUM':
            primary_names = [item['detector'] for item in primary[:2]]
            if any('Trailing Data' in name for name in primary_names):
                summary_parts.append(
                    "Suspicious indicators detected primarily driven by appended data past the format EOF marker. "
                    "Spatial LSB planes exhibit moderate or baseline characteristics."
                )
            elif primary_names:
                summary_parts.append(
                    f"Moderate forensic anomalies identified in {', '.join(primary_names)}. "
                    "Results warrant secondary manual inspection."
                )
            else:
                summary_parts.append(
                    "Moderate statistical divergence observed relative to continuous-tone photographic baselines."
                )
        else:
            summary_parts.append(
                "Low suspicion index across all evaluated forensic layers. RS steganalysis, Sample Pair Analysis, "
                "and Shannon entropy conform to clean carrier baselines with standard format termination."
            )

        summary = " ".join(summary_parts)

        # Extract mathematical detector contributions from scoring breakdown
        contributions: List[Dict[str, Any]] = []
        for item in scoring_res.get('detector_breakdown', []):
            if item.get('category') != 'Tampering & Manipulation Forensics':
                contributions.append({
                    'category': item.get('category', ''),
                    'detector': item.get('detector', ''),
                    'status': item.get('status', ''),
                    'points_added': item.get('points_added', 0.0),
                    'details': item.get('details', '')
                })

        return {
            'score': score,
            'risk': risk,
            'summary': summary,
            'primary_evidence': primary,
            'supporting_evidence': supporting,
            'detector_contributions': contributions
        }

    @classmethod
    def generate_tampering_explanation(
        cls,
        evidence_items: List[Dict[str, Any]],
        tampering_res: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Synthesizes explainability data for the tampering and manipulation assessment.
        """
        if not tampering_res or not tampering_res.get('available', False):
            return {
                'score': 0.0,
                'status': 'NOT AVAILABLE',
                'summary': 'Image tampering forensics were not executed or not applicable for this format.',
                'primary_evidence': [],
                'supporting_evidence': [],
                'detector_contributions': []
            }

        score = float(tampering_res.get('combined_score', 0.0))
        is_susp = bool(tampering_res.get('is_suspicious', False))
        status = 'SUSPICIOUS' if is_susp else 'NOT SUSPICIOUS'

        primary: List[Dict[str, Any]] = []
        supporting: List[Dict[str, Any]] = []

        for item in evidence_items:
            if item.get('severity') in ('anomaly', 'suspicious'):
                primary.append(item)
            else:
                supporting.append(item)

        flagged = tampering_res.get('flagged_detectors', [])
        summary_parts = []

        if is_susp:
            if 'copy_move' in flagged:
                summary_parts.append(
                    "Spatially separated duplicate block clusters detected by copy-move analysis, "
                    "consistent with possible localized cloning or stamp manipulation."
                )
            if 'ela' in flagged:
                summary_parts.append(
                    "Elevated Error Level Analysis (ELA) error rate disparities observed across JPEG blocks, "
                    "suggesting differing compression histories."
                )
            if 'noise' in flagged or 'local_variance' in flagged or 'edge' in flagged:
                summary_parts.append(
                    f"Localized inconsistencies observed across high-frequency texture/noise layers ({', '.join(flagged)})."
                )
            if not summary_parts:
                summary_parts.append(
                    f"Localized manipulation anomalies observed with combined indicator {tampering_res.get('combined_indicator', 0.0):.3f}."
                )
        else:
            summary_parts.append(
                "No significant localized tampering detected across evaluated forensic layers. "
                "Residual noise, texture variance, and edge gradients conform to authentic carrier characteristics, "
                "and no coherent duplicate regions were identified by copy-move inspection."
            )

        summary = " ".join(summary_parts)

        # Tampering contributions (always points_added: 0.0)
        contributions: List[Dict[str, Any]] = []
        detectors = tampering_res.get('detectors', {})
        detector_names = {
            'ela': 'Error Level Analysis (ELA)',
            'noise': 'Local Residual Noise Consistency',
            'local_variance': 'Texture Variance Disparity',
            'edge': 'Edge Discontinuity & Gradients',
            'copy_move': 'Copy-Move Duplicate Detection'
        }

        for det_key, det_name in detector_names.items():
            d_res = detectors.get(det_key, {})
            if d_res.get('available', False):
                status_str = 'Anomaly' if d_res.get('is_suspicious') else ('Suspicious' if d_res.get('anomaly_indicator', 0) > 0.35 else 'Clean')
                contributions.append({
                    'category': 'Tampering & Manipulation Forensics',
                    'detector': det_name,
                    'status': status_str,
                    'points_added': 0.0,
                    'details': d_res.get('details', '')
                })

        return {
            'score': score,
            'status': status,
            'summary': summary,
            'primary_evidence': primary,
            'supporting_evidence': supporting,
            'detector_contributions': contributions
        }

    @classmethod
    def generate(
        cls,
        evidence_dict: Dict[str, Any],
        scoring_res: Dict[str, Any],
        tampering_res: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates full explainability assessment for both steganography and tampering.
        """
        stego_ev = evidence_dict.get('steganography', [])
        tamper_ev = evidence_dict.get('tampering', [])

        stego_exp = cls.generate_steganography_explanation(stego_ev, scoring_res)
        tamper_exp = cls.generate_tampering_explanation(tamper_ev, tampering_res)

        return {
            'steganography': stego_exp,
            'tampering': tamper_exp
        }
