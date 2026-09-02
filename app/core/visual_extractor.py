import base64
from io import BytesIO
from typing import Dict, Any, Tuple
import numpy as np
from PIL import Image

class VisualExtractor:
    """
    Extracts and visualizes bit planes (LSB to MSB) across RGB and Grayscale channels
    to identify spatial steganography patterns.
    """

    MAX_DISPLAY_DIMENSION = 800  # Max dimension for rendered visual bit-plane previews

    @classmethod
    def _array_to_base64_png(cls, arr: np.ndarray) -> str:
        """Converts a 2D or 3D uint8 numpy array to a base64 encoded PNG data URI."""
        img = Image.fromarray(arr.astype(np.uint8))
        buf = BytesIO()
        img.save(buf, format='PNG', optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode('ascii')
        return f"data:image/png;base64,{encoded}"

    @classmethod
    def extract_bit_planes(cls, image_pil: Image.Image) -> Dict[str, Any]:
        """
        Extracts bit planes for Grayscale and RGB channels.
        Returns a dictionary of base64 data URIs and visual inspection metrics.
        """
        # Ensure image is in RGB format
        rgb_img = image_pil.convert('RGB')
        
        # Create thumbnail for web preview to avoid gigantic base64 payloads
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

        # Color channels
        r_chan = img_np[:, :, 0]
        g_chan = img_np[:, :, 1]
        b_chan = img_np[:, :, 2]

        r_lsb = ((r_chan & 1) * 255).astype(np.uint8)
        g_lsb = ((g_chan & 1) * 255).astype(np.uint8)
        b_lsb = ((b_chan & 1) * 255).astype(np.uint8)

        bitplanes['red_lsb'] = cls._array_to_base64_png(r_lsb)
        bitplanes['green_lsb'] = cls._array_to_base64_png(g_lsb)
        bitplanes['blue_lsb'] = cls._array_to_base64_png(b_lsb)

        # Combined RGB LSB image: each channel replaced by its LSB * 255
        rgb_lsb = np.stack([r_lsb, g_lsb, b_lsb], axis=2)
        bitplanes['rgb_lsb'] = cls._array_to_base64_png(rgb_lsb)

        # Visual noise uniformity metric:
        # In natural LSB planes, standard deviation and local spatial gradients reflect subtle image geometry.
        # In stego images, LSB is uniformly random noise.
        # We calculate the mean and standard deviation of the LSB planes.
        lsb_stats = {
            'gray_lsb_mean': float(np.mean(gray_lsb == 255)),
            'red_lsb_mean': float(np.mean(r_lsb == 255)),
            'green_lsb_mean': float(np.mean(g_lsb == 255)),
            'blue_lsb_mean': float(np.mean(b_lsb == 255)),
        }

        # If a channel is embedded with randomized data, the 1-bit density tends very close to 0.50 (50% 1s, 50% 0s)
        # We calculate the delta from perfectly random 0.50
        density_deltas = [abs(val - 0.5) for val in lsb_stats.values()]
        min_delta = min(density_deltas)
        visual_suspicious = bool(min_delta < 0.02)  # Exceptionally balanced 50/50 distribution in LSB

        return {
            'previews': bitplanes,
            'stats': lsb_stats,
            'is_visual_suspicious': bool(visual_suspicious),
            'min_balance_delta': float(min_delta)
        }
