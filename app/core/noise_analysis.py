from typing import Dict, Any, Union, List
import numpy as np
from scipy.ndimage import uniform_filter
from PIL import Image


class NoiseAnalyzer:
    """
    Analyzes spatial noise consistency across localized image regions.

    Forensic Methodology:
    1. Converts image to grayscale luminance representation.
    2. Applies a 3x3 spatial smoothing filter to estimate underlying content.
    3. Calculates the high-frequency residual signal:
       residual = original - smoothed
    4. Evaluates local residual noise via Median Absolute Deviation (MAD):
       sigma_mad = median(|residual - median(residual)|) / 0.6745
       MAD is far more robust to sharp step edges than standard deviation,
       suppressing false positives along natural boundaries and vector lines.
    5. Compares local noise levels against global distribution statistics.
       - Spliced patches from different camera sensors, synthetic inserts, or smoothed edits
         frequently exhibit discordant local noise levels compared to the rest of the carrier.
    6. Identifies statistically anomalous outlier regions while suppressing false positives
       in natural flat areas (sky, uniform backgrounds).

    Forensic Caveat:
    Noise inconsistency is a heuristic indicator, NOT proof of manipulation.
    Natural causes include depth of field, focus blur, lens vignetting, complex textures
    (hair, foliage), and local JPEG compression artifacts.
    """

    DEFAULT_BLOCK_SIZE = 32
    MAX_REGIONS_REPORTED = 10

    @classmethod
    def analyze(cls, image_input: Union[Image.Image, np.ndarray]) -> Dict[str, Any]:
        """
        Estimates local noise characteristics and identifies inconsistent regions.
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
                'global_noise_std': 0.0,
                'mean_local_noise': 0.0,
                'noise_std': 0.0,
                'outlier_region_fraction': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'regions': [],
                'details': 'Invalid image input format for noise analysis.'
            }

        h, w = gray_arr.shape
        if h < 16 or w < 16:
            return {
                'available': False,
                'reason': 'insufficient_dimensions',
                'global_noise_std': 0.0,
                'mean_local_noise': 0.0,
                'noise_std': 0.0,
                'outlier_region_fraction': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'regions': [],
                'details': 'Image dimensions too small for localized noise analysis.'
            }

        # Check for constant/uniform image
        if float(np.std(gray_arr)) < 1e-4:
            return {
                'available': True,
                'global_noise_std': 0.0,
                'mean_local_noise': 0.0,
                'noise_std': 0.0,
                'outlier_region_fraction': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'regions': [],
                'details': 'Completely uniform image; zero residual noise variance observed.'
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

        # 2. Extract noise residual via spatial smoothing
        smoothed = uniform_filter(gray_arr, size=3, mode='reflect')
        residual = gray_arr - smoothed

        # Global residual MAD
        global_med = float(np.median(residual))
        global_noise_std = float(np.median(np.abs(residual - global_med)) / 0.6745)

        if global_noise_std < 1e-4:
            return {
                'available': True,
                'global_noise_std': 0.0,
                'mean_local_noise': 0.0,
                'noise_std': 0.0,
                'outlier_region_fraction': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'regions': [],
                'details': 'Negligible residual noise variation across carrier.'
            }

        # 3. Block-wise noise MAD calculation
        block_mads: List[float] = []
        block_info: List[Dict[str, Any]] = []

        h_steps = h // block_size
        w_steps = w // block_size

        for r_idx in range(h_steps):
            y = r_idx * block_size
            for c_idx in range(w_steps):
                x = c_idx * block_size
                block_res = residual[y:y + block_size, x:x + block_size]
                b_med = float(np.median(block_res))
                b_mad = float(np.median(np.abs(block_res - b_med)) / 0.6745)
                block_mads.append(b_mad)
                block_info.append({
                    'x': int(x * scale_factor),
                    'y': int(y * scale_factor),
                    'width': int(block_size * scale_factor),
                    'height': int(block_size * scale_factor),
                    'noise_mad': b_mad
                })

        total_blocks = len(block_mads)
        if total_blocks == 0:
            return {
                'available': False,
                'reason': 'no_valid_blocks',
                'global_noise_std': round(global_noise_std, 3),
                'mean_local_noise': 0.0,
                'noise_std': 0.0,
                'outlier_region_fraction': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'regions': [],
                'details': 'Could not partition image into valid analysis blocks.'
            }

        mads_arr = np.array(block_mads, dtype=np.float32)
        mean_local = float(np.mean(mads_arr))
        std_local = float(np.std(mads_arr))
        median_local = float(np.median(mads_arr))
        q25 = float(np.percentile(mads_arr, 25))
        q75 = float(np.percentile(mads_arr, 75))
        iqr = max(float(q75 - q25), 1.0)

        # 4. Outlier detection using robust interquartile threshold
        upper_bound = median_local + 3.0 * iqr
        outlier_regions: List[Dict[str, Any]] = []
        for blk in block_info:
            b_val = blk['noise_mad']
            if b_val > upper_bound and (b_val - median_local) > 2.5:
                deviation = abs(b_val - median_local) / iqr
                indicator_val = float(min(1.0, deviation / 4.0))
                outlier_regions.append({
                    'x': blk['x'],
                    'y': blk['y'],
                    'width': blk['width'],
                    'height': blk['height'],
                    'noise_std': round(b_val, 2),
                    'indicator': round(indicator_val, 2)
                })

        # Sort outliers by highest deviation / indicator
        outlier_regions.sort(key=lambda r: r['indicator'], reverse=True)
        reported_regions = outlier_regions[:cls.MAX_REGIONS_REPORTED]

        outlier_fraction = float(len(outlier_regions) / total_blocks)

        # Compute bounded anomaly indicator [0.0, 1.0]
        raw_ind = (outlier_fraction * 4.0) + (min(1.0, std_local / 6.0) * 0.30)
        anomaly_indicator = float(max(0.0, min(1.0, raw_ind)))
        is_suspicious = bool(anomaly_indicator > 0.40 or outlier_fraction > 0.08)

        details_msg = (
            f"Local noise MAD evaluation: global residual MAD {global_noise_std:.2f}, "
            f"local block MAD std {std_local:.2f}, "
            f"outlier blocks {len(outlier_regions)}/{total_blocks} ({outlier_fraction:.1%})."
        )

        return {
            'available': True,
            'global_noise_std': round(global_noise_std, 3),
            'mean_local_noise': round(mean_local, 3),
            'noise_std': round(std_local, 3),
            'outlier_region_fraction': round(outlier_fraction, 4),
            'anomaly_indicator': round(anomaly_indicator, 4),
            'is_suspicious': is_suspicious,
            'regions': reported_regions,
            'details': details_msg
        }
