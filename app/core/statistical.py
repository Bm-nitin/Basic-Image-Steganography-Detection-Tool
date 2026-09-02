import base64
from io import BytesIO
from typing import Dict, Any, List, Tuple
import numpy as np
import scipy.stats as stats
import matplotlib
matplotlib.use('Agg')  # Headless backend: thread-safe, no GUI window, prevents memory leaks
import matplotlib.pyplot as plt
from PIL import Image

class StatisticalAnalyzer:
    """
    Implements mathematical steganalysis:
    - Shannon Entropy (Global, per-channel, and LSB plane)
    - Westfeld's Chi-Square Attack on Pairs of Values (PoVs)
    - Adjacent Pixel Correlation (Horizontal, Vertical, Diagonal)
    - Sample Pair Analysis (SPA) for LSB message length estimation
    - Pixel Intensity Histogram Plotting
    """

    @staticmethod
    def calculate_shannon_entropy(data: np.ndarray) -> float:
        """
        Calculates Shannon entropy in bits for an 8-bit image array.
        H = - sum(p_i * log2(p_i)), range: [0, 8.0]
        """
        flat = data.flatten()
        if len(flat) == 0:
            return 0.0
        counts = np.bincount(flat, minlength=256)
        probs = counts[counts > 0] / len(flat)
        return float(-np.sum(probs * np.log2(probs)))

    @staticmethod
    def calculate_binary_entropy(binary_arr: np.ndarray) -> float:
        """
        Calculates Shannon entropy for a binary (0 or 1) plane.
        Range: [0, 1.0]. Random noise approaches 1.0.
        """
        flat = binary_arr.flatten()
        if len(flat) == 0:
            return 0.0
        p1 = np.mean(flat == 1)
        p0 = 1.0 - p1
        if p0 <= 0 or p1 <= 0:
            return 0.0
        return float(-(p0 * np.log2(p0) + p1 * np.log2(p1)))

    @classmethod
    def analyze_entropy(cls, img_np: np.ndarray) -> Dict[str, Any]:
        """Calculates global, channel-wise, and LSB bit-plane entropies."""
        is_color = len(img_np.shape) == 3 and img_np.shape[2] >= 3

        if is_color:
            r_chan = img_np[:, :, 0]
            g_chan = img_np[:, :, 1]
            b_chan = img_np[:, :, 2]
            gray = (0.299 * r_chan + 0.587 * g_chan + 0.114 * b_chan).astype(np.uint8)

            global_entropy = cls.calculate_shannon_entropy(gray)
            r_entropy = cls.calculate_shannon_entropy(r_chan)
            g_entropy = cls.calculate_shannon_entropy(g_chan)
            b_entropy = cls.calculate_shannon_entropy(b_chan)

            r_lsb_entropy = cls.calculate_binary_entropy(r_chan & 1)
            g_lsb_entropy = cls.calculate_binary_entropy(g_chan & 1)
            b_lsb_entropy = cls.calculate_binary_entropy(b_chan & 1)
            gray_lsb_entropy = cls.calculate_binary_entropy(gray & 1)

            max_lsb_entropy = max(r_lsb_entropy, g_lsb_entropy, b_lsb_entropy)
        else:
            gray = img_np if len(img_np.shape) == 2 else img_np[:, :, 0]
            global_entropy = cls.calculate_shannon_entropy(gray)
            r_entropy = g_entropy = b_entropy = global_entropy
            gray_lsb_entropy = cls.calculate_binary_entropy(gray & 1)
            r_lsb_entropy = g_lsb_entropy = b_lsb_entropy = gray_lsb_entropy
            max_lsb_entropy = gray_lsb_entropy

        # High LSB entropy threshold: >= 0.995 indicates potential pseudorandom payload
        is_suspicious = max_lsb_entropy >= 0.995

        return {
            'global_entropy': round(global_entropy, 4),
            'channel_entropy': {
                'red': round(r_entropy, 4),
                'green': round(g_entropy, 4),
                'blue': round(b_entropy, 4)
            },
            'lsb_entropy': {
                'gray': round(gray_lsb_entropy, 4),
                'red': round(r_lsb_entropy, 4),
                'green': round(g_lsb_entropy, 4),
                'blue': round(b_lsb_entropy, 4),
                'max': round(max_lsb_entropy, 4)
            },
            'is_suspicious': is_suspicious,
            'summary': 'Elevated LSB entropy detected (near 1.0 bit/pixel)' if is_suspicious else 'LSB entropy within natural photographic variation'
        }

    @classmethod
    def chi_square_attack(cls, channel: np.ndarray) -> Dict[str, Any]:
        """
        Westfeld's Chi-Square Test on Pairs of Values (PoVs).
        Pairs (2k, 2k+1) for k in [0, 127].
        In LSB steganography, observed counts equalize toward their mean.
        Returns chi2 statistic, degrees of freedom, p-value (probability of embedding).
        """
        flat = channel.flatten()
        counts = np.bincount(flat, minlength=256)

        chi2_sum = 0.0
        active_pairs = 0

        for k in range(128):
            n_2k = counts[2 * k]
            n_2k1 = counts[2 * k + 1]
            pair_sum = n_2k + n_2k1
            if pair_sum > 4:  # Minimum count threshold for statistical validity
                expected = pair_sum / 2.0
                chi2_sum += ((n_2k - expected) ** 2) / expected + ((n_2k1 - expected) ** 2) / expected
                active_pairs += 1

        if active_pairs <= 1:
            return {
                'chi2_stat': 0.0,
                'df': 0,
                'p_value': 0.0,
                'probability_stego': 0.0,
                'is_suspicious': False,
                'details': 'Insufficient pixel variation for Chi-Square attack.'
            }

        df = int(active_pairs - 1)
        p_val = float(stats.chi2.sf(chi2_sum, df))
        
        # When embedding occurs, chi2_stat / df is very close to 1.0 (or below).
        # In natural images with variance between pairs, chi2_stat / df >> 1.0.
        ratio = float(chi2_sum / df) if df > 0 else 999.0
        if ratio <= 1.2:
            prob_stego = max(p_val, 0.85)
        elif ratio <= 2.0:
            prob_stego = max(p_val, 0.60)
        else:
            prob_stego = p_val

        prob_stego = float(max(0.0, min(1.0, prob_stego)))
        is_suspicious = bool(prob_stego > 0.70 or ratio <= 1.5)

        return {
            'chi2_stat': round(float(chi2_sum), 2),
            'df': int(df),
            'ratio': round(ratio, 2),
            'p_value': round(float(p_val), 4),
            'probability_stego': round(float(prob_stego), 4),
            'is_suspicious': bool(is_suspicious),
            'details': f'Equalized PoV distribution (P={prob_stego:.2%}, ratio={ratio:.2f})' if is_suspicious else f'Natural variation between adjacent values (ratio={ratio:.2f})'
        }

    @classmethod
    def calculate_pixel_correlations(cls, gray: np.ndarray) -> Dict[str, Any]:
        """
        Calculates Pearson correlation coefficient between adjacent pixels:
        - Horizontal: (x, y) vs (x+1, y)
        - Vertical: (x, y) vs (x, y+1)
        - Diagonal: (x, y) vs (x+1, y+1)
        Natural images typically exhibit r > 0.85; severe stego disrupts fine correlation.
        """
        h, w = gray.shape
        if h < 4 or w < 4:
            return {'horizontal': 1.0, 'vertical': 1.0, 'diagonal': 1.0, 'is_anomalous': False}

        gray_f = gray.astype(np.float64)

        # Horizontal
        x_h = gray_f[:, :-1].flatten()
        y_h = gray_f[:, 1:].flatten()
        r_h = float(np.corrcoef(x_h, y_h)[0, 1]) if np.std(x_h) > 0 and np.std(y_h) > 0 else 1.0

        # Vertical
        x_v = gray_f[:-1, :].flatten()
        y_v = gray_f[1:, :].flatten()
        r_v = float(np.corrcoef(x_v, y_v)[0, 1]) if np.std(x_v) > 0 and np.std(y_v) > 0 else 1.0

        # Diagonal
        x_d = gray_f[:-1, :-1].flatten()
        y_d = gray_f[1:, 1:].flatten()
        r_d = float(np.corrcoef(x_d, y_d)[0, 1]) if np.std(x_d) > 0 and np.std(y_d) > 0 else 1.0

        # Correlation in LSB plane (should be near 0 in stego, low-to-medium in natural)
        lsb = (gray & 1).astype(np.float64)
        lsb_x = lsb[:, :-1].flatten()
        lsb_y = lsb[:, 1:].flatten()
        r_lsb = float(np.corrcoef(lsb_x, lsb_y)[0, 1]) if np.std(lsb_x) > 0 and np.std(lsb_y) > 0 else 0.0

        return {
            'horizontal': round(r_h, 4),
            'vertical': round(r_v, 4),
            'diagonal': round(r_d, 4),
            'lsb_horizontal_corr': round(r_lsb, 4),
            'is_anomalous': bool(abs(r_lsb) < 0.005 and (r_h > 0.80))
        }

    @classmethod
    def sample_pair_analysis(cls, gray: np.ndarray) -> Dict[str, Any]:
        """
        Sample Pair Analysis (SPA) by Dumitrescu, Wu, and Wang.
        Estimates the hidden LSB message length p in [0, 1].
        """
        h, w = gray.shape
        # Downsample for SPA if image is larger than 1024x1024 to bound compute
        work_img = gray
        if h > 800 or w > 800:
            step_y = max(1, h // 600)
            step_x = max(1, w // 600)
            work_img = gray[::step_y, ::step_x]

        # Flatten horizontal pairs
        u = work_img[:, :-1].flatten().astype(int)
        v = work_img[:, 1:].flatten().astype(int)

        # Count pair types:
        # P = {(u, v) : v is even and u < v OR v is odd and u > v}
        # In SPA formulation:
        # X: pairs with (u >> 1 == v >> 1) and (u & 1 != v & 1)
        # Y: pairs with (u >> 1 == v >> 1) and (u & 1 == v & 1)
        # Z: pairs with (u >> 1 != v >> 1) and condition
        u_div = u >> 1
        v_div = v >> 1
        same_pov = (u_div == v_div)
        diff_lsb = ((u & 1) != (v & 1))
        same_lsb = ((u & 1) == (v & 1))

        c_diff = np.sum(same_pov & diff_lsb)
        c_same = np.sum(same_pov & same_lsb)

        total_pairs = len(u)
        if total_pairs == 0:
            return {'estimated_embedding_rate': 0.0, 'is_suspicious': False}

        # Simplified sample pair estimation based on PoV parity asymmetry:
        # For clean image, c_diff ~ 0.5 * same_pov
        # Under full LSB replacement, c_diff and c_same equalize.
        sum_pov = c_diff + c_same
        if sum_pov < 50:
            est_rate = 0.0
        else:
            diff_ratio = abs(c_diff - c_same) / float(sum_pov)
            # In clean image diff_ratio is high; in fully embedded stego diff_ratio -> 0
            est_rate = max(0.0, min(1.0, 1.0 - diff_ratio))

        is_suspicious = bool(est_rate > 0.40)

        return {
            'estimated_embedding_rate': round(float(est_rate), 4),
            'estimated_percentage': round(float(est_rate * 100), 2),
            'is_suspicious': bool(is_suspicious),
            'confidence': 'High' if est_rate > 0.6 else ('Medium' if est_rate > 0.3 else 'Low')
        }

    @classmethod
    def generate_histogram_plot(cls, img_np: np.ndarray) -> str:
        """
        Generates a Matplotlib histogram plot for image color/intensity distribution,
        rendered to base64 PNG using the Agg headless backend.
        """
        fig, ax = plt.subplots(figsize=(6.5, 3.2), dpi=100)
        fig.patch.set_facecolor('#1e222d')  # Dark cybersecurity theme
        ax.set_facecolor('#161922')

        is_color = len(img_np.shape) == 3 and img_np.shape[2] >= 3

        if is_color:
            colors = [('#ff4d4d', 'Red', 0), ('#2ecc71', 'Green', 1), ('#3498db', 'Blue', 2)]
            for hex_col, label, ch in colors:
                channel_data = img_np[:, :, ch].flatten()
                counts = np.bincount(channel_data, minlength=256)
                ax.plot(range(256), counts, color=hex_col, label=label, alpha=0.85, linewidth=1.2)
        else:
            gray = img_np if len(img_np.shape) == 2 else img_np[:, :, 0]
            counts = np.bincount(gray.flatten(), minlength=256)
            ax.plot(range(256), counts, color='#00e5ff', label='Grayscale Intensity', alpha=0.9, linewidth=1.4)

        ax.set_title('Pixel Intensity Distribution Histogram', color='#e0e6ed', fontsize=10, fontweight='bold', pad=8)
        ax.set_xlabel('Pixel Intensity Value (0 - 255)', color='#9ba3af', fontsize=8)
        ax.set_ylabel('Pixel Frequency', color='#9ba3af', fontsize=8)
        ax.tick_params(colors='#9ba3af', labelsize=8)
        ax.grid(color='#2d3748', linestyle='--', linewidth=0.5, alpha=0.7)
        ax.legend(facecolor='#1e222d', edgecolor='#2d3748', labelcolor='#e0e6ed', fontsize=8)

        for spine in ax.spines.values():
            spine.set_color('#2d3748')

        plt.tight_layout()

        buf = BytesIO()
        plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)  # Always close to prevent matplotlib memory leaks

        encoded = base64.b64encode(buf.getvalue()).decode('ascii')
        return f"data:image/png;base64,{encoded}"

    @classmethod
    def analyze(cls, image_pil: Image.Image) -> Dict[str, Any]:
        """Runs full Layer 3 statistical analysis."""
        rgb_img = image_pil.convert('RGB')
        img_np = np.array(rgb_img, dtype=np.uint8)
        gray_np = np.array(rgb_img.convert('L'), dtype=np.uint8)

        entropy_res = cls.analyze_entropy(img_np)
        chi2_gray = cls.chi_square_attack(gray_np)
        chi2_red = cls.chi_square_attack(img_np[:, :, 0])
        chi2_green = cls.chi_square_attack(img_np[:, :, 1])
        chi2_blue = cls.chi_square_attack(img_np[:, :, 2])

        # Max chi2 stego probability across all channels
        max_chi2_prob = max(
            chi2_gray['probability_stego'],
            chi2_red['probability_stego'],
            chi2_green['probability_stego'],
            chi2_blue['probability_stego']
        )

        corr_res = cls.calculate_pixel_correlations(gray_np)
        spa_res = cls.sample_pair_analysis(gray_np)
        histogram_b64 = cls.generate_histogram_plot(img_np)

        return {
            'entropy': entropy_res,
            'chi_square': {
                'gray': chi2_gray,
                'red': chi2_red,
                'green': chi2_green,
                'blue': chi2_blue,
                'max_probability': round(max_chi2_prob, 4),
                'is_suspicious': bool(max_chi2_prob > 0.70)
            },
            'correlations': corr_res,
            'sample_pair_analysis': spa_res,
            'histogram_plot': histogram_b64
        }
