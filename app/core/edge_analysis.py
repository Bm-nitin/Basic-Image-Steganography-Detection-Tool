from typing import Dict, Any, Union, List
import numpy as np
from scipy.ndimage import sobel
from PIL import Image


class EdgeAnalyzer:
    """
    Analyzes high-frequency spatial edge gradients and boundary discontinuities.

    Forensic Methodology:
    1. Converts image to 2D grayscale float32 luminance.
    2. Computes orthogonal directional gradients using SciPy Sobel operators:
       Gx = sobel(image, axis=1)
       Gy = sobel(image, axis=0)
       magnitude = hypot(Gx, Gy)
    3. Evaluates global edge gradient statistics (mean gradient, maximum gradient,
       and edge density thresholded at magnitude > 30.0).
    4. Partitions gradient field into bounded spatial blocks (default: 32x32, or 16x16 for small images).
    5. Flags localized regions with anomalous gradient density or unnatural step discontinuities.
       - Hard cut-and-paste splices without anti-aliasing feathering introduce unnaturally high
         gradient boundaries.
       - Retouched, cloned, or inpainted patches may introduce artificially suppressed edge density.
    6. Produces a bounded anomaly indicator and reports top anomalous edge regions.

    Forensic Caveat:
    Edge characteristics are heuristic indicators, NOT proof of manipulation.
    High edge density naturally occurs in complex textures (foliage, text, fine grids).
    """

    DEFAULT_BLOCK_SIZE = 32
    MAX_REGIONS_REPORTED = 10
    GRADIENT_THRESHOLD = 30.0

    @classmethod
    def analyze(cls, image_input: Union[Image.Image, np.ndarray]) -> Dict[str, Any]:
        """
        Computes spatial gradient magnitude and identifies anomalous edge discontinuities.
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
                'mean_gradient': 0.0,
                'max_gradient': 0.0,
                'edge_density': 0.0,
                'discontinuity_score': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'regions': [],
                'details': 'Invalid image input format for edge analysis.'
            }

        h, w = gray_arr.shape
        if h < 16 or w < 16:
            return {
                'available': False,
                'reason': 'insufficient_dimensions',
                'mean_gradient': 0.0,
                'max_gradient': 0.0,
                'edge_density': 0.0,
                'discontinuity_score': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'regions': [],
                'details': 'Image dimensions too small for localized edge analysis.'
            }

        # Check for constant/uniform image
        if float(np.std(gray_arr)) < 1e-4:
            return {
                'available': True,
                'mean_gradient': 0.0,
                'max_gradient': 0.0,
                'edge_density': 0.0,
                'discontinuity_score': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'regions': [],
                'details': 'Completely uniform image; zero edge gradient observed.'
            }

        # Bound compute for large images by adaptive downsampling
        scale_factor = 1
        if max(h, w) > 1200:
            scale_factor = max(1, int(max(h, w) / 800))
            gray_arr = gray_arr[::scale_factor, ::scale_factor]
            h, w = gray_arr.shape

        # 2. Compute directional gradients via Sobel operators
        gx = sobel(gray_arr, axis=1)
        gy = sobel(gray_arr, axis=0)
        mag = np.hypot(gx, gy)

        mean_g = float(np.mean(mag))
        max_g = float(np.max(mag))
        edge_density = float(np.mean(mag > cls.GRADIENT_THRESHOLD))

        # Select block size based on dimensions
        block_size = cls.DEFAULT_BLOCK_SIZE
        if h < 64 or w < 64:
            block_size = 16

        h_steps = h // block_size
        w_steps = w // block_size

        block_densities: List[float] = []
        block_info: List[Dict[str, Any]] = []

        for r_idx in range(h_steps):
            y = r_idx * block_size
            for c_idx in range(w_steps):
                x = c_idx * block_size
                block_mag = mag[y:y + block_size, x:x + block_size]
                b_density = float(np.mean(block_mag > cls.GRADIENT_THRESHOLD))
                block_densities.append(b_density)
                block_info.append({
                    'x': int(x * scale_factor),
                    'y': int(y * scale_factor),
                    'width': int(block_size * scale_factor),
                    'height': int(block_size * scale_factor),
                    'gradient_density': round(b_density, 3)
                })

        total_blocks = len(block_densities)
        if total_blocks == 0:
            return {
                'available': False,
                'reason': 'no_valid_blocks',
                'mean_gradient': round(mean_g, 2),
                'max_gradient': round(max_g, 2),
                'edge_density': round(edge_density, 4),
                'discontinuity_score': 0.0,
                'anomaly_indicator': 0.0,
                'is_suspicious': False,
                'regions': [],
                'details': 'Could not partition image into valid edge analysis blocks.'
            }

        d_arr = np.array(block_densities, dtype=np.float32)
        std_d = float(np.std(d_arr))
        q25 = float(np.percentile(d_arr, 25))
        q75 = float(np.percentile(d_arr, 75))
        iqr = max(float(q75 - q25), 0.05)

        upper_bound = q75 + 2.0 * iqr

        outlier_regions: List[Dict[str, Any]] = []
        for blk in block_info:
            b_val = blk['gradient_density']
            # Outlier must exceed upper IQR fence and have significant absolute edge density
            if b_val > upper_bound and b_val > 0.40:
                dev = (b_val - upper_bound) / iqr
                indicator_val = float(min(1.0, dev / 3.0))
                outlier_regions.append({
                    'x': blk['x'],
                    'y': blk['y'],
                    'width': blk['width'],
                    'height': blk['height'],
                    'gradient_density': b_val,
                    'indicator': round(indicator_val, 2)
                })

        outlier_regions.sort(key=lambda r: r['indicator'], reverse=True)
        reported_regions = outlier_regions[:cls.MAX_REGIONS_REPORTED]

        outlier_fraction = float(len(outlier_regions) / total_blocks)

        # Compute bounded anomaly indicator [0.0, 1.0]
        raw_indicator = max(0.0, (outlier_fraction - 0.06) * 3.0) + min(1.0, std_d / 0.5) * 0.15
        anomaly_indicator = float(max(0.0, min(1.0, raw_indicator)))
        is_suspicious = bool(anomaly_indicator > 0.45 or outlier_fraction > 0.15)

        details_msg = (
            f"Edge discontinuity evaluation: mean gradient {mean_g:.1f}, "
            f"edge density {edge_density:.1%}, "
            f"discontinuity outliers {len(outlier_regions)}/{total_blocks} ({outlier_fraction:.1%})."
        )

        return {
            'available': True,
            'mean_gradient': round(mean_g, 2),
            'max_gradient': round(max_g, 2),
            'edge_density': round(edge_density, 4),
            'discontinuity_score': round(anomaly_indicator, 4),
            'anomaly_indicator': round(anomaly_indicator, 4),
            'is_suspicious': is_suspicious,
            'regions': reported_regions,
            'details': details_msg
        }
