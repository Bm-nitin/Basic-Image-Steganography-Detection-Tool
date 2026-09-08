import os
import uuid
import time
from io import BytesIO
from typing import Dict, Any
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file,
    current_app,
    abort
)
from werkzeug.utils import secure_filename
from PIL import Image

from app.core import (
    MetadataAnalyzer,
    VisualExtractor,
    StatisticalAnalyzer,
    SuspicionScoringEngine,
    ReportGenerator,
    ImageValidator,
    FileForensicsAnalyzer,
    TamperingAnalyzer
)

main_bp = Blueprint('main', __name__)

# In-memory storage for analysis results to enable PDF download and API access
# Evicts records older than 30 minutes to prevent memory leaks
ANALYSIS_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_MAX_AGE_SECONDS = 1800


def clean_expired_cache():
    """Removes cached reports older than CACHE_MAX_AGE_SECONDS."""
    now = time.time()
    expired = [k for k, v in ANALYSIS_CACHE.items() if now - v.get('cached_at', 0) > CACHE_MAX_AGE_SECONDS]
    for k in expired:
        ANALYSIS_CACHE.pop(k, None)


def is_allowed_file(filename: str) -> bool:
    """Checks file extension against configuration whitelist."""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in current_app.config['ALLOWED_EXTENSIONS']


@main_bp.route('/')
def index():
    """Renders the drag-and-drop image upload portal."""
    return render_template('index.html')


@main_bp.route('/health')
def health():
    """Render health-check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'Basic Image Steganography Detection Tool',
        'version': '1.0.0'
    })


@main_bp.route('/analyze', methods=['POST'])
def analyze():
    """
    Main image ingestion and forensic steganalysis pipeline.
    """
    clean_expired_cache()

    if 'image' not in request.files:
        flash('No image file selected. Please choose a file to analyze.', 'danger')
        return redirect(url_for('main.index'))

    file = request.files['image']

    val_res = ImageValidator.validate(
        file_source=file,
        filename=file.filename,
        client_mimetype=file.mimetype,
        config=current_app.config
    )

    if not val_res['valid']:
        err_msg = val_res['errors'][0] if val_res['errors'] else 'Image validation failed.'
        flash(err_msg, 'danger')
        return redirect(url_for('main.index'))

    try:
        file_bytes = val_res['file_bytes']
        raw_filename = val_res['safe_filename']
        pil_img = val_res['pil_image']

        # Layer 1: Structural & Metadata Analysis
        meta_res = MetadataAnalyzer.analyze(file_bytes, raw_filename)
        if val_res.get('warnings'):
            meta_res.setdefault('warnings', []).extend(val_res['warnings'])
        if val_res.get('format_consistency'):
            meta_res['format_consistency'] = val_res['format_consistency']

        # Layer 1B: File & Container Forensics (Phase B)
        forensics_res = FileForensicsAnalyzer.analyze(file_bytes, meta_res)

        # Layer 2: Visual Bit-Plane Extraction
        visual_res = VisualExtractor.extract_bit_planes(pil_img)

        # Layer 3: Statistical Steganalysis
        statistical_res = StatisticalAnalyzer.analyze(
            pil_img,
            file_bytes=file_bytes,
            image_format=meta_res.get('detected_format')
        )

        # Layer 4: Image Tampering & Manipulation Forensics (Phase D)
        tampering_res = TamperingAnalyzer.analyze(
            pil_img,
            file_bytes=file_bytes,
            image_format=meta_res.get('detected_format')
        )

        # Layer 5: Heuristic Scoring & Risk Classification
        scoring_res = SuspicionScoringEngine.evaluate(
            meta_res,
            visual_res,
            statistical_res,
            forensics_res=forensics_res,
            tampering_res=tampering_res
        )

        # Compile full analysis payload
        analysis_id = str(uuid.uuid4())
        full_results = {
            'analysis_id': analysis_id,
            'filename': raw_filename,
            'metadata': meta_res,
            'file_forensics': forensics_res,
            'visual': visual_res,
            'statistical': statistical_res,
            'tampering': tampering_res,
            'scoring': scoring_res,
            'cached_at': time.time()
        }

        # Cache results for report export
        ANALYSIS_CACHE[analysis_id] = full_results

        return render_template('results.html', results=full_results)

    except Exception as e:
        current_app.logger.error(f"Analysis error: {str(e)}", exc_info=True)
        flash(f'An unexpected error occurred during forensic inspection: {str(e)}', 'danger')
        return redirect(url_for('main.index'))


@main_bp.route('/download-report/<analysis_id>')
def download_report(analysis_id: str):
    """
    Streams a downloadable PDF forensic report.
    """
    clean_expired_cache()
    report_data = ANALYSIS_CACHE.get(analysis_id)

    if not report_data:
        flash('Report session expired or not found. Please re-analyze the image.', 'warning')
        return redirect(url_for('main.index'))

    try:
        pdf_bytes = ReportGenerator.generate_pdf_bytes(report_data)
        safe_name = secure_filename(report_data.get('filename', 'image')).rsplit('.', 1)[0]
        download_filename = f"Forensic_Report_{safe_name}_{analysis_id[:8]}.pdf"

        return send_file(
            BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=download_filename
        )
    except Exception as e:
        current_app.logger.error(f"PDF generation error: {str(e)}", exc_info=True)
        flash(f'Failed to generate PDF forensic report: {str(e)}', 'danger')
        return redirect(url_for('main.index'))


def to_serializable(obj):
    """Recursively converts numpy types and non-primitive objects to standard Python types."""
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [to_serializable(v) for v in obj]
    elif hasattr(obj, 'item'):
        return obj.item()
    return obj


@main_bp.route('/api/analyze', methods=['POST'])
def api_analyze():
    """
    REST API endpoint returning forensic results as JSON.
    """
    clean_expired_cache()

    if 'image' not in request.files:
        return jsonify({
            'error': 'Missing image file in request',
            'code': 'MISSING_FILE',
            'details': 'No image file uploaded in the "image" form field.'
        }), 400

    file = request.files['image']

    val_res = ImageValidator.validate(
        file_source=file,
        filename=file.filename,
        client_mimetype=file.mimetype,
        config=current_app.config
    )

    if not val_res['valid']:
        status_code = 413 if val_res['error_code'] == 'FILE_TOO_LARGE' else 400
        details = val_res['errors'][0] if val_res['errors'] else 'Image validation failed'
        return jsonify({
            'error': 'Image validation failed',
            'code': val_res['error_code'],
            'details': details
        }), status_code

    try:
        file_bytes = val_res['file_bytes']
        raw_filename = val_res['safe_filename']
        pil_img = val_res['pil_image']

        meta_res = MetadataAnalyzer.analyze(file_bytes, raw_filename)
        if val_res.get('warnings'):
            meta_res.setdefault('warnings', []).extend(val_res['warnings'])
        if val_res.get('format_consistency'):
            meta_res['format_consistency'] = val_res['format_consistency']

        # Layer 1B: File & Container Forensics (Phase B)
        forensics_res = FileForensicsAnalyzer.analyze(file_bytes, meta_res)

        visual_res = VisualExtractor.extract_bit_planes(pil_img)
        statistical_res = StatisticalAnalyzer.analyze(
            pil_img,
            file_bytes=file_bytes,
            image_format=meta_res.get('detected_format')
        )
        tampering_res = TamperingAnalyzer.analyze(
            pil_img,
            file_bytes=file_bytes,
            image_format=meta_res.get('detected_format')
        )
        scoring_res = SuspicionScoringEngine.evaluate(
            meta_res,
            visual_res,
            statistical_res,
            forensics_res=forensics_res,
            tampering_res=tampering_res
        )

        # Exclude raw base64 bitplane images from JSON payload to keep API response compact
        response_payload = {
            'filename': raw_filename,
            'metadata': meta_res,
            'file_forensics': forensics_res,
            'statistical': {
                'entropy': statistical_res['entropy'],
                'chi_square': statistical_res['chi_square'],
                'correlations': statistical_res['correlations'],
                'sample_pair_analysis': statistical_res['sample_pair_analysis'],
                'spa_analysis': statistical_res['spa_analysis'],
                'rs_analysis': statistical_res['rs_analysis'],
                'jpeg_analysis': statistical_res['jpeg_analysis'],
                'channel_analysis': statistical_res['channel_analysis'],
                'combined_indicator': statistical_res['combined_indicator']
            },
            'tampering': tampering_res,
            'scoring': scoring_res
        }

        return jsonify(to_serializable(response_payload)), 200

    except Exception as e:
        current_app.logger.error(f"API analysis error: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Forensic analysis failed',
            'code': 'ANALYSIS_ERROR',
            'details': str(e)
        }), 500
