from typing import Dict, Any, Union, List
import numpy as np
from PIL import Image


class LocalVarianceAnalyzer:
    """
    Analyzes spatial texture variance consistency across localized image windows.

    Forensic Methodology:
    1. Converts image to 2D grayscale float32 luminance.
    2. Partitions the image into bounded spatial blocks (default: 32x32, or 16x16 for small images).
    3. Computes the statistical variance within each localized window.
    4. Evaluates global and local distribution of variance (mean, std, median, IQR).
    5. Identifies outlier regions exhibiting anomalous texture energy compared to the carrier baseline.
       - Spliced content from cameras with different sensor noise or MTF characteristics,
         or heavily smoothed/blurred retouched regions, frequently present discordant local variance.
    6. Produces a bounded anomaly indicator and reports top anomalous regions.

    Forensic Caveat:
    Variance inconsistency is a heuristic indicator, NOT proof of manipulation.
    Natural scenes inherently exhibit diverse texture energies (e.g., flat skies vs. intricate foliage).
    """

    DEFAULT_BLOCK_SIZE = 32
    MAX_REGIONS_REPORTED = 10

    @classmethod
    def analyze(cls, image_input: Union[Image.Image, np.ndarray]) -> Dict[str, Any]:
        """
        Computes localized texture variance and flags statistical outlier regions.
        Accepts PIL Image or NumPy array.
        """
        # 1. Normalize input to 2D grayscale float32 array
        if isinstance(image_input, Image.Image):
            gray_pil = image_input.convert('L')
            gray_arr = np.array(gray_pil, dtype=np.float32)
        elif isinstance(image_input, np.ndarray):
            if len(image_input.shape) == 2:
                gray_arr = image_input.astype(np.float32)
            elif len(image_input.shape) == 3 and image_input.shape[2] >= 3:
                gray_arr = (0.299 * image_input[:, :, 0] +
                            0.587 * image_input[:, :, 1] +
                            0.114 * image_input[:, :, 2]).astype(np.float32)
            else:
                gray_arr = image_input[:, :, 0].astype(np.float32)
        else:
            return {
                'available': False,
                'reason': 'invalid_input_type',
                'global_variance': 0.0,
                'mean_local_variance': 0.0,
                'variance_std': 0.0,
                'outlier_region_fraction': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'regions': [],
                'details': 'Invalid image input format for local variance analysis.'
            }

        h, w = gray_arr.shape
        if h < 16 or w < 16:
            return {
                'available': False,
                'reason': 'insufficient_dimensions',
                'global_variance': 0.0,
                'mean_local_variance': 0.0,
                'variance_std': 0.0,
                'outlier_region_fraction': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'regions': [],
                'details': 'Image dimensions too small for localized variance analysis.'
            }

        global_var = float(np.var(gray_arr))
        if global_var < 1e-4:
            return {
                'available': True,
                'global_variance': 0.0,
                'mean_local_variance': 0.0,
                'variance_std': 0.0,
                'outlier_region_fraction': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'regions': [],
                'details': 'Completely uniform image; zero texture variance observed.'
            }

        # Bound compute for large images by adaptive downsampling
        scale_factor = 1
        if max(h, w) > 1200:
            scale_factor = max(1, int(max(h, w) / 800))
            gray_arr = gray_arr[::scale_factor, ::scale_factor]
            h, w = gray_arr.shape

        # Select block size based on dimensions
        block_size = cls.DEFAULT_BLOCK_SIZE
        if h < 64 or w < 64:
            block_size = 16

        h_steps = h // block_size
        w_steps = w // block_size

        block_vars: List[float] = []
        block_info: List[Dict[str, Any]] = []

        for r_idx in range(h_steps):
            y = r_idx * block_size
            for c_idx in range(w_steps):
                x = c_idx * block_size
                block = gray_arr[y:y + block_size, x:x + block_size]
                b_var = float(np.var(block))
                block_vars.append(b_var)
                block_info.append({
                    'x': int(x * scale_factor),
                    'y': int(y * scale_factor),
                    'width': int(block_size * scale_factor),
                    'height': int(block_size * scale_factor),
                    'variance': b_var
                })

        total_blocks = len(block_vars)
        if total_blocks == 0:
            return {
                'available': False,
                'reason': 'no_valid_blocks',
                'global_variance': round(global_var, 3),
                'mean_local_variance': 0.0,
                'variance_std': 0.0,
                'outlier_region_fraction': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'regions': [],
                'details': 'Could not partition image into valid variance analysis blocks.'
            }

        v_arr = np.array(block_vars, dtype=np.float32)
        mean_local = float(np.mean(v_arr))
        std_local = float(np.std(v_arr))
        median_local = float(np.median(v_arr))
        q25 = float(np.percentile(v_arr, 25))
        q75 = float(np.percentile(v_arr, 75))
        iqr = max(float(q75 - q25), 10.0)

        # Tukey fence threshold for upper outlier variance
        upper_bound = q75 + 2.0 * iqr

        outlier_regions: List[Dict[str, Any]] = []
        for blk in block_info:
            b_val = blk['variance']
            if b_val > upper_bound:
                dev = (b_val - upper_bound) / iqr
                indicator_val = float(min(1.0, dev / 3.0))
                outlier_regions.append({
                    'x': blk['x'],
                    'y': blk['y'],
                    'width': blk['width'],
                    'height': blk['height'],
                    'variance': round(b_val, 2),
                    'indicator': round(indicator_val, 2)
                })

        outlier_regions.sort(key=lambda r: r['indicator'], reverse=True)
        reported_regions = outlier_regions[:cls.MAX_REGIONS_REPORTED]

        outlier_fraction = float(len(outlier_regions) / total_blocks)

        # Compute bounded anomaly indicator [0.0, 1.0]
        # In skewed distributions like image texture variance, 5-8% upper-tail blocks are natural.
        # Anomaly indicator is triggered when outlier fraction significantly exceeds normal baseline.
        cv = std_local / (mean_local + 1e-4)
        raw_indicator = max(0.0, (outlier_fraction - 0.05) * 2.5) + min(1.0, cv / 5.0) * 0.15
        anomaly_indicator = float(max(0.0, min(1.0, raw_indicator)))
        is_suspicious = bool(anomaly_indicator > 0.45 or outlier_fraction > 0.18)

        details_msg = (
            f"Local variance evaluation: global variance {global_var:.1f}, "
            f"mean local variance {mean_local:.1f}, std {std_local:.1f}, "
            f"outliers {len(outlier_regions)}/{total_blocks} ({outlier_fraction:.1%})."
        )

        return {
            'available': True,
            'global_variance': round(global_var, 3),
            'mean_local_variance': round(mean_local, 3),
            'variance_std': round(std_local, 3),
            'outlier_region_fraction': round(outlier_fraction, 4),
            'anomaly_indicator': round(anomaly_indicator, 4),
            'is_suspicious': is_suspicious,
            'regions': reported_regions,
            'details': details_msg
        }
