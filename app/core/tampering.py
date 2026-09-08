from typing import Dict, Any, Optional, List
from PIL import Image
from app.core.ela_analysis import ELAAnalyzer
from app.core.noise_analysis import NoiseAnalyzer
from app.core.local_variance_analysis import LocalVarianceAnalyzer
from app.core.edge_analysis import EdgeAnalyzer
from app.core.copy_move_analysis import CopyMoveAnalyzer


class TamperingAnalyzer:
    """
    Orchestrates multi-layer image tampering and manipulation forensics.

    Forensic Scope:
    Coordinates explainable heuristic detectors to identify localized anomalies:
    1. Error Level Analysis (ELA) - JPEG compression disparity
    2. Local Residual Noise Analysis - sensor / smoothing noise inconsistency
    3. Local Variance Analysis - spatial texture energy disparities
    4. Edge Discontinuity Analysis - high-frequency boundary steps & gradients
    5. Copy-Move Analysis - clustered block duplicate matching

    Forensic Caveat:
    Detectors provide explainable forensic indicators of anomaly, NOT legal or scientific
    proof that an image was forged or edited. Camera settings, lighting, depth-of-field,
    natural symmetries, and legitimate post-processing can produce anomalies.
    """

    DEFAULT_WEIGHTS_JPEG = {
        'ela': 0.30,
        'noise': 0.25,
        'local_variance': 0.15,
        'edge': 0.15,
        'copy_move': 0.15
    }

    DEFAULT_WEIGHTS_NON_JPEG = {
        'noise': 0.35,
        'local_variance': 0.25,
        'edge': 0.20,
        'copy_move': 0.20
    }

    MAX_SUSPICIOUS_REGIONS = 15

    @classmethod
    def analyze(
        cls,
        pil_img: Image.Image,
        file_bytes: Optional[bytes] = None,
        image_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes complete tampering forensic analysis on an image.
        Returns detailed per-detector results, aggregated indicators, and suspicious regions.
        """
        # 1. Execute individual detectors with failsafe isolation
        try:
            ela_res = ELAAnalyzer.analyze(file_bytes or b'', image_format=image_format)
        except Exception as e:
            ela_res = {'available': False, 'reason': f"error: {str(e)}", 'anomaly_indicator': 0.0, 'is_suspicious': False}

        try:
            noise_res = NoiseAnalyzer.analyze(pil_img)
        except Exception as e:
            noise_res = {'available': False, 'reason': f"error: {str(e)}", 'anomaly_indicator': 0.0, 'is_suspicious': False, 'regions': []}

        try:
            var_res = LocalVarianceAnalyzer.analyze(pil_img)
        except Exception as e:
            var_res = {'available': False, 'reason': f"error: {str(e)}", 'anomaly_indicator': 0.0, 'is_suspicious': False, 'regions': []}

        try:
            edge_res = EdgeAnalyzer.analyze(pil_img)
        except Exception as e:
            edge_res = {'available': False, 'reason': f"error: {str(e)}", 'anomaly_indicator': 0.0, 'is_suspicious': False, 'regions': []}

        try:
            cm_res = CopyMoveAnalyzer.analyze(pil_img)
        except Exception as e:
            cm_res = {'available': False, 'reason': f"error: {str(e)}", 'anomaly_indicator': 0.0, 'is_suspicious': False, 'matches': []}

        # 2. Select appropriate weighting based on availability
        has_ela = ela_res.get('available', False)
        weights = cls.DEFAULT_WEIGHTS_JPEG if has_ela else cls.DEFAULT_WEIGHTS_NON_JPEG

        weighted_sum = 0.0
        total_weight = 0.0
        max_single_indicator = 0.0
        flagged_detectors: List[str] = []

        detector_map = {
            'ela': ela_res,
            'noise': noise_res,
            'local_variance': var_res,
            'edge': edge_res,
            'copy_move': cm_res
        }

        for det_name, weight in weights.items():
            res = detector_map.get(det_name, {})
            if res.get('available', False):
                ind = float(res.get('anomaly_indicator', 0.0))
                weighted_sum += ind * weight
                total_weight += weight
                max_single_indicator = max(max_single_indicator, ind)
                if res.get('is_suspicious', False):
                    flagged_detectors.append(det_name)

        if total_weight > 0.0:
            base_indicator = weighted_sum / total_weight
        else:
            base_indicator = 0.0

        # Max-pooling boost: if a single detector observes strong localized manipulation
        # (e.g., clustered copy-move or severe ELA disparity), the score retains that anomaly
        if max_single_indicator >= 0.70:
            combined_indicator = max(base_indicator, max_single_indicator * 0.85)
        elif max_single_indicator >= 0.50:
            combined_indicator = max(base_indicator, max_single_indicator * 0.70)
        else:
            combined_indicator = base_indicator

        combined_indicator = float(max(0.0, min(1.0, combined_indicator)))
        combined_score = round(combined_indicator * 100.0, 1)
        is_suspicious = bool(combined_indicator >= 0.40 or len(flagged_detectors) >= 2 or max_single_indicator >= 0.75)

        # 3. Aggregate suspicious region coordinates for visual / forensic review
        suspicious_regions: List[Dict[str, Any]] = []

        # Noise outlier regions
        for r in noise_res.get('regions', []):
            suspicious_regions.append({
                'x': r.get('x', 0),
                'y': r.get('y', 0),
                'width': r.get('width', 0),
                'height': r.get('height', 0),
                'source': 'noise_anomaly',
                'indicator': r.get('indicator', 0.0)
            })

        # Variance outlier regions
        for r in var_res.get('regions', []):
            suspicious_regions.append({
                'x': r.get('x', 0),
                'y': r.get('y', 0),
                'width': r.get('width', 0),
                'height': r.get('height', 0),
                'source': 'variance_anomaly',
                'indicator': r.get('indicator', 0.0)
            })

        # Edge discontinuity regions
        for r in edge_res.get('regions', []):
            suspicious_regions.append({
                'x': r.get('x', 0),
                'y': r.get('y', 0),
                'width': r.get('width', 0),
                'height': r.get('height', 0),
                'source': 'edge_discontinuity',
                'indicator': r.get('indicator', 0.0)
            })

        # Copy-move duplicate regions
        for m in cm_res.get('matches', []):
            tgt = m.get('target', {})
            suspicious_regions.append({
                'x': tgt.get('x', 0),
                'y': tgt.get('y', 0),
                'width': tgt.get('width', 0),
                'height': tgt.get('height', 0),
                'source': 'duplicate_match',
                'indicator': m.get('similarity', 0.0)
            })

        # Sort by indicator and truncate to bound payload
        suspicious_regions.sort(key=lambda item: item.get('indicator', 0.0), reverse=True)
        bounded_regions = suspicious_regions[:cls.MAX_SUSPICIOUS_REGIONS]

        # 4. Formulate explainable details message
        if is_suspicious:
            details_str = (
                f"Localized tampering anomalies observed across {len(flagged_detectors)} detector(s): "
                f"{', '.join(flagged_detectors) if flagged_detectors else 'elevated indicators'}. "
                f"Combined manipulation indicator: {combined_indicator:.3f} ({combined_score}/100)."
            )
        else:
            details_str = (
                f"No localized tampering patterns detected across evaluated forensic layers. "
                f"Combined manipulation indicator: {combined_indicator:.3f} ({combined_score}/100)."
            )

        return {
            'available': True,
            'combined_indicator': round(combined_indicator, 4),
            'combined_score': combined_score,
            'is_suspicious': is_suspicious,
            'flagged_detectors': flagged_detectors,
            'suspicious_regions': bounded_regions,
            'detectors': {
                'ela': ela_res,
                'noise': noise_res,
                'local_variance': var_res,
                'edge': edge_res,
                'copy_move': cm_res
            },
            'details': details_str
        }
