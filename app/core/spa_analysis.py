from typing import Dict, Any, Union, Optional
import numpy as np
from PIL import Image


class SPAnalyzer:
    """
    Implements Sample Pair Analysis (SPA) for LSB steganography detection,
    introduced by Sorina Dumitrescu, Xiaolin Wu, and Zhe Wang (2003).

    Methodology:
    1. Scans adjacent horizontal and vertical pixel pairs (u, v).
    2. Partitions pairs into trace multisets:
       - C_0: Pairs in the same Pair of Values (PoV): u // 2 == v // 2
         - X: Pairs with different LSBs (u % 2 != v % 2)
         - Y: Pairs with identical LSBs (u % 2 == v % 2, meaning u == v)
       - C_1: Pairs in adjacent PoVs (|v // 2 - u // 2| == 1)
         - W: Pairs with opposite boundary parities
         - V: Pairs with matching boundary parities
    3. Solves the Dumitrescu-Wu-Wang quadratic model:
         0.5 * (W + V) * p^2 + (2X - (X + Y) - (W - V)) * p + (Y - X) = 0
       with fallback to the calibrated PoV parity asymmetry ratio:
         p_asym = 1.0 - |X - Y| / (X + Y).
    4. Handles edge cases (uniform images, tiny images, invalid roots) deterministically.
    """

    MIN_SAMPLES = 64

    @classmethod
    def _extract_pairs(cls, gray_2d: np.ndarray) -> tuple:
        """Extracts horizontal and vertical sample pairs from 2D array."""
        h, w = gray_2d.shape

        # Bound compute for very large images while preserving statistical significance
        work = gray_2d
        if h > 900 or w > 900:
            step_y = max(1, h // 600)
            step_x = max(1, w // 600)
            work = gray_2d[::step_y, ::step_x]

        arr = work.astype(np.int32)
        h_u, h_v = arr[:, :-1].flatten(), arr[:, 1:].flatten()
        v_u, v_v = arr[:-1, :].flatten(), arr[1:, :].flatten()
        u = np.concatenate([h_u, v_u])
        v = np.concatenate([h_v, v_v])
        return u, v

    @classmethod
    def analyze(cls, image_input: Union[Image.Image, np.ndarray]) -> Dict[str, Any]:
        """
        Executes Sample Pair Analysis (SPA).
        Accepts PIL Image or NumPy array.
        """
        if isinstance(image_input, Image.Image):
            gray_img = image_input.convert('L')
            gray_np = np.array(gray_img, dtype=np.uint8)
        elif isinstance(image_input, np.ndarray):
            if len(image_input.shape) == 2:
                gray_np = image_input
            elif len(image_input.shape) == 3 and image_input.shape[2] >= 3:
                gray_np = (0.299 * image_input[:, :, 0] + 0.587 * image_input[:, :, 1] + 0.114 * image_input[:, :, 2]).astype(np.uint8)
            else:
                gray_np = image_input[:, :, 0]
        else:
            return {
                'available': False,
                'reason': 'invalid_input_type',
                'pair_count': 0,
                'same_pairs': 0,
                'different_pairs': 0,
                'estimated_embedding_rate': 0.0,
                'suspicion_indicator': 0.0,
                'is_suspicious': False
            }

        h, w = gray_np.shape
        if h < 4 or w < 4:
            return {
                'available': False,
                'reason': 'insufficient_dimensions',
                'pair_count': 0,
                'same_pairs': 0,
                'different_pairs': 0,
                'estimated_embedding_rate': 0.0,
                'suspicion_indicator': 0.0,
                'is_suspicious': False
            }

        u, v = cls._extract_pairs(gray_np)
        pair_count = len(u)

        if pair_count < cls.MIN_SAMPLES:
            return {
                'available': False,
                'reason': 'insufficient_sample_pairs',
                'pair_count': int(pair_count),
                'same_pairs': 0,
                'different_pairs': 0,
                'estimated_embedding_rate': 0.0,
                'suspicion_indicator': 0.0,
                'is_suspicious': False
            }

        # Check for constant/uniform image
        if np.std(u) == 0 and np.std(v) == 0:
            return {
                'available': True,
                'pair_count': int(pair_count),
                'same_pairs': int(pair_count),
                'different_pairs': 0,
                'estimated_embedding_rate': 0.0,
                'estimated_percentage': 0.0,
                'suspicion_indicator': 0.0,
                'is_suspicious': False,
                'confidence': 'Low',
                'details': 'Image is completely uniform; zero LSB variance detected.'
            }

        u_div = u >> 1
        v_div = v >> 1
        diff_div = v_div - u_div

        # C0 multiset: same PoV
        c0 = (diff_div == 0)
        x_count = float(np.sum(c0 & ((u & 1) != (v & 1))))
        y_count = float(np.sum(c0 & ((u & 1) == (v & 1))))
        sum_c0 = x_count + y_count

        # C1 and C_-1 multisets: adjacent PoVs
        c1 = (diff_div == 1)
        c_neg1 = (diff_div == -1)
        w_count = float(
            np.sum(c1 & ((u & 1) == 1) & ((v & 1) == 0)) +
            np.sum(c_neg1 & ((u & 1) == 0) & ((v & 1) == 1))
        )
        v_count = float(
            np.sum(c1 & ((u & 1) == 0) & ((v & 1) == 1)) +
            np.sum(c_neg1 & ((u & 1) == 1) & ((v & 1) == 0))
        )

        if sum_c0 < 10:
            return {
                'available': True,
                'pair_count': int(pair_count),
                'same_pairs': int(y_count),
                'different_pairs': int(x_count),
                'estimated_embedding_rate': 0.0,
                'estimated_percentage': 0.0,
                'suspicion_indicator': 0.0,
                'is_suspicious': False,
                'confidence': 'Low',
                'details': 'Insufficient same-PoV sample pairs for reliable estimation.'
            }

        # Calibrated parity asymmetry ratio
        diff_ratio = abs(x_count - y_count) / float(sum_c0)
        p_asym = max(0.0, min(1.0, 1.0 - diff_ratio))

        # Dumitrescu-Wu-Wang quadratic equation:
        # a * p^2 + b * p + c = 0
        a = 0.5 * (w_count + v_count)
        b = 2.0 * x_count - sum_c0 - (w_count - v_count)
        c = y_count - x_count

        chosen_p = p_asym
        # Use DWW quadratic root if image is photographic (not dominated by solid graphics)
        if a > 1e-7 and (w_count > 0.15 * y_count or y_count / (x_count + 1.0) < 3.5):
            discriminant = b * b - 4.0 * a * c
            if discriminant >= 0:
                sqrt_disc = np.sqrt(discriminant)
                r1 = (-b + sqrt_disc) / (2.0 * a)
                r2 = (-b - sqrt_disc) / (2.0 * a)
                valid_roots = [r for r in [r1, r2] if 0.0 <= r <= 1.0]
                if valid_roots:
                    chosen_p = min(valid_roots)

        if np.isnan(chosen_p) or np.isinf(chosen_p):
            chosen_p = 0.0

        est_rate = float(max(0.0, min(1.0, chosen_p)))
        suspicion_indicator = est_rate

        is_suspicious = bool(est_rate > 0.35)
        confidence = 'High' if est_rate > 0.60 else ('Medium' if est_rate > 0.30 else 'Low')

        return {
            'available': True,
            'pair_count': int(pair_count),
            'same_pairs': int(y_count),
            'different_pairs': int(x_count),
            'estimated_embedding_rate': round(est_rate, 4),
            'estimated_percentage': round(est_rate * 100.0, 2),
            'suspicion_indicator': round(suspicion_indicator, 4),
            'is_suspicious': is_suspicious,
            'confidence': confidence,
            'details': (
                f"Sample Pair Analysis estimates {est_rate * 100:.1f}% spatial LSB payload "
                f"(same_PoV pairs={int(sum_c0):,}, Y={int(y_count):,}, X={int(x_count):,})."
            )
        }
