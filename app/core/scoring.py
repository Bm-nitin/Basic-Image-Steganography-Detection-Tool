from typing import Dict, Any, List, Optional
from .evidence import EvidenceCollector
from .explainability import ExplainabilityEngine

class SuspicionScoringEngine:
    """
    Combines forensic indicators into an interpretable Steganography Suspicion Index (0-100).
    
    Academic Disclaimer:
    This index is a weighted heuristic indicator for digital forensics triage,
    NOT a deterministic mathematical proof. Statistical variation, compression artifacts,
    or synthetic noise can influence scores.
    """

    @classmethod
    def evaluate(cls, 
                 metadata_res: Dict[str, Any], 
                 visual_res: Dict[str, Any], 
                 statistical_res: Dict[str, Any],
                 forensics_res: Optional[Dict[str, Any]] = None,
                 tampering_res: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Evaluates test results from Layers 1, 2, 3, File Forensics, and Tampering Forensics.
        """

        score = 0.0
        breakdown: List[Dict[str, Any]] = []

        # 1. Structural / File Forensics (Weight: 20% / Max 20.0 pts)
        trailing = (forensics_res.get('trailing_data') if forensics_res else None) or metadata_res.get('trailing_data', {})
        has_trailing = trailing.get('has_trailing_data', trailing.get('detected', False))
        trailing_bytes = trailing.get('trailing_bytes_count', trailing.get('size', 0))
        
        if has_trailing:
            if trailing_bytes > 512:
                trailing_pts = 20.0
            elif trailing_bytes > 64:
                trailing_pts = 14.0
            else:
                trailing_pts = 8.0
            trailing_status = 'Anomaly'
            trailing_details = f"Found {trailing_bytes:,} appended bytes past the legitimate image EOF marker."
        else:
            trailing_pts = 0.0
            trailing_status = 'Clean'
            trailing_details = 'File structure conforms strictly to format EOF specifications without trailing bytes.'

        breakdown.append({
            'category': 'Structural / EOF Analysis',
            'detector': 'Appended Trailing Data',
            'status': trailing_status,
            'points_added': round(trailing_pts, 1),
            'details': trailing_details
        })

        # File & Container Forensics: Embedded Signatures and Polyglot Analysis
        structural_pts = trailing_pts
        if forensics_res:
            embedded_sigs = forensics_res.get('embedded_signatures', [])
            is_polyglot = forensics_res.get('polyglot_suspected', False)
            polyglot_reason = forensics_res.get('polyglot_reason', '')

            # Embedded Container / Payload Signatures
            if embedded_sigs:
                sig_names = [f"{s['type']} (@0x{s['offset']:X})" for s in embedded_sigs[:3]]
                if len(embedded_sigs) > 3:
                    sig_names.append(f"+{len(embedded_sigs) - 3} more")
                has_high = any(s.get('evidence_strength') == 'high' or s.get('after_image_eof') for s in embedded_sigs)
                sig_status = 'Anomaly' if has_high else 'Suspicious'
                sig_details = f"Detected {len(embedded_sigs)} foreign file/container signature(s): {', '.join(sig_names)}."
            else:
                sig_status = 'Clean'
                sig_details = 'No secondary or embedded container signatures found in byte stream.'

            # Polyglot Container Analysis
            if is_polyglot:
                poly_status = 'Anomaly'
                poly_details = f"Possible polyglot structure: {polyglot_reason}"
            else:
                poly_status = 'Clean'
                poly_details = 'No coexisting secondary container structures identified.'

            # Compute combined bounded structural points (capped at 20.0 pts)
            i_struct = forensics_res.get('structural_anomaly_indicator', 0.0)
            total_structural_pts = round(min(20.0, max(trailing_pts, 20.0 * i_struct)), 1)
            extra_forensics_pts = round(max(0.0, total_structural_pts - trailing_pts), 1)

            breakdown.append({
                'category': 'Structural / EOF Analysis',
                'detector': 'Embedded Container Signatures',
                'status': sig_status,
                'points_added': extra_forensics_pts if not is_polyglot else round(extra_forensics_pts / 2, 1),
                'details': sig_details
            })

            if is_polyglot or any(s.get('after_image_eof') for s in embedded_sigs):
                breakdown.append({
                    'category': 'Structural / EOF Analysis',
                    'detector': 'Polyglot Container Analysis',
                    'status': poly_status,
                    'points_added': round(extra_forensics_pts / 2, 1) if is_polyglot else 0.0,
                    'details': poly_details
                })

            structural_pts = total_structural_pts

        score += structural_pts

        # 2. Metadata Inspection (Weight: 10% / Max 10.0 pts)
        sigs = metadata_res.get('metadata', {}).get('suspicious_signatures', [])
        if sigs:
            sig_pts = 10.0
            score += sig_pts
            breakdown.append({
                'category': 'Metadata Inspection',
                'detector': 'Known Steganography Signatures',
                'status': 'Anomaly',
                'points_added': sig_pts,
                'details': f"Identified stego application signature(s): {', '.join(sigs)}"
            })
        else:
            sig_pts = 0.0
            breakdown.append({
                'category': 'Metadata Inspection',
                'detector': 'Known Steganography Signatures',
                'status': 'Clean',
                'points_added': 0.0,
                'details': 'No known steganography tool markers or suspicious metadata tags found.'
            })

        # 3. Statistical Steganalysis (Weight: 50% / Max 50.0 pts)
        is_jpeg = bool(statistical_res.get('jpeg_analysis', {}).get('available', False))

        # Dynamic normalized weighting within 50.0 pt statistical budget
        if is_jpeg:
            # JPEG Carrier: 25% Chi2, 15% Entropy, 20% SPA, 25% RS, 15% JPEG structural
            w_chi2 = 12.5
            w_entropy = 7.5
            w_spa = 10.0
            w_rs = 12.5
            w_jpeg = 7.5
        else:
            # Non-JPEG Carrier: proportional redistribution (29.41% Chi2, 17.65% Entropy, 23.53% SPA, 29.41% RS)
            w_chi2 = 14.7
            w_entropy = 8.8
            w_spa = 11.8
            w_rs = 14.7
            w_jpeg = 0.0

        # 3a. Westfeld Chi-Square Pairs of Values
        chi2 = statistical_res.get('chi_square', {})
        max_chi2_indicator = chi2.get('max_indicator', chi2.get('max_probability', 0.0))
        if max_chi2_indicator >= 0.85:
            chi2_pts = w_chi2
            status_chi2 = 'Anomaly'
            msg_chi2 = f"Strong equalization of adjacent Pairs of Values (indicator={max_chi2_indicator:.2%}), typical of LSB replacement."
        elif max_chi2_indicator > 0.60:
            chi2_pts = round(0.60 * w_chi2, 1)
            status_chi2 = 'Suspicious'
            msg_chi2 = f"Moderate Pairs of Values equalization detected (indicator={max_chi2_indicator:.2%})."
        else:
            chi2_pts = 0.0
            status_chi2 = 'Clean'
            msg_chi2 = f"Natural variance between adjacent pixel pairs preserved (indicator={max_chi2_indicator:.2%})."

        breakdown.append({
            'category': 'Statistical Steganalysis',
            'detector': 'Chi-Square Attack (PoVs)',
            'status': status_chi2,
            'points_added': round(chi2_pts, 1),
            'details': msg_chi2
        })

        # 3b. Shannon Entropy of LSB Plane
        entropy_data = statistical_res.get('entropy', {})
        max_lsb_entropy = entropy_data.get('lsb_entropy', {}).get('max', 0.0)
        if max_lsb_entropy >= 0.998:
            entropy_pts = w_entropy
            status_entropy = 'Anomaly'
            msg_entropy = f"Extreme LSB entropy ({max_lsb_entropy:.4f} / 1.0000 bit/pixel), consistent with encrypted/compressed payload."
        elif max_lsb_entropy >= 0.990:
            entropy_pts = round(0.60 * w_entropy, 1)
            status_entropy = 'Suspicious'
            msg_entropy = f"Elevated LSB entropy ({max_lsb_entropy:.4f} / 1.0000 bit/pixel)."
        else:
            entropy_pts = 0.0
            status_entropy = 'Clean'
            msg_entropy = f"Normal LSB plane entropy ({max_lsb_entropy:.4f} / 1.0000 bit/pixel) consistent with natural sensor noise."

        breakdown.append({
            'category': 'Statistical Steganalysis',
            'detector': 'Shannon Entropy (LSB Plane)',
            'status': status_entropy,
            'points_added': round(entropy_pts, 1),
            'details': msg_entropy
        })

        # 3c. Sample Pair Analysis (SPA)
        spa = statistical_res.get('spa_analysis', statistical_res.get('sample_pair_analysis', {}))
        spa_rate = spa.get('estimated_embedding_rate', spa.get('suspicion_indicator', 0.0))
        if spa_rate > 0.60:
            spa_pts = w_spa
            status_spa = 'Anomaly'
            msg_spa = f"SPA estimates {spa_rate * 100:.1f}% capacity spatial LSB payload."
        elif spa_rate > 0.30:
            spa_pts = round(0.60 * w_spa, 1)
            status_spa = 'Suspicious'
            msg_spa = f"SPA estimates moderate {spa_rate * 100:.1f}% spatial LSB payload."
        else:
            spa_pts = 0.0
            status_spa = 'Clean'
            msg_spa = f"SPA indicates negligible spatial LSB modification ({spa_rate * 100:.1f}% estimated rate)."

        breakdown.append({
            'category': 'Statistical Steganalysis',
            'detector': 'Sample Pair Analysis (SPA)',
            'status': status_spa,
            'points_added': round(spa_pts, 1),
            'details': msg_spa
        })

        # 3d. Regular-Singular (RS) Steganalysis
        rs = statistical_res.get('rs_analysis', {})
        rs_rate = rs.get('estimated_embedding_rate', 0.0)
        rs_ind = rs.get('suspicion_indicator', 0.0)
        if rs_rate > 0.50 or rs_ind > 0.70:
            rs_pts = w_rs
            status_rs = 'Anomaly'
            msg_rs = f"RS steganalysis indicates high probability LSB embedding ({rs_rate * 100:.1f}% estimated rate)."
        elif rs_rate > 0.25 or rs_ind > 0.40:
            rs_pts = round(0.60 * w_rs, 1)
            status_rs = 'Suspicious'
            msg_rs = f"RS steganalysis indicates moderate LSB asymmetry ({rs_rate * 100:.1f}% estimated rate)."
        else:
            rs_pts = 0.0
            status_rs = 'Clean'
            msg_rs = f"RS steganalysis curves conform to clean carrier symmetry ({rs_rate * 100:.1f}% estimated rate)."

        breakdown.append({
            'category': 'Statistical Steganalysis',
            'detector': 'RS Steganalysis (Regular-Singular)',
            'status': status_rs,
            'points_added': round(rs_pts, 1),
            'details': msg_rs
        })

        # 3e. JPEG-Domain Structural Analysis (When applicable)
        jpeg_pts = 0.0
        if is_jpeg:
            jpeg_struct = statistical_res.get('jpeg_analysis', {})
            jpeg_ind = jpeg_struct.get('jpeg_structural_indicator', jpeg_struct.get('recompression_indicator', 0.0))
            if jpeg_ind > 0.50:
                jpeg_pts = w_jpeg
                status_jpeg = 'Anomaly'
                msg_jpeg = f"Severe JPEG structural anomalies detected: {jpeg_struct.get('details', '')}"
            elif jpeg_ind > 0.25:
                jpeg_pts = round(0.60 * w_jpeg, 1)
                status_jpeg = 'Suspicious'
                msg_jpeg = f"Moderate JPEG structural or quantization variations: {jpeg_struct.get('details', '')}"
            else:
                jpeg_pts = 0.0
                status_jpeg = 'Clean'
                msg_jpeg = f"Standard JPEG compression structures validated ({jpeg_struct.get('details', '')})"

            breakdown.append({
                'category': 'Statistical Steganalysis',
                'detector': 'JPEG Structural Analysis',
                'status': status_jpeg,
                'points_added': round(jpeg_pts, 1),
                'details': msg_jpeg
            })

        # 3f. Color & Alpha Channel Distribution
        chan_data = statistical_res.get('channel_analysis', {})
        chan_ind = chan_data.get('channel_anomaly_indicator', 0.0)
        alpha_suspicious = chan_data.get('alpha_analysis', {}).get('suspicious', False)
        if alpha_suspicious:
            breakdown.append({
                'category': 'Statistical Steganalysis',
                'detector': 'Color & Alpha Channel Distribution',
                'status': 'Anomaly',
                'points_added': 0.0,
                'details': chan_data.get('alpha_analysis', {}).get('details', '')
            })
        elif chan_ind > 0.40:
            breakdown.append({
                'category': 'Statistical Steganalysis',
                'detector': 'Color & Alpha Channel Distribution',
                'status': 'Suspicious',
                'points_added': 0.0,
                'details': f"Cross-channel correlation/entropy divergence detected (indicator={chan_ind:.2f})."
            })

        # Bound total statistical category points to strictly 50.0 pts
        raw_stat_pts = chi2_pts + entropy_pts + spa_pts + rs_pts + jpeg_pts
        total_stat_pts = min(50.0, round(raw_stat_pts, 1))
        score += total_stat_pts

        # 4. Visual Steganalysis / LSB Uniformity & Parity Balance (Weight: 20% / Max 20.0 pts)
        min_delta = visual_res.get('min_balance_delta', 1.0)
        vis_pts = 0.0
        if min_delta < 0.005:  # within 0.5% of perfect 50/50 balance
            vis_pts = 20.0
            status = 'Suspicious'
            msg = f"Near-perfect 50/50 binary distribution in LSB plane (delta = {min_delta:.4f}), typical of pseudorandom keystream."
        else:
            status = 'Clean'
            msg = f"Natural bias in LSB bit distribution (delta = {min_delta:.4f})."
        
        score += vis_pts
        breakdown.append({
            'category': 'Visual Steganalysis',
            'detector': 'LSB Parity Distribution',
            'status': status,
            'points_added': round(vis_pts, 1),
            'details': msg
        })

        # 5. Image Tampering & Manipulation Forensics (Independent Forensic Layer)
        tampering_indicator = 0.0
        tampering_score = 0.0
        tampering_suspicious = False
        if tampering_res and tampering_res.get('available', False):
            tampering_indicator = float(tampering_res.get('combined_indicator', 0.0))
            tampering_score = float(tampering_res.get('combined_score', 0.0))
            tampering_suspicious = bool(tampering_res.get('is_suspicious', False))

            t_dets = tampering_res.get('detectors', {})
            # 5a. Error Level Analysis (ELA)
            ela_d = t_dets.get('ela', {})
            if ela_d.get('available', False):
                ela_status = 'Anomaly' if ela_d.get('is_suspicious') else ('Suspicious' if ela_d.get('anomaly_indicator', 0) > 0.35 else 'Clean')
                breakdown.append({
                    'category': 'Tampering & Manipulation Forensics',
                    'detector': 'Error Level Analysis (ELA)',
                    'status': ela_status,
                    'points_added': 0.0,
                    'details': ela_d.get('details', '')
                })

            # 5b. Local Residual Noise Consistency
            noise_d = t_dets.get('noise', {})
            if noise_d.get('available', False):
                noise_status = 'Anomaly' if noise_d.get('is_suspicious') else ('Suspicious' if noise_d.get('anomaly_indicator', 0) > 0.35 else 'Clean')
                breakdown.append({
                    'category': 'Tampering & Manipulation Forensics',
                    'detector': 'Local Residual Noise Consistency',
                    'status': noise_status,
                    'points_added': 0.0,
                    'details': noise_d.get('details', '')
                })

            # 5c. Local Texture Variance Disparity
            var_d = t_dets.get('local_variance', {})
            if var_d.get('available', False):
                var_status = 'Anomaly' if var_d.get('is_suspicious') else ('Suspicious' if var_d.get('anomaly_indicator', 0) > 0.35 else 'Clean')
                breakdown.append({
                    'category': 'Tampering & Manipulation Forensics',
                    'detector': 'Texture Variance Disparity',
                    'status': var_status,
                    'points_added': 0.0,
                    'details': var_d.get('details', '')
                })

            # 5d. Edge Discontinuity & Gradients
            edge_d = t_dets.get('edge', {})
            if edge_d.get('available', False):
                edge_status = 'Anomaly' if edge_d.get('is_suspicious') else ('Suspicious' if edge_d.get('anomaly_indicator', 0) > 0.35 else 'Clean')
                breakdown.append({
                    'category': 'Tampering & Manipulation Forensics',
                    'detector': 'Edge Discontinuity & Gradients',
                    'status': edge_status,
                    'points_added': 0.0,
                    'details': edge_d.get('details', '')
                })

            # 5e. Copy-Move Duplicate Matching
            cm_d = t_dets.get('copy_move', {})
            if cm_d.get('available', False):
                cm_status = 'Anomaly' if cm_d.get('is_suspicious') else ('Suspicious' if cm_d.get('cluster_count', 0) > 0 else 'Clean')
                breakdown.append({
                    'category': 'Tampering & Manipulation Forensics',
                    'detector': 'Copy-Move Duplicate Detection',
                    'status': cm_status,
                    'points_added': 0.0,
                    'details': cm_d.get('details', '')
                })

        # Clamp composite score between 0 and 100
        final_score = round(max(0.0, min(100.0, score)), 1)

        # Risk categorization
        if final_score >= 60.0:
            risk_level = 'High'
            risk_badge = 'danger'
            risk_summary = 'Strong suspicious indicators detected; multiple forensic anomalies observed.'
        elif final_score >= 20.0:
            risk_level = 'Medium'
            risk_badge = 'warning'
            risk_summary = 'Suspicious indicators detected; moderate forensic or structural anomalies observed.'
        else:
            risk_level = 'Low'
            risk_badge = 'success'
            risk_summary = 'Low suspicion; characteristics align with clean/unmodified photographic imagery.'

        # Collect Phase E Evidence and Explainable Assessment
        evidence_data = EvidenceCollector.collect_all(
            metadata_res, visual_res, statistical_res,
            forensics_res=forensics_res,
            tampering_res=tampering_res
        )
        explainability_data = ExplainabilityEngine.generate(
            evidence_data,
            {
                'suspicion_score': final_score,
                'risk_level': risk_level,
                'detector_breakdown': breakdown
            },
            tampering_res=tampering_res
        )

        return {
            'suspicion_score': final_score,
            'risk_level': risk_level,
            'risk_badge': risk_badge,
            'risk_summary': risk_summary,
            'tampering_indicator': tampering_indicator,
            'tampering_score': tampering_score,
            'tampering_suspicious': tampering_suspicious,
            'category_scores': {
                'structural': round(structural_pts, 1),
                'metadata': round(sig_pts, 1),
                'statistical': round(total_stat_pts, 1),
                'visual': round(vis_pts, 1),
                'tampering': round(tampering_score, 1)
            },
            'detector_breakdown': breakdown,
            'evidence': evidence_data,
            'explainability': explainability_data,
            'disclaimer': (
                'Notice: The Steganography Suspicion Index is a heuristic digital forensics indicator '
                'and is not proof that hidden information is present. Non-standard compression, heavy noise, '
                'or synthetic artwork can trigger elevated statistical indicators.'
            )
        }

