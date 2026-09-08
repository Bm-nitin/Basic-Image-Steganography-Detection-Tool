from typing import Dict, Any, Union
import numpy as np
from PIL import Image


class RSAnalyzer:
    """
    Implements Regular-Singular (RS) Steganalysis for spatial LSB steganography detection,
    introduced by Fridrich, Goljan, and Du (2001).

    Methodology:
    1. Partitions pixel rows into disjoint horizontal groups G of size n=4:
       G = (x_1, x_2, x_3, x_4)
    2. Discrimination function f(G) measures local group smoothness:
       f(G) = sum_{i=1}^{n-1} |x_{i+1} - x_i|
    3. Invertible flipping operations:
       F_1(x)  = x ^ 1  (Standard LSB toggle)
       F_{-1}(x) = x - 1 if x is even else x + 1 (with [0, 255] clipping)
       F_0(x)  = x      (Identity)
    4. Dual masks:
       M  = [0, 1, 1, 0]
       -M = [0, -1, -1, 0]
    5. Group classification:
       Regular (R):   f(F(G)) > f(G)
       Singular (S):  f(F(G)) < f(G)
       Unusable (U):  f(F(G)) == f(G)
    6. In clean natural images:
       R_M ~= R_{-M} and S_M ~= S_{-M} with R_M > S_M.
       Under LSB steganography, R_M and S_M equalize while R_{-M} and S_{-M} diverge.
    7. Solves the Fridrich quadratic equation to estimate the hidden embedding rate p in [0.0, 1.0].
    """

    GROUP_SIZE = 4
    MASK_POS = np.array([0, 1, 1, 0], dtype=np.int32)
    MASK_NEG = np.array([0, -1, -1, 0], dtype=np.int32)

    @staticmethod
    def _flip_neg1(arr: np.ndarray) -> np.ndarray:
        """Applies F_{-1} flipping operation with boundary safety on uint8 range."""
        out = arr.astype(np.int32).copy()
        even_mask = (out % 2 == 0)
        odd_mask = ~even_mask
        out[even_mask] -= 1
        out[odd_mask] += 1
        return np.clip(out, 0, 255).astype(np.uint8)

    @staticmethod
    def _discrimination(groups: np.ndarray) -> np.ndarray:
        """Computes smoothness variation f(G) for each row group."""
        return np.sum(np.abs(np.diff(groups.astype(np.int32), axis=1)), axis=1)

    @classmethod
    def _apply_mask(cls, groups: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Applies mask flipping operations to group pixels."""
        out = groups.copy()
        for idx, m in enumerate(mask):
            if m == 1:
                out[:, idx] = out[:, idx] ^ 1
            elif m == -1:
                out[:, idx] = cls._flip_neg1(out[:, idx])
        return out

    @classmethod
    def _solve_embedding_rate(cls, d0: float, d1: float, d_neg0: float, d_neg1: float) -> float:
        """
        Solves the Fridrich RS quadratic equation:
        2(d_1 + d_0) z^2 + (d_{-0} - d_{-1} - d_1 - 3d_0) z + (d_0 - d_{-0}) = 0
        and converts root z to embedding rate p = z / (z - 0.5).
        """
        a = 2.0 * (d1 + d0)
        b = d_neg0 - d_neg1 - d1 - 3.0 * d0
        c = d0 - d_neg0

        if abs(c) < 1e-7:
            return 0.0

        if abs(a) < 1e-9:
            if abs(b) > 1e-9:
                z = -c / b
            else:
                return 0.0
        else:
            discriminant = b * b - 4.0 * a * c
            if discriminant < 0:
                z = -b / (2.0 * a)
            else:
                sqrt_d = np.sqrt(discriminant)
                z1 = (-b + sqrt_d) / (2.0 * a)
                z2 = (-b - sqrt_d) / (2.0 * a)
                z = z1 if abs(z1) <= abs(z2) else z2

        denom = z - 0.5
        if abs(denom) < 1e-9:
            p = 0.0
        else:
            p = z / denom

        if np.isnan(p) or np.isinf(p) or p < 0.0:
            return 0.0
        return float(min(1.0, p))

    @classmethod
    def _analyze_channel(cls, channel_2d: np.ndarray) -> Dict[str, Any]:
        """Analyzes a single 2D channel array using RS steganalysis."""
        h, w = channel_2d.shape
        w_trimmed = (w // cls.GROUP_SIZE) * cls.GROUP_SIZE

        if h < 4 or w_trimmed < cls.GROUP_SIZE:
            return {
                'available': False,
                'reason': 'insufficient_dimensions',
                'group_size': cls.GROUP_SIZE,
                'group_count': 0,
                'regular': 0.0,
                'singular': 0.0,
                'negative_regular': 0.0,
                'negative_singular': 0.0,
                'estimated_embedding_rate': 0.0,
                'suspicion_indicator': 0.0,
                'is_suspicious': False
            }

        grid = channel_2d[:, :w_trimmed]
        groups = grid.reshape(-1, cls.GROUP_SIZE)
        total_groups = groups.shape[0]

        if total_groups < 16:
            return {
                'available': False,
                'reason': 'insufficient_groups',
                'group_size': cls.GROUP_SIZE,
                'group_count': int(total_groups),
                'regular': 0.0,
                'singular': 0.0,
                'negative_regular': 0.0,
                'negative_singular': 0.0,
                'estimated_embedding_rate': 0.0,
                'suspicion_indicator': 0.0,
                'is_suspicious': False
            }

        # Original state: G
        f_orig = cls._discrimination(groups)

        # Mask M applied to G
        g_m = cls._apply_mask(groups, cls.MASK_POS)
        f_m = cls._discrimination(g_m)

        # Mask -M applied to G
        g_neg_m = cls._apply_mask(groups, cls.MASK_NEG)
        f_neg_m = cls._discrimination(g_neg_m)

        r_m = float(np.sum(f_m > f_orig)) / total_groups
        s_m = float(np.sum(f_m < f_orig)) / total_groups
        r_neg_m = float(np.sum(f_neg_m > f_orig)) / total_groups
        s_neg_m = float(np.sum(f_neg_m < f_orig)) / total_groups

        # Inverted state: G' = G ^ 1
        groups_inv = groups ^ 1
        f_orig_inv = cls._discrimination(groups_inv)

        g_m_inv = cls._apply_mask(groups_inv, cls.MASK_POS)
        f_m_inv = cls._discrimination(g_m_inv)

        g_neg_m_inv = cls._apply_mask(groups_inv, cls.MASK_NEG)
        f_neg_m_inv = cls._discrimination(g_neg_m_inv)

        r_m_inv = float(np.sum(f_m_inv > f_orig_inv)) / total_groups
        s_m_inv = float(np.sum(f_m_inv < f_orig_inv)) / total_groups
        r_neg_m_inv = float(np.sum(f_neg_m_inv > f_orig_inv)) / total_groups
        s_neg_m_inv = float(np.sum(f_neg_m_inv < f_orig_inv)) / total_groups

        d0 = r_m - s_m
        d1 = r_m_inv - s_m_inv
        d_neg0 = r_neg_m - s_neg_m
        d_neg1 = r_neg_m_inv - s_neg_m_inv

        est_rate = cls._solve_embedding_rate(d0, d1, d_neg0, d_neg1)

        # Asymmetry metric between regular and singular groups
        sym_diff = abs(r_m - r_neg_m) + abs(s_m - s_neg_m)
        indicator = float(max(est_rate, min(1.0, sym_diff * 4.0)))

        is_suspicious = bool(est_rate > 0.35 or indicator > 0.50)

        return {
            'available': True,
            'group_size': cls.GROUP_SIZE,
            'group_count': int(total_groups),
            'regular': round(r_m, 5),
            'singular': round(s_m, 5),
            'negative_regular': round(r_neg_m, 5),
            'negative_singular': round(s_neg_m, 5),
            'discrimination_regular': round(d0, 5),
            'discrimination_singular': round(d_neg0, 5),
            'estimated_embedding_rate': round(est_rate, 4),
            'suspicion_indicator': round(indicator, 4),
            'is_suspicious': is_suspicious
        }

    @classmethod
    def analyze(cls, image_input: Union[Image.Image, np.ndarray]) -> Dict[str, Any]:
        """
        Executes RS steganalysis across image planes.
        Accepts PIL Image or NumPy array.
        """
        if isinstance(image_input, Image.Image):
            rgb_img = image_input.convert('RGB')
            img_np = np.array(rgb_img, dtype=np.uint8)
            gray_np = np.array(rgb_img.convert('L'), dtype=np.uint8)
        elif isinstance(image_input, np.ndarray):
            img_np = image_input
            if len(img_np.shape) == 2:
                gray_np = img_np
            elif len(img_np.shape) == 3 and img_np.shape[2] >= 3:
                gray_np = (0.299 * img_np[:, :, 0] + 0.587 * img_np[:, :, 1] + 0.114 * img_np[:, :, 2]).astype(np.uint8)
            else:
                gray_np = img_np[:, :, 0]
        else:
            return {
                'available': False,
                'reason': 'invalid_input_type',
                'estimated_embedding_rate': 0.0,
                'suspicion_indicator': 0.0,
                'is_suspicious': False
            }

        # Analyze grayscale/luminance
        gray_res = cls._analyze_channel(gray_np)
        if not gray_res['available']:
            return gray_res

        # If color image, also inspect color planes
        channels_res = {}
        max_rate = gray_res['estimated_embedding_rate']
        max_indicator = gray_res['suspicion_indicator']

        if len(img_np.shape) == 3 and img_np.shape[2] >= 3:
            for ch_idx, ch_name in enumerate(['red', 'green', 'blue']):
                ch_out = cls._analyze_channel(img_np[:, :, ch_idx])
                channels_res[ch_name] = ch_out
                if ch_out['available']:
                    if ch_out['estimated_embedding_rate'] > max_rate:
                        max_rate = ch_out['estimated_embedding_rate']
                    if ch_out['suspicion_indicator'] > max_indicator:
                        max_indicator = ch_out['suspicion_indicator']

        gray_res['channel_breakdown'] = channels_res
        gray_res['estimated_embedding_rate'] = round(float(max_rate), 4)
        gray_res['suspicion_indicator'] = round(float(max_indicator), 4)
        gray_res['is_suspicious'] = bool(max_rate > 0.35 or max_indicator > 0.50)
        gray_res['estimated_percentage'] = round(float(max_rate * 100.0), 2)
        gray_res['details'] = (
            f"RS Steganalysis estimates {max_rate * 100:.1f}% spatial LSB embedding capacity "
            f"(Regular={gray_res['regular']:.3f}, Singular={gray_res['singular']:.3f}, "
            f"R_-M={gray_res['negative_regular']:.3f}, S_-M={gray_res['negative_singular']:.3f})."
        )
        return gray_res
