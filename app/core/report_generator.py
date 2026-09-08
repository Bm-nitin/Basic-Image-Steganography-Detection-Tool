import base64
from io import BytesIO
from datetime import datetime
from typing import Dict, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether
)

class ReportGenerator:
    """
    Generates professional digital forensic steganalysis PDF reports using ReportLab.
    Produces in-memory PDF streams for direct download.
    """

    @classmethod
    def generate_pdf_bytes(cls, analysis_results: Dict[str, Any]) -> bytes:
        """
        Builds a comprehensive PDF forensic report from analysis results.
        Returns: PDF as bytes.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#0f172a')
        )

        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#64748b')
        )

        heading2_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#1e293b'),
            spaceBefore=10,
            spaceAfter=6
        )

        cell_text = ParagraphStyle(
            'CellText',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#1e293b')
        )

        cell_text_bold = ParagraphStyle(
            'CellTextBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#0f172a')
        )

        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=7,
            leading=9,
            textColor=colors.HexColor('#64748b')
        )

        story = []

        # 1. Header & Title
        story.append(Paragraph("DIGITAL FORENSIC STEGANOGRAPHY INSPECTION REPORT", title_style))
        gen_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        story.append(Paragraph(f"Generated on {gen_time} | Basic Image Steganography Detection Tool", subtitle_style))
        story.append(Spacer(1, 12))

        # 2. Executive Summary & Verdict Box
        score_info = analysis_results.get('scoring', {})
        score_val = score_info.get('suspicion_score', 0.0)
        risk_level = score_info.get('risk_level', 'Unknown')
        
        if risk_level == 'High':
            verdict_bg = colors.HexColor('#fee2e2')
            verdict_text_color = colors.HexColor('#991b1b')
        elif risk_level == 'Medium':
            verdict_bg = colors.HexColor('#fef3c7')
            verdict_text_color = colors.HexColor('#92400e')
        else:
            verdict_bg = colors.HexColor('#dcfce7')
            verdict_text_color = colors.HexColor('#166534')

        verdict_data = [
            [
                Paragraph(f"<b>OVERALL SUSPICION INDEX:</b> {score_val} / 100", ParagraphStyle('Score', fontName='Helvetica-Bold', fontSize=12, leading=14, textColor=verdict_text_color)),
                Paragraph(f"<b>RISK LEVEL:</b> {risk_level.upper()}", ParagraphStyle('Risk', fontName='Helvetica-Bold', fontSize=12, leading=14, textColor=verdict_text_color))
            ],
            [
                Paragraph(f"<b>Verdict Summary:</b> {score_info.get('risk_summary', '')}", cell_text),
                ""
            ]
        ]
        verdict_table = Table(verdict_data, colWidths=[270, 270])
        verdict_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), verdict_bg),
            ('BOX', (0, 0), (-1, -1), 1, verdict_text_color),
            ('SPAN', (0, 1), (1, 1)),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(verdict_table)
        story.append(Spacer(1, 14))

        # 3. File & Cryptographic Integrity Table
        story.append(Paragraph("1. File Identification & Integrity", heading2_style))
        meta = analysis_results.get('metadata', {})
        hashes = meta.get('hashes', {})
        dims = meta.get('metadata', {}).get('dimensions', (0, 0))
        file_size_kb = round(meta.get('file_size_bytes', 0) / 1024, 2)

        file_info_data = [
            [Paragraph("<b>Filename:</b>", cell_text_bold), Paragraph(str(analysis_results.get('filename', 'Unknown')), cell_text),
             Paragraph("<b>Detected Format:</b>", cell_text_bold), Paragraph(str(meta.get('detected_format', 'Unknown')), cell_text)],
            [Paragraph("<b>Dimensions:</b>", cell_text_bold), Paragraph(f"{dims[0]} × {dims[1]} px", cell_text),
             Paragraph("<b>File Size:</b>", cell_text_bold), Paragraph(f"{file_size_kb} KB ({meta.get('file_size_bytes', 0):,} bytes)", cell_text)],
            [Paragraph("<b>MD5 Hash:</b>", cell_text_bold), Paragraph(hashes.get('md5', 'N/A'), cell_text),
             Paragraph("<b>Signature:</b>", cell_text_bold), Paragraph(meta.get('signature_verification', 'N/A'), cell_text)],
            [Paragraph("<b>SHA-256 Hash:</b>", cell_text_bold), Paragraph(hashes.get('sha256', 'N/A'), cell_text), "", ""]
        ]
        file_table = Table(file_info_data, colWidths=[90, 180, 90, 180])
        file_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('SPAN', (1, 3), (3, 3)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(file_table)
        story.append(Spacer(1, 12))

        # 4. Detailed Forensic Tests Table
        story.append(Paragraph("2. Detailed Forensic Analysis Breakdown", heading2_style))
        breakdown_rows = [
            [
                Paragraph("<b>Category</b>", cell_text_bold),
                Paragraph("<b>Detector Method</b>", cell_text_bold),
                Paragraph("<b>Status</b>", cell_text_bold),
                Paragraph("<b>Score Impact</b>", cell_text_bold),
                Paragraph("<b>Technical Findings</b>", cell_text_bold)
            ]
        ]
        
        for item in score_info.get('detector_breakdown', []):
            st = item.get('status', 'Clean')
            if st == 'Anomaly':
                status_color = colors.HexColor('#ef4444')
            elif st == 'Suspicious':
                status_color = colors.HexColor('#f59e0b')
            else:
                status_color = colors.HexColor('#10b981')

            status_p = Paragraph(f"<b><font color='{status_color.hexval()}'>{st}</font></b>", cell_text)
            pts_p = Paragraph(f"+{item.get('points_added', 0.0)} pts", cell_text)

            breakdown_rows.append([
                Paragraph(item.get('category', ''), cell_text),
                Paragraph(item.get('detector', ''), cell_text),
                status_p,
                pts_p,
                Paragraph(item.get('details', ''), cell_text)
            ])

        breakdown_table = Table(breakdown_rows, colWidths=[90, 100, 60, 60, 230])
        breakdown_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(breakdown_table)
        story.append(Spacer(1, 14))

        # 5. Key Statistical Metrics
        story.append(Paragraph("3. Summary of Forensic Metrics", heading2_style))
        stat_data = analysis_results.get('statistical', {})
        entropy_data = stat_data.get('entropy', {})
        chi2_data = stat_data.get('chi_square', {})
        spa_data = stat_data.get('spa_analysis', stat_data.get('sample_pair_analysis', {}))
        rs_data = stat_data.get('rs_analysis', {})
        jpeg_data = stat_data.get('jpeg_analysis', {})
        trailing_data = meta.get('trailing_data', {})

        metrics_data = [
            [
                Paragraph("<b>Metric Name</b>", cell_text_bold),
                Paragraph("<b>Observed Value</b>", cell_text_bold),
                Paragraph("<b>Baseline Reference</b>", cell_text_bold),
                Paragraph("<b>Indicator</b>", cell_text_bold)
            ],
            [
                Paragraph("Global Shannon Entropy", cell_text),
                Paragraph(f"{entropy_data.get('global_entropy', 0.0)} bits", cell_text),
                Paragraph("5.0 - 7.5 bits (Photographic)", cell_text),
                Paragraph("Normal" if entropy_data.get('global_entropy', 0) < 7.8 else "Elevated", cell_text)
            ],
            [
                Paragraph("Max LSB Plane Entropy", cell_text),
                Paragraph(f"{entropy_data.get('lsb_entropy', {}).get('max', 0.0)} bits/pixel", cell_text),
                Paragraph("< 0.990 (Natural Noise)", cell_text),
                Paragraph("Suspicious" if entropy_data.get('lsb_entropy', {}).get('max', 0) >= 0.995 else "Normal", cell_text)
            ],
            [
                Paragraph("Chi-Square Max Stego Prob.", cell_text),
                Paragraph(f"{chi2_data.get('max_probability', 0.0):.2%}", cell_text),
                Paragraph("< 50% (Natural pairs)", cell_text),
                Paragraph("Elevated" if chi2_data.get('max_probability', 0) > 0.70 else "Normal", cell_text)
            ],
            [
                Paragraph("Sample Pair (SPA) Embedding", cell_text),
                Paragraph(f"{spa_data.get('estimated_percentage', 0.0)}% capacity", cell_text),
                Paragraph("< 15% (Clean carrier)", cell_text),
                Paragraph("Anomaly" if spa_data.get('estimated_embedding_rate', 0) > 0.60 else ("Suspicious" if spa_data.get('estimated_embedding_rate', 0) > 0.30 else "Normal"), cell_text)
            ],
            [
                Paragraph("RS Steganalysis Embedding", cell_text),
                Paragraph(f"{rs_data.get('estimated_percentage', 0.0)}% capacity", cell_text),
                Paragraph("< 20% (Natural symmetry)", cell_text),
                Paragraph("Anomaly" if rs_data.get('estimated_embedding_rate', 0) > 0.50 else ("Suspicious" if rs_data.get('estimated_embedding_rate', 0) > 0.25 else "Normal"), cell_text)
            ],
            [
                Paragraph("Appended EOF Trailing Data", cell_text),
                Paragraph(f"{trailing_data.get('trailing_bytes_count', 0)} bytes", cell_text),
                Paragraph("0 bytes (Standard format)", cell_text),
                Paragraph("Anomaly" if trailing_data.get('has_trailing_data') else "Clean", cell_text)
            ]
        ]

        if jpeg_data.get('available'):
            metrics_data.append([
                Paragraph("JPEG Structural / Quantization", cell_text),
                Paragraph(f"Quality ~{jpeg_data.get('estimated_quality', 'N/A')}, {jpeg_data.get('subsampling', 'N/A')}", cell_text),
                Paragraph("Standard IJG Markers", cell_text),
                Paragraph("Suspicious" if jpeg_data.get('is_suspicious') else "Clean", cell_text)
            ])
        metrics_table = Table(metrics_data, colWidths=[140, 120, 140, 140])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(metrics_table)
        story.append(Spacer(1, 14))

        # 6. Image Tampering & Manipulation Forensics (Phase D)
        tampering_data = analysis_results.get('tampering', {})
        if tampering_data and tampering_data.get('available'):
            t_story = [
                Paragraph("4. Image Tampering & Manipulation Forensics", heading2_style)
            ]
            t_dets = tampering_data.get('detectors', {})
            ela_d = t_dets.get('ela', {})
            noise_d = t_dets.get('noise', {})
            var_d = t_dets.get('local_variance', {})
            edge_d = t_dets.get('edge', {})
            cm_d = t_dets.get('copy_move', {})

            t_rows = [
                [
                    Paragraph("<b>Detector / Forensic Layer</b>", cell_text_bold),
                    Paragraph("<b>Observed Metrics</b>", cell_text_bold),
                    Paragraph("<b>Indicator</b>", cell_text_bold),
                    Paragraph("<b>Status</b>", cell_text_bold)
                ]
            ]

            # ELA row
            if ela_d.get('available'):
                ela_stat = "Anomaly" if ela_d.get('is_suspicious') else ("Suspicious" if ela_d.get('anomaly_indicator', 0) > 0.35 else "Clean")
                t_rows.append([
                    Paragraph("Error Level Analysis (ELA)", cell_text),
                    Paragraph(f"Mean error {ela_d.get('mean_error', 0.0):.2f}, high-err {ela_d.get('high_error_fraction', 0.0):.1%}", cell_text),
                    Paragraph(f"{ela_d.get('anomaly_indicator', 0.0):.3f}", cell_text),
                    Paragraph(f"<b>{ela_stat}</b>", cell_text)
                ])
            else:
                t_rows.append([
                    Paragraph("Error Level Analysis (ELA)", cell_text),
                    Paragraph("Non-JPEG image format; ELA not applicable", cell_text),
                    Paragraph("N/A", cell_text),
                    Paragraph("N/A", cell_text)
                ])

            # Noise row
            if noise_d.get('available'):
                noise_stat = "Anomaly" if noise_d.get('is_suspicious') else ("Suspicious" if noise_d.get('anomaly_indicator', 0) > 0.35 else "Clean")
                t_rows.append([
                    Paragraph("Local Residual Noise Consistency", cell_text),
                    Paragraph(f"Residual MAD {noise_d.get('global_noise_std', 0.0):.2f}, outliers {noise_d.get('outlier_region_fraction', 0.0):.1%}", cell_text),
                    Paragraph(f"{noise_d.get('anomaly_indicator', 0.0):.3f}", cell_text),
                    Paragraph(f"<b>{noise_stat}</b>", cell_text)
                ])

            # Variance row
            if var_d.get('available'):
                var_stat = "Anomaly" if var_d.get('is_suspicious') else ("Suspicious" if var_d.get('anomaly_indicator', 0) > 0.35 else "Clean")
                t_rows.append([
                    Paragraph("Texture Variance Disparity", cell_text),
                    Paragraph(f"Global var {var_d.get('global_variance', 0.0):.1f}, outliers {var_d.get('outlier_region_fraction', 0.0):.1%}", cell_text),
                    Paragraph(f"{var_d.get('anomaly_indicator', 0.0):.3f}", cell_text),
                    Paragraph(f"<b>{var_stat}</b>", cell_text)
                ])

            # Edge row
            if edge_d.get('available'):
                edge_stat = "Anomaly" if edge_d.get('is_suspicious') else ("Suspicious" if edge_d.get('anomaly_indicator', 0) > 0.35 else "Clean")
                t_rows.append([
                    Paragraph("Edge Discontinuity & Gradients", cell_text),
                    Paragraph(f"Mean grad {edge_d.get('mean_gradient', 0.0):.1f}, density {edge_d.get('edge_density', 0.0):.1%}", cell_text),
                    Paragraph(f"{edge_d.get('anomaly_indicator', 0.0):.3f}", cell_text),
                    Paragraph(f"<b>{edge_stat}</b>", cell_text)
                ])

            # Copy-Move row
            if cm_d.get('available'):
                cm_stat = "Anomaly" if cm_d.get('is_suspicious') else ("Suspicious" if cm_d.get('cluster_count', 0) > 0 else "Clean")
                t_rows.append([
                    Paragraph("Copy-Move Duplicate Matching", cell_text),
                    Paragraph(f"{cm_d.get('candidate_matches', 0)} pairs, {cm_d.get('cluster_count', 0)} coherent cluster(s)", cell_text),
                    Paragraph(f"{cm_d.get('anomaly_indicator', 0.0):.3f}", cell_text),
                    Paragraph(f"<b>{cm_stat}</b>", cell_text)
                ])

            t_table = Table(t_rows, colWidths=[150, 190, 100, 100])
            t_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            t_story.append(t_table)

            # ELA heatmap thumbnail if available
            ela_hm = ela_d.get('heatmap', {})
            if ela_hm.get('heatmap_available') and ela_hm.get('heatmap_base64'):
                try:
                    b64_img = ela_hm['heatmap_base64']
                    if b64_img.startswith('data:image/png;base64,'):
                        raw_hm_png = base64.b64decode(b64_img.split(',', 1)[1])
                        hm_buf = BytesIO(raw_hm_png)
                        t_story.append(Spacer(1, 6))
                        t_story.append(Paragraph("<b>Error Level Analysis (ELA) Amplified Difference Heatmap:</b>", cell_text))
                        t_story.append(Spacer(1, 4))
                        t_story.append(RLImage(hm_buf, width=2.6 * inch, height=2.6 * inch))
                except Exception:
                    pass

            t_story.append(Spacer(1, 12))
            story.append(KeepTogether(t_story))

        # Ensure Phase E Evidence and Explainability are present
        evidence_data = analysis_results.get('evidence') or score_info.get('evidence')
        explainability_data = analysis_results.get('explainability') or score_info.get('explainability')

        if not evidence_data or not explainability_data:
            from .evidence import EvidenceCollector
            from .explainability import ExplainabilityEngine
            evidence_data = EvidenceCollector.collect_all(
                meta,
                analysis_results.get('visual', {}),
                stat_data,
                forensics_res=analysis_results.get('file_forensics'),
                tampering_res=tampering_data
            )
            explainability_data = ExplainabilityEngine.generate(
                evidence_data,
                score_info,
                tampering_res=tampering_data
            )

        stego_exp = explainability_data.get('steganography', {})
        tamper_exp = explainability_data.get('tampering', {})

        # 5. Forensic Evidence & Explainable Assessment (Phase E)
        story.append(Paragraph("5. Forensic Evidence & Explainable Assessment", heading2_style))
        
        # Summary callouts
        stego_box_data = [
            [Paragraph("<b>Steganography Suspicion Assessment</b>", cell_text_bold),
             Paragraph(f"Risk: <b>{stego_exp.get('risk', 'UNKNOWN')}</b> | Score: <b>{stego_exp.get('score', 0.0)} / 100</b>", cell_text_bold)],
            [Paragraph(f"<b>Summary:</b> {stego_exp.get('summary', 'No summary available.')}", cell_text), ""]
        ]
        stego_box_table = Table(stego_box_data, colWidths=[270, 270])
        stego_box_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94a3b8')),
            ('SPAN', (0, 1), (1, 1)),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(stego_box_table)
        story.append(Spacer(1, 6))

        if tampering_data and tampering_data.get('available'):
            tamper_box_data = [
                [Paragraph("<b>Tampering & Manipulation Assessment</b>", cell_text_bold),
                 Paragraph(f"Status: <b>{tamper_exp.get('status', 'UNKNOWN')}</b> | Score: <b>{tamper_exp.get('score', 0.0)} / 100</b>", cell_text_bold)],
                [Paragraph(f"<b>Summary:</b> {tamper_exp.get('summary', 'No summary available.')}", cell_text), ""]
            ]
            tamper_box_table = Table(tamper_box_data, colWidths=[270, 270])
            tamper_box_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94a3b8')),
                ('SPAN', (0, 1), (1, 1)),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(tamper_box_table)
            story.append(Spacer(1, 6))

        # Primary Evidence Table
        story.append(Paragraph("<b>Primary Forensic Evidence Items:</b>", cell_text_bold))
        story.append(Spacer(1, 4))

        primary_items = list(stego_exp.get('primary_evidence', [])) + list(tamper_exp.get('primary_evidence', []))
        ev_rows = [
            [
                Paragraph("<b>Category</b>", cell_text_bold),
                Paragraph("<b>Detector</b>", cell_text_bold),
                Paragraph("<b>Severity</b>", cell_text_bold),
                Paragraph("<b>Observed Value</b>", cell_text_bold),
                Paragraph("<b>Baseline</b>", cell_text_bold),
                Paragraph("<b>Forensic Explanation</b>", cell_text_bold)
            ]
        ]

        if primary_items:
            for item in primary_items:
                sev = item.get('severity', 'clean').lower()
                if sev == 'anomaly':
                    sev_color = colors.HexColor('#ef4444')
                elif sev == 'suspicious':
                    sev_color = colors.HexColor('#f59e0b')
                else:
                    sev_color = colors.HexColor('#10b981')

                ev_rows.append([
                    Paragraph(item.get('category', '').capitalize(), cell_text),
                    Paragraph(item.get('detector', ''), cell_text),
                    Paragraph(f"<b><font color='{sev_color.hexval()}'>{item.get('severity', '').upper()}</font></b>", cell_text),
                    Paragraph(str(item.get('observed_value', '')), cell_text),
                    Paragraph(str(item.get('threshold', '')), cell_text),
                    Paragraph(str(item.get('explanation', '')), cell_text)
                ])
        else:
            ev_rows.append([
                Paragraph("All Categories", cell_text),
                Paragraph("All Detectors", cell_text),
                Paragraph("<b><font color='#10b981'>CLEAN</font></b>", cell_text),
                Paragraph("Baseline values", cell_text),
                Paragraph("Standard baselines", cell_text),
                Paragraph("All evaluated forensic layers conform to clean, unmodified photographic carrier characteristics.", cell_text)
            ])

        ev_table = Table(ev_rows, colWidths=[65, 95, 55, 95, 85, 145])
        ev_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(ev_table)
        story.append(Spacer(1, 14))

        # 6. Detector Contribution Breakdown (Phase E)
        story.append(Paragraph("6. Detector Contribution Breakdown", heading2_style))
        story.append(Paragraph(
            "Mathematical point contributions to the Steganography Suspicion Index (0-100) under Phase A-C weighting: "
            "Structural (20%), Metadata (10%), Statistical (50%), Visual (20%). "
            "Tampering forensic detectors evaluate independent spatial manipulation dimensions and contribute 0.0 pts to the steganography index.",
            cell_text
        ))
        story.append(Spacer(1, 6))

        total_score_val = float(score_info.get('suspicion_score', 0.0))
        contrib_rows = [
            [
                Paragraph("<b>Category</b>", cell_text_bold),
                Paragraph("<b>Detector Method</b>", cell_text_bold),
                Paragraph("<b>Status</b>", cell_text_bold),
                Paragraph("<b>Points Added</b>", cell_text_bold),
                Paragraph("<b>Impact Share</b>", cell_text_bold),
                Paragraph("<b>Technical Details</b>", cell_text_bold)
            ]
        ]

        for item in score_info.get('detector_breakdown', []):
            st = item.get('status', 'Clean')
            if st == 'Anomaly':
                st_color = colors.HexColor('#ef4444')
            elif st == 'Suspicious':
                st_color = colors.HexColor('#f59e0b')
            else:
                st_color = colors.HexColor('#10b981')

            pts = float(item.get('points_added', 0.0))
            if total_score_val > 0 and pts > 0:
                share_str = f"{(pts / total_score_val * 100):.1f}%"
            elif item.get('category') == 'Tampering & Manipulation Forensics':
                share_str = "Independent"
            else:
                share_str = "0.0%"

            contrib_rows.append([
                Paragraph(item.get('category', ''), cell_text),
                Paragraph(item.get('detector', ''), cell_text),
                Paragraph(f"<b><font color='{st_color.hexval()}'>{st}</font></b>", cell_text),
                Paragraph(f"+{pts:.1f} pts", cell_text),
                Paragraph(share_str, cell_text),
                Paragraph(item.get('details', ''), cell_text)
            ])

        contrib_table = Table(contrib_rows, colWidths=[95, 105, 55, 60, 55, 170])
        contrib_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(contrib_table)
        story.append(Spacer(1, 14))

        # 7. Embedded Histogram Plot & Visual Slices Preview
        hist_b64 = stat_data.get('histogram_plot', '')
        if hist_b64 and hist_b64.startswith('data:image/png;base64,'):
            try:
                raw_png = base64.b64decode(hist_b64.split(',', 1)[1])
                hist_buf = BytesIO(raw_png)
                story.append(KeepTogether([
                    Paragraph("7. Pixel Intensity Histogram Visualization", heading2_style),
                    RLImage(hist_buf, width=5.5 * inch, height=2.6 * inch),
                    Spacer(1, 10)
                ]))
            except Exception:
                pass

        # 8. Forensic Disclaimer & Signoff
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>FORENSIC DISCLAIMER:</b> " + score_info.get('disclaimer', ''), disclaimer_style))

        doc.build(story)
        return buffer.getvalue()

