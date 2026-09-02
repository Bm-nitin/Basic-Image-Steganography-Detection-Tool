from typing import Dict, Any, List

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
                 statistical_res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates test results from Layers 1, 2, and 3 to compute a composite suspicion score.
        """
        score = 0.0
        breakdown: List[Dict[str, Any]] = []

        # 1. Trailing / Appended Data beyond EOF (Max: 35 points)
        trailing = metadata_res.get('trailing_data', {})
        has_trailing = trailing.get('has_trailing_data', False)
        trailing_bytes = trailing.get('trailing_bytes_count', 0)
        
        if has_trailing:
            if trailing_bytes > 512:
                trailing_pts = 35.0
            elif trailing_bytes > 64:
                trailing_pts = 25.0
            else:
                trailing_pts = 15.0
            score += trailing_pts
            breakdown.append({
                'category': 'Structural / EOF Analysis',
                'detector': 'Appended Trailing Data',
                'status': 'Anomaly',
                'points_added': round(trailing_pts, 1),
                'details': f"Found {trailing_bytes:,} appended bytes past the legitimate image EOF marker."
            })
        else:
            breakdown.append({
                'category': 'Structural / EOF Analysis',
                'detector': 'Appended Trailing Data',
                'status': 'Clean',
                'points_added': 0.0,
                'details': 'File structure conforms strictly to format EOF specifications without trailing bytes.'
            })

        # 2. Suspicious Software / EXIF Signatures (Max: 20 points)
        sigs = metadata_res.get('metadata', {}).get('suspicious_signatures', [])
        if sigs:
            sig_pts = 20.0
            score += sig_pts
            breakdown.append({
                'category': 'Metadata Inspection',
                'detector': 'Known Steganography Signatures',
                'status': 'Anomaly',
                'points_added': sig_pts,
                'details': f"Identified stego application signature(s): {', '.join(sigs)}"
            })
        else:
            breakdown.append({
                'category': 'Metadata Inspection',
                'detector': 'Known Steganography Signatures',
                'status': 'Clean',
                'points_added': 0.0,
                'details': 'No known steganography tool markers or suspicious metadata tags found.'
            })

        # 3. Westfeld Chi-Square Pairs of Values (Max: 25 points)
        chi2 = statistical_res.get('chi_square', {})
        max_chi2_prob = chi2.get('max_probability', 0.0)
        chi2_pts = 0.0
        if max_chi2_prob > 0.85:
            chi2_pts = 25.0
            status = 'Anomaly'
            msg = f"Strong equalization of adjacent Pairs of Values (p={max_chi2_prob:.2%}), typical of LSB replacement."
        elif max_chi2_prob > 0.60:
            chi2_pts = 15.0
            status = 'Suspicious'
            msg = f"Moderate Pairs of Values equalization detected (p={max_chi2_prob:.2%})."
        else:
            chi2_pts = 0.0
            status = 'Clean'
            msg = f"Natural variance between adjacent pixel pairs preserved (p={max_chi2_prob:.2%})."
        
        score += chi2_pts
        breakdown.append({
            'category': 'Statistical Steganalysis',
            'detector': 'Chi-Square Attack (PoVs)',
            'status': status,
            'points_added': round(chi2_pts, 1),
            'details': msg
        })

        # 4. Shannon Entropy of LSB Plane (Max: 15 points)
        entropy_data = statistical_res.get('entropy', {})
        max_lsb_entropy = entropy_data.get('lsb_entropy', {}).get('max', 0.0)
        entropy_pts = 0.0
        if max_lsb_entropy >= 0.998:
            entropy_pts = 15.0
            status = 'Anomaly'
            msg = f"Extreme LSB entropy ({max_lsb_entropy:.4f} / 1.0000 bit/pixel), consistent with encrypted/compressed payload."
        elif max_lsb_entropy >= 0.990:
            entropy_pts = 8.0
            status = 'Suspicious'
            msg = f"Elevated LSB entropy ({max_lsb_entropy:.4f} / 1.0000 bit/pixel)."
        else:
            status = 'Clean'
            msg = f"Normal LSB plane entropy ({max_lsb_entropy:.4f} / 1.0000 bit/pixel) consistent with natural sensor noise."
        
        score += entropy_pts
        breakdown.append({
            'category': 'Statistical Steganalysis',
            'detector': 'Shannon Entropy (LSB Plane)',
            'status': status,
            'points_added': round(entropy_pts, 1),
            'details': msg
        })

        # 5. Sample Pair Analysis (SPA) (Max: 15 points)
        spa = statistical_res.get('sample_pair_analysis', {})
        est_rate = spa.get('estimated_embedding_rate', 0.0)
        spa_pts = 0.0
        if est_rate > 0.60:
            spa_pts = 15.0
            status = 'Anomaly'
            msg = f"SPA estimates {est_rate * 100:.1f}% capacity spatial LSB payload."
        elif est_rate > 0.30:
            spa_pts = 8.0
            status = 'Suspicious'
            msg = f"SPA estimates moderate {est_rate * 100:.1f}% spatial LSB payload."
        else:
            status = 'Clean'
            msg = f"SPA indicates negligible spatial LSB modification ({est_rate * 100:.1f}% estimated rate)."
        
        score += spa_pts
        breakdown.append({
            'category': 'Statistical Steganalysis',
            'detector': 'Sample Pair Analysis (SPA)',
            'status': status,
            'points_added': round(spa_pts, 1),
            'details': msg
        })

        # 6. Visual LSB Uniformity & Parity Balance (Max: 10 points)
        min_delta = visual_res.get('min_balance_delta', 1.0)
        vis_pts = 0.0
        if min_delta < 0.005:  # within 0.5% of perfect 50/50 balance
            vis_pts = 10.0
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

        # Clamp composite score between 0 and 100
        final_score = round(max(0.0, min(100.0, score)), 1)

        # Risk categorization
        if final_score >= 70.0:
            risk_level = 'High'
            risk_badge = 'danger'
            risk_summary = 'High probability of steganographic content or structural anomaly.'
        elif final_score >= 35.0:
            risk_level = 'Medium'
            risk_badge = 'warning'
            risk_summary = 'Suspicious indicators detected; multiple statistical anomalies observed.'
        else:
            risk_level = 'Low'
            risk_badge = 'success'
            risk_summary = 'Low suspicion; characteristics align with clean/unmodified photographic imagery.'

        return {
            'suspicion_score': final_score,
            'risk_level': risk_level,
            'risk_badge': risk_badge,
            'risk_summary': risk_summary,
            'detector_breakdown': breakdown,
            'disclaimer': (
                'Notice: The Steganography Suspicion Index is a heuristic digital forensics indicator '
                'and not mathematical proof of steganography. Non-standard compression, heavy noise, '
                'or synthetic artwork can trigger elevated statistical indicators.'
            )
        }
