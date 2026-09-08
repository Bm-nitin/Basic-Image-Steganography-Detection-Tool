import os
import sys
import json
import urllib.request
import urllib.error
import http.cookiejar
import re
from io import BytesIO
from PIL import Image

BASE_URL = 'http://127.0.0.1:5000'

# Install cookie processor so session cookies (flashed messages) persist across 302 redirects
cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
urllib.request.install_opener(opener)

def test_multipart_upload(filepath, filename=None, content_type='image/png'):
    boundary = '----WebKitFormBoundaryCheckTotal123'
    if filename is None:
        filename = os.path.basename(filepath)

    if isinstance(filepath, bytes):
        img_data = filepath
    else:
        with open(filepath, 'rb') as f:
            img_data = f.read()

    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f'Content-Type: {content_type}\r\n\r\n'
    ).encode('utf-8') + img_data + f'\r\n--{boundary}--\r\n'.encode('utf-8')

    req = urllib.request.Request(
        f'{BASE_URL}/analyze',
        data=body,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
        method='POST'
    )
    return urllib.request.urlopen(req)


def run_all_checks():
    print("================================================================")
    print("           COMPREHENSIVE INDEPENDENT VERIFICATION               ")
    print("================================================================")

    # 1. Verify GET /
    print("\n[CHECK 1] GET / (Homepage)")
    with urllib.request.urlopen(f'{BASE_URL}/') as resp:
        assert resp.getcode() == 200
        html = resp.read().decode('utf-8')
        assert 'Basic Image Steganography Detection Tool' in html
        assert 'Drag &amp; Drop Carrier Image Here' in html
        print("  -> Status 200 OK, UI elements properly rendered.")

    # 2. Verify GET /health
    print("\n[CHECK 2] GET /health (Health Check)")
    with urllib.request.urlopen(f'{BASE_URL}/health') as resp:
        assert resp.getcode() == 200
        data = json.loads(resp.read().decode('utf-8'))
        assert data['status'] == 'healthy'
        print(f"  -> Status 200 OK, payload: {data}")

    # 3. Verify POST /analyze and GET /download-report/<id> on all 3 sample images
    samples = [
        ('Clean Sample', 'tests/test_samples/clean_sample.png'),
        ('LSB Stego Sample', 'tests/test_samples/stego_lsb_sample.png'),
        ('EOF Trailing Sample', 'tests/test_samples/stego_eof_sample.jpg')
    ]

    for title, path in samples:
        print(f"\n[CHECK 3] Testing sample: {title} ({os.path.basename(path)})")
        with test_multipart_upload(path) as resp:
            assert resp.getcode() == 200
            html = resp.read().decode('utf-8')
            assert 'Steganography Suspicion Index' in html
            
            # Extract suspicion score
            score_match = re.search(r'<span class="score-number[^>]*>\s*([0-9\.]+)\s*</span>', html)
            risk_match = re.search(r'<h5 class="fw-bold[^>]*>\s*([A-Z]+)\s+RISK', html)
            score = score_match.group(1) if score_match else "N/A"
            risk = risk_match.group(1) if risk_match else "N/A"
            assert 'Forensic Evidence &amp; Explainable Assessment' in html
            print(f"  -> HTML includes Phase E Forensic Evidence & Explainability section.")

            # Extract report link
            match = re.search(r'/download-report/([a-f0-9\-]+)', html)
            assert match is not None, "Report download ID missing from HTML!"
            report_id = match.group(1)

            # Test GET /download-report/<id>
            with urllib.request.urlopen(f'{BASE_URL}/download-report/{report_id}') as pdf_resp:
                assert pdf_resp.getcode() == 200
                pdf_data = pdf_resp.read()
                assert pdf_data.startswith(b'%PDF'), "Downloaded file is not valid PDF!"
                assert b'ReportLab' in pdf_data, "PDF missing ReportLab marker!"
                assert b'%%EOF' in pdf_data[-1024:], "PDF missing %%EOF trailer marker!"
                assert len(pdf_data) > 20000, f"PDF file size suspiciously small: {len(pdf_data)} bytes"
                print(f"  -> PDF Report verified: {len(pdf_data):,} bytes with valid %PDF-1.4 and %%EOF structure.")

    # 3B. Verify POST /api/analyze returns Phase E evidence and explainability
    print("\n[CHECK 3B] REST API: POST /api/analyze (Phase E Payload)")
    api_boundary = '----WebKitFormBoundaryCheckApi123'
    with open('tests/test_samples/stego_lsb_sample.png', 'rb') as f:
        api_img_bytes = f.read()
    api_body = (
        f'--{api_boundary}\r\n'
        f'Content-Disposition: form-data; name="image"; filename="stego_lsb_sample.png"\r\n'
        f'Content-Type: image/png\r\n\r\n'
    ).encode('utf-8') + api_img_bytes + f'\r\n--{api_boundary}--\r\n'.encode('utf-8')

    api_req = urllib.request.Request(
        f'{BASE_URL}/api/analyze',
        data=api_body,
        headers={'Content-Type': f'multipart/form-data; boundary={api_boundary}'},
        method='POST'
    )
    with urllib.request.urlopen(api_req) as api_resp:
        assert api_resp.getcode() == 200
        api_json = json.loads(api_resp.read().decode('utf-8'))
        assert 'evidence' in api_json, "Missing top-level 'evidence' in API response"
        assert 'explainability' in api_json, "Missing top-level 'explainability' in API response"
        assert 'steganography' in api_json['explainability'], "Missing 'steganography' in explainability"
        assert 'tampering' in api_json['explainability'], "Missing 'tampering' in explainability"
        assert len(api_json['evidence']['steganography']) > 0, "Missing steganography evidence items"
        print("  -> API response verified: Contains evidence, explainability, steganography, and tampering.")

    # 4. Verify rejection of invalid extensions
    print("\n[CHECK 4] Security: Rejecting invalid file extensions")
    dummy_exe = b"MZ\x90\x00" + b"\x00" * 100
    with test_multipart_upload(dummy_exe, filename='malware.exe') as resp:
        html = resp.read().decode('utf-8')
        assert 'Unsupported file extension' in html
        print("  -> Correctly detected and rejected invalid extension with flash warning.")

    # 5. Verify rejection of spoofed magic bytes
    print("\n[CHECK 5] Security: Rejecting spoofed magic bytes (renamed text file)")
    spoofed_png = b"THIS IS NOT A VALID PNG MAGIC BYTE HEADER"
    with test_multipart_upload(spoofed_png, filename='spoofed.png') as resp:
        html = resp.read().decode('utf-8')
        assert 'Security Alert: Magic byte verification failed' in html
        print("  -> Correctly detected and blocked: 'Magic byte verification failed'")

    # 6. Verify 10 MB upload ceiling
    print("\n[CHECK 6] Security: 10 MB upload limit enforcement")
    oversized_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * (11 * 1024 * 1024)
    try:
        test_multipart_upload(oversized_data, filename='huge.png')
        print("  -> ERROR: Expected rejection of 11MB file!")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        # 413 Payload Too Large
        print(f"  -> Correctly rejected oversized file with HTTP {e.code}")
        assert e.code == 413 or e.code == 400

    # 7. Verify Image dimension / decompression bomb protection
    print("\n[CHECK 7] Security: Image dimension / decompression bomb protection")
    # Generate an image with dimensions 5000x10 (exceeding MAX_IMAGE_DIMENSION of 4096)
    large_dim_img = Image.new('RGB', (5000, 10), color=(100, 100, 100))
    buf = BytesIO()
    large_dim_img.save(buf, format='PNG')
    large_bytes = buf.getvalue()

    with test_multipart_upload(large_bytes, filename='wide_image.png') as resp:
        html = resp.read().decode('utf-8')
        assert 'exceed maximum allowed dimension' in html
        print("  -> Correctly blocked image exceeding dimension boundary (5000x10 > 4096px).")

    # 8. Verify static directory does not expose user uploads or reports
    print("\n[CHECK 8] Security: Verify static directory isolation")
    static_dirs = os.listdir('app/static')
    assert 'uploads' not in static_dirs, "Security concern: 'uploads' folder found in app/static!"
    assert 'reports' not in static_dirs, "Security concern: 'reports' folder found in app/static!"
    print("  -> app/static/ contains only: " + ", ".join(static_dirs))
    print("  -> No user files or reports are stored in or accessible through /static/.")

    print("\n================================================================")
    print("             ALL VERIFICATION CHECKS PASSED!                    ")
    print("================================================================")

if __name__ == '__main__':
    run_all_checks()
