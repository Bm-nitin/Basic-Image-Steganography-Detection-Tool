import base64
from io import BytesIO
from typing import Dict, Any, List, Tuple
import numpy as np
from PIL import Image

class VisualExtractor:
    """
    Extracts and visualizes bit planes (LSB to MSB) across RGB and Grayscale channels
    to identify spatial steganography patterns.

    Audit Phase G1 notes (correctness/consistency pass, see technical audit):
    - BASE_BALANCE_THRESHOLD is the single authoritative threshold for the LSB
      parity-balance heuristic. scoring.py and evidence.py must defer to the
      `is_visual_suspicious` decision computed here (or, when given only a bare
      `min_balance_delta` value with no other context, fall back to comparing
      against this same constant) rather than re-declaring their own literal.
    - The suspicion decision is now computed on the full-resolution channel
      data, not on the display thumbnail. Resampling (Lanczos) recomputes
      pixel values via interpolation and does not preserve the original LSB
      plane, so computing the balance statistic on a downscaled preview
      silently measured interpolation artifacts rather than the image itself
      for any upload larger than MAX_DISPLAY_DIMENSION.
    - The suspicion decision pools only statistically independent channels.
      `gray` is a deterministic linear combination of R/G/B
      (0.299R + 0.587G + 0.114B) and is therefore not independent evidence;
      it is still computed and reported for display/debugging, but it is
      excluded from the "minimum across channels" suspicion pool. For a
      genuinely grayscale-source image (R == G == B after conversion), the
      pool naturally collapses to a single independent channel (k=1) and the
      threshold is not corrected. For a real color image, the pool is
      {red, green, blue} (k=3) and a Bonferroni-style correction
      (threshold / k) is applied to the flagging decision, because taking the
      minimum delta across k approximately-independent tests and comparing it
      to a single-test threshold systematically inflates the false-positive
      rate relative to testing one channel alone. This is a generic,
      sample-independent correction (not tuned against any specific image)
      and is applied uniformly to any k-channel pool.
    """

    MAX_DISPLAY_DIMENSION = 800  # Max dimension for rendered visual bit-plane previews

    # Single authoritative source for the LSB parity-balance suspicion threshold.
    # scoring.py and evidence.py import this constant rather than hardcoding
    # their own copy, and defer to `is_visual_suspicious` when available.
    BASE_BALANCE_THRESHOLD = 0.005

    @classmethod
    def _array_to_base64_png(cls, arr: np.ndarray) -> str:
        """Converts a 2D or 3D uint8 numpy array to a base64 encoded PNG data URI."""
        img = Image.fromarray(arr.astype(np.uint8))
        buf = BytesIO()
        img.save(buf, format='PNG', optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode('ascii')
        return f"data:image/png;base64,{encoded}"

    @classmethod
    def _resolve_balance_decision(cls, lsb_stats: Dict[str, float], is_effectively_grayscale: bool) -> Dict[str, Any]:
        """
        Determines the LSB parity-balance suspicion decision from per-channel
        1-bit densities, excluding the derived `gray` value from the pool and
        applying a Bonferroni-style correction for the number of independent
        channels actually pooled.
        """
        if is_effectively_grayscale:
            # R, G, B are identical to gray; there is exactly one independent
            # signal, so gray is used directly and no correction is needed.
            pool = {'gray': lsb_stats['gray_lsb_mean']}
        else:
            # gray is a deterministic function of red/green/blue and is
            # excluded from the independent-evidence pool.
            pool = {
                'red': lsb_stats['red_lsb_mean'],
                'green': lsb_stats['green_lsb_mean'],
                'blue': lsb_stats['blue_lsb_mean'],
            }

        deltas = {name: abs(val - 0.5) for name, val in pool.items()}
        min_channel = min(deltas, key=deltas.get)
        min_delta = deltas[min_channel]
        k = len(pool)
        effective_threshold = cls.BASE_BALANCE_THRESHOLD / k

        return {
            'min_balance_delta': float(min_delta),
            'min_balance_channel': min_channel,
            'tested_channels': sorted(pool.keys()),
            'channel_count': int(k),
            'effective_threshold': float(effective_threshold),
            'is_visual_suspicious': bool(min_delta < effective_threshold),
        }

    @classmethod
    def extract_bit_planes(cls, image_pil: Image.Image) -> Dict[str, Any]:
        """
        Extracts bit planes for Grayscale and RGB channels.
        Returns a dictionary of base64 data URIs and visual inspection metrics.
        """
        # Ensure image is in RGB format
        rgb_img = image_pil.convert('RGB')

        # Full-resolution arrays are used for all statistics (LSB density,
        # balance delta, suspicion decision). Statistics must never be
        # computed from a resampled/interpolated copy of the image.
        full_np = np.array(rgb_img, dtype=np.uint8)
        r_chan = full_np[:, :, 0]
        g_chan = full_np[:, :, 1]
        b_chan = full_np[:, :, 2]
        gray_full_np = np.array(rgb_img.convert('L'), dtype=np.uint8)

        is_effectively_grayscale = bool(np.array_equal(r_chan, g_chan) and np.array_equal(g_chan, b_chan))

        lsb_stats = {
            'gray_lsb_mean': float(np.mean((gray_full_np & 1) == 1)),
            'red_lsb_mean': float(np.mean((r_chan & 1) == 1)),
            'green_lsb_mean': float(np.mean((g_chan & 1) == 1)),
            'blue_lsb_mean': float(np.mean((b_chan & 1) == 1)),
        }

        balance = cls._resolve_balance_decision(lsb_stats, is_effectively_grayscale)

        # Create thumbnail for web preview to avoid gigantic base64 payloads.
        # This is used ONLY for the rendered bit-plane preview images below;
        # it must never feed the statistics computed above.
        w, h = rgb_img.size
        preview_img = rgb_img.copy()
        if max(w, h) > cls.MAX_DISPLAY_DIMENSION:
            preview_img.thumbnail((cls.MAX_DISPLAY_DIMENSION, cls.MAX_DISPLAY_DIMENSION), Image.Resampling.LANCZOS)

        img_np = np.array(preview_img, dtype=np.uint8)
        gray_np = np.array(preview_img.convert('L'), dtype=np.uint8)

        # Bit 0 (LSB) and Bit 7 (MSB) extraction:
        # bit_plane_k = ((pixel >> k) & 1) * 255
        bitplanes: Dict[str, str] = {}

        # Grayscale bit planes
        gray_lsb = ((gray_np & 1) * 255).astype(np.uint8)
        gray_msb = (((gray_np >> 7) & 1) * 255).astype(np.uint8)
        gray_bit1 = (((gray_np >> 1) & 1) * 255).astype(np.uint8)
        bitplanes['gray_lsb'] = cls._array_to_base64_png(gray_lsb)
        bitplanes['gray_msb'] = cls._array_to_base64_png(gray_msb)
        bitplanes['gray_bit1'] = cls._array_to_base64_png(gray_bit1)

        # Color channel preview planes (from the display thumbnail only)
        p_r = img_np[:, :, 0]
        p_g = img_np[:, :, 1]
        p_b = img_np[:, :, 2]

        r_lsb = ((p_r & 1) * 255).astype(np.uint8)
        g_lsb = ((p_g & 1) * 255).astype(np.uint8)
        b_lsb = ((p_b & 1) * 255).astype(np.uint8)

        bitplanes['red_lsb'] = cls._array_to_base64_png(r_lsb)
        bitplanes['green_lsb'] = cls._array_to_base64_png(g_lsb)
        bitplanes['blue_lsb'] = cls._array_to_base64_png(b_lsb)

        # Combined RGB LSB image: each channel replaced by its LSB * 255
        rgb_lsb = np.stack([r_lsb, g_lsb, b_lsb], axis=2)
        bitplanes['rgb_lsb'] = cls._array_to_base64_png(rgb_lsb)

        return {
            'previews': bitplanes,
            'stats': lsb_stats,
            'is_visual_suspicious': balance['is_visual_suspicious'],
            'min_balance_delta': balance['min_balance_delta'],
            'min_balance_channel': balance['min_balance_channel'],
            'tested_channels': balance['tested_channels'],
            'channel_count': balance['channel_count'],
            'effective_threshold': balance['effective_threshold'],
            'is_effectively_grayscale': is_effectively_grayscale,
        }
