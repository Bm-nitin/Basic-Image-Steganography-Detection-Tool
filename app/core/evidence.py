from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class EvidenceItem:
    """
    Standardized, safe forensic evidence item representation.
    Decoupled from filesystem paths, raw memory pointers, or system secrets.
    """
    category: str              # 'structural', 'metadata', 'statistical', 'visual', 'tampering'
    detector: str              # e.g., 'RS Steganalysis', 'Error Level Analysis'
    severity: str              # 'anomaly', 'suspicious', 'clean', 'info'
    indicator: float           # Normalized anomaly indicator [0.0, 1.0]
    observed_value: str        # Formatted human-readable observation
    threshold: str             # Forensic reference threshold / baseline
    explanation: str           # Explainable, non-conclusive forensic statement
    supporting_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converts evidence item to JSON-serializable dictionary."""
        return {
            'category': self.category,
            'detector': self.detector,
            'severity': self.severity,
            'indicator': round(float(self.indicator), 4),
            'observed_value': self.observed_value,
            'threshold': self.threshold,
            'explanation': self.explanation,
            'supporting_details': self.supporting_details
        }


class EvidenceCollector:
    """
    Extracts, normalizes, and ranks forensic evidence items across all analysis layers.
    Does not alter or double-count scoring points; operates purely as an explanatory model.
    """

    SEVERITY_ORDER = {
        'anomaly': 3,
        'suspicious': 2,
        'clean': 1,
        'info': 0
    }

    @classmethod
    def collect_steganography_evidence(
        cls,
        metadata_res: Dict[str, Any],
        visual_res: Dict[str, Any],
        statistical_res: Dict[str, Any],
        forensics_res: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extracts and ranks evidence items relevant to steganography analysis.
        """
        items: List[EvidenceItem] = []

        # 1. Structural / Trailing Data
        trailing = (forensics_res.get('trailing_data') if forensics_res else None) or metadata_res.get('trailing_data', {})
        has_trailing = trailing.get('has_trailing_data', trailing.get('detected', False))
        trailing_bytes = trailing.get('trailing_bytes_count', trailing.get('size', 0))

        if has_trailing:
            sev = 'anomaly' if trailing_bytes > 64 else 'suspicious'
            ind = min(1.0, trailing_bytes / 512.0)
            items.append(EvidenceItem(
                category='structural',
                detector='Appended Trailing Data',
                severity=sev,
                indicator=ind,
                observed_value=f"{trailing_bytes:,} bytes past EOF",
                threshold="0 bytes (Standard format termination)",
                explanation=f"Found {trailing_bytes:,} extra bytes appended past the valid End-of-File marker, characteristic of naive concatenation steganography.",
                supporting_details={'trailing_bytes': trailing_bytes}
            ))
        else:
            items.append(EvidenceItem(
                category='structural',
                detector='Appended Trailing Data',
                severity='clean',
                indicator=0.0,
                observed_value="0 bytes past EOF",
                threshold="0 bytes (Standard format termination)",
                explanation="File structure strictly conforms to standard format termination specifications without appended trailing bytes.",
                supporting_details={'trailing_bytes': 0}
            ))

        # 2. Embedded Signatures & Polyglot
        if forensics_res:
            sigs = forensics_res.get('embedded_signatures', [])
            is_polyglot = forensics_res.get('polyglot_suspected', False)
            poly_reason = forensics_res.get('polyglot_reason', '')

            if sigs:
                has_high = any(s.get('evidence_strength') == 'high' or s.get('after_image_eof') for s in sigs)
                sev = 'anomaly' if has_high else 'suspicious'
                sig_names = [s.get('type', 'Unknown') for s in sigs[:3]]
                items.append(EvidenceItem(
                    category='structural',
                    detector='Embedded Container Signatures',
                    severity=sev,
                    indicator=forensics_res.get('structural_anomaly_indicator', 0.8),
                    observed_value=f"{len(sigs)} embedded signature(s): {', '.join(sig_names)}",
                    threshold="0 foreign container signatures",
                    explanation=f"Identified {len(sigs)} foreign archive or binary container signature(s) within the file stream.",
                    supporting_details={'signatures_count': len(sigs), 'types': sig_names}
                ))
            else:
                items.append(EvidenceItem(
                    category='structural',
                    detector='Embedded Container Signatures',
                    severity='clean',
                    indicator=0.0,
                    observed_value="0 embedded signatures",
                    threshold="0 foreign container signatures",
                    explanation="No secondary or embedded foreign container signatures found in byte stream.",
                    supporting_details={'signatures_count': 0}
                ))

            if is_polyglot:
                items.append(EvidenceItem(
                    category='structural',
                    detector='Polyglot Structure Analysis',
                    severity='anomaly',
                    indicator=0.9,
                    observed_value=poly_reason or "Secondary executable container identified",
                    threshold="Single valid carrier container",
                    explanation=f"File exhibits characteristics consistent with a dual-format polyglot structure: {poly_reason}.",
                    supporting_details={'polyglot_reason': poly_reason}
                ))

        # 3. Known Steganography Metadata Signatures
        meta_sigs = metadata_res.get('metadata', {}).get('suspicious_signatures', [])
        if meta_sigs:
            items.append(EvidenceItem(
                category='metadata',
                detector='Steganography Application Markers',
                severity='anomaly',
                indicator=1.0,
                observed_value=f"Signatures: {', '.join(meta_sigs)}",
                threshold="No known stego software markers",
                explanation=f"Detected known steganography tool application metadata signatures ({', '.join(meta_sigs)}).",
                supporting_details={'signatures': meta_sigs}
            ))
        else:
            items.append(EvidenceItem(
                category='metadata',
                detector='Steganography Application Markers',
                severity='clean',
                indicator=0.0,
                observed_value="None detected",
                threshold="No known stego software markers",
                explanation="No recognized steganography tool markers or suspicious metadata tags found in file headers.",
                supporting_details={'signatures': []}
            ))

        # 4. Statistical: Chi-Square PoVs
        chi2 = statistical_res.get('chi_square', {})
        max_chi2 = chi2.get('max_indicator', chi2.get('max_probability', 0.0))
        if max_chi2 >= 0.85:
            items.append(EvidenceItem(
                category='statistical',
                detector='Chi-Square Attack (PoVs)',
                severity='anomaly',
                indicator=max_chi2,
                observed_value=f"{max_chi2:.1%} stego probability",
                threshold="< 60.0% probability (Natural variation)",
                explanation=f"Strong equalization of adjacent Pairs of Values ({max_chi2:.1%}), consistent with sequential spatial LSB replacement.",
                supporting_details={'max_probability': round(max_chi2, 4)}
            ))
        elif max_chi2 > 0.60:
            items.append(EvidenceItem(
                category='statistical',
                detector='Chi-Square Attack (PoVs)',
                severity='suspicious',
                indicator=max_chi2,
                observed_value=f"{max_chi2:.1%} stego probability",
                threshold="< 60.0% probability (Natural variation)",
                explanation=f"Moderate equalization between adjacent Pairs of Values ({max_chi2:.1%}), warranting deeper inspection.",
                supporting_details={'max_probability': round(max_chi2, 4)}
            ))
        else:
            items.append(EvidenceItem(
                category='statistical',
                detector='Chi-Square Attack (PoVs)',
                severity='clean',
                indicator=max_chi2,
                observed_value=f"{max_chi2:.1%} stego probability",
                threshold="< 60.0% probability (Natural variation)",
                explanation="Natural frequency distribution preserved between adjacent pixel pairs without artificial equalization.",
                supporting_details={'max_probability': round(max_chi2, 4)}
            ))

        # 5. Statistical: Shannon Entropy of LSB Plane
        entropy_data = statistical_res.get('entropy', {})
        max_lsb_ent = entropy_data.get('lsb_entropy', {}).get('max', 0.0)
        if max_lsb_ent >= 0.998:
            items.append(EvidenceItem(
                category='statistical',
                detector='Shannon Entropy (LSB Plane)',
                severity='anomaly',
                indicator=1.0,
                observed_value=f"{max_lsb_ent:.4f} bits/pixel",
                threshold="< 0.9900 bits/pixel (Natural sensor noise)",
                explanation=f"Extreme LSB entropy ({max_lsb_ent:.4f} bits/px) approaching theoretical limit (1.0000), consistent with compressed/encrypted payload.",
                supporting_details={'max_lsb_entropy': max_lsb_ent}
            ))
        elif max_lsb_ent >= 0.990:
            items.append(EvidenceItem(
                category='statistical',
                detector='Shannon Entropy (LSB Plane)',
                severity='suspicious',
                indicator=0.6,
                observed_value=f"{max_lsb_ent:.4f} bits/pixel",
                threshold="< 0.9900 bits/pixel (Natural sensor noise)",
                explanation=f"Elevated LSB entropy ({max_lsb_ent:.4f} bits/px) exhibiting reduced natural structure.",
                supporting_details={'max_lsb_entropy': max_lsb_ent}
            ))
        else:
            items.append(EvidenceItem(
                category='statistical',
                detector='Shannon Entropy (LSB Plane)',
                severity='clean',
                indicator=0.0,
                observed_value=f"{max_lsb_ent:.4f} bits/pixel",
                threshold="< 0.9900 bits/pixel (Natural sensor noise)",
                explanation=f"Normal LSB plane entropy ({max_lsb_ent:.4f} bits/px) conforming to expected photographic sensor distributions.",
                supporting_details={'max_lsb_entropy': max_lsb_ent}
            ))

        # 6. Statistical: Sample Pair Analysis (SPA)
        spa = statistical_res.get('spa_analysis', statistical_res.get('sample_pair_analysis', {}))
        spa_rate = spa.get('estimated_embedding_rate', spa.get('suspicion_indicator', 0.0))
        spa_pct = spa.get('estimated_percentage', round(spa_rate * 100.0, 1))
        if spa_rate > 0.60:
            items.append(EvidenceItem(
                category='statistical',
                detector='Sample Pair Analysis (SPA)',
                severity='anomaly',
                indicator=min(1.0, spa_rate),
                observed_value=f"{spa_pct}% estimated capacity",
                threshold="< 30.0% estimated capacity",
                explanation=f"Dumitrescu-Wu-Wang SPA model estimates a high-capacity spatial LSB payload ({spa_pct}%).",
                supporting_details={'embedding_rate': round(spa_rate, 4)}
            ))
        elif spa_rate > 0.30:
            items.append(EvidenceItem(
                category='statistical',
                detector='Sample Pair Analysis (SPA)',
                severity='suspicious',
                indicator=min(1.0, spa_rate),
                observed_value=f"{spa_pct}% estimated capacity",
                threshold="< 30.0% estimated capacity",
                explanation=f"Sample Pair Analysis indicates moderate spatial LSB modification ({spa_pct}%).",
                supporting_details={'embedding_rate': round(spa_rate, 4)}
            ))
        else:
            items.append(EvidenceItem(
                category='statistical',
                detector='Sample Pair Analysis (SPA)',
                severity='clean',
                indicator=min(1.0, spa_rate),
                observed_value=f"{spa_pct}% estimated capacity",
                threshold="< 30.0% estimated capacity",
                explanation="SPA indicates negligible spatial LSB modification conforming to clean carrier baselines.",
                supporting_details={'embedding_rate': round(spa_rate, 4)}
            ))

        # 7. Statistical: Regular-Singular (RS) Steganalysis
        rs = statistical_res.get('rs_analysis', {})
        rs_rate = rs.get('estimated_embedding_rate', 0.0)
        rs_ind = rs.get('suspicion_indicator', 0.0)
        rs_pct = rs.get('estimated_percentage', round(rs_rate * 100.0, 1))
        if rs_rate > 0.50 or rs_ind > 0.70:
            items.append(EvidenceItem(
                category='statistical',
                detector='RS Steganalysis (Regular-Singular)',
                severity='anomaly',
                indicator=max(rs_rate, rs_ind),
                observed_value=f"{rs_pct}% estimated capacity",
                threshold="< 25.0% estimated capacity",
                explanation=f"Fridrich RS steganalysis curves demonstrate severe group count convergence ({rs_pct}% estimated rate), typical of LSB embedding.",
                supporting_details={'embedding_rate': round(rs_rate, 4), 'indicator': round(rs_ind, 4)}
            ))
        elif rs_rate > 0.25 or rs_ind > 0.40:
            items.append(EvidenceItem(
                category='statistical',
                detector='RS Steganalysis (Regular-Singular)',
                severity='suspicious',
                indicator=max(rs_rate, rs_ind),
                observed_value=f"{rs_pct}% estimated capacity",
                threshold="< 25.0% estimated capacity",
                explanation=f"RS steganalysis exhibits moderate curve asymmetry ({rs_pct}% estimated rate).",
                supporting_details={'embedding_rate': round(rs_rate, 4), 'indicator': round(rs_ind, 4)}
            ))
        else:
            items.append(EvidenceItem(
                category='statistical',
                detector='RS Steganalysis (Regular-Singular)',
                severity='clean',
                indicator=max(rs_rate, rs_ind),
                observed_value=f"{rs_pct}% estimated capacity",
                threshold="< 25.0% estimated capacity",
                explanation="RS steganalysis regular/singular group counts preserve clean photographic symmetry.",
                supporting_details={'embedding_rate': round(rs_rate, 4), 'indicator': round(rs_ind, 4)}
            ))

        # 8. Visual / Parity Balance
        min_delta = visual_res.get('min_balance_delta', 1.0)
        if min_delta < 0.005:
            items.append(EvidenceItem(
                category='visual',
                detector='LSB Parity Distribution',
                severity='suspicious',
                indicator=1.0,
                observed_value=f"Delta = {min_delta:.4f} (near 50.0/50.0)",
                threshold="Delta >= 0.0050 (Natural photographic bias)",
                explanation=f"Near-perfect 50/50 parity balance in LSB plane (delta = {min_delta:.4f}), typical of pseudorandom or encrypted keystreams.",
                supporting_details={'min_delta': round(min_delta, 5)}
            ))
        else:
            items.append(EvidenceItem(
                category='visual',
                detector='LSB Parity Distribution',
                severity='clean',
                indicator=0.0,
                observed_value=f"Delta = {min_delta:.4f}",
                threshold="Delta >= 0.0050 (Natural photographic bias)",
                explanation=f"Natural photographic bias preserved in LSB bit distribution (delta = {min_delta:.4f}).",
                supporting_details={'min_delta': round(min_delta, 5)}
            ))

        # 9. JPEG Structural Analysis (when applicable)
        jpeg_data = statistical_res.get('jpeg_analysis', {})
        if jpeg_data.get('available'):
            j_ind = jpeg_data.get('jpeg_structural_indicator', 0.0)
            if j_ind > 0.50:
                items.append(EvidenceItem(
                    category='statistical',
                    detector='JPEG Structural Analysis',
                    severity='anomaly',
                    indicator=j_ind,
                    observed_value=f"Indicator = {j_ind:.2f}",
                    threshold="< 0.25 (Standard baseline quantization)",
                    explanation=f"JPEG structural markers show anomalous quantization or recompression artifacts ({jpeg_data.get('details', '')}).",
                    supporting_details={'jpeg_indicator': j_ind}
                ))
            elif j_ind > 0.25:
                items.append(EvidenceItem(
                    category='statistical',
                    detector='JPEG Structural Analysis',
                    severity='suspicious',
                    indicator=j_ind,
                    observed_value=f"Indicator = {j_ind:.2f}",
                    threshold="< 0.25 (Standard baseline quantization)",
                    explanation=f"Moderate JPEG structural or quantization variation ({jpeg_data.get('details', '')}).",
                    supporting_details={'jpeg_indicator': j_ind}
                ))
            else:
                items.append(EvidenceItem(
                    category='statistical',
                    detector='JPEG Structural Analysis',
                    severity='clean',
                    indicator=j_ind,
                    observed_value=f"Quality ~{jpeg_data.get('estimated_quality', 'N/A')}, {jpeg_data.get('subsampling', 'N/A')}",
                    threshold="< 0.25 (Standard baseline quantization)",
                    explanation="Standard baseline JPEG quantization tables and markers validated without anomalies.",
                    supporting_details={'jpeg_indicator': j_ind}
                ))

        # Sort items: Anomalies first, then Suspicious, then Clean; sub-sorted by indicator desc
        items.sort(key=lambda it: (cls.SEVERITY_ORDER.get(it.severity, 0), it.indicator), reverse=True)
        return [it.to_dict() for it in items]

    @classmethod
    def collect_tampering_evidence(
        cls,
        tampering_res: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extracts and ranks evidence items relevant to image tampering and manipulation forensics.
        """
        if not tampering_res or not tampering_res.get('available', False):
            return []

        items: List[EvidenceItem] = []
        detectors = tampering_res.get('detectors', {})

        # 1. Error Level Analysis (ELA)
        ela_d = detectors.get('ela', {})
        if ela_d.get('available', False):
            ind = ela_d.get('anomaly_indicator', 0.0)
            sev = 'anomaly' if ela_d.get('is_suspicious') else ('suspicious' if ind > 0.35 else 'clean')
            items.append(EvidenceItem(
                category='tampering',
                detector='Error Level Analysis (ELA)',
                severity=sev,
                indicator=ind,
                observed_value=f"Mean error {ela_d.get('mean_error', 0.0):.2f}, high-err {ela_d.get('high_error_fraction', 0.0):.1%}",
                threshold="High-error fraction < 12.0%, indicator < 0.45",
                explanation=ela_d.get('details', 'Error Level Analysis evaluates compression history disparities across JPEG blocks.'),
                supporting_details={'mean_error': ela_d.get('mean_error', 0.0), 'high_error_fraction': ela_d.get('high_error_fraction', 0.0)}
            ))
        else:
            items.append(EvidenceItem(
                category='tampering',
                detector='Error Level Analysis (ELA)',
                severity='info',
                indicator=0.0,
                observed_value="Not applicable (Non-JPEG)",
                threshold="JPEG compression required",
                explanation="Error Level Analysis is specifically formulated for lossy JPEG quantization and is not applicable to lossless formats.",
                supporting_details={'reason': 'not_jpeg'}
            ))

        # 2. Local Residual Noise Consistency (MAD)
        noise_d = detectors.get('noise', {})
        if noise_d.get('available', False):
            ind = noise_d.get('anomaly_indicator', 0.0)
            sev = 'anomaly' if noise_d.get('is_suspicious') else ('suspicious' if ind > 0.35 else 'clean')
            items.append(EvidenceItem(
                category='tampering',
                detector='Local Residual Noise Consistency',
                severity=sev,
                indicator=ind,
                observed_value=f"Residual MAD {noise_d.get('global_noise_std', 0.0):.2f}, outliers {noise_d.get('outlier_region_fraction', 0.0):.1%}",
                threshold="Outlier fraction < 8.0%, indicator < 0.40",
                explanation=noise_d.get('details', 'Local residual noise MAD evaluates sensor noise uniformity across spatial blocks.'),
                supporting_details={'outliers_fraction': noise_d.get('outlier_region_fraction', 0.0)}
            ))

        # 3. Local Texture Variance Disparity
        var_d = detectors.get('local_variance', {})
        if var_d.get('available', False):
            ind = var_d.get('anomaly_indicator', 0.0)
            sev = 'anomaly' if var_d.get('is_suspicious') else ('suspicious' if ind > 0.35 else 'clean')
            items.append(EvidenceItem(
                category='tampering',
                detector='Texture Variance Disparity',
                severity=sev,
                indicator=ind,
                observed_value=f"Global variance {var_d.get('global_variance', 0.0):.1f}, outliers {var_d.get('outlier_region_fraction', 0.0):.1%}",
                threshold="Outlier fraction < 18.0%, indicator < 0.45",
                explanation=var_d.get('details', 'Texture variance analysis inspects localized high-frequency energy consistency.'),
                supporting_details={'global_variance': var_d.get('global_variance', 0.0)}
            ))

        # 4. Edge Discontinuity & Gradients
        edge_d = detectors.get('edge', {})
        if edge_d.get('available', False):
            ind = edge_d.get('anomaly_indicator', 0.0)
            sev = 'anomaly' if edge_d.get('is_suspicious') else ('suspicious' if ind > 0.35 else 'clean')
            items.append(EvidenceItem(
                category='tampering',
                detector='Edge Discontinuity & Gradients',
                severity=sev,
                indicator=ind,
                observed_value=f"Mean gradient {edge_d.get('mean_gradient', 0.0):.1f}, edge density {edge_d.get('edge_density', 0.0):.1%}",
                threshold="Edge density outliers < 15.0%, indicator < 0.45",
                explanation=edge_d.get('details', 'Directional Sobel edge analysis evaluates abrupt gradient step boundaries.'),
                supporting_details={'mean_gradient': edge_d.get('mean_gradient', 0.0)}
            ))

        # 5. Copy-Move Duplicate Matching
        cm_d = detectors.get('copy_move', {})
        if cm_d.get('available', False):
            ind = cm_d.get('anomaly_indicator', 0.0)
            sev = 'anomaly' if cm_d.get('is_suspicious') else ('suspicious' if cm_d.get('cluster_count', 0) > 0 else 'clean')
            items.append(EvidenceItem(
                category='tampering',
                detector='Copy-Move Duplicate Detection',
                severity=sev,
                indicator=ind,
                observed_value=f"{cm_d.get('candidate_matches', 0)} candidate pairs, {cm_d.get('cluster_count', 0)} coherent cluster(s)",
                threshold="0 coherent displacement clusters (>= 3 matching blocks)",
                explanation=cm_d.get('details', 'Copy-move analysis uses KD-tree nearest-neighbor matching and displacement vector clustering to detect cloned regions.'),
                supporting_details={'cluster_count': cm_d.get('cluster_count', 0), 'candidate_matches': cm_d.get('candidate_matches', 0)}
            ))

        # Sort items: Anomalies first, then Suspicious, then Clean, then Info
        items.sort(key=lambda it: (cls.SEVERITY_ORDER.get(it.severity, 0), it.indicator), reverse=True)
        return [it.to_dict() for it in items]

    @classmethod
    def collect_all(
        cls,
        metadata_res: Dict[str, Any],
        visual_res: Dict[str, Any],
        statistical_res: Dict[str, Any],
        forensics_res: Optional[Dict[str, Any]] = None,
        tampering_res: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Aggregates all evidence into structured steganography and tampering categories.
        """
        stego_ev = cls.collect_steganography_evidence(
            metadata_res, visual_res, statistical_res, forensics_res=forensics_res
        )
        tamper_ev = cls.collect_tampering_evidence(tampering_res)

        return {
            'steganography': stego_ev,
            'tampering': tamper_ev
        }
