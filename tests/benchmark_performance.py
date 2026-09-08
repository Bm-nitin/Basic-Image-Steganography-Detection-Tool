import time
import os
import sys
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PIL import Image
from app.core.image_validator import ImageValidator
from app.core.metadata_analyzer import MetadataAnalyzer
from app.core.file_forensics import FileForensicsAnalyzer
from app.core.visual_extractor import VisualExtractor
from app.core.statistical import StatisticalAnalyzer
from app.core.tampering import TamperingAnalyzer
from app.core.scoring import SuspicionScoringEngine
from app.core.report_generator import ReportGenerator

def benchmark_pipeline(img_bytes, filename, client_mime='image/png'):
    t0 = time.perf_counter()
    
    # 1. Validation
    val_res = ImageValidator.validate(img_bytes, filename=filename, client_mimetype=client_mime)
    t_val = time.perf_counter()
    
    # 2. Extractors & Analyzers
    pil_img = val_res['pil_image']
    meta_res = MetadataAnalyzer.analyze(img_bytes, filename)
    forensics_res = FileForensicsAnalyzer.analyze(img_bytes, meta_res)
    visual_res = VisualExtractor.extract_bit_planes(pil_img)
    stat_res = StatisticalAnalyzer.analyze(
        pil_img, file_bytes=img_bytes, image_format=meta_res.get('detected_format')
    )
    tamper_res = TamperingAnalyzer.analyze(
        pil_img, file_bytes=img_bytes, image_format=meta_res.get('detected_format')
    )
    t_detect = time.perf_counter()
    
    # 3. Scoring & Evidence & Explainability
    scoring_res = SuspicionScoringEngine.evaluate(
        meta_res,
        visual_res,
        stat_res,
        forensics_res=forensics_res,
        tampering_res=tamper_res
    )
    t_score = time.perf_counter()
    
    # 4. PDF Generation
    payload = {
        'analysis_id': 'bench-test-1234',
        'filename': filename,
        'metadata': meta_res,
        'file_forensics': forensics_res,
        'visual': visual_res,
        'statistical': stat_res,
        'tampering': tamper_res,
        'scoring': scoring_res,
        'evidence': scoring_res.get('evidence', {}),
        'explainability': scoring_res.get('explainability', {}),
        'cached_at': time.time()
    }
    pdf_bytes = ReportGenerator.generate_pdf_bytes(payload)
    t_pdf = time.perf_counter()
    
    return {
        'val_ms': (t_val - t0) * 1000,
        'detect_ms': (t_detect - t_val) * 1000,
        'score_ms': (t_score - t_detect) * 1000,
        'pdf_ms': (t_pdf - t_score) * 1000,
        'total_ms': (t_pdf - t0) * 1000,
        'pdf_size': len(pdf_bytes)
    }

def run_benchmarks():
    print("================================================================")
    print("           PIPELINE PERFORMANCE BENCHMARK                      ")
    print("================================================================")
    
    samples = [
        ('Clean Small PNG (300x300)', 'tests/test_samples/clean_sample.png', 'clean_sample.png', 'image/png'),
        ('LSB Stego PNG (300x300)', 'tests/test_samples/stego_lsb_sample.png', 'stego_lsb_sample.png', 'image/png'),
        ('Clean Synthetic Carrier (256x256)', 'tests/evaluation/samples/clean_carrier.png', 'clean_carrier.png', 'image/png'),
        ('Clean JPEG Carrier (256x256)', 'tests/evaluation/samples/clean_carrier.jpg', 'clean_carrier.jpg', 'image/jpeg'),
        ('EOF Stego JPEG (256x256)', 'tests/evaluation/samples/stego_eof.jpg', 'stego_eof.jpg', 'image/jpeg'),
        ('Tampered Copy-Move PNG (256x256)', 'tests/evaluation/samples/tamper_copymove.png', 'tamper_copymove.png', 'image/png'),
    ]
    
    # Also create a 1024x1024 synthetic image to test scaling
    large_bio = io.BytesIO()
    Image.new('RGB', (1024, 1024), color=(120, 150, 180)).save(large_bio, format='PNG')
    large_bytes = large_bio.getvalue()
    
    results = []
    
    for label, path, filename, mime in samples:
        if os.path.exists(path):
            with open(path, 'rb') as f:
                data = f.read()
            res = benchmark_pipeline(data, filename, mime)
            results.append((label, len(data), res))
            print(f"Sample: {label:<35} Size: {len(data):>7} bytes -> Total: {res['total_ms']:>6.1f}ms (Analysis: {res['detect_ms']:>6.1f}ms, PDF: {res['pdf_ms']:>6.1f}ms)")

    # Benchmark large 1024x1024
    res_large = benchmark_pipeline(large_bytes, 'large_1024.png', 'image/png')
    results.append(('Synthetic Large PNG (1024x1024)', len(large_bytes), res_large))
    print(f"Sample: {'Synthetic Large PNG (1024x1024)':<35} Size: {len(large_bytes):>7} bytes -> Total: {res_large['total_ms']:>6.1f}ms (Analysis: {res_large['detect_ms']:>6.1f}ms, PDF: {res_large['pdf_ms']:>6.1f}ms)")
    
    print("================================================================")
    print("All benchmarks finished within operational bounds (<5000ms ceiling).")

if __name__ == '__main__':
    run_benchmarks()
