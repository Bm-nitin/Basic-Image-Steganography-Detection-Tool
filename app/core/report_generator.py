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
        spa_data = stat_data.get('sample_pair_analysis', {})
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
                Paragraph("High" if spa_data.get('estimated_percentage', 0) > 40 else "Normal", cell_text)
            ],
            [
                Paragraph("Appended EOF Trailing Data", cell_text),
                Paragraph(f"{trailing_data.get('trailing_bytes_count', 0)} bytes", cell_text),
                Paragraph("0 bytes (Standard format)", cell_text),
                Paragraph("Anomaly" if trailing_data.get('has_trailing_data') else "Clean", cell_text)
            ]
        ]
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

        # 6. Embedded Histogram Plot & Visual Slices Preview
        hist_b64 = stat_data.get('histogram_plot', '')
        if hist_b64 and hist_b64.startswith('data:image/png;base64,'):
            try:
                raw_png = base64.b64decode(hist_b64.split(',', 1)[1])
                hist_buf = BytesIO(raw_png)
                story.append(KeepTogether([
                    Paragraph("4. Pixel Intensity Histogram Visualization", heading2_style),
                    RLImage(hist_buf, width=5.5 * inch, height=2.6 * inch),
                    Spacer(1, 10)
                ]))
            except Exception:
                pass

        # 7. Forensic Disclaimer & Signoff
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>FORENSIC DISCLAIMER:</b> " + score_info.get('disclaimer', ''), disclaimer_style))

        doc.build(story)
        return buffer.getvalue()
