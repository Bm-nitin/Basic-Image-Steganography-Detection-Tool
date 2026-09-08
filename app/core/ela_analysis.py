import base64
from io import BytesIO
from typing import Dict, Any, Optional
import numpy as np
from PIL import Image


class ELAAnalyzer:
    """
    Implements Error Level Analysis (ELA) for JPEG images.

    Forensic Methodology:
    1. Decodes the input JPEG image into memory.
    2. Recompresses the image at a known, controlled quality level (default: 90).
    3. Computes the absolute pixel-wise difference between the original decoded
       image and the recompressed version.
    4. Evaluates global and block-level error distributions:
       - In uniform JPEG images, error levels are relatively consistent across similar textures.
       - Spliced patches, foreign inserts, or edited regions with different compression histories
         frequently exhibit distinct error rates compared to surrounding native content.
    5. Produces an ELA anomaly indicator and a bounded visual preview.

    Forensic Caveat:
    ELA is a heuristic indicator, NOT proof of manipulation. High error levels naturally
    occur along high-contrast edges, sharp text, fine textures, or in synthetic artwork.
    For non-JPEG formats (PNG, BMP, WebP), ELA is non-applicable and returns available: False.
    """

    RECOMPRESSION_QUALITY = 90
    MAX_HEATMAP_DIMENSION = 512

    @classmethod
    def _generate_heatmap_preview(cls, diff_arr: np.ndarray) -> Dict[str, Any]:
        """
        Generates a bounded base64-encoded visual representation of ELA differences.
        Failsafe: errors do not interrupt forensic analysis.
        """
        try:
            # Average across RGB channels to compute scalar difference
            if len(diff_arr.shape) == 3:
                scalar_diff = np.mean(diff_arr, axis=2)
            else:
                scalar_diff = diff_arr

            # Amplify differences for human visual inspection (scale factor: 10x)
            amplified = np.clip(scalar_diff * 10.0, 0.0, 255.0).astype(np.uint8)

            img = Image.fromarray(amplified, mode='L')

            # Bound dimensions to prevent large payloads
            w, h = img.size
            if max(w, h) > cls.MAX_HEATMAP_DIMENSION:
                img.thumbnail((cls.MAX_HEATMAP_DIMENSION, cls.MAX_HEATMAP_DIMENSION), Image.Resampling.LANCZOS)
                w, h = img.size

            buf = BytesIO()
            img.save(buf, format='PNG')
            b64_str = base64.b64encode(buf.getvalue()).decode('ascii')

            return {
                'heatmap_available': True,
                'heatmap_base64': f"data:image/png;base64,{b64_str}",
                'width': w,
                'height': h
            }
        except Exception:
            return {
                'heatmap_available': False,
                'heatmap_base64': None,
                'width': 0,
                'height': 0
            }

    @classmethod
    def analyze(cls, file_bytes: bytes, image_format: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes Error Level Analysis on JPEG byte stream.
        Returns unavailable state for non-JPEG formats.
        """
        # Format check
        if image_format and image_format.upper() != 'JPEG':
            return {
                'available': False,
                'reason': 'not_jpeg',
                'quality': cls.RECOMPRESSION_QUALITY,
                'mean_error': 0.0,
                'max_error': 0.0,
                'error_std': 0.0,
                'high_error_fraction': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'heatmap': {
                    'heatmap_available': False,
                    'heatmap_base64': None,
                    'width': 0,
                    'height': 0
                },
                'details': 'Error Level Analysis is specifically formulated for JPEG compression characteristics.'
            }

        if not file_bytes or len(file_bytes) < 4 or not file_bytes.startswith(b'\xFF\xD8'):
            return {
                'available': False,
                'reason': 'not_jpeg',
                'quality': cls.RECOMPRESSION_QUALITY,
                'mean_error': 0.0,
                'max_error': 0.0,
                'error_std': 0.0,
                'high_error_fraction': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'heatmap': {
                    'heatmap_available': False,
                    'heatmap_base64': None,
                    'width': 0,
                    'height': 0
                },
                'details': 'Missing or invalid JPEG stream header; ELA unavailable.'
            }

        try:
            # 1. Decode original JPEG
            orig_pil = Image.open(BytesIO(file_bytes)).convert('RGB')
            orig_arr = np.array(orig_pil, dtype=np.float32)

            # 2. Recompress at controlled quality in-memory
            buf = BytesIO()
            orig_pil.save(buf, format='JPEG', quality=cls.RECOMPRESSION_QUALITY)
            recomp_bytes = buf.getvalue()

            # 3. Decode recompressed version
            recomp_pil = Image.open(BytesIO(recomp_bytes)).convert('RGB')
            recomp_arr = np.array(recomp_pil, dtype=np.float32)

            # 4. Compute pixel difference
            diff = np.abs(orig_arr - recomp_arr)
            mean_err = float(np.mean(diff))
            max_err = float(np.max(diff))
            std_err = float(np.std(diff))

            # Fraction of pixels with elevated error (> 15.0 on 0-255 scale)
            high_error_fraction = float(np.mean(diff > 15.0))

            # 5. Block-based error inconsistency evaluation
            # Divide into 16x16 blocks to evaluate spatial error variance
            h, w = diff.shape[:2]
            block_size = 16
            h_blocks = h // block_size
            w_blocks = w // block_size

            if h_blocks >= 2 and w_blocks >= 2:
                trimmed = diff[:h_blocks * block_size, :w_blocks * block_size]
                blocks = trimmed.reshape(h_blocks, block_size, w_blocks, block_size, 3)
                block_means = blocks.mean(axis=(1, 3, 4))
                block_mean_std = float(np.std(block_means))
                block_mean_avg = float(np.mean(block_means))
            else:
                block_mean_std = 0.0
                block_mean_avg = mean_err

            # Compute bounded anomaly indicator [0.0, 1.0]
            # Baseline: clean JPEGs have low mean error, few high-error pixels, and low block spread
            raw_indicator = (
                (high_error_fraction * 3.5) +
                (min(1.0, mean_err / 20.0) * 0.35) +
                (min(1.0, block_mean_std / 8.0) * 0.30)
            )
            anomaly_ind = float(max(0.0, min(1.0, raw_indicator)))
            is_suspicious = bool(anomaly_ind > 0.45 or high_error_fraction > 0.12)

            # Generate preview
            heatmap_data = cls._generate_heatmap_preview(diff)

            details_msg = (
                f"ELA at Q{cls.RECOMPRESSION_QUALITY}: mean error {mean_err:.2f}, "
                f"high-error fraction {high_error_fraction:.1%}, "
                f"block variance std {block_mean_std:.2f}."
            )

            return {
                'available': True,
                'quality': cls.RECOMPRESSION_QUALITY,
                'mean_error': round(mean_err, 3),
                'max_error': round(max_err, 3),
                'error_std': round(std_err, 3),
                'high_error_fraction': round(high_error_fraction, 4),
                'anomaly_indicator': round(anomaly_ind, 4),
                'is_suspicious': is_suspicious,
                'heatmap': heatmap_data,
                'details': details_msg
            }

        except Exception as e:
            return {
                'available': False,
                'reason': 'processing_error',
                'quality': cls.RECOMPRESSION_QUALITY,
                'mean_error': 0.0,
                'max_error': 0.0,
                'error_std': 0.0,
                'high_error_fraction': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'heatmap': {
                    'heatmap_available': False,
                    'heatmap_base64': None,
                    'width': 0,
                    'height': 0
                },
                'details': f"Error Level Analysis failed gracefully: {str(e)}"
            }
