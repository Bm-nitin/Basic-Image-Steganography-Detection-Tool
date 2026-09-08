from typing import Dict, Any, Optional, List, Tuple
import numpy as np


class JPEGDomainAnalyzer:
    """
    Performs safe static JPEG structural and compression domain analysis.
    
    Inspects:
    1. DQT markers (Quantization table step distributions and quality approximation)
    2. SOF markers (Component precision, count, and chroma subsampling ratios)
    3. DHT markers (Huffman table counts and definitions)
    4. SOS marker and entropy-coded stream characteristics (Shannon entropy)
    5. Non-standard compression or structural anomalies
    
    Scientific Integrity Note:
    This analyzer evaluates JPEG structural and quantization container properties.
    It does not claim to parse individual quantized DCT coefficients unless full
    entropy decoding is performed.
    """

    # Standard IJG 50% Quality Luminance Quantization Table (Zig-Zag order mapped to natural)
    STD_LUM_Q50 = np.array([
        16, 11, 10, 16, 24, 40, 51, 61,
        12, 12, 14, 19, 26, 58, 60, 55,
        14, 13, 16, 24, 40, 57, 69, 56,
        14, 17, 22, 29, 51, 87, 80, 62,
        18, 22, 37, 56, 68, 109, 103, 77,
        24, 35, 55, 64, 81, 104, 113, 92,
        49, 64, 78, 87, 103, 121, 120, 101,
        72, 92, 95, 98, 112, 100, 103, 99
    ], dtype=np.float64)

    @classmethod
    def _estimate_quality_factor(cls, lum_table: np.ndarray) -> int:
        """Estimates IJG quality factor Q in [1, 100] by least-squares comparison."""
        if len(lum_table) < 64:
            return 50

        obs = np.array(lum_table[:64], dtype=np.float64)
        best_q = 50
        min_diff = float('inf')

        for q in range(1, 101):
            if q < 50:
                s = 5000.0 / float(q)
            else:
                s = 200.0 - 2.0 * float(q)

            pred = np.clip(np.floor((cls.STD_LUM_Q50 * s + 50.0) / 100.0), 1.0, 255.0)
            diff = float(np.mean(np.abs(obs - pred)))
            if diff < min_diff:
                min_diff = diff
                best_q = q

        return int(best_q)

    @classmethod
    def _calculate_byte_entropy(cls, data_bytes: bytes) -> float:
        """Computes Shannon entropy for byte buffer in bits/byte [0.0, 8.0]."""
        if not data_bytes:
            return 0.0
        arr = np.frombuffer(data_bytes, dtype=np.uint8)
        counts = np.bincount(arr, minlength=256)
        probs = counts[counts > 0] / len(arr)
        return float(-np.sum(probs * np.log2(probs)))

    @classmethod
    def analyze(cls, file_bytes: bytes, image_format: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyzes JPEG container structures, quantization tables, and entropy stream.
        Returns empty/disabled state if format is not JPEG.
        """
        # Guard: format check
        if image_format and image_format.upper() != 'JPEG':
            return {
                'available': False,
                'reason': 'not_jpeg',
                'components': 0,
                'sampling_factors': {},
                'subsampling': 'N/A',
                'quantization_tables_count': 0,
                'quantization_tables': {},
                'sos_entropy': 0.0,
                'estimated_quality': None,
                'recompression_indicator': 0.0,
                'jpeg_structural_indicator': 0.0,
                'dct_suspicion_indicator': 0.0,
                'is_suspicious': False,
                'details': 'JPEG-domain structural analysis is only applicable to JPEG files.'
            }

        if not file_bytes or len(file_bytes) < 4 or not file_bytes.startswith(b'\xFF\xD8'):
            return {
                'available': False,
                'reason': 'not_jpeg',
                'components': 0,
                'sampling_factors': {},
                'subsampling': 'N/A',
                'quantization_tables_count': 0,
                'quantization_tables': {},
                'sos_entropy': 0.0,
                'estimated_quality': None,
                'recompression_indicator': 0.0,
                'jpeg_structural_indicator': 0.0,
                'dct_suspicion_indicator': 0.0,
                'is_suspicious': False,
                'details': 'Invalid JPEG stream: missing standard SOI marker.'
            }

        data_len = len(file_bytes)
        idx = 2
        q_tables: Dict[int, List[int]] = {}
        huffman_tables_count = 0
        components = 0
        sampling_factors: Dict[str, str] = {}
        subsampling = 'Unknown'
        sos_stream = b''
        sos_found = False

        # Safe bounded marker scan loop
        while idx < data_len - 1:
            if file_bytes[idx] == 0xFF:
                marker = file_bytes[idx + 1]

                # Discard stuffed byte or restart marker
                if marker in (0x00, 0xFF) or (0xD0 <= marker <= 0xD7):
                    idx += 1
                    continue

                if marker == 0xD9:  # EOI
                    break

                if marker == 0xD8:  # SOI
                    idx += 2
                    continue

                if idx + 4 > data_len:
                    break

                seg_len = int.from_bytes(file_bytes[idx + 2:idx + 4], 'big')
                if seg_len < 2:
                    break

                seg_start = idx + 4
                seg_end = idx + 2 + seg_len
                if seg_end > data_len:
                    seg_end = data_len

                # DQT: Define Quantization Table (0xDB)
                if marker == 0xDB:
                    dqt_ptr = seg_start
                    while dqt_ptr < seg_end:
                        if dqt_ptr >= data_len:
                            break
                        info_byte = file_bytes[dqt_ptr]
                        precision = (info_byte >> 4) & 0x0F
                        table_id = info_byte & 0x0F
                        elem_size = 2 if precision == 1 else 1
                        table_bytes_len = 64 * elem_size
                        dqt_ptr += 1

                        if dqt_ptr + table_bytes_len <= seg_end:
                            raw_vals = file_bytes[dqt_ptr:dqt_ptr + table_bytes_len]
                            if elem_size == 1:
                                vals = list(raw_vals)
                            else:
                                vals = [int.from_bytes(raw_vals[k:k+2], 'big') for k in range(0, 128, 2)]
                            q_tables[table_id] = vals
                            dqt_ptr += table_bytes_len
                        else:
                            break

                # DHT: Define Huffman Table (0xC4)
                elif marker == 0xC4:
                    huffman_tables_count += 1

                # SOF0 / SOF2: Baseline or Progressive Frame (0xC0, 0xC2)
                elif marker in (0xC0, 0xC2):
                    if seg_end - seg_start >= 6:
                        precision_bits = file_bytes[seg_start]
                        frame_h = int.from_bytes(file_bytes[seg_start + 1:seg_start + 3], 'big')
                        frame_w = int.from_bytes(file_bytes[seg_start + 3:seg_start + 5], 'big')
                        num_comp = file_bytes[seg_start + 5]
                        components = num_comp

                        comp_ptr = seg_start + 6
                        comp_names = ['Y', 'Cb', 'Cr', 'K']
                        comp_factors = {}
                        for c_idx in range(num_comp):
                            if comp_ptr + 3 <= seg_end:
                                cid = file_bytes[comp_ptr]
                                factors = file_bytes[comp_ptr + 1]
                                h_factor = (factors >> 4) & 0x0F
                                v_factor = factors & 0x0F
                                q_sel = file_bytes[comp_ptr + 2]
                                c_label = comp_names[c_idx] if c_idx < len(comp_names) else f"Comp_{cid}"
                                sampling_factors[c_label] = f"{h_factor}x{v_factor}"
                                comp_factors[c_label] = (h_factor, v_factor)
                                comp_ptr += 3

                        # Derive standard chroma subsampling notation
                        if 'Y' in comp_factors and 'Cb' in comp_factors:
                            y_h, y_v = comp_factors['Y']
                            cb_h, cb_v = comp_factors['Cb']
                            if y_h == 2 and y_v == 2 and cb_h == 1 and cb_v == 1:
                                subsampling = '4:2:0'
                            elif y_h == 2 and y_v == 1 and cb_h == 1 and cb_v == 1:
                                subsampling = '4:2:2'
                            elif y_h == 1 and y_v == 1 and cb_h == 1 and cb_v == 1:
                                subsampling = '4:4:4'
                            else:
                                subsampling = f"{y_h}:{cb_h}:{cb_v}"
                        elif num_comp == 1:
                            subsampling = 'Grayscale (1 Comp)'

                # SOS: Start of Scan (0xDA)
                elif marker == 0xDA:
                    sos_found = True
                    sos_header_end = seg_end
                    scan_ptr = sos_header_end
                    
                    # Scan until next marker indicating EOF or end of scan
                    while scan_ptr < data_len - 1:
                        if file_bytes[scan_ptr] == 0xFF:
                            nxt = file_bytes[scan_ptr + 1]
                            if nxt not in (0x00, 0xFF) and not (0xD0 <= nxt <= 0xD7):
                                break
                        scan_ptr += 1

                    sos_stream = file_bytes[sos_header_end:scan_ptr]
                    idx = scan_ptr
                    continue

                idx = seg_end
                continue

            idx += 1

        # Calculate SOS Shannon Entropy
        sos_entropy = cls._calculate_byte_entropy(sos_stream) if sos_stream else 0.0

        # Estimate Quality Factor
        est_quality = None
        recompression_indicator = 0.0
        anomalies = []

        if 0 in q_tables:
            lum_tab = np.array(q_tables[0], dtype=np.float64)
            est_quality = cls._estimate_quality_factor(lum_tab)

            # Anomaly check: All-ones or uniform quantization table
            if len(lum_tab) >= 64:
                if np.all(lum_tab == 1):
                    anomalies.append("All-ones quantization table detected (potential raw injection/quality 100).")
                    recompression_indicator += 0.35
                elif np.std(lum_tab) < 1.0:
                    anomalies.append("Uniform non-varying quantization steps detected.")
                    recompression_indicator += 0.30

        # Check color components vs quantization tables
        if components >= 3:
            if len(q_tables) == 1:
                anomalies.append("Single quantization table shared between luminance and chrominance.")
                recompression_indicator += 0.15
            elif 0 in q_tables and 1 in q_tables:
                if np.array_equal(q_tables[0], q_tables[1]):
                    anomalies.append("Identical luminance and chrominance quantization tables.")
                    recompression_indicator += 0.15

        # SOS Entropy analysis (Natural compressed JPEG stream: 7.75 - 7.99 bits/byte)
        if sos_found:
            if len(sos_stream) > 256:
                if sos_entropy < 7.2:
                    anomalies.append(f"Abnormally low entropy in entropy-coded scan ({sos_entropy:.2f} bits/byte).")
                    recompression_indicator += 0.30
        else:
            anomalies.append("Missing or unparseable Start of Scan (SOS) marker.")
            recompression_indicator += 0.20

        structural_indicator = float(min(1.0, max(0.0, recompression_indicator)))
        is_suspicious = bool(structural_indicator > 0.40)

        detail_msg = "; ".join(anomalies) if anomalies else (
            f"Standard JPEG structural markers validated (Quality ~{est_quality or 'N/A'}, "
            f"Subsampling {subsampling}, SOS Entropy {sos_entropy:.3f} bits/byte)."
        )

        return {
            'available': True,
            'components': int(components),
            'sampling_factors': sampling_factors,
            'subsampling': subsampling,
            'quantization_tables_count': len(q_tables),
            'quantization_tables': {k: v[:8] for k, v in q_tables.items()},  # First row preview
            'huffman_tables_count': int(huffman_tables_count),
            'sos_entropy': round(float(sos_entropy), 4),
            'estimated_quality': est_quality,
            'recompression_indicator': round(structural_indicator, 4),
            'jpeg_structural_indicator': round(structural_indicator, 4),
            'dct_suspicion_indicator': round(structural_indicator, 4),  # Alias for backward compatibility
            'is_suspicious': is_suspicious,
            'details': detail_msg
        }
